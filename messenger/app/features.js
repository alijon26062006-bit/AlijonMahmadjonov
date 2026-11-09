'use strict';
/* =========================================================
   Aloqa: message menu & reactions, editing, forwarding,
   photo viewer, chat appearance (wallpapers, glass, motion).
   ========================================================= */
I.download = '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>';
const QUICK = ['❤️', '👍', '😂', '😮', '😢', '🔥', '🙏'];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

/* ---------- Reactions ---------- */
function toggleReact(mid, e) {
  const [c, m] = findMsg(mid); if (!m) return;
  m.reacts = m.reacts || {};
  const had = Object.keys(m.reacts).find(k => m.reacts[k].includes('me'));
  for (const k of Object.keys(m.reacts)) { m.reacts[k] = m.reacts[k].filter(x => x !== 'me'); if (!m.reacts[k].length) delete m.reacts[k]; }
  const set = had !== e;
  if (set) (m.reacts[e] = m.reacts[e] || []).push('me');
  if (NET.on) NET.react(mid, set ? e : null); else save();
  refreshChat(c.id);
  if (set) {
    const chip = $(`#threadIn .b[data-mid="${mid}"] .rx.mine`); if (chip) chip.classList.add('pop');
    if (navigator.vibrate) navigator.vibrate(8);
  }
}
function burst(x, y, e) {
  if (RM.matches) return;
  const el = document.createElement('span'); el.className = 'burst'; el.textContent = e; el.setAttribute('aria-hidden', 'true');
  el.style.left = x + 'px'; el.style.top = y + 'px'; document.body.appendChild(el);
  setTimeout(() => el.remove(), 900);
}
/* Double tap on a message = quick ❤️ (works for touch and mouse) */
let lastTap = null;
document.addEventListener('pointerup', e => {
  const b = e.target.closest('#threadIn .b');
  if (!b || e.button > 0 || e.target.closest('button, a, input, video, .rxs')) { lastTap = null; return; }
  const t = performance.now();
  if (lastTap && lastTap.mid === b.dataset.mid && t - lastTap.t < 320 && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < 30) {
    lastTap = null;
    const [c, m] = findMsg(b.dataset.mid); if (!m || (c && c.blocked)) return;
    const mine = m.reacts && Object.keys(m.reacts).find(k => m.reacts[k].includes('me'));
    if (mine !== '❤️') burst(e.clientX, e.clientY, '❤️');
    toggleReact(b.dataset.mid, '❤️');
  } else lastTap = { mid: b.dataset.mid, t, x: e.clientX, y: e.clientY };
});

