import { vibrate } from '../platform.js';
import { ico } from './dom.js';
import { esc } from '../lib/format.js';

// Кнопка «потяните вправо»: главный шаг доставки нельзя нажать случайно в кармане или за рулём.
// Без пальца: кнопка-ползунок получает фокус, Enter или пробел тоже подтверждают (экранный диктор, клавиатура).

/** Разметка ползунка. act — имя действия, которое выполнится, data — data-атрибуты. */
export const slider = (label, act, data = {}, tone = '') => `<div class="slide ${tone}" data-slide="${act}" ${Object.entries(data).map(([k, v]) => `data-${k}="${esc(v)}"`).join(' ')}>
  <span class="slide-fill"></span><span class="slide-label">${esc(label)}</span>
  <button class="slide-knob" type="button" aria-label="${esc(label)}: потяните вправо или нажмите Enter">${ico('arrowR')}</button></div>`;

let onDone = () => {};
/** Что делать, когда ползунок дотянули: fn(имя действия, элемент). */
export const onSlide = fn => { onDone = fn; };

let drag = null;
const DONE_AT = 0.82;   // сколько дорожки надо пройти
function finish(el) {
  el.classList.add('done'); vibrate(40);
  onDone(el.dataset.slide, el);
  setTimeout(() => { if (el.isConnected) { el.classList.remove('done'); set(el, 0); } }, 900);
}
function set(el, k) {
  const knob = el.querySelector('.slide-knob'), room = el.clientWidth - knob.offsetWidth - 8;
  knob.style.transform = `translateX(${k * room}px)`;
  el.querySelector('.slide-fill').style.width = `${knob.offsetWidth + 8 + k * room}px`;
  el.style.setProperty('--k', k);
}
document.addEventListener('pointerdown', e => {
  const knob = e.target.closest('.slide-knob'); if (!knob || knob.closest('.slide').classList.contains('done')) return;
  const el = knob.closest('.slide');
  drag = { el, x0: e.clientX, room: el.clientWidth - knob.offsetWidth - 8, id: e.pointerId };
  knob.setPointerCapture?.(e.pointerId); el.classList.add('drag');
});
document.addEventListener('pointermove', e => {
  if (!drag || e.pointerId !== drag.id) return;
  set(drag.el, Math.max(0, Math.min(1, (e.clientX - drag.x0) / drag.room)));
});
const up = e => {
  if (!drag || e.pointerId !== drag.id) return;
  const { el } = drag; drag = null; el.classList.remove('drag');
  const k = +getComputedStyle(el).getPropertyValue('--k') || 0;
  if (k >= DONE_AT) { set(el, 1); finish(el); } else set(el, 0);
};
document.addEventListener('pointerup', up);
document.addEventListener('pointercancel', up);
document.addEventListener('keydown', e => {
  const knob = e.target.closest?.('.slide-knob');
  if (knob && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); const el = knob.closest('.slide'); set(el, 1); finish(el); }
});
