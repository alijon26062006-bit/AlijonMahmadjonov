/* Главная: шапка, языки RU/TJ/EN, поиск домена, лёгкий параллакс иллюстрации. */
(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const I18N = {
    ru: {
      tagline: "хостинг и домены", navLabel: "Основное меню", menu: "Открыть меню",
      navHome: "Главная", navVps: "VPS/VDS", navDedicated: "Выделенные серверы", navDomains: "Домены", navSupport: "Поддержка",
      login: "Войти", pill: "Сервер готов примерно за 60 секунд",
      title: 'Мощные <span class="grad-text">серверы</span> для ваших проектов',
      lead: "VPS, выделенные серверы и регистрация доменов — всё в одном месте. Быстрый запуск и удобное управление.",
      ctaServer: "Выбрать сервер", ctaDomain: "Найти домен", searchLabel: "Поиск домена",
      placeholder: "Введите домен, например example.com", check: "Проверить",
      cardLoc: "Франкфурт · Ubuntu 24.04", online: "Работает", ram: "8 ГБ", ssd: "160 ГБ NVMe", uptime: "Аптайм", uptimeVal: "47 дн. 6 ч",
      p1t: "SSD NVMe", p1d: "Быстрые диски во всех тарифах",
      p2t: "Защита серверов", p2d: "Защита от DDoS и изоляция KVM",
      p3t: "Техническая поддержка", p3d: "Отвечаем на русском, таджикском и английском",
      empty: "Введите имя домена, например mysite.tj",
      invalid: "Проверьте имя: латиница, цифры и дефис, например mysite.com",
      checking: (d) => `Проверяем <b>${d}</b>…`,
      preview: (d) => `Здесь откроется проверка <b>${d}</b> и цены во всех зонах.`,
    },
    tj: {
      tagline: "хостинг ва доменҳо", navLabel: "Менюи асосӣ", menu: "Кушодани меню",
      navHome: "Асосӣ", navVps: "VPS/VDS", navDedicated: "Серверҳои ҷудогона", navDomains: "Доменҳо", navSupport: "Дастгирӣ",
      login: "Ворид шудан", pill: "Сервер тақрибан дар 60 сония омода мешавад",
      title: '<span class="grad-text">Серверҳои</span> пурқувват барои лоиҳаҳои шумо',
      lead: "VPS, серверҳои ҷудогона ва бақайдгирии доменҳо — ҳама дар як ҷо. Оғози зуд ва идоракунии қулай.",
      ctaServer: "Интихоби сервер", ctaDomain: "Ҷустуҷӯи домен", searchLabel: "Ҷустуҷӯи домен",
      placeholder: "Доменро ворид кунед, масалан example.com", check: "Санҷидан",
      cardLoc: "Франкфурт · Ubuntu 24.04", online: "Фаъол", ram: "8 ГБ", ssd: "160 ГБ NVMe", uptime: "Вақти корӣ", uptimeVal: "47 рӯз 6 соат",
      p1t: "SSD NVMe", p1d: "Дискҳои тез дар ҳамаи тарифҳо",
      p2t: "Ҳифзи серверҳо", p2d: "Ҳифз аз DDoS ва ҷудокунии KVM",
      p3t: "Дастгирии техникӣ", p3d: "Ба забонҳои тоҷикӣ, русӣ ва англисӣ ҷавоб медиҳем",
      empty: "Номи доменро ворид кунед, масалан mysite.tj",
      invalid: "Номро санҷед: ҳарфҳои лотинӣ, рақамҳо ва дефис, масалан mysite.com",
      checking: (d) => `<b>${d}</b> санҷида мешавад…`,
      preview: (d) => `Дар ин ҷо санҷиши <b>${d}</b> ва нархҳо дар ҳамаи минтақаҳо кушода мешавад.`,
    },
    en: {
      tagline: "hosting & domains", navLabel: "Main menu", menu: "Open menu",
      navHome: "Home", navVps: "VPS/VDS", navDedicated: "Dedicated servers", navDomains: "Domains", navSupport: "Support",
      login: "Sign in", pill: "Your server is ready in about 60 seconds",
      title: 'Powerful <span class="grad-text">servers</span> for your projects',
      lead: "VPS, dedicated servers and domain registration in one place. Fast setup and easy management.",
      ctaServer: "Choose a server", ctaDomain: "Find a domain", searchLabel: "Domain search",
      placeholder: "Enter a domain, e.g. example.com", check: "Check",
      cardLoc: "Frankfurt · Ubuntu 24.04", online: "Online", ram: "8 GB", ssd: "160 GB NVMe", uptime: "Uptime", uptimeVal: "47 d 6 h",
      p1t: "NVMe SSD", p1d: "Fast drives on every plan",
      p2t: "Server protection", p2d: "DDoS protection and KVM isolation",
      p3t: "Technical support", p3d: "We answer in English, Russian and Tajik",
      empty: "Enter a domain name, e.g. mysite.com",
      invalid: "Check the name: Latin letters, digits and hyphens, e.g. mysite.com",
      checking: (d) => `Checking <b>${d}</b>…`,
      preview: (d) => `The availability check and prices for <b>${d}</b> will open here.`,
    },
  };
  const HTML_LANG = { ru: "ru", tj: "tg", en: "en" };
  let lang = "ru";

  function applyLang(next) {
    const t = I18N[next] || I18N.ru;
    lang = next in I18N ? next : "ru";
    document.documentElement.lang = HTML_LANG[lang];
    $$("[data-i18n]").forEach((el) => { const v = t[el.dataset.i18n]; if (typeof v === "string") el.textContent = v; });
    $$("[data-i18n-html]").forEach((el) => { el.innerHTML = t[el.dataset.i18nHtml]; });
    $$("[data-i18n-ph]").forEach((el) => { el.placeholder = t[el.dataset.i18nPh]; });
    $$("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t[el.dataset.i18nAria]); });
    $$("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
    $("#domainNote").textContent = "";
    try { localStorage.setItem("am-lang", lang); } catch (e) { /* хранилище недоступно */ }
  }
  $$("[data-lang]").forEach((b) => b.addEventListener("click", () => applyLang(b.dataset.lang)));
  let saved = null;
  try { saved = localStorage.getItem("am-lang"); } catch (e) { /* хранилище недоступно */ }
  if (saved && saved !== "ru") applyLang(saved);

  // ── Шапка: фон при прокрутке и мобильное меню ──
  const header = $("#header");
  const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  const burger = $("#burger"), drawer = $("#drawer");
  const setMenu = (open) => {
    burger.setAttribute("aria-expanded", String(open));
    drawer.dataset.open = String(open);
    header.classList.toggle("scrolled", open || window.scrollY > 8);
  };
  burger.addEventListener("click", () => setMenu(burger.getAttribute("aria-expanded") !== "true"));
  drawer.addEventListener("click", (e) => { if (e.target.closest("a")) setMenu(false); });
  addEventListener("keydown", (e) => { if (e.key === "Escape" && burger.getAttribute("aria-expanded") === "true") { setMenu(false); burger.focus(); } });
  matchMedia("(min-width: 981px)").addEventListener?.("change", (e) => { if (e.matches) setMenu(false); });

  // ── Поиск домена ──
  const form = $("#domainForm"), input = $("#domain-input"), note = $("#domainNote");
  const DOMAIN = /^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z]{2,24})?$/;
  const clean = (v) => v.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0];

  function fail(msg) {
    note.textContent = msg;
    form.classList.remove("err"); void form.offsetWidth; form.classList.add("err");
    input.focus();
  }
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const t = I18N[lang], d = clean(input.value);
    if (!d) return fail(t.empty);
    if (!DOMAIN.test(d)) return fail(t.invalid);
    const url = document.body.dataset.checkUrl;
    if (url) {
      note.innerHTML = t.checking(d);
      location.href = url + encodeURIComponent(d);
    } else {
      note.innerHTML = t.preview(d);
    }
  });
  $$("[data-zone]").forEach((b) => b.addEventListener("click", () => {
    const base = clean(input.value).split(".")[0] || "mysite";
    input.value = `${base}.${b.dataset.zone}`;
    note.textContent = "";
    input.focus();
  }));

  // ── Лёгкий параллакс 3D-сцены (только мышь, без анимации на телефонах) ──
  const scene = $("#scene"), visual = $("#visual");
  if (!reduced && matchMedia("(hover: hover) and (pointer: fine)").matches) {
    let raf = 0;
    $(".hero").addEventListener("pointermove", (e) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const r = visual.getBoundingClientRect();
        const x = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (r.width)));
        const y = Math.max(-1, Math.min(1, (e.clientY - (r.top + r.height / 2)) / (r.height)));
        scene.style.setProperty("--ry", `${-34 + x * 6}deg`);
        scene.style.setProperty("--rx", `${-16 - y * 4}deg`);
      });
    });
    $(".hero").addEventListener("pointerleave", () => {
      scene.style.setProperty("--ry", "-34deg");
      scene.style.setProperty("--rx", "-16deg");
    });
  }
})();