/* ---------- Telegram-style message menu: lifted bubble, reactions above, actions below ---------- */
function openMsgMenu(mid) {
  const [c, m] = findMsg(mid);
  const src = $(`#threadIn .b[data-mid="${mid}"]`);
  if (!m || !src || $('#overlay').innerHTML) return;
  lastFocus = document.activeElement;
  const out = m.from === 'me', canWrite = c.type !== 'channel' && !c.blocked;
  const acts = [];
  if (canWrite) acts.push(['m-reply', 'reply', 'Ответить']);
  if (m.kind === 'text') acts.push(['m-copy', 'copy', 'Копировать']);
  if (out && m.kind === 'text' && canWrite && Date.now() - m.ts < 48 * 3600e3) acts.push(['m-edit', 'edit', 'Изменить']);
  if (m.kind === 'text') acts.push(['m-forward', 'send', 'Переслать']);
  if (out || !NET.on) acts.push(['m-delete', 'trash', out && NET.on ? 'Удалить у всех' : 'Удалить', 1]);
  const mine = m.reacts && Object.keys(m.reacts).find(k => m.reacts[k].includes('me'));
  const ov = $('#overlay');
  ov.innerHTML = `<div class="mm-scrim" data-act="close-overlay"></div>
    <div class="mm" role="dialog" aria-modal="true" aria-label="Действия с сообщением">
      ${c.blocked ? '' : `<div class="mm-rx" role="group" aria-label="Реакции">${QUICK.map((e, i) => `<button type="button" class="${mine === e ? 'on' : ''}" data-act="react" data-id="${mid}" data-e="${e}" style="--i:${i}" aria-label="Реакция ${e}">${e}</button>`).join('')}<button type="button" class="more" data-act="rx-more" data-id="${mid}" style="--i:${QUICK.length}" aria-label="Все реакции">${ic('chevronDown', 20)}</button></div>`}
      <div class="mm-msg"></div>
      <div class="mm-menu" role="menu">${acts.map(([a, i, l, d]) => `<button type="button" role="menuitem" class="${d ? 'danger' : ''}" data-act="${a}" data-id="${mid}"><span>${l}</span>${ic(i, 20)}</button>`).join('')}</div>
    </div>`;
  const bar = $('.mm-rx', ov), box = $('.mm-msg', ov), menu = $('.mm-menu', ov);
  const clone = src.cloneNode(true);
  clone.classList.remove('enter', 'spring', 'dragging', 'pressed', 'hl'); clone.removeAttribute('tabindex'); clone.style.cssText = '';
  $$('[data-act]', clone).forEach(x => x.removeAttribute('data-act')); $$('.swipe-ic', clone).forEach(x => x.remove());
  box.appendChild(clone);
  const r = src.getBoundingClientRect(), W = innerWidth, H = innerHeight, gap = 8;
  const barH = bar ? bar.offsetHeight : 0, menuH = menu.offsetHeight, menuW = menu.offsetWidth;
  const msgH = Math.min(r.height, H - barH - menuH - gap * 2 - 40);
  let top = r.top - barH - gap;
  top = clamp(top, 20, H - (barH + gap + msgH + gap + menuH) - 20);
  const msgTop = top + barH + gap;
  Object.assign(box.style, { left: r.left + 'px', top: msgTop + 'px', width: r.width + 'px', height: msgH + 'px' });
  if (bar) {
    const bw = bar.offsetWidth;
    Object.assign(bar.style, { left: clamp(out ? r.right - bw : r.left, 8, W - bw - 8) + 'px', top: top + 'px', transformOrigin: out ? '100% 100%' : '0 100%' });
  }
  Object.assign(menu.style, { left: clamp(out ? r.right - menuW : r.left, 8, W - menuW - 8) + 'px', top: (msgTop + msgH + gap) + 'px', transformOrigin: out ? '100% 0' : '0 0' });
  if (!RM.matches) box.animate([{ transform: `translateY(${r.top - msgTop}px)` }, { transform: 'translateY(0) scale(1.03)', offset: .65 }, { transform: 'none' }], { duration: 360, easing: 'cubic-bezier(.32,.72,0,1)' });
  src.style.visibility = 'hidden'; UI.menuSrc = src;
  if (navigator.vibrate) navigator.vibrate(12);
  const first = $('.mm-rx button, .mm-menu button', ov); if (first) first.focus({ preventScroll: true });
}
function closeMsgMenu() {
  const ov = $('#overlay'), mm = $('.mm', ov); if (!mm || mm.classList.contains('closing')) return;
  mm.classList.add('closing'); const sc = $('.mm-scrim', ov); if (sc) sc.classList.add('closing');
  const src = UI.menuSrc, box = $('.mm-msg', ov);
  if (src && document.contains(src) && !RM.matches) {
    const r = src.getBoundingClientRect(), cur = box.getBoundingClientRect();
    box.animate([{ transform: 'none' }, { transform: `translateY(${r.top - cur.top}px)` }], { duration: 220, easing: 'cubic-bezier(.4,0,1,1)', fill: 'forwards' });
  }
  setTimeout(() => {
    if ($('.mm.closing', ov)) ov.innerHTML = '';
    if (src) src.style.visibility = ''; UI.menuSrc = null;
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
  }, RM.matches ? 0 : 220);
}
function expandReactions(btn) {
  const bar = btn.closest('.mm-rx'), mid = btn.dataset.id;
  bar.classList.add('full');
  bar.innerHTML = EMOJI.concat(['🤯', '🥳', '😡', '💯', '🤝', '👀', '🎉', '😇']).filter((e, i, a) => a.indexOf(e) === i)
    .map((e, i) => `<button type="button" data-act="react" data-id="${mid}" data-e="${e}" style="--i:${i % 8}" aria-label="Реакция ${e}">${e}</button>`).join('');
  const r = bar.getBoundingClientRect(); if (r.right > innerWidth - 8) bar.style.left = Math.max(8, innerWidth - r.width - 8) + 'px';
  if (r.top < 12) bar.style.top = '12px';
  $('button', bar).focus();
}

