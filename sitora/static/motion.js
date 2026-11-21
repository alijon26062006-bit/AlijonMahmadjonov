/* SITORA · motion.js — живой, но быстрый интерфейс. Ничего не блокирует нажатия. */
(function () {
  "use strict";
  var still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  var M = {};

  // «1 240 500»: пробелы между разрядами, дробная часть — если есть
  M.fmt = function (n, digits) {
    var d = digits == null ? (Math.abs(n % 1) > 1e-9 ? 1 : 0) : digits;
    return n.toFixed(d).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  };

  // Блоки поднимаются по очереди: шаг 55ms задаёт переменная --i
  M.stagger = function (root) {
    $$(".rise", root).forEach(function (box) {
      [].forEach.call(box.children, function (el, i) { el.style.setProperty("--i", i); });
    });
  };

  // Число «набегает» от старого к новому: 0.9s, ease-out cubic. Никогда не меняется мгновенно
  M.count = function (el, to, ms, digits) {
    var from = el._v == null ? parseFloat(String(el.textContent).replace(/\s/g, "").replace(",", ".")) || 0 : el._v;
    cancelAnimationFrame(el._raf);
    el._v = to;
    if (still || from === to) { el.textContent = M.fmt(to, digits); return; }
    var t0 = performance.now(); ms = ms || 900;
    var d = digits == null ? ((Math.abs(to % 1) > 1e-9 || Math.abs(from % 1) > 1e-9) ? 1 : 0) : digits;
    (function step(t) {
      var k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
      el.textContent = M.fmt(from + (to - from) * e, k < 1 ? d : digits);
      if (k < 1) el._raf = requestAnimationFrame(step);
    })(t0);
  };

  // Буквы логотипа падают по одной
  M.logo = function (el) {
    var text = el.textContent; el.textContent = ""; el.setAttribute("aria-label", text);
    text.split("").forEach(function (ch, i) {
      var s = document.createElement("span"); s.textContent = ch; s.style.setProperty("--i", i);
      s.setAttribute("aria-hidden", "true"); el.appendChild(s);
    });
  };

  // Страницы: вперёд — справа, назад — слева
  var order = [];
  M.go = function (name, back) {
    var next = $('.page[data-page="' + name + '"]'), cur = $(".page.on");
    if (!next || next === cur) return;
    if (cur) cur.classList.remove("on", "enter-r", "enter-l");
    next.classList.remove("enter-r", "enter-l"); void next.offsetWidth;
    next.classList.add("on", back ? "enter-l" : "enter-r");
    document.documentElement.classList.toggle("dark-on", next.classList.contains("dark"));
    var nav = $(".nav"); if (nav) nav.hidden = next.hasAttribute("data-nonav");
    M.stagger(next);
    $$(".rise>*,.progress i,.bars i,.barcode i", next).forEach(function (el) {   // проиграть появление заново
      el.style.animationName = "none"; void el.offsetWidth; el.style.animationName = "";
    });
    window.scrollTo(0, 0);
    if (next._enter) next._enter();
  };

  // Нижнее меню: полоска переезжает, иконка подпрыгивает
  M.nav = function (nav) {
    var bar = $(".bar", nav), items = $$("button", nav);
    function place() {
      var a = $("[aria-current=page]", nav);
      if (a) bar.style.transform = "translateX(" + (a.offsetLeft + a.offsetWidth / 2 - 13) + "px)";
    }
    items.forEach(function (b, i) {
      b.addEventListener("click", function () {
        var was = items.indexOf($("[aria-current=page]", nav));
        if (was === i) return;
        items.forEach(function (x) { x.removeAttribute("aria-current"); x.classList.remove("jump"); });
        b.setAttribute("aria-current", "page"); void b.offsetWidth; b.classList.add("jump");
        place(); M.go(b.dataset.go, i < was);
      });
    });
    window.addEventListener("resize", place); place();
    return place;
  };

  // Вкладки с ползунком
  M.seg = function (seg, onChange) {
    var thumb = $(".thumb", seg), tabs = $$("button", seg);
    tabs.forEach(function (b, i) {
      b.addEventListener("click", function () {
        tabs.forEach(function (x) { x.setAttribute("aria-selected", x === b); });
        thumb.style.transform = "translateX(calc(" + i * 100 + "% + " + i * 4 + "px))";
        if (onChange) onChange(b.dataset.tab, i);
      });
    });
  };

  // Уведомление: падает сверху, через 2.5s уезжает
  M.toast = function (text) {
    $$(".toast").forEach(function (t) { t.remove(); });
    var t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status"); t.textContent = text;
    document.body.appendChild(t);
    setTimeout(function () { t.classList.add("out"); setTimeout(function () { t.remove(); }, 320); }, 2500);
  };

  // Лист снизу. Закрывается по фону; анимация не мешает нажимать
  M.sheet = function (el) {
    var dim = document.createElement("div"); dim.className = "dim";
    document.body.appendChild(dim); el.hidden = false; el.classList.remove("out"); M.stagger(el);
    function close() {
      el.classList.add("out"); dim.classList.add("out");
      setTimeout(function () { el.hidden = true; el.classList.remove("out"); dim.remove(); }, still ? 0 : 280);
    }
    dim.addEventListener("click", close); el._close = close; return close;
  };

  // Ошибка: поле трясётся (±9px, 0.4s) и очищается. Без красного
  M.shake = function (input) {
    input.classList.remove("shake"); void input.offsetWidth; input.classList.add("shake");
    setTimeout(function () { input.classList.remove("shake"); input.value = ""; }, still ? 0 : 400);
  };

  // Чёрно-белое конфетти из точки (x, y): 60–70 частиц, гравитация, вращение, гаснут за 2s. Canvas
  M.confetti = function (x, y) {
    if (still) return;
    var c = document.createElement("canvas"); c.className = "confetti"; document.body.appendChild(c);
    var dpr = Math.min(2, window.devicePixelRatio || 1), w = c.width = innerWidth * dpr, h = c.height = innerHeight * dpr;
    var g = c.getContext("2d"), tones = ["#FFFFFF", "#E4E4E2", "#8C8C88", "#5C5C58", "#FFFFFF"];
    var n = 60 + Math.floor(Math.random() * 11), parts = [];
    for (var i = 0; i < n; i++) {
      var a = Math.random() * Math.PI * 2, v = (5 + Math.random() * 9) * dpr;
      parts.push({ x: x * dpr, y: y * dpr, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 5 * dpr, r: Math.random() * 6.28,
                   vr: (Math.random() - .5) * .5, s: (4 + Math.random() * 5) * dpr, round: i % 3 === 0, c: tones[i % tones.length] });
    }
    var t0 = performance.now(), last = t0;
    (function frame(t) {
      var k = (t - t0) / 2000, dt = Math.min(2, (t - last) / 16.7); last = t;
      g.clearRect(0, 0, w, h);
      if (k >= 1) { c.remove(); return; }
      g.globalAlpha = k < .6 ? 1 : 1 - (k - .6) / .4;
      parts.forEach(function (p) {
        p.vy += .42 * dpr * dt; p.vx *= .985; p.x += p.vx * dt; p.y += p.vy * dt; p.r += p.vr * dt;
        g.save(); g.translate(p.x, p.y); g.rotate(p.r); g.fillStyle = p.c;
        if (p.round) { g.beginPath(); g.arc(0, 0, p.s / 2, 0, 6.28); g.fill(); }
        else g.fillRect(-p.s / 2, -p.s * .8, p.s, p.s * 1.6);
        g.restore();
      });
      requestAnimationFrame(frame);
    })(t0);
  };

  // Успех: круг выстреливает, галочка рисуется, конфетти из центра круга, баланс набегает за 1s
  M.success = function (page, balanceEl, from, to) {
    var ok = $(".ok", page);
    ok.style.animationName = "none"; $("path", ok).style.animationName = "none"; void ok.offsetWidth;
    ok.style.animationName = ""; $("path", ok).style.animationName = "";
    setTimeout(function () {
      var r = ok.getBoundingClientRect(); M.confetti(r.left + r.width / 2, r.top + r.height / 2);
    }, still ? 0 : 380);
    if (balanceEl) { balanceEl._v = from; balanceEl.textContent = M.fmt(from); M.count(balanceEl, to, 1000); }
  };

  // FLIP: строки плавно переезжают на новые места за 0.75s
  M.flip = function (list, change) {
    var rows = [].slice.call(list.children), first = rows.map(function (r) { return r.getBoundingClientRect().top; });
    change();
    if (still) return;
    rows.forEach(function (r, i) {
      var dy = first[i] - r.getBoundingClientRect().top;
      if (!dy) return;
      r.animate([{ transform: "translateY(" + dy + "px)" }, { transform: "none" }],
                { duration: 750, easing: "cubic-bezier(.2,.9,.2,1)" });
    });
  };
  M.fresh = function (row) { row.classList.add("fresh"); setTimeout(function () { row.classList.remove("fresh"); }, 1100); };

  // Штрихкод из числа: полоски растут снизу по очереди
  M.barcode = function (el, code) {
    el.textContent = "";
    String(code).split("").forEach(function (d, k) {
      [1 + (+d % 3), 1 + ((+d + k) % 2), 2 + (+d % 2)].forEach(function (wd, j) {
        var b = document.createElement("i"); b.style.width = wd + "px"; b.style.setProperty("--i", k * 3 + j);
        if (j === 1) b.style.opacity = "0"; el.appendChild(b);
      });
    });
  };

  window.Motion = M;
})();
