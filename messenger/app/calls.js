'use strict';
/* =========================================================
   Aloqa calls: real audio & video calls over WebRTC.
   Signaling (offer / answer / ICE) goes through the Aloqa
   server WebSocket; media flows peer-to-peer (or via TURN)
   and is always encrypted by WebRTC (DTLS-SRTP).
   ========================================================= */
window.RTC = (() => {
  const R = {};
  let C = null, callFocus = null;
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));

  /* ---------- Ring tones (generated, no audio files) ---------- */
  let toneCtx = null, toneTimer = 0, vibTimer = 0;
  function playTone(kind) {
    stopTone();
    try { toneCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return; }
    const beep = (f, at, len) => {
      if (!toneCtx) return;
      const t = toneCtx.currentTime + at, g = toneCtx.createGain(), o = toneCtx.createOscillator();
      o.frequency.value = f; o.type = 'sine'; o.connect(g); g.connect(toneCtx.destination);
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(.14, t + .03); g.gain.setValueAtTime(.14, t + len - .06); g.gain.linearRampToValueAtTime(0, t + len);
      o.start(t); o.stop(t + len);
    };
    const cycle = kind === 'ring' ? () => { beep(659, 0, .16); beep(784, .2, .16); beep(988, .4, .3); beep(659, 1.0, .16); beep(784, 1.2, .16); beep(988, 1.4, .3); } : () => beep(425, 0, 1.1);
    cycle(); toneTimer = setInterval(cycle, kind === 'ring' ? 3000 : 4000);
    if (kind === 'ring' && navigator.vibrate) { navigator.vibrate([500, 300, 500]); vibTimer = setInterval(() => navigator.vibrate([500, 300, 500]), 3000); }
  }
  function stopTone() {
    clearInterval(toneTimer); clearInterval(vibTimer); if (navigator.vibrate) navigator.vibrate(0);
    if (toneCtx) { toneCtx.close().catch(() => {}); toneCtx = null; }
  }

  /* ---------- Media & peer connection ---------- */
  const getMedia = (video, facing = 'user') => navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    video: video ? { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 } } : false
  });
  const send = data => C && NET.signal(C.peer, C.chatId, { ...data, callId: C.id });
  function makePC() {
    const pc = new RTCPeerConnection({ iceServers: (NET.ice && NET.ice.length) ? NET.ice : [] });
    pc.onicecandidate = e => { if (e.candidate) send({ kind: 'ice', cand: e.candidate.toJSON() }); };
    pc.ontrack = e => { if (!C) return; C.remote = e.streams[0] || new MediaStream([e.track]); attachRemote(); render(); };
    pc.onconnectionstatechange = () => {
      if (!C || C.pc !== pc) return;
      const st = pc.connectionState;
      if (st === 'connected') {
        clearTimeout(C.dcTimer);
        if (C.state !== 'active') { C.state = 'active'; C.connectedAt = Date.now(); stopTone(); render(); C.timer = setInterval(tick, 1000); tick(); }
        else setSub(dur((Date.now() - C.connectedAt) / 1000));
      } else if (st === 'disconnected') {
        setSub('Переподключение…');
        C.dcTimer = setTimeout(() => { if (C && C.pc === pc && pc.connectionState !== 'connected') finish('ended', true); }, 10000);
      } else if (st === 'failed') { toast('Не удалось соединиться. Проверьте интернет или настройку TURN-сервера'); finish('failed', true); }
    };
    return pc;
  }
  async function flushIce() { const q = C.iceQueue; C.iceQueue = []; for (const cand of q) { try { await C.pc.addIceCandidate(cand); } catch (e) { /* stale candidate */ } } }

  /* ---------- Outgoing call ---------- */
  R.start = async (cid, video) => {
    if (C) { toast('Вы уже разговариваете'); return; }
    const chat = S.chats.find(x => x.type === 'direct' && x.cid === cid); if (!chat) return;
    if (!navigator.mediaDevices || !window.RTCPeerConnection) { toast('Этот браузер не поддерживает звонки'); return; }
    if (!window.isSecureContext) { toast('Звонки работают только по HTTPS'); return; }
    callFocus = document.activeElement;
    C = { id: uuid(), peer: cid, chatId: chat.id, video: !!video, dir: 'out', state: 'calling', iceQueue: [], facing: 'user', mic: true, cam: !!video };
    render();
    const me = C;
    try { me.local = await getMedia(me.video); } catch (e) { if (C === me) { cleanup(me); toast(video ? 'Нет доступа к камере или микрофону' : 'Нет доступа к микрофону'); } return; }
    if (C !== me) { me.local.getTracks().forEach(t => t.stop()); return; }
    attachLocal();
    me.pc = makePC(); me.local.getTracks().forEach(t => me.pc.addTrack(t, me.local));
    await me.pc.setLocalDescription(await me.pc.createOffer());
    if (C !== me) return;
    if (!NET.signal(cid, chat.id, { kind: 'offer', callId: me.id, video: me.video, sdp: me.pc.localDescription.toJSON() })) { toast('Нет соединения с сервером'); finish('failed', false); return; }
    playTone('back');
    me.noAnswer = setTimeout(() => { if (C === me && me.state === 'calling') finish('missed', true); }, 45000);
  };

  /* ---------- Signals from the other side ---------- */
  R.onSignal = async (from, chatId, d) => {
    if (d.kind === 'offer') {
      if (C) { NET.signal(from, chatId, { kind: 'busy', callId: d.callId }); return; }
      if (!person(from)) return;
      callFocus = document.activeElement;
      C = { id: d.callId, peer: from, chatId, video: !!d.video, dir: 'in', state: 'incoming', offer: d.sdp, iceQueue: [], facing: 'user', mic: true, cam: !!d.video };
      render(); playTone('ring');
      if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
        try { C.note = new Notification((d.video ? 'Видеозвонок · ' : 'Звонок · ') + person(from).name, { body: 'Откройте Aloqa, чтобы ответить', icon: 'icons/icon-192.png', tag: 'aloqa-call', requireInteraction: true }); C.note.onclick = () => { window.focus(); C && C.note && C.note.close(); }; } catch (e) { /* ignore */ }
      }
      const me = C; me.noAnswer = setTimeout(() => { if (C === me && me.state === 'incoming') finish('missed', false); }, 45000);
      return;
    }
    if (!C || d.callId !== C.id) return;
    const me = C;
    switch (d.kind) {
      case 'answer':
        if (me.dir !== 'out' || !me.pc) return;
        clearTimeout(me.noAnswer); stopTone(); me.state = 'connecting'; render();
        await me.pc.setRemoteDescription(d.sdp); await flushIce(); return;
      case 'ice':
        if (me.pc && me.pc.remoteDescription) { try { await me.pc.addIceCandidate(d.cand); } catch (e) { /* ignore */ } } else me.iceQueue.push(d.cand);
        return;
      case 'decline': toast(person(me.peer).name + ' отклонил(а) звонок'); finish('declined', false); return;
      case 'busy': toast(person(me.peer).name + ' сейчас разговаривает'); finish('busy', false); return;
      case 'unavailable': toast(person(me.peer).name + ' сейчас не в сети'); finish('unavailable', false); return;
      case 'end': finish(me.connectedAt ? 'ended' : 'missed', false); return;
      case 'media': me.remoteCam = !!d.cam; render(); return;
    }
  };

  async function accept() {
    const me = C; if (!me || me.state !== 'incoming') return;
    stopTone(); clearTimeout(me.noAnswer); if (me.note) me.note.close();
    me.state = 'connecting'; render();
    try { me.local = await getMedia(me.video); }
    catch (e) {
      try { me.local = await getMedia(false); me.cam = false; toast('Камера недоступна — звонок без видео с вашей стороны'); }
      catch (e2) { toast('Нет доступа к микрофону'); decline(); return; }
    }
    if (C !== me) { me.local.getTracks().forEach(t => t.stop()); return; }
    attachLocal();
    me.pc = makePC(); me.local.getTracks().forEach(t => me.pc.addTrack(t, me.local));
    await me.pc.setRemoteDescription(me.offer); await flushIce();
    await me.pc.setLocalDescription(await me.pc.createAnswer());
    send({ kind: 'answer', sdp: me.pc.localDescription.toJSON() });
  }
  function decline() { if (!C) return; send({ kind: 'decline' }); finish('declined', false); }
  function hangup() { if (!C) return; if (C.state === 'incoming') return decline(); finish(C.connectedAt ? 'ended' : 'missed', true); }

  function finish(status, notify) {
    const c = C; if (!c) return;
    if (notify) send({ kind: 'end' });
    C = null; cleanup(c);
    const secs = c.connectedAt ? Math.round((Date.now() - c.connectedAt) / 1000) : 0;
    if (c.dir === 'out') { const chat = chatById(c.chatId); if (chat) addMessage(chat, { from: 'me', kind: 'call', call: { video: c.video, dur: secs, status } }); }
    toast(secs ? `Звонок завершён · ${dur(secs)}` : status === 'missed' && c.dir === 'in' ? 'Пропущенный звонок' : 'Звонок завершён');
    if (UI.route.tab === 'calls') R.renderCallsTab();
  }
  function cleanup(c) {
    clearTimeout(c.noAnswer); clearTimeout(c.dcTimer); clearInterval(c.timer); stopTone();
    if (c.local) c.local.getTracks().forEach(t => t.stop());
    if (c.pc) { try { c.pc.close(); } catch (e) { /* ignore */ } }
    if (c.note) c.note.close();
    if (C === c) C = null;
    const el = $('#callLayer .call'); if (el) el.classList.add('closing');
    setTimeout(() => { if (!C) $('#callLayer').innerHTML = ''; if (callFocus && document.contains(callFocus)) callFocus.focus({ preventScroll: true }); }, 200);
  }

  /* ---------- Controls ---------- */
  function toggleMic() { C.mic = !C.mic; C.local && C.local.getAudioTracks().forEach(t => { t.enabled = C.mic; }); render(); }
  function toggleCam() {
    if (!C.local || !C.local.getVideoTracks().length) { toast('Камера недоступна'); return; }
    C.cam = !C.cam; C.local.getVideoTracks().forEach(t => { t.enabled = C.cam; }); send({ kind: 'media', cam: C.cam }); render();
  }
  async function flipCam() {
    if (!C || !C.local || !C.pc) return;
    const facing = C.facing === 'user' ? 'environment' : 'user';
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing } }), t = s.getVideoTracks()[0];
      const sender = C.pc.getSenders().find(x => x.track && x.track.kind === 'video'); if (sender) await sender.replaceTrack(t);
      C.local.getVideoTracks().forEach(x => { C.local.removeTrack(x); x.stop(); }); C.local.addTrack(t);
      C.facing = facing; attachLocal(); render();
    } catch (e) { toast('Не удалось переключить камеру'); }
  }

  /* ---------- UI ---------- */
  const setSub = t => { const s = $('#callSub'); if (s) s.textContent = t; };
  const tick = () => { if (C && C.connectedAt) setSub(dur((Date.now() - C.connectedAt) / 1000)); };
  function attachLocal() { const v = $('#lv'); if (v && C && C.local) v.srcObject = C.local; }
  function attachRemote() {
    const v = $('#rv'), a = $('#ra'); if (!C || !C.remote) return;
    if (v) { v.srcObject = C.remote; v.muted = true; v.play().catch(() => {}); }
    if (a) { a.srcObject = C.remote; a.play().catch(() => {}); }
  }
  const ctrl = (act, icon, label, pressed) => `<button type="button" class="ctrl" data-rtc="${act}" aria-pressed="${!!pressed}"><span class="c">${ic(icon, 24)}</span>${label}</button>`;
  function render() {
    if (!C) return;
    const L = $('#callLayer'), p = person(C.peer);
    if (!$('.call.rtc', L)) {
      L.innerHTML = `<div class="call rtc" role="dialog" aria-modal="true" aria-label="Звонок: ${esc(p.name)}">
        <video class="rv" id="rv" autoplay playsinline muted></video><audio id="ra" autoplay></audio>
        <div class="call-ui">
          <div class="enc">${ic('lock', 14)} Звонок зашифрован</div>
          <div class="who-c"><div class="pulse">${av(p.ini, p.g, 128)}</div><h2>${esc(p.name)}</h2><div class="sub" id="callSub" aria-live="polite"></div></div>
          <div class="ctrls" id="callCtrls"></div>
          <div class="call-main" id="callMain"></div>
        </div>
        <video class="lv" id="lv" autoplay playsinline muted aria-label="Ваше видео"></video></div>`;
      initPip(); attachLocal(); attachRemote();
    }
    const box = $('.call.rtc', L);
    const remoteVideo = !!(C.remote && C.remote.getVideoTracks().length && C.remoteCam !== false && C.state === 'active');
    box.classList.toggle('ringing', C.state === 'calling' || C.state === 'incoming');
    box.classList.toggle('has-video', remoteVideo);
    box.classList.toggle('self-video', !!(C.local && C.cam && C.local.getVideoTracks().length));
    if (C.state !== 'active') setSub({ calling: C.video ? 'Видеовызов…' : 'Вызов…', incoming: C.video ? 'Входящий видеозвонок' : 'Входящий звонок', connecting: 'Соединение…' }[C.state]);
    if (C.state === 'incoming') {
      $('#callCtrls').innerHTML = '';
      $('#callMain').innerHTML = `<button type="button" class="ctrl big" data-rtc="decline"><span class="c red">${ic('phone', 30)}</span>Отклонить</button>
        <button type="button" class="ctrl big" data-rtc="accept"><span class="c green">${ic(C.video ? 'video' : 'phone', 30)}</span>Принять</button>`;
      $('[data-rtc="accept"]').focus({ preventScroll: true });
    } else {
      const hasCam = C.local && C.local.getVideoTracks().length;
      $('#callCtrls').innerHTML = ctrl('mic', C.mic ? 'mic' : 'micOff', C.mic ? 'Микрофон' : 'Без звука', !C.mic)
        + (C.video ? ctrl('cam', C.cam ? 'video' : 'videoOff', 'Камера', !C.cam) : '')
        + (C.video && hasCam && C.cam ? ctrl('flip', 'camera', 'Повернуть') : '');
      $('#callMain').innerHTML = `<button type="button" class="ctrl big" data-rtc="end" aria-label="Завершить звонок"><span class="c red">${ic('phone', 30)}</span>Завершить</button>`;
    }
  }
  /* Draggable self-view that snaps to the nearest side */
  function initPip() {
    const v = $('#lv'); if (!v) return;
    let s = null;
    v.addEventListener('pointerdown', e => { v.setPointerCapture(e.pointerId); const r = v.getBoundingClientRect(); s = { dx: e.clientX - r.left, dy: e.clientY - r.top }; v.style.transition = 'none'; });
    v.addEventListener('pointermove', e => { if (!s) return; v.style.left = clamp(e.clientX - s.dx, 8, innerWidth - v.offsetWidth - 8) + 'px'; v.style.top = clamp(e.clientY - s.dy, 8, innerHeight - v.offsetHeight - 8) + 'px'; v.style.right = 'auto'; });
    const up = () => { if (!s) return; s = null; v.style.transition = ''; const r = v.getBoundingClientRect(); v.style.left = (r.left + r.width / 2 < innerWidth / 2 ? 12 : innerWidth - r.width - 12) + 'px'; };
    v.addEventListener('pointerup', up); v.addEventListener('pointercancel', up);
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-rtc]'); if (!b || !C) return;
    ({ accept, decline, end: hangup, mic: toggleMic, cam: toggleCam, flip: flipCam })[b.dataset.rtc]?.();
  });
  addEventListener('beforeunload', () => { if (C) send({ kind: C.state === 'incoming' ? 'decline' : 'end' }); });

  /* ---------- Calls tab (online): built from call messages ---------- */
  R.renderCallsTab = () => {
    const items = [];
    for (const c of S.chats) if (c.cid) for (const m of c.messages) if (m.kind === 'call') items.push({ c, m });
    items.sort((a, b) => b.m.ts - a.m.ts);
    const missed = ({ m }) => m.from !== 'me' && !(m.call || {}).dur;
    const list = items.filter(x => UI.callFilter === 'all' || missed(x));
    $('#tabView').innerHTML = `<header class="lh"><h1>Звонки</h1></header>
      <div class="seg" role="radiogroup" aria-label="Фильтр звонков" style="margin-top:0">
        <button type="button" role="radio" aria-checked="${UI.callFilter === 'all'}" data-act="call-filter" data-id="all">Все</button>
        <button type="button" role="radio" aria-checked="${UI.callFilter === 'missed'}" data-act="call-filter" data-id="missed">Пропущенные</button>
        <button type="button" role="radio" aria-checked="false" data-act="call-new">${ic('plus', 16)}Новый</button></div>
      <div class="list">${list.length ? list.map(x => {
        const { c, m } = x, p = person(c.cid), C2 = m.call || {}, out = m.from === 'me', miss = missed(x);
        const label = miss ? 'Пропущенный' : (out ? 'Исходящий' : 'Входящий') + (C2.dur ? ' · ' + dur(C2.dur) : ' · без ответа');
        return `<div class="row call-row">${av(p.ini, p.g, 48, p.online)}
          <span class="rc"><span class="nm${miss ? ' miss' : ''}"><span>${esc(p.name)}</span></span>
          <span class="msg dir${miss ? ' miss' : ''}">${ic(out ? 'arrowOut' : 'arrowIn', 14)}${C2.video ? 'Видео · ' : ''}${label}</span></span>
          <span class="tm">${listTime(m.ts)}</span>
          <button class="ib cb" type="button" data-act="call" data-cid="${c.cid}" ${C2.video ? 'data-video="1"' : ''} aria-label="${C2.video ? 'Видеозвонок' : 'Позвонить'}: ${esc(p.name)}">${ic(C2.video ? 'video' : 'phone', 22)}</button></div>`;
      }).join('') : `<div class="empty"><b>${UI.callFilter === 'missed' ? 'Нет пропущенных' : 'Звонков пока нет'}</b>Позвоните другу из его чата или профиля</div>`}</div>`;
  };
  R.active = () => C;
  return R;
})();