/* ---------- Editing ---------- */
function setEdit(m) {
  const ta = $('#msgInput'), bar = $('#replyBar'); if (!m || !ta || !bar) return;
  UI.reply = null; UI.edit = { id: m.id };
  bar.hidden = false;
  bar.innerHTML = `${ic('edit', 20)}<div class="rb"><b>Редактирование</b><span>${esc(m.text)}</span></div><button class="ib" type="button" data-act="cancel-edit" aria-label="Отменить редактирование">${ic('x', 20)}</button>`;
  ta.value = m.text; ta.dispatchEvent(new Event('input')); ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
}
function cancelEdit() {
  UI.edit = null;
  const ta = $('#msgInput'); if (ta) { ta.value = ''; ta.dispatchEvent(new Event('input')); }
  const bar = $('#replyBar'); if (bar) { bar.hidden = true; bar.innerHTML = ''; }
}
function finishEdit() {
  const ta = $('#msgInput'), text = ta.value.trim(), [c, m] = findMsg(UI.edit.id);
  if (m && text && text !== m.text) {
    m.text = text; m.edited = true;
    if (NET.on) NET.edit(m.id, text); else save();
    refreshChat(c.id); renderChatList(); toast('Сообщение изменено');
  }
  if (c) UI.drafts[c.id] = '';
  cancelEdit(); ta.focus();
}

/* ---------- Forwarding, jump to quoted message ---------- */
function forwardSheet(mid) {
  const list = sortedChats().filter(c => c.type !== 'channel' && !c.blocked);
  openSheet('Переслать', `<h3>Переслать в…</h3>${list.map(c => `<button type="button" class="opt" data-act="fwd-to" data-id="${mid}" data-chat="${c.id}">${chatAv(c, 40, false)}<span>${esc(chatTitle(c))}</span></button>`).join('')}`);
}
function doForward(mid, chatId) {
  const [c0, m] = findMsg(mid), c = chatById(chatId); if (!m || !c) return;
  closeOverlay();
  const author = m.fwd || (m.from === 'me' ? meName() : (c0.type === 'channel' ? chatTitle(c0) : person(m.from).name));
  addMessage(c, { from: 'me', kind: 'text', text: m.text, fwd: author });
  toast('Сообщение переслано', 'Открыть', () => { location.hash = '#/chat/' + c.id; });
}
function gotoMsg(id) {
  const el = $(`#threadIn .b[data-mid="${id}"]`);
  if (!el) { toast('Сообщение уже не в истории'); return; }
  el.scrollIntoView({ block: 'center', behavior: RM.matches ? 'auto' : 'smooth' });
  el.classList.remove('hl'); void el.offsetWidth; el.classList.add('hl');
}

