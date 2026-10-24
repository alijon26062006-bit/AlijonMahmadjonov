import { BRAND, EVERY, WAIT_CLIENT_MIN } from './config.js';
import { startTranslating, tr } from './i18n.js';
import { play } from './lib/sound.js';
import { askNotify, keepAwake, notify, onResume, vibrate, watch, where } from './platform.js';
import * as api from './services/api.js';
import { activeJob, cancelledJob, K, reset, rt, save } from './state.js';
import { $, actions, app, closeSheet, ico, on, openSheet, sheetOpen, toast } from './ui/dom.js';
import { onSlide } from './ui/slide.js';
import { authActions, vRegister, vWelcome } from './views/auth.js';
import { doStep, jobActions, mmss, setCurrent, vCancelled, vDone, vJob } from './views/job.js';
import { moneyActions, vMoney } from './views/money.js';
import { applyTheme, profileActions, vProfile } from './views/profile.js';
import { vShift } from './views/shift.js';

// Приложение курьера: экраны, смена на линии, лента заказов, живые обновления, место курьера.

const TABS = [['shift', '#/', 'Смена', 'bike'], ['money', '#/money', 'Доход', 'wallet'], ['profile', '#/profile', 'Профиль', 'user']];
setCurrent(activeJob);

export function render() {
  applyTheme();
  if (!K.phone) { app.innerHTML = vWelcome(); return; }
  if (!K.me || location.hash === '#/register') { app.innerHTML = vRegister(); return; }
  const h = location.hash || '#/', j = activeJob(), c = cancelledJob();
  let html, tab = 'shift', dock = false;
  if (h === '#/money') { html = vMoney(); tab = 'money'; }
  else if (h === '#/profile') { html = vProfile(); tab = 'profile'; }
  else if (rt.done) html = vDone(rt.done, [...(rt.history || []), ...K.jobs]);
  else if (c) html = vCancelled(c);
  else if (j) { html = vJob(j); dock = true; }
  else html = vShift();
  const typing = document.activeElement?.id === 'code', caret = typing ? document.activeElement.selectionStart : 0, y = window.scrollY;
  app.innerHTML = `<main class="page ${dock ? 'has-dock' : ''}" id="main">${html}</main>
    <nav class="tabs" aria-label="Разделы"><div class="tabs-in">${TABS.map(([k, to, t, i]) => `<button class="tab" data-go="${to}" ${tab === k ? 'aria-current="page"' : ''}>${ico(i)}<span>${t}</span>${k === 'shift' && j && tab !== 'shift' ? '<span class="badge dot"></span>' : ''}</button>`).join('')}</div></nav>`;
  window.scrollTo(0, y);
  if (typing) { const i = $('#code'); i?.focus(); i?.setSelectionRange(caret, caret); }
}
// перерисовать само, если курьер сейчас ничего не трогает: не открыта шторка, не тянет ползунок
const calm = () => !sheetOpen() && !document.querySelector('.slide.drag') && !(document.activeElement?.matches('input:not(#code),textarea'));
const soft = () => { if (calm()) render(); };

// ---------- база: свои заказы, лента, место ----------
let uid = null, stopListen = () => {};
function netOk() { if (rt.net !== 'ok') { rt.net = 'ok'; soft(); } }
function netFail(e) { if (e?.net && rt.net !== 'off') { rt.net = 'off'; soft(); } }

async function refreshJobs() {
  if (!K.me) return;
  try {
    const before = activeJob(), list = await api.jobs(0); netOk();
    const ids = new Set(list.map(j => j.id));
    K.jobs = [...list, ...K.jobs.filter(j => !ids.has(j.id))].slice(0, 30); save();
    // заказ, который вёз курьер, отменили или покупатель сам нажал «Получил»
    const now = before && K.jobs.find(j => j.id === before.id);
    if (now?.status === 'cancelled') { if (K.sound) play('bad'); vibrate([200, 100, 200]); }
    else if (now?.step === 'delivered' && !rt.done && !K.seenDone.includes(now.id)) { K.seenDone.push(now.id); save(); rt.done = now; if (K.sound) play('done'); }
    soft();
  } catch (e) { netFail(e); }
}

async function refreshFeed() {
  if (!K.online || activeJob() || !K.me) return;
  try {
    const list = await api.feed(); netOk();
    const old = new Set(rt.feed.map(o => o.id)), fresh = list.filter(o => !old.has(o.id));
    const changed = JSON.stringify(list.map(o => [o.id, o.status, o.to_shop])) !== JSON.stringify(rt.feed.map(o => [o.id, o.status, o.to_shop]));
    rt.feed = list;
    if (fresh.length) {
      fresh.forEach(o => rt.fresh.add(o.id)); setTimeout(() => { fresh.forEach(o => rt.fresh.delete(o.id)); soft(); }, 8000);
      if (K.sound) play('offer'); vibrate([300, 120, 300, 120, 300]);
      const o = fresh[0];
      if (document.visibilityState !== 'visible') notify(tr(`Новый заказ: +${o.earn} смн`), tr(`${o.shop} → ${o.area || 'покупатель'}`));
    }
    if (changed) soft();
  } catch (e) { netFail(e); }
}

