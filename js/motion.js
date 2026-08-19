/* ===========================================================
   Движение: появление блоков, навигация, меню, кнопка «наверх».
   Всё уважает системную настройку «уменьшить движение».
   =========================================================== */

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

/* --- Навигация и кнопка «наверх» ------------------------------- */

const nav = document.getElementById('nav');
const toTop = document.getElementById('toTop');

function onScroll() {
  const y = window.scrollY;
  if (nav) nav.classList.toggle('scrolled', y > 24);
  if (toTop) toTop.classList.toggle('show', y > window.innerHeight * 0.8);
}
onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

if (toTop) {
  toTop.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: reduceMotion.matches ? 'auto' : 'smooth' });
  });
}

/* --- Мобильное меню --------------------------------------------- */

const burger = document.getElementById('burger');
const menu = document.getElementById('menu');

if (burger && menu) {
  const setMenu = open => {
    menu.classList.toggle('open', open);
    burger.setAttribute('aria-expanded', String(open));
    document.body.style.overflow = open ? 'hidden' : '';
  };
  burger.addEventListener('click', () => setMenu(!menu.classList.contains('open')));
  menu.addEventListener('click', e => { if (e.target.tagName === 'A') setMenu(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') setMenu(false); });
}

/* --- Появление блоков -------------------------------------------- */

let observer = null;

function watchReveals() {
  if (reduceMotion.matches) {
    document.querySelectorAll('.reveal').forEach(n => n.classList.add('in'));
    return;
  }
  if (!observer) {
    observer = new IntersectionObserver(entries => {
      entries.forEach((entry, i) => {
        if (!entry.isIntersecting) return;
        // Небольшая лесенка: соседние карточки появляются друг за другом
        entry.target.style.transitionDelay = Math.min(i * 45, 220) + 'ms';
        entry.target.classList.add('in');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px' });
  }
  document.querySelectorAll('.reveal:not(.in)').forEach(n => observer.observe(n));
}

// Блоки создаются рендером, поэтому наблюдение вешаем после каждой отрисовки
document.addEventListener('site:rendered', watchReveals);
document.addEventListener('site:data', watchReveals);
watchReveals();