/* ---------- Full-screen photo viewer: pinch, double-tap zoom, swipe down to close ---------- */
function openViewer(mid) {
  const [c, m] = findMsg(mid); if (!m) return;
  lastFocus = document.activeElement;
  const who = m.from === 'me' ? 'Вы' : (c.type === 'channel' ? chatTitle(c) : person(m.from).name);
  const ok = m.media && m.media.url && !m.media.expired;
  const v = document.createElement('div');
  v.className = 'viewer'; v.setAttribute('role', 'dialog'); v.setAttribute('aria-modal', 'true'); v.setAttribute('aria-label', 'Просмотр фото');
  v.innerHTML = `<div class="vw-bg"></div>
    <div class="vw-top"><button class="ib" type="button" data-vw="close" aria-label="Закрыть">${ic('back', 26)}</button>
      <div class="vw-who"><b>${esc(who)}</b><small>${dayLabel(m.ts)}, ${hhmm(m.ts)}</small></div>
      ${ok ? `<a class="ib" href="${esc(m.media.url)}" download aria-label="Скачать">${ic('download', 22)}</a>` : ''}</div>
    <div class="vw-stage">${ok ? `<img src="${esc(m.media.url)}" alt="${esc(m.caption || 'Фото')}" draggable="false">` : `<div class="vw-svg">${hueGrad(m.hue || 250)}</div>`}</div>
    ${m.caption ? `<div class="vw-cap">${esc(m.caption)}</div>` : ''}`;
  document.body.appendChild(v);
  const stage = $('.vw-stage', v), media = stage.firstElementChild, bg = $('.vw-bg', v);
  let sc = 1, tx = 0, ty = 0, drag = null, pinch = null, tap = 0;
  const pts = new Map();
  const apply = (anim) => { media.style.transition = anim ? 'transform 260ms cubic-bezier(.32,.72,0,1)' : 'none'; media.style.transform = `translate(${tx}px, ${ty}px) scale(${sc})`; };
  const close = () => {
    v.classList.add('closing');
    setTimeout(() => { v.remove(); if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true }); }, 200);
    removeEventListener('keydown', onKey);
  };
  const onKey = e => { if (e.key === 'Escape') close(); };
  addEventListener('keydown', onKey);
  $('[data-vw="close"]', v).onclick = close;
  $('[data-vw="close"]', v).focus();
  stage.addEventListener('pointerdown', e => {
    stage.setPointerCapture(e.pointerId); pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), sc }; drag = null; }
    else drag = { x: e.clientX, y: e.clientY, tx, ty, t: performance.now() };
  });
  stage.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return; pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pts.size === 2) { const [a, b] = [...pts.values()]; sc = clamp(pinch.sc * Math.hypot(a.x - b.x, a.y - b.y) / pinch.d, 1, 4); apply(); return; }
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (sc > 1) { tx = drag.tx + dx; ty = drag.ty + dy; apply(); }
    else { ty = dy; tx = 0; apply(); bg.style.opacity = String(clamp(1 - Math.abs(dy) / 420, .2, 1)); }
  });
  const up = e => {
    pts.delete(e.pointerId);
    if (pinch) { if (pts.size < 2) { pinch = null; if (sc <= 1.02) { sc = 1; tx = ty = 0; apply(true); } } return; }
    if (!drag) return;
    const moved = Math.hypot(e.clientX - drag.x, e.clientY - drag.y), v2 = Math.abs(e.clientY - drag.y) / Math.max(1, performance.now() - drag.t);
    if (sc === 1 && (Math.abs(ty) > 120 || (v2 > .6 && Math.abs(ty) > 40))) { media.style.transition = 'transform 200ms ease-in, opacity 200ms'; media.style.transform = `translateY(${ty > 0 ? innerHeight : -innerHeight}px)`; close(); drag = null; return; }
    if (sc === 1) { ty = 0; apply(true); bg.style.opacity = ''; }
    if (moved < 8) {
      const now = performance.now();
      if (now - tap < 300) { /* double tap: zoom in / out at the tap point */
        if (sc > 1) { sc = 1; tx = ty = 0; } else { const r = stage.getBoundingClientRect(); sc = 2.5; tx = (r.width / 2 - (e.clientX - r.left)) * 1.5; ty = (r.height / 2 - (e.clientY - r.top)) * 1.5; }
        apply(true); tap = 0;
      } else tap = now;
    }
    drag = null;
  };
  stage.addEventListener('pointerup', up); stage.addEventListener('pointercancel', up);
}

/* =========================================================
   Chat appearance: wallpapers, blur/dim, glass UI, motion
   ========================================================= */
