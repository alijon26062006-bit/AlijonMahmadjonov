/* ===========================================================
   Звёзды на canvas. Рисуются один раз, медленно мерцают.
   Ни одной картинки не грузится — только математика.
   При «уменьшить движение» рисуем статичное небо без мерцания.
   =========================================================== */

(() => {
  const canvas = document.getElementById('stars');
  if (!canvas) return;

  const ctx = canvas.getContext('2d', { alpha: true });
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const COLORS = ['#FFFFFF', '#FFE9C8', '#CFE4FF', '#FFD9F2'];

  let stars = [];
  let raf = null;

  function build() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Плотность по площади: на телефоне звёзд меньше, на большом экране больше
    const count = Math.round((w * h) / 9000);
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.1 + 0.25,
      a: Math.random() * 0.5 + 0.2,
      speed: Math.random() * 0.0012 + 0.0004,
      phase: Math.random() * Math.PI * 2,
      color: COLORS[(Math.random() * COLORS.length) | 0]
    }));
  }

  function paint(time = 0) {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);

    for (const s of stars) {
      const alpha = reduce.matches
        ? s.a
        : s.a + Math.sin(time * s.speed + s.phase) * 0.28;
      ctx.globalAlpha = Math.max(0.05, Math.min(1, alpha));
      ctx.fillStyle = s.color;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function loop(time) {
    paint(time);
    raf = requestAnimationFrame(loop);
  }

  function start() {
    cancelAnimationFrame(raf);
    build();
    if (reduce.matches) paint();
    else raf = requestAnimationFrame(loop);
  }

  // Пересобираем только при заметном изменении ширины: на мобильных
  // адресная строка постоянно меняет высоту, и это не повод всё перерисовывать.
  let lastWidth = window.innerWidth;
  window.addEventListener('resize', () => {
    if (Math.abs(window.innerWidth - lastWidth) < 60) return;
    lastWidth = window.innerWidth;
    start();
  }, { passive: true });

  // Во вкладке в фоне анимация не нужна — экономим батарею
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(raf);
    else if (!reduce.matches) raf = requestAnimationFrame(loop);
  });

  reduce.addEventListener('change', start);
  start();
})();