// смена: место курьера, лента, экран не гаснет
let stopWatch = null, lastPing = 0, feedTimer = 0;
function startShift() {
  if (!stopWatch) stopWatch = watch(p => {
    rt.pos = p; if (rt.geoErr) { rt.geoErr = ''; soft(); }
    if (Date.now() - lastPing > EVERY.ping) { lastPing = Date.now(); api.ping(p).then(netOk, netFail); }
  }, e => { rt.geoErr = e.message; soft(); });
  if (K.awake) keepAwake(true);
  clearInterval(feedTimer); feedTimer = setInterval(refreshFeed, EVERY.feed); refreshFeed();
}
function stopShift() { stopWatch?.(); stopWatch = null; keepAwake(false); clearInterval(feedTimer); rt.feed = []; }
setInterval(() => { if (K.me && (K.online || activeJob())) refreshJobs(); }, EVERY.job);
// таймер ожидания покупателя тикает каждую секунду, остальное («готов через N мин») — раз в 30 секунд
setInterval(() => {
  const t = $('#waitT'), j = activeJob();
  if (t && j && K.waitFrom[j.id]) { const left = Math.max(0, WAIT_CLIENT_MIN * 60000 - (Date.now() - K.waitFrom[j.id])); t.textContent = mmss(left); if (!left) soft(); }
}, 1000);
setInterval(soft, 30000);

async function boot() {
  if (!K.phone) return render();
  render();
  try {
    await api.login(K.phone);
    const m = await api.me(); netOk();
    K.me = m; save();
    if (m && uid !== m.id) { uid = m.id; stopListen(); stopListen = api.listen(uid, refreshJobs); }
  } catch (e) { netFail(e); }
  await refreshJobs();
  if (K.online && K.me) startShift();
  render();
  if (location.hash === '#/money') loadHistory();
}
async function loadHistory() {
  try { rt.history = await api.jobs(30); netOk(); } catch (e) { netFail(e); rt.history ||= K.jobs; }
  soft();
}

// ---------- действия ----------
Object.entries({ ...authActions, ...jobActions, ...moneyActions, ...profileActions }).forEach(([k, fn]) => on(k, fn));
on('closeSheet', () => { closeSheet(); return false; });
on('toggleOnline', async () => {
  const want = !K.online; rt.busy = true; render();
  try {
    let pos = null;
    if (want) {
      askNotify();
      pos = await where().catch(e => { rt.geoErr = e.message; return null; });
      if (pos) { rt.pos = pos; rt.geoErr = ''; }
    }
    K.me = await api.setOnline(want, pos); K.online = want; save(); netOk();
    if (want) { startShift(); toast('Вы на линии. Заказы придут со звуком'); }
    else { stopShift(); toast('Смена закончена. Хорошего отдыха!'); }
  } catch (e) { toast(e.message); netFail(e); }
  finally { rt.busy = false; }
});
on('take', async el => {
  rt.busy = true; render();
  try {
    const j = await api.take(el.dataset.id);
    K.jobs = [j, ...K.jobs.filter(x => x.id !== j.id)]; rt.feed = rt.feed.filter(o => o.id !== j.id); save();
    vibrate([40, 40, 40]); toast('Заказ ваш! Едем в магазин'); window.scrollTo(0, 0);
  } catch (e) { toast(e.message); refreshFeed(); }
  finally { rt.busy = false; }
});
on('install', () => { install(); return false; });
onSlide((act, el) => { if (act === 'step') doStep(el).then(render); });

document.addEventListener('submit', e => e.preventDefault());
document.addEventListener('click', async e => {
  const g = e.target.closest('[data-go]');
  if (g && !g.disabled) { e.preventDefault(); closeSheet(); if (location.hash === g.dataset.go) render(); else location.hash = g.dataset.go; return; }
  const el = e.target.closest('[data-a]'); if (!el || el.disabled) return;
  const fn = actions[el.dataset.a]; if (!fn) return;
  e.preventDefault();
  const res = await fn(el);
  if (res === 'logout') return logout();
  if (res !== false && !sheetOpen()) render();
  if (['login', 'saveMe'].includes(el.dataset.a) && K.me) boot();
});
document.addEventListener('input', e => {
  if (e.target.id === 'code') { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 4); rt.code = e.target.value; }
  if (e.target.id === 'phone') { const d = e.target.value.replace(/\D/g, '').replace(/^992(?=\d{9})/, '').slice(0, 9); e.target.value = d.replace(/^(\d{2})(\d{0,3})(\d{0,2})(\d{0,2}).*/, (m, a, b, c, x) => [a, b, c, x].filter(Boolean).join(' ')); }
});
window.addEventListener('hashchange', () => { closeSheet(); window.scrollTo(0, 0); render(); if (location.hash === '#/money') loadHistory(); });
onResume(() => { if (!K.me) return; refreshJobs(); refreshFeed(); if (K.online && K.awake) keepAwake(true); });

async function logout() {
  stopShift(); stopListen(); uid = null;
  try { if (K.online) await api.setOnline(false, null); } catch { /* без сети — сервер сам снимет с линии */ }
  await api.logout(); reset(); location.hash = '#/'; render();
}

// ---------- установка на телефон ----------
let deferred = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferred = e; });
async function install() {
  if (matchMedia('(display-mode: standalone)').matches || navigator.standalone) return toast('Приложение уже установлено');
  if (deferred) { deferred.prompt(); await deferred.userChoice; deferred = null; return; }
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  openSheet(`<h2>Установить ${BRAND} Курьер</h2><ol class="col" style="padding-left:20px;gap:8px;margin:0">${(ios ? ['Откройте сайт в Safari', 'Нажмите «Поделиться» внизу экрана', 'Выберите «На экран Домой»'] : ['Откройте сайт в Chrome', 'Нажмите ⋮ в правом верхнем углу', 'Выберите «Установить приложение»']).map(s => `<li>${s}</li>`).join('')}</ol>`, { label: 'Установка' });
}
if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) navigator.serviceWorker.register('sw.js').catch(() => {});

document.title = tr(BRAND + ' Курьер');
startTranslating();
boot();