const WALLS = [
  ['default', 'Классика', null],
  ['aurora', 'Аврора', 'linear-gradient(160deg,#A99BFF 0%,#FF9A9A 55%,#FDBA74 100%)'],
  ['ocean', 'Океан', 'linear-gradient(165deg,#22D3EE 0%,#2563EB 55%,#1E1652 100%)'],
  ['mint', 'Мята', 'linear-gradient(160deg,#ECFDF5 0%,#A7F3D0 50%,#5EEAD4 100%)'],
  ['sunset', 'Закат', 'linear-gradient(170deg,#FDBA74 0%,#F43F5E 45%,#6D28D9 100%)'],
  ['night', 'Ночь', 'radial-gradient(120% 80% at 20% 10%,#4338CA 0%,#1E1B4B 45%,#05060A 100%)'],
  ['doodle', 'Узор', 'doodle']
];
const ACCENTS = [['#5B4BFF', 'Фиолетовый'], ['#2563EB', 'Синий'], ['#0E9F8E', 'Бирюзовый'], ['#16A34A', 'Зелёный'], ['#EA580C', 'Оранжевый'], ['#DB2777', 'Розовый'], ['#111827', 'Графит']];
const DOODLE = col => `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160' viewBox='0 0 160 160' fill='none' stroke='${col}' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round' opacity='.45'><g transform='translate(12 14)'>${I.chat}</g><g transform='translate(98 20) rotate(12)'>${I.camera}</g><g transform='translate(36 92) rotate(-10)'>${I.mic}</g><g transform='translate(112 104)'>${I.smile}</g><g transform='translate(70 52) scale(.8)'>${I.send}</g><g transform='translate(12 128) scale(.75)'>${I.bell}</g><g transform='translate(126 66) scale(.7)'>${I.image}</g></svg>`)}")`;
const LOOK_DEFAULT = { wall: 'default', blur: 0, dim: 0, glass: false, motion: false, accent: '#5B4BFF', size: 16 };
const getLook = () => ({ ...LOOK_DEFAULT, ...((S && S.settings && S.settings.look) || {}) });
let customWall = null;
function getCustomWall() { if (customWall == null) { try { customWall = localStorage.getItem('aloqa.wall') || ''; } catch (e) { customWall = ''; } } return customWall; }
function setCustomWall(d) { customWall = d; try { localStorage.setItem('aloqa.wall', d); return true; } catch (e) { toast('Картинка слишком большая для хранения — она сбросится после перезапуска'); return false; } }
function wallBg(id, dark) {
  if (id === 'custom') { const d = getCustomWall(); return d ? `center / cover no-repeat url("${d}")` : null; }
  if (id === 'doodle') return `${DOODLE(dark ? '#8B7FFF' : '#5B4BFF')} 0 0 / 160px 160px, ${dark ? '#0B0D12' : '#E8EBF5'}`;
  const w = WALLS.find(x => x[0] === id); return w ? w[2] : null;
}
const isDark = () => document.documentElement.dataset.theme === 'dark';
function lookClass() { const L = getLook(); return (L.wall !== 'default' && wallBg(L.wall, isDark()) ? ' has-wall' : '') + (L.glass ? ' glass' : ''); }
function paintWall(el, L = getLook()) {
  (el ? [el] : $$('#wall')).forEach(w => {
    const bg = L.wall === 'default' ? null : wallBg(L.wall, isDark());
    w.hidden = !bg; w.style.background = bg || '';
    w.style.filter = bg && L.blur ? `blur(${L.blur}px)` : '';
    w.style.setProperty('--dim', bg ? L.dim / 100 : 0);
  });
}
function applyChatLook() {
  const L = getLook(), root = document.documentElement;
  if (L.accent && L.accent.toLowerCase() !== '#5b4bff') {
    root.style.setProperty('--brand', L.accent); root.style.setProperty('--bubble-out', L.accent);
    root.style.setProperty('--brand-soft', `color-mix(in srgb, ${L.accent} 16%, var(--bg-surface))`);
  } else ['--brand', '--bubble-out', '--brand-soft'].forEach(v => root.style.removeProperty(v));
  root.style.setProperty('--msg-size', L.size + 'px'); root.style.setProperty('--msg-lh', Math.round(L.size * 1.38) + 'px');
  const conv = $('#main .conv');
  if (conv && $('#thread')) { conv.className = 'conv' + lookClass(); paintWall(); setupGlass(); setupMotion(); }
}
let glassRO = null;
function setupGlass() {
  if (glassRO) { glassRO.disconnect(); glassRO = null; }
  const conv = $('#main .conv'); if (!conv || !conv.classList.contains('glass')) return;
  const ch = $('.ch', conv), cw = $('#composerWrap', conv);
  const sync = () => { conv.style.setProperty('--chH', ch.offsetHeight + 'px'); conv.style.setProperty('--cpH', cw.offsetHeight + 'px'); };
  glassRO = new ResizeObserver(sync); glassRO.observe(ch); glassRO.observe(cw); sync();
}
function afterConvRender() { paintWall(); setupGlass(); setupMotion(); }

