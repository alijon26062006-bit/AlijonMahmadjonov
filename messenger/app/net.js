'use strict';
/* =========================================================
   Aloqa network layer.
   If the page is served by the Aloqa server (server/server.js)
   the app runs in online mode: real accounts, real-time chats,
   media uploads. Otherwise it stays in the offline demo.
   ========================================================= */
window.NET = (() => {
  const N = { on: false, ws: null, me: null, token: null, ready: false, queue: [], conn: 'offline', backoff: 1000, lastRead: {}, lastTyping: {}, typingTimers: {}, refSeq: 0, pending: {}, ttl: 72, maxMb: 50 };
  const TK = 'aloqa.token';
  const getToken = () => { try { return localStorage.getItem(TK); } catch (e) { return null; } };
  const setToken = t => { try { if (t) localStorage.setItem(TK, t); else localStorage.removeItem(TK); } catch (e) { /* ignore */ } };
  const uuid4 = () => (crypto.randomUUID ? crypto.randomUUID() : '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)));
  const ini = name => String(name || '?').split(/\s+/).filter(Boolean).map(w => w[0]).join('').slice(0, 2).toUpperCase() || '?';

  async function api(path, body) {
    const r = await fetch(path, {
      method: body ? 'POST' : 'GET', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', ...(N.token ? { Authorization: 'Bearer ' + N.token } : {}) },
      body: body ? JSON.stringify(body) : undefined
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(j.error || 'Сервер недоступен'), { status: r.status });
    return j;
  }

  /* ---------- Boot ---------- */
  window.NETBOOT = async () => {
    try {
      const r = await fetch('api/health', { cache: 'no-store' });
      const j = await r.json();
      if (j.app !== 'aloqa') throw new Error('not aloqa');
      N.on = true; N.ttl = j.mediaTtlHours; N.maxMb = j.maxUploadMb;
    } catch (e) {
      if (getToken()) { renderConnecting(); setTimeout(window.NETBOOT, 4000); return; } /* server is temporarily down */
      N.on = false; renderApp(); return;
    }
    S = { v: 1, user: null, contacts: {}, chats: [], calls: [], stories: [], myStory: null, settings: (S && S.settings) || { theme: 'system', notify: true } };
    applyTheme();
    N.token = getToken();
    if (N.token) { renderConnecting(); connect(); } else renderOnboarding();
  };
  function renderConnecting() { $('#app').innerHTML = `<div class="main-empty" style="height:100dvh"><div>${LOGO}<b>Aloqa</b><p>Подключение…</p></div></div>`; }

  /* ---------- WebSocket ---------- */
  function connect() {
    const u = new URL('ws', location.href); u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    let ws; try { ws = new WebSocket(u); } catch (e) { return retry(); }
    N.ws = ws; setConn('connecting');
    ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token: N.token }));
    ws.onmessage = e => { let d; try { d = JSON.parse(e.data); } catch (err) { return; } handle(d); };
    ws.onclose = ev => {
      N.ready = false;
      if (ev.code === 4001) { setToken(null); N.token = null; S.user = null; $('#app').innerHTML = ''; OB.step = 1; renderOnboarding(); toast('Сессия закончилась — войдите снова'); return; }
      setConn('offline'); retry();
    };
  }
  function retry() { clearTimeout(N.rt); N.rt = setTimeout(connect, N.backoff); N.backoff = Math.min(N.backoff * 2, 15000); }
  function sendWS(o) { if (N.ready && N.ws.readyState === 1) N.ws.send(JSON.stringify(o)); else N.queue.push(o); }
  function setConn(state) {
    N.conn = state;
    const h = $('.lh h1'); if (h && UI.route.tab === 'chats') h.textContent = N.title();
  }
  N.title = () => (!N.on || N.conn === 'online') ? 'Чаты' : 'Соединение…';
  document.addEventListener('visibilitychange', () => { if (!document.hidden && N.on && N.token && (!N.ws || N.ws.readyState > 1)) { N.backoff = 1000; connect(); } });

  /* ---------- Server → client mapping ---------- */
  function addProfile(p) {
    const old = S.contacts[p.id] || {};
    S.contacts[p.id] = { ...old, id: p.id, name: p.name, ini: ini(p.name), g: p.color, phone: p.phone, user: p.username || '', bio: p.bio || '', online: !!p.online, seen: p.lastSeen };
  }
  function fromMsg(sm) {
    const meta = sm.meta || {}, me = sm.from === N.me;
    const m = { id: sm.id, chatId: sm.chatId, from: me ? 'me' : sm.from, ts: sm.ts, kind: sm.kind, text: sm.body || '', status: 'sent', media: sm.media || null };
    if (meta.reply) m.reply = meta.reply;
    switch (sm.kind) {
      case 'voice': m.dur = meta.dur || 1; m.wave = meta.wave; break;
      case 'image': case 'video': m.caption = sm.body; m.hue = meta.hue || 250; break;
      case 'file': m.name = meta.name || 'Файл'; m.size = meta.size || ''; break;
      case 'location': m.lat = meta.lat; m.lon = meta.lon; m.addr = meta.addr || ''; break;
      case 'contact': m.card = meta.card || {}; m.cid = S.contacts[m.card.id] ? m.card.id : null; break;
      case 'poll': {
        const votes = meta.votes || {};
        m.poll = { q: meta.q || '', opts: (meta.opts || []).map((t, i) => ({ t, v: Object.values(votes).filter(v => v === i).length })), my: N.me in votes ? votes[N.me] : -1 };
        break;
      }
      case 'event': { const going = meta.going || {}; m.event = { title: meta.title || '', at: meta.at || Date.now(), going: Object.keys(going).length, me: !!going[N.me] }; break; }
    }
    return m;
  }
  function toMeta(m) {
    const meta = {};
    if (m.reply) meta.reply = m.reply;
    switch (m.kind) {
      case 'voice': meta.dur = m.dur; meta.wave = m.wave; break;
      case 'image': case 'video': meta.hue = m.hue; break;
      case 'file': meta.name = m.name; meta.size = m.size; break;
      case 'location': meta.lat = m.lat; meta.lon = m.lon; meta.addr = m.addr; break;
      case 'contact': { const p = person(m.cid); meta.card = { id: m.cid, name: p.name, phone: p.phone, color: p.g }; m.card = meta.card; break; }
      case 'poll': meta.q = m.poll.q; meta.opts = m.poll.opts.map(o => o.t); meta.votes = {}; break;
      case 'event': meta.title = m.event.title; meta.at = m.event.at; meta.going = { [N.me]: true }; break;
    }
    return meta;
  }
  function fromChat(sc) {
    const mine = sc.members.find(x => x.id === N.me) || {};
    const others = sc.members.filter(x => x.id !== N.me);
    const c = {
      id: sc.id, type: sc.type, title: sc.title, ini: ini(sc.title), g: 'g5', members: others.map(x => x.id),
      cid: sc.type === 'direct' && others[0] ? others[0].id : undefined, muted: !!mine.muted,
      reads: Object.fromEntries(others.map(x => [x.id, x.lastRead])), messages: sc.messages.map(fromMsg)
    };
    c.unread = c.messages.filter(m => m.from !== 'me' && m.ts > (mine.lastRead || 0)).length;
    applyReads(c); return c;
  }
  function applyReads(c) {
    const maxRead = Math.max(0, ...Object.values(c.reads || {}));
    c.messages.forEach(m => { if (m.from === 'me' && m.status !== 'sending') m.status = m.ts <= maxRead ? 'read' : 'sent'; });
  }
  function rerenderAll() { if (!S.user) return; UI.route = {}; renderApp(); }

  /* ---------- Incoming events ---------- */
  function handle(d) {
    switch (d.type) {
      case 'init': {
        N.me = d.me.id; N.ttl = d.mediaTtlHours || N.ttl; N.ready = true; N.backoff = 1000;
        const keepSettings = S.settings;
        S.contacts = {}; d.profiles.forEach(addProfile);
        S.user = { id: d.me.id, name: d.me.name, phone: d.me.phone, user: d.me.username || '', bio: d.me.bio || '' };
        S.chats = d.chats.map(fromChat); S.settings = keepSettings;
        setConn('online');
        const q = N.queue; N.queue = []; q.forEach(sendWS);
        rerenderAll();
        return;
      }
      case 'message': {
        const m = fromMsg(d.message), c = chatById(m.chatId); if (!c) return;
        const have = c.messages.find(x => x.id === m.id);
        if (have) { Object.assign(have, { ts: m.ts, media: m.media || have.media, status: have.status === 'sending' ? 'sent' : have.status }); applyReads(c); refreshChat(c.id); renderChatList(); return; }
        if (m.from === 'me') { c.messages.push(m); refreshChat(c.id); renderChatList(); return; }
        delete UI.typing[c.id];
        pushIncoming(c, m); return;
      }
      case 'ack': {
        for (const c of S.chats) {
          const m = c.messages.find(x => x.id === d.id);
          if (m) { m.status = 'sent'; if (d.ts) m.ts = d.ts; if (d.media) m.media = d.media; applyReads(c); refreshChat(c.id); renderChatList(); break; }
        }
        return;
      }
      case 'typing': {
        UI.typing[d.chatId] = d.userId; refreshChat(d.chatId); renderChatList();
        clearTimeout(N.typingTimers[d.chatId]);
        N.typingTimers[d.chatId] = setTimeout(() => { delete UI.typing[d.chatId]; refreshChat(d.chatId); renderChatList(); }, 4500);
        return;
      }
      case 'read': { const c = chatById(d.chatId); if (!c) return; c.reads[d.userId] = d.at; applyReads(c); refreshChat(c.id); renderChatList(); return; }
      case 'chat': {
        (d.profiles || []).forEach(addProfile);
        let c = chatById(d.chat.id);
        if (!c) { c = fromChat(d.chat); S.chats.push(c); }
        renderChatList(); renderTabbar();
        if (d.ref && N.pending[d.ref]) { delete N.pending[d.ref]; location.hash = '#/chat/' + c.id; }
        return;
      }
      case 'deleted': { const c = chatById(d.chatId); if (!c) return; c.messages = c.messages.filter(m => m.id !== d.id); refreshChat(c.id); renderChatList(); return; }
      case 'update': {
        const m = fromMsg(d.message), c = chatById(m.chatId); if (!c) return;
        const i = c.messages.findIndex(x => x.id === m.id); if (i < 0) return;
        m.status = c.messages[i].status; c.messages[i] = m; UI.rendered.add(m.id); refreshChat(c.id); return;
      }
      case 'presence': {
        const p = S.contacts[d.userId]; if (!p) return;
        p.online = d.online; p.seen = d.lastSeen; renderChatList();
        const c = UI.route.chat && chatById(UI.route.chat);
        if (c && c.cid === d.userId) { const st = $('#convStatus'); if (st) st.innerHTML = headerStatus(c); }
        return;
      }
      case 'profile': {
        if (d.profile.id === N.me) { S.user.name = d.profile.name; S.user.bio = d.profile.bio; }
        else addProfile(d.profile);
        renderChatList(); return;
      }
      case 'error': {
        if (d.ref && N.pending[d.ref]) delete N.pending[d.ref];
        toast(esc(d.message || 'Ошибка')); return;
      }
    }
  }
  function pushIncoming(c, m) {
    c.messages.push(m);
    const viewing = UI.route.chat === c.id && !UI.route.info && !document.hidden;
    if (viewing) N.read(c.id);
    else {
      c.unread = (c.unread || 0) + 1;
      if (S.settings.notify && !c.muted) toast(`${chatAv(c, 32, false)}<span><b>${esc(chatTitle(c))}</b><br><span style="font-weight:500;opacity:.85">${esc(bodyText(m)).slice(0, 60)}</span></span>`, 'Открыть', () => { location.hash = '#/chat/' + c.id; }, 4000);
      if (document.hidden && S.settings.notify && !c.muted && 'Notification' in window && Notification.permission === 'granted') {
        try { new Notification(chatTitle(c), { body: bodyText(m).slice(0, 120), icon: 'icons/icon-192.png', tag: c.id }); } catch (e) { /* ignore */ }
      }
    }
    refreshChat(c.id); renderChatList(); renderTabbar();
  }

  /* ---------- Outgoing ---------- */
  N.send = (c, m, mediaId) => {
    m.id = m.id || uuid4(); m.ts = Date.now(); m.from = 'me'; m.status = 'sending';
    if (!c.messages.includes(m)) c.messages.push(m);
    refreshChat(c.id); renderChatList(); renderTabbar();
    if (m.uploading) return;
    sendWS({ type: 'send', id: m.id, chatId: c.id, kind: m.kind, body: m.kind === 'text' ? m.text : (m.caption || ''), meta: toMeta(m), mediaId: mediaId || null });
  };
  N.read = chatId => {
    const c = chatById(chatId); if (c) c.unread = 0;
    const t = Date.now(); if (t - (N.lastRead[chatId] || 0) < 800) return;
    N.lastRead[chatId] = t; sendWS({ type: 'read', chatId });
  };
  N.typing = chatId => { const t = Date.now(); if (t - (N.lastTyping[chatId] || 0) < 2500) return; N.lastTyping[chatId] = t; sendWS({ type: 'typing', chatId }); };
  N.mute = c => sendWS({ type: 'mute', chatId: c.id, muted: !!c.muted });
  N.del = (c, m) => { c.messages = c.messages.filter(x => x !== m); refreshChat(c.id); renderChatList(); sendWS({ type: 'delete', id: m.id }); toast('Сообщение удалено'); };
  N.vote = (c, m, i) => { if (m.poll.my >= 0) return; m.poll.my = i; m.poll.opts[i].v++; refreshChat(c.id); sendWS({ type: 'vote', id: m.id, opt: i }); };
  N.rsvp = (c, m) => { m.event.me = !m.event.me; m.event.going += m.event.me ? 1 : -1; refreshChat(c.id); sendWS({ type: 'rsvp', id: m.id }); };
  N.profile = (name, bio) => sendWS({ type: 'profile', name, bio });
  N.startChat = phone => { const ref = 'r' + (++N.refSeq); N.pending[ref] = true; sendWS({ type: 'start_chat', phone, ref }); };
  N.openDirect = cid => { const c = S.chats.find(x => x.type === 'direct' && x.cid === cid); if (c) location.hash = '#/chat/' + c.id; else if (person(cid)) N.startChat(person(cid).phone); };
  N.logout = async () => { try { await api('api/logout', {}); } catch (e) { /* ignore */ } setToken(null); location.hash = ''; location.reload(); };

  /* ---------- Media upload ---------- */
  function upload(blob, name, onProgress) {
    return new Promise((resolve, reject) => {
      const x = new XMLHttpRequest();
      x.open('POST', 'api/upload'); x.setRequestHeader('Authorization', 'Bearer ' + N.token);
      x.setRequestHeader('Content-Type', blob.type || 'application/octet-stream');
      x.upload.onprogress = e => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
      x.onload = () => { let j = {}; try { j = JSON.parse(x.responseText); } catch (e) { /* ignore */ } x.status === 200 ? resolve(j) : reject(new Error(j.error || 'Не удалось загрузить файл')); };
      x.onerror = () => reject(new Error('Нет соединения с сервером'));
      x.send(blob);
    });
  }
  const fmtSize = b => b < 1024 * 1024 ? Math.max(1, Math.round(b / 1024)) + ' КБ' : (b / 1048576).toFixed(1).replace('.', ',') + ' МБ';
  async function sendBlob(c, blob, m) {
    if (blob.size > N.maxMb * 1048576) { toast(`Файл больше ${N.maxMb} МБ`); return; }
    m.media = { url: URL.createObjectURL(blob), mime: blob.type, local: true };
    m.uploading = true; N.send(c, m);
    try {
      const res = await upload(blob, m.name, p => { m.progress = p; const el = $(`.b[data-mid="${m.id}"] .upl`); if (el) el.textContent = Math.round(p * 100) + '%'; });
      m.uploading = false; delete m.progress;
      sendWS({ type: 'send', id: m.id, chatId: c.id, kind: m.kind, body: m.caption || '', meta: toMeta(m), mediaId: res.id });
    } catch (e) {
      c.messages = c.messages.filter(x => x !== m); refreshChat(c.id); renderChatList(); toast(esc(e.message));
    }
  }
  N.pickFile = (c, mode) => {
    const inp = document.createElement('input'); inp.type = 'file';
    inp.accept = mode === 'doc' ? '' : 'image/*,video/*';
    if (mode === 'camera') inp.capture = 'environment';
    inp.onchange = () => {
      const f = inp.files && inp.files[0]; if (!f) return;
      const kind = mode === 'doc' ? 'file' : f.type.startsWith('video/') ? 'video' : f.type.startsWith('image/') ? 'image' : 'file';
      sendBlob(c, f, { kind, name: f.name, size: fmtSize(f.size), hue: 250, caption: '' });
    };
    inp.click();
  };

  /* ---------- Real voice recording ---------- */
  N.recStart = async R => {
    try {
      R.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) { stopRec(false); toast('Нет доступа к микрофону — разрешите его в настройках браузера'); return; }
    if (!UI.rec) { R.stream.getTracks().forEach(t => t.stop()); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    R.ac = new AC(); const src = R.ac.createMediaStreamSource(R.stream); const an = R.ac.createAnalyser(); an.fftSize = 512; src.connect(an);
    const buf = new Uint8Array(an.fftSize);
    R.level = () => { an.getByteTimeDomainData(buf); let s = 0; for (const v of buf) { const x = (v - 128) / 128; s += x * x; } return Math.min(1, Math.sqrt(s / buf.length) * 4); };
    const mime = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', ''].find(t => !t || (window.MediaRecorder && MediaRecorder.isTypeSupported(t)));
    R.chunks = []; R.mr = new MediaRecorder(R.stream, mime ? { mimeType: mime } : undefined);
    R.mr.ondataavailable = e => { if (e.data && e.data.size) R.chunks.push(e.data); };
    R.mr.start(250);
  };
  N.recStop = (R, send, secs, wave) => {
    const finish = () => {
      if (R.stream) R.stream.getTracks().forEach(t => t.stop());
      if (R.ac) R.ac.close().catch(() => {});
      if (!send) return;
      const blob = new Blob(R.chunks || [], { type: (R.mr && R.mr.mimeType) || 'audio/webm' });
      if (!blob.size) { toast('Запись пустая — попробуйте ещё раз'); return; }
      sendBlob(chatById(UI.route.chat), blob, { kind: 'voice', dur: secs, wave });
    };
    if (R.mr && R.mr.state !== 'inactive') { R.mr.onstop = finish; R.mr.stop(); } else finish();
  };

  /* ---------- Online onboarding: phone → password (+ name for new users) ---------- */
  N.phoneSubmit = async btn => {
    const phone = OB.cc + OB.phone;
    btn.disabled = true; btn.innerHTML = '<span class="spinner" aria-hidden="true"></span><span class="sr-only">Проверяем номер</span>';
    try { const j = await api('api/phone?p=' + encodeURIComponent(phone)); OB.registered = j.registered; OB.step = 2; renderOnboarding(); }
    catch (e) { btn.disabled = false; btn.textContent = 'Продолжить'; $('#phoneErr').innerHTML = `<p class="err">${ic('alert', 16)}${esc(e.message)}</p>`; }
  };
  N.renderPassStep = () => {
    const reg = OB.registered, phone = OB.cc + ' ' + fmtPhone(OB.phone, OB.cc);
    $('#app').innerHTML = `<div class="ob"><div class="ob-in" id="main">
      <div class="top-nav"><button class="ib accent" type="button" id="obBack" aria-label="Назад">${ic('back', 26)}</button><div class="steps" aria-label="Шаг 2 из 2"><i></i><i class="on"></i></div></div>
      <form class="step-body" id="passForm" novalidate>
        <div class="step-ill">${ic(reg ? 'lock' : 'smile', 32)}</div>
        <h1>${reg ? 'Введите пароль' : 'Создайте аккаунт'}</h1>
        <p class="lead">${reg ? `Номер <b style="color:var(--text)">${esc(phone)}</b> уже зарегистрирован в Aloqa.` : `Номер <b style="color:var(--text)">${esc(phone)}</b>. Тестовый режим: номер пока не подтверждается по SMS.`}</p>
        ${reg ? '' : `<label class="lbl" for="fname">Имя</label><input class="inp" id="fname" autocomplete="given-name" required>
        <label class="lbl" for="lname">Фамилия <span style="font-weight:500">(необязательно)</span></label><input class="inp" id="lname" autocomplete="family-name">`}
        <label class="lbl" for="pass">${reg ? 'Пароль' : 'Придумайте пароль'}</label>
        <div style="position:relative"><input class="inp" id="pass" type="password" minlength="6" autocomplete="${reg ? 'current-password' : 'new-password'}" aria-describedby="passErr passHint" style="padding-right:56px">
          <button type="button" class="ib" id="passEye" aria-label="Показать пароль" aria-pressed="false" style="position:absolute;right:6px;top:6px">${ic('lock', 20)}</button></div>
        ${reg ? '' : '<p class="hint" id="passHint">Не короче 6 символов</p>'}
        <div id="passErr" aria-live="polite"></div>
        <button class="btn primary block" type="submit" id="passBtn" style="margin-top:20px">${reg ? 'Войти' : 'Создать аккаунт'}</button>
      </form></div></div>`;
    $('#obBack').onclick = () => { OB.step = 1; renderOnboarding(); };
    const pass = $('#pass'); (reg ? pass : $('#fname')).focus();
    $('#passEye').onclick = e => { const b = e.currentTarget, show = pass.type === 'password'; pass.type = show ? 'text' : 'password'; b.setAttribute('aria-pressed', show); b.setAttribute('aria-label', show ? 'Скрыть пароль' : 'Показать пароль'); };
    const err = (msg, field) => { $('#passErr').innerHTML = `<p class="err">${ic('alert', 16)}${esc(msg)}</p>`; if (field) { field.setAttribute('aria-invalid', 'true'); field.focus(); } };
    $('#passForm').addEventListener('submit', async e => {
      e.preventDefault();
      const btn = $('#passBtn'), phoneFull = OB.cc + OB.phone;
      $$('[aria-invalid]').forEach(x => x.removeAttribute('aria-invalid'));
      if (!reg && !$('#fname').value.trim()) return err('Укажите имя, чтобы контакты вас узнали', $('#fname'));
      if (pass.value.length < 6) return err('Пароль должен быть не короче 6 символов', pass);
      btn.disabled = true; const label = btn.textContent; btn.innerHTML = '<span class="spinner" aria-hidden="true"></span><span class="sr-only">Загрузка</span>';
      try {
        const j = reg ? await api('api/login', { phone: phoneFull, password: pass.value })
          : await api('api/register', { phone: phoneFull, password: pass.value, name: ($('#fname').value.trim() + ' ' + $('#lname').value.trim()).trim() });
        N.token = j.token; setToken(j.token); location.hash = '#/chats'; renderConnecting(); connect();
        if ('Notification' in window && Notification.permission === 'default') { try { Notification.requestPermission(); } catch (er) { /* ignore */ } }
      } catch (er) { btn.disabled = false; btn.textContent = label; err(er.message, er.status === 401 ? pass : null); }
    });
  };

  return N;
})();
