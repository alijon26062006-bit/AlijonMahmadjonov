/* Главная: шапка, языки RU/TJ/EN, тарифы и цены из API, поиск доменов, контакты, лёгкий параллакс. */
(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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
      vpsEyebrow: "VPS/VDS на NVMe", vpsTitle: "Тарифы без скрытых платежей",
      vpsLead: "Оплата помесячно с баланса. Root‑доступ, IPv4 и IPv6, защита от DDoS — в каждом тарифе.",
      perMonth: "/ мес.", popular: "Популярный", order: "Заказать", cpu: "Процессор", memory: "Память", disk: "Диск NVMe", traffic: "Трафик",
      gb: "ГБ", tb: "ТБ", vcpu: "vCPU", dcLabel: "Дата‑центры:", plansError: "Не удалось загрузить тарифы. Обновите страницу.",
      panelEyebrow: "Личный кабинет", panelTitle: "Управляйте сервером сами, без писем в поддержку",
      f1t: "Root‑пароль в два клика", f1d: "Задайте свой пароль или сгенерируйте новый. Он уходит на сервер по SSH и не хранится у нас.",
      f2t: "Графики нагрузки", f2d: "Процессор, память, сеть и диск за час, сутки и неделю. Плюс процессы, которые грузят сервер.",
      f3t: "DNS‑записи с проверкой", f3d: "A, AAAA, CNAME, MX, TXT, SRV, CAA. Ошибку в формате панель покажет до публикации.",
      domEyebrow: "Домены", domTitle: "Найдите имя для проекта", domLead: "Уже есть домен? Добавьте его в кабинет бесплатно и ведите DNS у нас.",
      domEmpty: "Введите имя в поиске на первом экране — здесь появятся свободные зоны и цены.",
      priceTitle: "Цены на регистрацию", zone: "Зона", perYear: "За год", year: "/год", register: "Зарегистрировать", taken: "Занят",
      checkError: "Проверка временно недоступна. Попробуйте через минуту.",
      dedEyebrow: "Выделенные серверы", dedTitle: "Целый физический сервер под ваш проект",
      dedLead: "Для нагруженных сайтов, баз данных и игровых серверов. Подберём процессор, память и диски под задачу и назовём цену до оплаты.",
      dedCta: "Оставить заявку",
      faqEyebrow: "Вопросы и поддержка", faqTitle: "Частые вопросы",
      faqLead: "Не нашли ответ? Напишите нам — отвечаем на русском, таджикском и английском.",
      q1: "Как быстро будет готов сервер?", a1: "Обычно примерно через минуту после заказа. IP‑адрес и доступ появятся в личном кабинете.",
      q2: "Как оплатить?", a2: "Пополните баланс в личном кабинете: переведите деньги удобным способом и отправьте заявку. Серверы и домены оплачиваются с баланса.",
      q3: "Что будет, если закончатся деньги на балансе?", a3: "Мы заранее напишем на почту. Если не пополнить баланс, сервер выключится через несколько дней после окончания оплаты, а данные сохранятся.",
      q4: "Можно ли самому сменить root‑пароль?", a4: "Да, в личном кабинете: задайте свой пароль или сгенерируйте новый. Мы пароль не храним.",
      q5: "Есть ли защита от DDoS?", a5: "Да, базовая защита от DDoS‑атак включена во все тарифы бесплатно.",
      q6: "Можно ли подключить домен, купленный в другом месте?", a6: "Да. Добавьте домен в кабинет и пропишите наши неймсерверы у своего регистратора — DNS будет работать у нас.",
      footTag: "VPS, выделенные серверы и домены в одном кабинете.", footServices: "Услуги", footDocs: "Документы", footContacts: "Контакты",
      docOffer: "Публичная оферта", docPrivacy: "Конфиденциальность", docRules: "Правила использования",
      tgLabel: "Telegram", mailLabel: "Почта", phoneLabel: "Телефон", writeUs: "Написать в поддержку", cabinet: "Личный кабинет",
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
      vpsEyebrow: "VPS/VDS бо NVMe", vpsTitle: "Тарифҳо бе пардохтҳои пинҳонӣ",
      vpsLead: "Пардохти моҳона аз тавозун. Дастрасии root, IPv4 ва IPv6, ҳифз аз DDoS — дар ҳар тариф.",
      perMonth: "/ моҳ", popular: "Маъмул", order: "Фармоиш", cpu: "Протсессор", memory: "Хотира", disk: "Диски NVMe", traffic: "Трафик",
      gb: "ГБ", tb: "ТБ", vcpu: "vCPU", dcLabel: "Маркази додаҳо:", plansError: "Тарифҳо бор нашуданд. Саҳифаро нав кунед.",
      panelEyebrow: "Кабинети шахсӣ", panelTitle: "Серверро худатон идора кунед, бе мактуб ба дастгирӣ",
      f1t: "Пароли root бо ду клик", f1d: "Пароли худро гузоред ё навашро тавлид кунед. Он тавассути SSH ба сервер меравад ва дар назди мо нигоҳ дошта намешавад.",
      f2t: "Графикҳои сарборӣ", f2d: "Протсессор, хотира, шабака ва диск барои як соат, як шабонарӯз ва як ҳафта. Инчунин равандҳое, ки серверро бор мекунанд.",
      f3t: "Сабтҳои DNS бо санҷиш", f3d: "A, AAAA, CNAME, MX, TXT, SRV, CAA. Хатои форматро панел пеш аз нашр нишон медиҳад.",
      domEyebrow: "Доменҳо", domTitle: "Барои лоиҳа ном ёбед", domLead: "Домен доред? Онро ройгон ба кабинет илова кунед ва DNS-ро дар назди мо идора кунед.",
      domEmpty: "Номро дар ҷустуҷӯи экрани аввал ворид кунед — дар ин ҷо минтақаҳои озод ва нархҳо пайдо мешаванд.",
      priceTitle: "Нархи бақайдгирӣ", zone: "Минтақа", perYear: "Барои як сол", year: "/сол", register: "Ба қайд гирифтан", taken: "Банд",
      checkError: "Санҷиш муваққатан дастнорас аст. Пас аз як дақиқа кӯшиш кунед.",
      dedEyebrow: "Серверҳои ҷудогона", dedTitle: "Сервери пурраи физикӣ барои лоиҳаи шумо",
      dedLead: "Барои сайтҳои сербор, пойгоҳи додаҳо ва серверҳои бозӣ. Протсессор, хотира ва дискҳоро мувофиқи вазифа интихоб карда, нархро пеш аз пардохт мегӯем.",
      dedCta: "Дархост гузоштан",
      faqEyebrow: "Саволҳо ва дастгирӣ", faqTitle: "Саволҳои маъмул",
      faqLead: "Ҷавоб наёфтед? Ба мо нависед — ба забонҳои тоҷикӣ, русӣ ва англисӣ ҷавоб медиҳем.",
      q1: "Сервер чӣ қадар зуд омода мешавад?", a1: "Одатан тақрибан як дақиқа пас аз фармоиш. Суроғаи IP ва дастрасӣ дар кабинети шахсӣ пайдо мешаванд.",
      q2: "Чӣ тавр пардохт кунам?", a2: "Тавозунро дар кабинети шахсӣ пур кунед: пулро бо усули қулай интиқол диҳед ва дархост фиристед. Серверҳо ва доменҳо аз тавозун пардохт мешаванд.",
      q3: "Агар пул дар тавозун тамом шавад, чӣ мешавад?", a3: "Мо пешакӣ ба почта менависем. Агар тавозун пур карда нашавад, сервер пас аз чанд рӯзи анҷоми пардохт хомӯш мешавад, вале маълумот нигоҳ дошта мешавад.",
      q4: "Оё пароли root-ро худам иваз карда метавонам?", a4: "Бале, дар кабинети шахсӣ: пароли худро гузоред ё навашро тавлид кунед. Мо паролро нигоҳ намедорем.",
      q5: "Оё ҳифз аз DDoS ҳаст?", a5: "Бале, ҳифзи асосӣ аз ҳамлаҳои DDoS дар ҳамаи тарифҳо ройгон фаъол аст.",
      q6: "Оё домени дар ҷои дигар харидашударо пайваст кардан мумкин аст?", a6: "Бале. Доменро ба кабинет илова кунед ва неймсерверҳои моро дар бақайдгирандаи худ гузоред — DNS дар назди мо кор мекунад.",
      footTag: "VPS, серверҳои ҷудогона ва доменҳо дар як кабинет.", footServices: "Хизматрасониҳо", footDocs: "Ҳуҷҷатҳо", footContacts: "Тамос",
      docOffer: "Офертаи оммавӣ", docPrivacy: "Махфият", docRules: "Қоидаҳои истифода",
      tgLabel: "Telegram", mailLabel: "Почта", phoneLabel: "Телефон", writeUs: "Ба дастгирӣ навиштан", cabinet: "Кабинети шахсӣ",
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
      vpsEyebrow: "NVMe VPS/VDS", vpsTitle: "Plans with no hidden fees",
      vpsLead: "Billed monthly from your balance. Root access, IPv4 and IPv6, DDoS protection on every plan.",
      perMonth: "/ mo", popular: "Popular", order: "Order", cpu: "CPU", memory: "Memory", disk: "NVMe disk", traffic: "Traffic",
      gb: "GB", tb: "TB", vcpu: "vCPU", dcLabel: "Data centers:", plansError: "Couldn't load plans. Please refresh the page.",
      panelEyebrow: "Control panel", panelTitle: "Manage your server yourself, no support tickets",
      f1t: "Root password in two clicks", f1d: "Set your own password or generate one. It goes to the server over SSH and is never stored by us.",
      f2t: "Load graphs", f2d: "CPU, memory, network and disk for the last hour, day and week. Plus the processes that load your server.",
      f3t: "Validated DNS records", f3d: "A, AAAA, CNAME, MX, TXT, SRV, CAA. The panel flags format mistakes before publishing.",
      domEyebrow: "Domains", domTitle: "Find a name for your project", domLead: "Already have a domain? Add it to your account for free and manage DNS with us.",
      domEmpty: "Search for a name at the top of the page — free zones and prices will appear here.",
      priceTitle: "Registration prices", zone: "Zone", perYear: "Per year", year: "/yr", register: "Register", taken: "Taken",
      checkError: "The check is temporarily unavailable. Try again in a minute.",
      dedEyebrow: "Dedicated servers", dedTitle: "A whole physical server for your project",
      dedLead: "For busy websites, databases and game servers. We'll match CPU, memory and disks to your workload and quote a price before you pay.",
      dedCta: "Send a request",
      faqEyebrow: "Questions & support", faqTitle: "Frequently asked questions",
      faqLead: "Didn't find an answer? Write to us — we answer in English, Russian and Tajik.",
      q1: "How fast is a server ready?", a1: "Usually in about a minute after ordering. The IP address and access details appear in your account.",
      q2: "How do I pay?", a2: "Top up your balance in your account: transfer the money the way you prefer and submit a request. Servers and domains are paid from the balance.",
      q3: "What if my balance runs out?", a3: "We'll email you in advance. If the balance isn't topped up, the server is stopped a few days after the paid period ends, and your data is kept.",
      q4: "Can I change the root password myself?", a4: "Yes, in your account: set your own password or generate a new one. We never store it.",
      q5: "Is there DDoS protection?", a5: "Yes, basic DDoS protection is included free on every plan.",
      q6: "Can I connect a domain bought elsewhere?", a6: "Yes. Add the domain to your account and set our nameservers at your registrar — DNS will run with us.",
      footTag: "VPS, dedicated servers and domains in one account.", footServices: "Services", footDocs: "Legal", footContacts: "Contacts",
      docOffer: "Terms of service", docPrivacy: "Privacy policy", docRules: "Acceptable use",
      tgLabel: "Telegram", mailLabel: "Email", phoneLabel: "Phone", writeUs: "Contact support", cabinet: "Your account",
    },
  };
  const HTML_LANG = { ru: "ru", tj: "tg", en: "en" };
  let lang = "ru";
  const t = () => I18N[lang];
  const state = { config: null, catalog: null, lastSearch: null };

  // ── Языки ──
  function applyLang(next) {
    lang = next in I18N ? next : "ru";
    const d = t();
    document.documentElement.lang = HTML_LANG[lang];
    $$("[data-i18n]").forEach((el) => { const v = d[el.dataset.i18n]; if (typeof v === "string") el.textContent = v; });
    $$("[data-i18n-html]").forEach((el) => { el.innerHTML = d[el.dataset.i18nHtml]; });
    $$("[data-i18n-ph]").forEach((el) => { el.placeholder = d[el.dataset.i18nPh]; });
    $$("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", d[el.dataset.i18nAria]); });
    $$("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
    $("#domainNote").textContent = "";
    renderDynamic();
    if (state.lastSearch) renderResults(state.lastSearch);
    try { localStorage.setItem("am-lang", lang); } catch (e) { /* хранилище недоступно */ }
  }
  $$("[data-lang]").forEach((b) => b.addEventListener("click", () => applyLang(b.dataset.lang)));

  // ── Шапка ──
  const header = $("#header");
  const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 8 || burger.getAttribute("aria-expanded") === "true");
  const burger = $("#burger"), drawer = $("#drawer");
  addEventListener("scroll", onScroll, { passive: true });
  const setMenu = (open) => { burger.setAttribute("aria-expanded", String(open)); drawer.dataset.open = String(open); onScroll(); };
  burger.addEventListener("click", () => setMenu(burger.getAttribute("aria-expanded") !== "true"));
  drawer.addEventListener("click", (e) => { if (e.target.closest("a")) setMenu(false); });
  addEventListener("keydown", (e) => { if (e.key === "Escape" && burger.getAttribute("aria-expanded") === "true") { setMenu(false); burger.focus(); } });
  matchMedia("(min-width: 981px)").addEventListener?.("change", (e) => { if (e.matches) setMenu(false); });
  onScroll();

  // Подсветка пункта меню текущего раздела
  const navLinks = $$(".nav a, .drawer a");
  const setCurrent = (href) => navLinks.forEach((a) => {
    if (a.getAttribute("href") === href) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  if ("IntersectionObserver" in window) {
    const hero = $(".hero");
    const watched = [hero, ...["vps", "dedicated", "domains", "support"].map((id) => document.getElementById(id))].filter(Boolean);
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) setCurrent(en.target === hero ? "/" : `#${en.target.id}`); });
    }, { rootMargin: "-45% 0px -50% 0px" });
    watched.forEach((s) => io.observe(s));
  }

  // ── Данные с сервера ──
  const money = (v) => {
    const cur = (state.config && state.config.currency) || "USD";
    const sym = { USD: "$", EUR: "€", RUB: "₽" }[cur];
    const n = Number(v || 0);
    const s = n % 1 === 0 ? n.toFixed(0) : n.toFixed(2);
    return sym ? `${sym}${s}` : `${s} ${cur}`;
  };

  async function getJSON(url) {
    const r = await fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" });
    if (!r.ok) throw new Error(String(r.status));
    return r.json();
  }

  function renderDynamic() {
    const d = t(), c = state.catalog, cfg = state.config;
    const plans = $("#plans");
    if (c && plans) {
      plans.innerHTML = c.plans.map((p) => `
        <article class="plan ${p.featured ? "featured" : ""}">
          ${p.featured ? `<span class="badge">${esc(d.popular)}</span>` : ""}
          <h3>${esc(p.name)}</h3>
          <div class="price"><b>${money(p.price_month)}</b><span>${esc(d.perMonth)}</span></div>
          <ul class="specs">
            <li><span>${esc(d.cpu)}</span><b>${p.cpu} ${esc(d.vcpu)}</b></li>
            <li><span>${esc(d.memory)}</span><b>${p.ram_gb} ${esc(d.gb)}</b></li>
            <li><span>${esc(d.disk)}</span><b>${p.disk_gb} ${esc(d.gb)}</b></li>
            <li><span>${esc(d.traffic)}</span><b>${p.traffic_tb} ${esc(d.tb)}</b></li>
          </ul>
          <a class="btn ${p.featured ? "btn-primary" : "btn-outline"}" href="/app#/order?plan=${encodeURIComponent(p.id)}">${esc(d.order)}</a>
        </article>`).join("");
      $("#dcList").textContent = c.locations.map((l) => l.name).join(", ");
      $("#zoneTable").innerHTML = c.tlds.map((z) => `<tr><td>.${esc(z.zone)}</td><td>${money(z.price_year)}</td></tr>`).join("");
      $(".zones").innerHTML = c.tlds.slice(0, 6).map((z) => `<button class="zone" type="button" data-zone="${esc(z.zone)}">.${esc(z.zone)}</button>`).join("");
    }
    if (cfg) {
      const sup = cfg.support || {};
      const items = [];
      if (sup.telegram) items.push({ href: `https://t.me/${encodeURIComponent(sup.telegram)}`, icon: "i-tg", label: d.tgLabel, value: "@" + sup.telegram });
      if (sup.email) items.push({ href: `mailto:${sup.email}`, icon: "i-mail", label: d.mailLabel, value: sup.email });
      if (sup.phone) items.push({ href: `tel:${sup.phone.replace(/[^\d+]/g, "")}`, icon: "i-phone", label: d.phoneLabel, value: sup.phone });
      if (!items.length) items.push({ href: "/app", icon: "i-user", label: d.cabinet, value: d.writeUs });
      $("#contacts").innerHTML = items.map((i) => `<a class="contact" href="${esc(i.href)}" ${i.href.startsWith("http") ? 'target="_blank" rel="noopener"' : ""}>
        <span class="perk-ic"><svg class="icon" aria-hidden="true"><use href="#${i.icon}"/></svg></span><span><small>${esc(i.label)}</small><b>${esc(i.value)}</b></span></a>`).join("");
      $("#footContacts").innerHTML = items.map((i) => `<a href="${esc(i.href)}">${esc(i.value)}</a>`).join("");
      $("#dedCta").href = items[0].href;
      if (items[0].href.startsWith("http")) { $("#dedCta").target = "_blank"; $("#dedCta").rel = "noopener"; }
      $("#footCompany").textContent = cfg.company || cfg.brand;
      $("#footBrand").textContent = cfg.brand;
    }
    bindZones();
  }

  (async () => {
    $("#year").textContent = new Date().getFullYear();
    try {
      const [config, catalog] = await Promise.all([getJSON("/api/config"), getJSON("/api/catalog")]);
      state.config = config; state.catalog = catalog;
      renderDynamic();
    } catch (e) {
      const plans = $("#plans");
      if (plans) plans.innerHTML = `<p class="dom-empty">${esc(t().plansError)}</p>`;
    }
  })();

  // ── Поиск домена ──
  const form = $("#domainForm"), input = $("#domain-input"), note = $("#domainNote");
  const DOMAIN = /^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z]{2,24})?$/;
  const clean = (v) => v.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0];
  function fail(msg) {
    note.textContent = msg;
    form.classList.remove("err"); void form.offsetWidth; form.classList.add("err");
    input.focus();
  }
  function renderResults(results) {
    const d = t();
    $("#domResults").innerHTML = results.map((r, i) => {
      const [label, ...zone] = r.domain.split(".");
      return `<div class="dom-row ${r.available ? "free" : "taken"}" style="animation-delay:${i * 60}ms">
        <span class="dn">${esc(label)}<b>.${esc(zone.join("."))}</b></span>
        <span class="pr">${r.available ? `${money(r.price)}${esc(d.year)}` : ""}</span>
        ${r.available ? `<a class="btn btn-primary" href="/app#/domains/new?buy=${encodeURIComponent(r.domain)}">${esc(d.register)}</a>`
                      : `<span class="tag-taken">${esc(d.taken)}</span>`}</div>`;
    }).join("");
  }
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const d = clean(input.value);
    if (!d) return fail(t().empty);
    if (!DOMAIN.test(d)) return fail(t().invalid);
    note.textContent = "";
    const box = $("#domResults");
    box.innerHTML = '<div class="dom-row loading"></div>'.repeat(4);
    $("#domains").scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    try {
      const { results } = await getJSON(`/api/domains/check?name=${encodeURIComponent(d)}`);
      state.lastSearch = results;
      renderResults(results);
    } catch (err) {
      state.lastSearch = null;
      box.innerHTML = `<p class="dom-empty">${esc(t().checkError)}</p>`;
    }
  });
  function bindZones() {
    $$("[data-zone]").forEach((b) => { b.onclick = () => {
      const base = clean(input.value).split(".")[0] || "mysite";
      input.value = `${base}.${b.dataset.zone}`;
      note.textContent = "";
      input.focus();
    }; });
  }
  bindZones();

  // ── Язык из прошлого визита ──
  let saved = null;
  try { saved = localStorage.getItem("am-lang"); } catch (e) { /* хранилище недоступно */ }
  if (saved && saved !== "ru" && saved in I18N) applyLang(saved);

  // ── Лёгкий параллакс 3D-сцены (только мышь) ──
  const scene = $("#scene"), visual = $("#visual");
  if (!reduced && matchMedia("(hover: hover) and (pointer: fine)").matches) {
    let raf = 0;
    $(".hero").addEventListener("pointermove", (e) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const r = visual.getBoundingClientRect();
        const x = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / r.width));
        const y = Math.max(-1, Math.min(1, (e.clientY - (r.top + r.height / 2)) / r.height));
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