/* Motion effect: wallpaper follows phone tilt (and the mouse on desktop) */
const motion = { on: false, tx: 0, ty: 0, x: 0, y: 0, raf: 0 };
const onOrient = e => { if (e.gamma == null) return; motion.tx = clamp(e.gamma / 30, -1, 1) * 22; motion.ty = clamp((e.beta - 45) / 30, -1, 1) * 22; };
const onMouse = e => { if (e.pointerType !== 'mouse') return; motion.tx = (e.clientX / innerWidth - .5) * 28; motion.ty = (e.clientY / innerHeight - .5) * 28; };
function tickMotion() {
  motion.x += (motion.tx - motion.x) * .08; motion.y += (motion.ty - motion.y) * .08;
  const w = $('#wall'); if (w) w.style.transform = `translate3d(${(-motion.x).toFixed(2)}px, ${(-motion.y).toFixed(2)}px, 0) scale(1.1)`;
  motion.raf = requestAnimationFrame(tickMotion);
}
function setupMotion() {
  const L = getLook(), want = L.motion && L.wall !== 'default' && !RM.matches && !!$('#wall');
  if (want && !motion.on) { motion.on = true; addEventListener('deviceorientation', onOrient); addEventListener('pointermove', onMouse, { passive: true }); motion.raf = requestAnimationFrame(tickMotion); }
  else if (!want && motion.on) {
    motion.on = false; removeEventListener('deviceorientation', onOrient); removeEventListener('pointermove', onMouse); cancelAnimationFrame(motion.raf);
    const w = $('#wall'); if (w) w.style.transform = '';
  }
}
const needsMotionPermission = () => typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function';
async function askMotionPermission() {
  if (!needsMotionPermission()) return true;
  try { return (await DeviceOrientationEvent.requestPermission()) === 'granted'; } catch (e) { return false; }
}
/* iPhone asks again after every launch: request on the first tap */
document.addEventListener('click', function once() { if (getLook().motion && needsMotionPermission()) askMotionPermission(); }, { once: true });

