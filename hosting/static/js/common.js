/* Общие помощники: запросы к API, тосты, тема, форматирование. */
(function () {
  "use strict";
  const AM = (window.AM = { csrf: "", config: null, catalog: null });
  AM.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  AM.$ = (s, r = document) => r.querySelector(s);
  AM.$$ = (s, r = document) => [...r.querySelectorAll(s)];
  AM.token = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  AM.esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  AM.api = async function (method, url, body) {
    const opts = { method, credentials: "same-origin", headers: { "X-Requested-With": "fetch", "Accept": "application/json" } };
    if (AM.csrf) opts.headers["X-CSRF-Token"] = AM.csrf;
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    let r;
    try { r = await fetch(url, opts); } catch (e) { throw { status: 0, error: "Нет связи с сервером. Проверьте интернет." }; }
    let data = {};
    try { data = await r.json(); } catch (e) { /* пустой ответ */ }
    if (!r.ok) throw { status: r.status, error: data.error || `Ошибка ${r.status}`, field: data.field };
    return data;
  };

  AM.money = (v) => {
    const cur = (AM.config && AM.config.currency) || "USD";
    const sym = { USD: "$", EUR: "€", RUB: "₽" }[cur];
    const n = Number(v || 0).toFixed(2);
    return sym ? `${sym}${n}` : `${n} ${cur}`;
  };
  AM.date = (ts) => ts ? new Date(ts * 1000).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }) : "—";
  AM.dateTime = (ts) => ts ? new Date(ts * 1000).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—";
  AM.bytes = (b) => {
    const u = ["Б", "КБ", "МБ", "ГБ", "ТБ"]; let i = 0; b = Number(b || 0);
    while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
    return `${b.toFixed(b >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
  };
  AM.bits = (bps) => {
    const u = ["бит/с", "Кбит/с", "Мбит/с", "Гбит/с"]; let i = 0, x = Number(bps || 0) * 8;
    while (x >= 1000 && i < u.length - 1) { x /= 1000; i++; }
    return `${x.toFixed(x >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
  };

  AM.toast = function (text, kind = "on") {
    let box = AM.$("#toasts");
    if (!box) {
      box = document.createElement("div"); box.id = "toasts"; box.className = "toasts";
      box.setAttribute("aria-live", "polite"); document.body.appendChild(box);
    }
    const el = document.createElement("div");
    el.className = "toast";
    el.innerHTML = `<span class="led ${kind}"></span><span></span>`;
    el.lastChild.textContent = text;
    box.appendChild(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 320); }, kind === "bad" ? 6000 : 3500);
  };

  AM.copy = function (text, label) {
    const ok = () => AM.toast(label || "Скопировано");
    const fallback = () => AM.toast("Выделите текст и скопируйте вручную", "busy");
    try { navigator.clipboard.writeText(text).then(ok, fallback); } catch (e) { fallback(); }
  };

  AM.tween = function (from, to, ms, fn) {
    if (AM.reduced) { fn(to); return; }
    const s = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - s) / ms);
      fn(from + (to - from) * (1 - Math.pow(1 - t, 3)));
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  AM.shake = function (el) { if (!el) return; el.classList.remove("err"); void el.offsetWidth; el.classList.add("err"); };

  // Тема: системная по умолчанию, кнопка переключает и запоминает.
  try { const t = localStorage.getItem("am-theme"); if (t) document.documentElement.setAttribute("data-theme", t); } catch (e) { /* нет доступа */ }
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#themeBtn")) return;
    const cur = document.documentElement.getAttribute("data-theme") ||
      (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("am-theme", next); } catch (e) { /* нет доступа */ }
  });

  AM.boot = async function () {
    const [config, catalog] = await Promise.all([AM.api("GET", "/api/config"), AM.api("GET", "/api/catalog")]);
    AM.config = config; AM.catalog = catalog;
    AM.$$("[data-brand]").forEach((el) => { el.textContent = config.brand; });
    document.title = document.title.replace("AM Cloud", config.brand);
    return { config, catalog };
  };
})();