function openLook() {
  const L0 = getLook();
  openSheet('Оформление чата', `<h3>Оформление чата</h3>
    <div class="lk-prev${L0.glass ? ' glass' : ''}" id="lkPrev"><div class="wall" id="lkWall"></div>
      <div class="lk-msgs"><div class="b in first last">Привет! Как тебе новые обои? 😍<span class="mt">10:24</span></div>
      <div class="b out first last">Очень красиво, и стекло тоже ✨<span class="mt">10:25${ic('checks', 15)}</span></div></div></div>
    <p class="sect">Обои</p>
    <div class="lk-walls" role="radiogroup" aria-label="Обои">
      ${WALLS.map(([id, name]) => `<button type="button" role="radio" class="lk-w" data-wall="${id}" aria-checked="${L0.wall === id}"><span class="sw" data-sw="${id}"></span>${name}</button>`).join('')}
      <button type="button" role="radio" class="lk-w" data-wall="custom" aria-checked="${L0.wall === 'custom'}"><span class="sw sw-add" data-sw="custom">${ic('images', 24)}</span>Из галереи</button></div>
    <div id="lkAdj">
      <label class="lk-row"><span>Размытие</span><input type="range" min="0" max="20" step="1" id="lkBlur" value="${L0.blur}"></label>
      <label class="lk-row"><span>Затемнение</span><input type="range" min="0" max="60" step="5" id="lkDim" value="${L0.dim}"></label></div>
    <div class="card lk-card">
      <div class="li"><span class="t"><b id="lkGlassL">Стеклянный интерфейс</b><small>Прозрачные панели и сообщения поверх обоев</small></span><button type="button" class="switch" role="switch" aria-labelledby="lkGlassL" aria-checked="${L0.glass}" id="lkGlass"></button></div>
      <div class="li"><span class="t"><b id="lkMotL">Эффект движения</b><small>Обои сдвигаются, когда вы наклоняете телефон</small></span><button type="button" class="switch" role="switch" aria-labelledby="lkMotL" aria-checked="${L0.motion}" id="lkMotion"></button></div></div>
    <p class="sect">Цвет темы</p>
    <div class="swatches lk-acc" role="radiogroup" aria-label="Цвет темы">${ACCENTS.map(([col, n]) => `<button type="button" role="radio" aria-checked="${L0.accent.toLowerCase() === col.toLowerCase()}" aria-label="${n}" data-acc="${col}" style="background:${col}"></button>`).join('')}</div>
    <p class="sect">Размер текста · <span id="lkSizeV">${L0.size}</span></p>
    <div class="lk-row"><span aria-hidden="true" style="font-size:13px;width:auto">А</span><input type="range" min="14" max="20" step="1" id="lkSize" value="${L0.size}" aria-label="Размер текста сообщений"><span aria-hidden="true" style="font-size:20px;width:auto">А</span></div>
    <button type="button" class="btn ghost block" id="lkReset" style="margin-top:12px">Сбросить оформление</button>`, sh => {
    const set = patch => { S.settings.look = { ...getLook(), ...patch }; save(); applyChatLook(); sync(); };
    const sync = () => {
      const L = getLook();
      paintWall($('#lkWall', sh), L);
      $('#lkPrev', sh).classList.toggle('glass', L.glass);
      $('#lkPrev', sh).classList.toggle('has-wall', L.wall !== 'default');
      $$('.lk-w', sh).forEach(b => b.setAttribute('aria-checked', b.dataset.wall === L.wall));
      $$('[data-acc]', sh).forEach(b => b.setAttribute('aria-checked', b.dataset.acc.toLowerCase() === L.accent.toLowerCase()));
      $('#lkAdj', sh).hidden = L.wall === 'default';
      $('#lkGlass', sh).setAttribute('aria-checked', L.glass); $('#lkMotion', sh).setAttribute('aria-checked', L.motion);
      $('#lkSizeV', sh).textContent = L.size;
      $$('.sw', sh).forEach(s => { const bg = s.dataset.sw === 'default' ? null : wallBg(s.dataset.sw, isDark()); s.style.background = bg || ''; s.classList.toggle('has-img', !!bg); });
    };
    sh.addEventListener('click', async e => {
      const w = e.target.closest('.lk-w'), a = e.target.closest('[data-acc]');
      if (w) {
        if (w.dataset.wall === 'custom') { const d = await pickWallpaper(); if (!d) return; setCustomWall(d); set({ wall: 'custom' }); }
        else set({ wall: w.dataset.wall });
      }
      if (a) set({ accent: a.dataset.acc });
      if (e.target.closest('#lkGlass')) set({ glass: !getLook().glass });
      if (e.target.closest('#lkMotion')) {
        const on = !getLook().motion;
        if (on && !(await askMotionPermission())) { toast('Разрешите доступ к датчикам движения'); return; }
        set({ motion: on });
        if (on) toast(isMobile() ? 'Наклоните телефон — обои сдвинутся' : 'На компьютере обои следуют за мышью');
      }
      if (e.target.closest('#lkReset')) { S.settings.look = {}; save(); applyChatLook(); sync(); }
    });
    $('#lkBlur', sh).addEventListener('input', e => set({ blur: +e.target.value }));
    $('#lkDim', sh).addEventListener('input', e => set({ dim: +e.target.value }));
    $('#lkSize', sh).addEventListener('input', e => set({ size: +e.target.value }));
    sync();
  });
}
function pickWallpaper() {
  return new Promise(resolve => {
    const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*';
    inp.onchange = async () => {
      const f = inp.files && inp.files[0]; if (!f) return resolve(null);
      try {
        const bmp = await createImageBitmap(f), k = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
        const cv = document.createElement('canvas'); cv.width = Math.round(bmp.width * k); cv.height = Math.round(bmp.height * k);
        cv.getContext('2d').drawImage(bmp, 0, 0, cv.width, cv.height);
        resolve(cv.toDataURL('image/jpeg', .82));
      } catch (e) { toast('Не удалось открыть изображение'); resolve(null); }
    };
    inp.click();
  });
}

/* ---------- Events for this module ---------- */
document.addEventListener('click', e => {
  const el = e.target.closest('[data-act]'); if (!el) return;
  switch (el.dataset.act) {
    case 'react': {
      const inMenu = el.closest('.mm');
      if (inMenu) { const r = el.getBoundingClientRect(); burst(r.left + r.width / 2, r.top, el.dataset.e); }
      toggleReact(el.dataset.id, el.dataset.e);
      if (inMenu) closeMsgMenu();
      break;
    }
    case 'rx-more': expandReactions(el); break;
    case 'm-edit': { const [, m] = findMsg(el.dataset.id); closeMsgMenu(); setTimeout(() => setEdit(m), 230); break; }
    case 'cancel-edit': cancelEdit(); $('#msgInput').focus(); break;
    case 'm-forward': { const id = el.dataset.id; closeMsgMenu(); setTimeout(() => forwardSheet(id), 230); break; }
    case 'fwd-to': doForward(el.dataset.id, el.dataset.chat); break;
    case 'goto': gotoMsg(el.dataset.id); break;
    case 'view': if (!el.closest('.mm')) openViewer(el.dataset.id); break;
    case 'look': openLook(); break;
  }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && UI.edit && document.activeElement && document.activeElement.id === 'msgInput') cancelEdit(); });
