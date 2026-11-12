/* Личный кабинет: вход, серверы, графики, root-пароль, домены и DNS, баланс, админка. */
(async function () {
  "use strict";
  const { $, $$, esc, api, money } = AM;
  const root = $("#root");
  let me = null, servers = [], domains = [];
  let timers = [];
  const memo = { tab: {}, range: "1h" };
  const clearTimers = () => { timers.forEach((t) => clearInterval(t)); timers = []; };

  try { await AM.boot(); } catch (e) { root.innerHTML = `<div class="auth"><div class="empty"><b>Сервер недоступен</b><span>${esc(e.error)}</span></div></div>`; return; }

  const STATUS = {
    running: ["Работает", "on"], creating: ["Создаётся…", "busy"], starting: ["Запускается…", "busy"],
    stopping: ["Выключается…", "busy"], off: ["Выключен", "off"], rebooting: ["Перезагрузка…", "busy"],
    rebuilding: ["Переустановка…", "busy"], deleting: ["Удаляется…", "busy"], unknown: ["Нет связи", "busy"],
  };
  const statusOf = (s) => (s.suspended ? ["Приостановлен", "off"] : STATUS[s.status] || [s.status, "busy"]);
  const ledClass = (k) => (k === "on" ? "on" : k === "busy" ? "busy" : "");
  const transitional = (s) => ["creating", "starting", "stopping", "rebooting", "rebuilding", "deleting"].includes(s.status);

  // ═══════════ Окна ═══════════
  function modal({ title, html, actions, onOpen, onClose }) {
    const back = document.createElement("div");
    back.className = "modal-back";
    back.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><h3>${esc(title)}</h3>${html}
      <div class="actions"></div></div>`;
    const close = () => { back.remove(); document.removeEventListener("keydown", onKey); onClose && onClose(); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    back.addEventListener("click", (e) => { if (e.target === back) close(); });
    const bar = $(".actions", back);
    (actions || [{ label: "Готово", kind: "btn-primary" }]).forEach((a) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = `btn ${a.kind || ""}`; b.textContent = a.label;
      b.addEventListener("click", async () => {
        if (!a.onClick) return close();
        b.disabled = true;
        try { if ((await a.onClick(back, b)) !== false) close(); } finally { b.disabled = false; }
      });
      bar.appendChild(b);
    });
    document.body.appendChild(back);
    onOpen && onOpen(back);
    const first = $("input, select", back) || $(".actions .btn:last-child", back);
    first && first.focus();
    return close;
  }

  function showSecret(title, text, password) {
    modal({
      title,
      html: `<p>${esc(text)}</p><div class="secret"><span id="secretVal"></span>
        <button class="icon-btn" type="button" id="secretCopy" aria-label="Скопировать"><svg class="icon"><use href="#i-copy"/></svg></button></div>
        <p style="color:var(--amber)">Сохраните пароль сейчас: после закрытия окна мы не сможем показать его снова.</p>`,
      actions: [{ label: "Я сохранил пароль", kind: "btn-primary" }],
      onOpen: (m) => { $("#secretVal", m).textContent = password; $("#secretCopy", m).addEventListener("click", () => AM.copy(password, "Пароль скопирован")); },
    });
  }

  /** Подтверждение паролем от кабинета. Возвращает промис со значениями полей или null. */
  function confirmAccount({ title, text, okLabel, danger, extraHtml = "", collect }) {
    return new Promise((resolve) => {
      let done = false;
      const finish = (v) => { if (!done) { done = true; resolve(v); } };
      modal({
        title,
        html: `<p>${text}</p>${extraHtml}
          <div class="field"><label for="accPw">Пароль от личного кабинета</label>
          <div class="input" id="accPwBox"><input id="accPw" type="password" autocomplete="current-password"></div></div>`,
        actions: [
          { label: "Отмена" },
          {
            label: okLabel, kind: danger ? "btn-danger" : "btn-primary",
            onClick: async (m) => {
              const pw = $("#accPw", m).value;
              if (!pw) { AM.shake($("#accPwBox", m)); return false; }
              const extra = collect ? collect(m) : {};
              if (extra === false) return false;
              finish({ account_password: pw, ...extra });
            },
          },
        ],
        onClose: () => finish(null),
        onOpen: (m) => $("#accPw", m).addEventListener("keydown", (e) => { if (e.key === "Enter") $(".actions .btn:last-child", m).click(); }),
      });
    });
  }

  // ═══════════ Маршруты ═══════════
  function route() {
    const h = location.hash.replace(/^#/, "") || "/servers";
    const [path, qs] = h.split("?");
    return { parts: path.split("/").filter(Boolean), q: new URLSearchParams(qs || "") };
  }
  addEventListener("hashchange", render);

  async function loadMe() {
    try { me = await api("GET", "/api/me"); AM.csrf = me.csrf; return true; }
    catch (e) { if (e.status === 401) { me = null; return false; } throw e; }
  }

  async function refreshLists() {
    const [m, s, d] = await Promise.all([api("GET", "/api/me"), api("GET", "/api/servers"), api("GET", "/api/domains")]);
    me = m; AM.csrf = m.csrf; servers = s.servers; domains = d.domains;
    $("#balanceChip").hidden = false;
    $("#balanceText").textContent = money(me.balance);
    $("#logoutBtn").hidden = false;
  }

  async function render() {
    clearTimers();
    try {
      if (!me && !(await loadMe())) return renderAuth();
      await refreshLists();
    } catch (e) {
      if (e.status === 401) { me = null; return renderAuth(); }
      AM.toast(e.error, "bad"); return;
    }
    renderShell();
    const { parts, q } = route();
    const main = $("#main");
    main.innerHTML = `<div class="loading-line"></div>`;
    try {
      if (parts[0] === "servers" && parts[1]) await viewServer(+parts[1]);
      else if (parts[0] === "order") viewOrder(q);
      else if (parts[0] === "domains" && parts[1] === "new") viewDomainNew(q);
      else if (parts[0] === "domains" && parts[1]) await viewDomain(+parts[1]);
      else if (parts[0] === "domains") viewDomains();
      else if (parts[0] === "billing") await viewBilling();
      else if (parts[0] === "profile") viewProfile(q);
      else if (parts[0] === "admin" && me.is_admin) await viewAdmin(parts[1]);
      else viewServers();
    } catch (e) {
      if (e.status === 401) { me = null; return renderAuth(); }
      main.innerHTML = `<div class="empty"><b>${esc(e.error || "Ошибка")}</b><a class="btn btn-sm" href="#/servers">К серверам</a></div>`;
    }
  }

  $("#logoutBtn").addEventListener("click", async () => {
    try { await api("POST", "/api/auth/logout"); } catch (e) { /* всё равно выходим */ }
    me = null; AM.csrf = ""; $("#balanceChip").hidden = true; $("#logoutBtn").hidden = true;
    renderAuth();
  });

  // ═══════════ Вход и регистрация ═══════════
  function renderAuth(mode = "login") {
    clearTimers();
    $("#balanceChip").hidden = true; $("#logoutBtn").hidden = true;
    const reg = mode === "register";
    root.innerHTML = `
      <div class="auth"><form class="auth-card view" id="authForm" novalidate>
        <div style="display:grid;gap:6px"><span class="eyebrow">Личный кабинет</span>
        <h2>${reg ? "Создать аккаунт" : "Вход"}</h2></div>
        ${reg ? `<div class="field"><label for="aName">Имя</label><div class="input"><input id="aName" autocomplete="name"></div></div>` : ""}
        <div class="field"><label for="aEmail">Email</label><div class="input" id="aEmailBox"><input id="aEmail" type="email" autocomplete="email" required></div></div>
        <div class="field"><label for="aPw">Пароль</label><div class="input" id="aPwBox"><input id="aPw" type="password" autocomplete="${reg ? "new-password" : "current-password"}" required></div>
          ${reg ? `<span class="hint">Не короче 10 символов</span>` : ""}</div>
        <div class="form-error" id="aErr"></div>
        <button class="btn btn-primary" type="submit">${reg ? "Зарегистрироваться" : "Войти"}</button>
        <p class="auth-switch">${reg ? "Уже есть аккаунт?" : "Нет аккаунта?"} <button type="button" id="aSwitch">${reg ? "Войти" : "Зарегистрироваться"}</button></p>
      </form></div>`;
    $("#aSwitch").addEventListener("click", () => renderAuth(reg ? "login" : "register"));
    $("#authForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = $("#authForm button[type=submit]");
      btn.disabled = true; $("#aErr").textContent = "";
      try {
        const body = { email: $("#aEmail").value, password: $("#aPw").value };
        if (reg) body.name = $("#aName").value;
        await api("POST", reg ? "/api/auth/register" : "/api/auth/login", body);
        me = null;
        root.innerHTML = "";
        await render();
      } catch (err) {
        $("#aErr").textContent = err.error;
        AM.shake($(err.field === "email" ? "#aEmailBox" : "#aPwBox"));
      } finally { btn.disabled = false; }
    });
    $("#aEmail").focus();
  }

  // ═══════════ Оболочка ═══════════
  function renderShell() {
    const { parts } = route();
    const cur = (kind, id) => String(parts[0] === kind && String(parts[1]) === String(id));
    if (!$(".shell")) root.innerHTML = `<div class="shell"><aside class="side" id="side"></aside><div class="main" id="main"></div></div>`;
    $("#side").innerHTML = `
      <div><h4>Серверы</h4><div class="side-list">
        ${servers.map((s) => { const [, k] = statusOf(s); return `<a class="side-item" href="#/servers/${s.id}" aria-current="${cur("servers", s.id)}">
          <span class="led ${ledClass(k)}"></span>${esc(s.name)}<small>${esc(s.plan.name)}</small></a>`; }).join("")}
        <a class="side-item" href="#/order" aria-current="${parts[0] === "order"}"><svg class="icon"><use href="#i-plus"/></svg>Новый сервер</a>
      </div></div>
      <div><h4>Домены</h4><div class="side-list">
        ${domains.map((d) => `<a class="side-item" href="#/domains/${d.id}" aria-current="${cur("domains", d.id)}">
          <span class="led on" style="background:var(--accent)"></span>${esc(d.name)}</a>`).join("")}
        <a class="side-item" href="#/domains/new" aria-current="${cur("domains", "new")}"><svg class="icon"><use href="#i-plus"/></svg>Добавить домен</a>
      </div></div>
      <div><h4>Аккаунт</h4><div class="side-list">
        <a class="side-item" href="#/billing" aria-current="${parts[0] === "billing"}"><svg class="icon"><use href="#i-wallet"/></svg>Баланс<small>${money(me.balance)}</small></a>
        <a class="side-item" href="#/profile" aria-current="${parts[0] === "profile"}"><svg class="icon"><use href="#i-user"/></svg>Профиль</a>
        ${me.is_admin ? `<a class="side-item" href="#/admin" aria-current="${parts[0] === "admin"}"><svg class="icon"><use href="#i-shield"/></svg>Админка</a>` : ""}
      </div></div>
      <div class="balance"><span>${esc(me.email)}</span><b class="mono">${money(me.balance)}</b><span>на балансе</span></div>`;
  }

  function statusPill(s, id = "") {
    const [text, k] = statusOf(s);
    return `<span class="status ${k}" ${id ? `id="${id}"` : ""}><span class="led ${ledClass(k)}"></span><span>${esc(text)}</span></span>`;
  }

  // ═══════════ Список серверов ═══════════
  function viewServers() {
    const main = $("#main");
    if (!servers.length) {
      main.innerHTML = `<div class="view"><div class="page-head"><div><h2>Серверы</h2><p>Здесь появятся ваши VPS.</p></div></div>
        <div class="empty"><b>У вас пока нет серверов</b><span>Выберите тариф, локацию и ОС — сервер будет готов примерно через минуту.</span>
        <a class="btn btn-primary" href="#/order">Создать сервер</a></div></div>`;
      return;
    }
    main.innerHTML = `<div class="view">
      <div class="page-head"><div><h2>Серверы</h2><p>${servers.length} шт. · ${money(servers.reduce((a, s) => a + s.price, 0))} в месяц</p></div>
        <a class="btn btn-primary" href="#/order"><svg class="icon"><use href="#i-plus"/></svg>Новый сервер</a></div>
      <div class="card table-scroll"><table class="table"><thead><tr><th>Имя</th><th>Статус</th><th>IPv4</th><th>Тариф</th><th>Локация</th><th>Оплачен до</th></tr></thead><tbody>
      ${servers.map((s) => `<tr data-href="#/servers/${s.id}" style="cursor:pointer">
        <td><b>${esc(s.name)}</b></td><td>${statusPill(s)}</td><td class="mono">${esc(s.ipv4 || "—")}</td>
        <td>${esc(s.plan.name)}</td><td>${esc(s.location.name)}</td><td class="mono">${AM.date(s.paid_until)}</td></tr>`).join("")}
      </tbody></table></div></div>`;
    $$("tr[data-href]", main).forEach((tr) => tr.addEventListener("click", () => { location.hash = tr.dataset.href; }));
    if (servers.some(transitional)) timers.push(setInterval(render, 5000));
  }

  // ═══════════ Заказ сервера ═══════════
  function viewOrder(q) {
    const c = AM.catalog;
    const plan0 = c.plans.find((p) => p.id === q.get("plan")) || c.plans.find((p) => p.featured) || c.plans[0];
    let n = servers.length + 1, name;
    do { name = `server-${String(n++).padStart(2, "0")}`; } while (servers.some((s) => s.name === name));
    const main = $("#main");
    const choice = (group, value, checked, inner) =>
      `<label class="choice"><input type="radio" name="${group}" value="${esc(value)}" ${checked ? "checked" : ""}>${inner}</label>`;
    main.innerHTML = `<div class="view">
      <div class="page-head"><div><h2>Новый сервер</h2><p>Оплата за месяц спишется с баланса сразу после создания.</p></div></div>
      <form class="order-grid" id="orderForm" novalidate>
        <div style="display:grid;gap:22px;min-width:0">
          <div style="display:grid;gap:10px"><span class="step-title">Тариф</span><div class="choices">
            ${c.plans.map((p) => choice("plan", p.id, p.id === plan0.id, `<b>${esc(p.name)}</b><span class="mono">${money(p.price_month)} / мес.</span>
              <span>${p.cpu} vCPU · ${p.ram_gb} ГБ RAM · ${p.disk_gb} ГБ NVMe</span>`)).join("")}</div></div>
          <div style="display:grid;gap:10px"><span class="step-title">Локация</span><div class="choices">
            ${c.locations.map((l, i) => choice("location", l.id, i === 0, `<b>${esc(l.name)}</b><span>${esc(l.country)}</span>`)).join("")}</div></div>
          <div style="display:grid;gap:10px"><span class="step-title">Операционная система</span><div class="choices">
            ${c.images.map((im, i) => choice("image", im.id, i === 0, `<b>${esc(im.name)}</b><span class="mono">${esc(im.id)}</span>`)).join("")}</div></div>
          <div style="display:grid;gap:14px" class="card">
            <span class="step-title">Имя и доступ</span>
            <div class="field"><label for="oName">Имя сервера</label><div class="input" id="oNameBox"><input id="oName" value="${esc(name)}" maxlength="63" spellcheck="false"></div>
              <span class="hint">Латиница, цифры и дефис, например web-01</span></div>
            <div class="field"><label for="oPw">Root‑пароль <span style="color:var(--muted);font-weight:500">(можно оставить пустым)</span></label>
              <div class="input" id="oPwBox"><input id="oPw" type="password" autocomplete="new-password" spellcheck="false">
                <button class="icon-btn" type="button" id="oShow" aria-label="Показать пароль"><svg class="icon"><use href="#i-eye"/></svg></button>
                <button class="icon-btn" type="button" id="oGen" aria-label="Сгенерировать пароль"><svg class="icon"><use href="#i-dice"/></svg></button></div>
              <span class="hint">Пусто — сгенерируем сами и покажем один раз. Свой пароль: от 12 символов, буквы разного регистра, цифры и символы.</span></div>
          </div>
        </div>
        <aside class="card summary">
          <span class="step-title">Итого</span>
          <div id="sum"></div>
          <div class="total"><span>в месяц</span><b class="mono" id="sumPrice"></b></div>
          <div id="sumBalance" style="font-size:13px"></div>
          <div class="form-error" id="oErr"></div>
          <button class="btn btn-primary" type="submit" id="oSubmit">Создать сервер</button>
        </aside>
      </form></div>`;
    const form = $("#orderForm");
    const val = (n) => ($(`input[name=${n}]:checked`, form) || {}).value;
    function summary() {
      const p = c.plans.find((x) => x.id === val("plan")), l = c.locations.find((x) => x.id === val("location")), im = c.images.find((x) => x.id === val("image"));
      $("#sum").innerHTML = `<div class="row-line"><span>Тариф</span><b>${esc(p.name)}</b></div>
        <div class="row-line"><span>Ресурсы</span><b class="mono">${p.cpu} / ${p.ram_gb} ГБ / ${p.disk_gb} ГБ</b></div>
        <div class="row-line"><span>Локация</span><b>${esc(l.name)}</b></div><div class="row-line"><span>ОС</span><b>${esc(im.name)}</b></div>`;
      $("#sumPrice").textContent = money(p.price_month);
      const enough = me.balance >= p.price_month;
      $("#sumBalance").innerHTML = enough ? `<span style="color:var(--muted)">На балансе ${money(me.balance)}</span>`
        : `<div class="banner" style="padding:10px 12px"><span>Не хватает ${money(p.price_month - me.balance)}</span><a class="btn btn-sm" href="#/billing">Пополнить</a></div>`;
      $("#oSubmit").disabled = !enough;
    }
    form.addEventListener("change", summary);
    summary();
    $("#oShow").addEventListener("click", () => { const i = $("#oPw"); i.type = i.type === "password" ? "text" : "password"; });
    $("#oGen").addEventListener("click", () => { $("#oPw").type = "text"; $("#oPw").value = genPassword(); });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = $("#oSubmit");
      btn.disabled = true; btn.textContent = "Создаём…"; $("#oErr").textContent = "";
      try {
        const res = await api("POST", "/api/servers", {
          plan: val("plan"), location: val("location"), image: val("image"),
          name: $("#oName").value, root_password: $("#oPw").value || null,
        });
        AM.toast(`Сервер ${res.server.name} создаётся`);
        location.hash = `#/servers/${res.server.id}`;
        if (res.root_password) showSecret("Root‑пароль сервера", `Логин root, адрес появится через минуту на странице сервера.`, res.root_password);
      } catch (err) {
        $("#oErr").textContent = err.error;
        AM.shake($(err.field === "name" ? "#oNameBox" : err.field === "root_password" ? "#oPwBox" : "#oSubmit"));
        btn.disabled = false; btn.textContent = "Создать сервер";
      }
    });
  }

  function genPassword() {
    const sets = ["abcdefghijkmnopqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789", "!@#$%^&*-_=+"];
    const all = sets.join(""), buf = new Uint32Array(40); crypto.getRandomValues(buf);
    const out = sets.map((s, i) => s[buf[i] % s.length]);
    for (let i = 4; i < 20; i++) out.push(all[buf[i] % all.length]);
    return out.map((c, i) => [buf[20 + i], c]).sort((a, b) => a[0] - b[0]).map((x) => x[1]).join("");
  }

  // ═══════════ Страница сервера ═══════════
  async function viewServer(id) {
    let s = (await api("GET", `/api/servers/${id}`)).server;
    let tab = memo.tab[id] || "stats";
    const main = $("#main");
    main.innerHTML = `<div class="view">
      <div class="srv-head" id="srvHead"></div>
      <div id="banners" style="display:grid;gap:10px"></div>
      <div class="tabs" role="tablist">
        <button role="tab" type="button" data-tab="stats">Аналитика</button>
        <button role="tab" type="button" data-tab="root">Root‑пароль</button>
        <button role="tab" type="button" data-tab="settings">Настройки</button>
        <span class="ink" aria-hidden="true"></span>
      </div>
      <div id="tabBody"></div></div>`;

    function paintHead() {
      const on = s.status === "running", off = s.status === "off";
      $("#srvHead").innerHTML = `
        <div class="srv-title">
          <h3>${esc(s.name)} ${statusPill(s)}</h3>
          <div class="meta">
            <span>IPv4 <span class="mono">${esc(s.ipv4 || "назначается…")}</span>
              ${s.ipv4 ? `<button class="copy" type="button" data-copy="${esc(s.ipv4)}" aria-label="Скопировать IP"><svg class="icon"><use href="#i-copy"/></svg></button>` : ""}</span>
            <span>${esc(s.image.name)}</span><span>${esc(s.location.name)}</span><span>${esc(s.plan.name)}</span>
          </div>
        </div>
        <div class="actions">
          ${s.ipv4 ? `<button class="btn btn-sm" type="button" data-copy="ssh root@${esc(s.ipv4)}"><svg class="icon"><use href="#i-term"/></svg>SSH</button>` : ""}
          <button class="btn btn-sm" type="button" id="bReboot" ${on && !s.suspended ? "" : "disabled"}><svg class="icon"><use href="#i-reboot"/></svg>Перезагрузить</button>
          ${off ? `<button class="btn btn-sm btn-primary" type="button" id="bStart" ${s.suspended ? "disabled" : ""}><svg class="icon"><use href="#i-power"/></svg>Включить</button>`
                : `<button class="btn btn-sm" type="button" id="bStop" ${on ? "" : "disabled"}><svg class="icon"><use href="#i-power"/></svg>Выключить</button>`}
        </div>`;
      $$("[data-copy]", $("#srvHead")).forEach((b) => b.addEventListener("click", () => AM.copy(b.dataset.copy, `Скопировано: ${b.dataset.copy}`)));
      $("#bReboot")?.addEventListener("click", () => power("reboot"));
      $("#bStart")?.addEventListener("click", () => power("start"));
      $("#bStop")?.addEventListener("click", () => modal({
        title: `Выключить ${s.name}?`,
        html: `<p>Сервер корректно завершит работу. Сайты и сервисы на нём станут недоступны, пока вы его не включите. Оплата продолжает списываться.</p>`,
        actions: [{ label: "Отмена" }, { label: "Выключить", kind: "btn-danger", onClick: () => power("stop") }],
      }));
      const b = [];
      if (s.suspended) b.push(`<div class="banner bad"><span>Сервер приостановлен: оплата закончилась ${AM.date(s.paid_until)}. Пополните баланс — сервер включится автоматически в течение 10 минут.</span><a class="btn btn-sm" href="#/billing">Пополнить</a></div>`);
      else if (s.paid_until - Date.now() / 1000 < 3 * 86400) b.push(`<div class="banner"><span>Оплачен до ${AM.date(s.paid_until)}. Продление спишется с баланса автоматически.</span><a class="btn btn-sm" href="#/billing">Баланс</a></div>`);
      if (s.password_state === "pending") b.push(`<div class="banner"><span>Устанавливаем ваш root‑пароль. Это займёт около минуты после загрузки сервера.</span></div>`);
      if (s.password_state.startsWith("failed")) b.push(`<div class="banner bad"><span>Не удалось установить root‑пароль при создании. Задайте его на вкладке «Root‑пароль».</span></div>`);
      $("#banners").innerHTML = b.join("");
    }

    async function power(action) {
      try {
        s = (await api("POST", `/api/servers/${id}/power`, { action })).server;
        AM.toast({ reboot: "Перезагрузка отправлена", start: "Сервер запускается", stop: "Сервер выключается" }[action], "busy");
        paintHead(); syncSide();
      } catch (e) { AM.toast(e.error, "bad"); }
    }

    function syncSide() {
      const item = $(`#side a[href="#/servers/${id}"] .led`);
      if (item) item.className = `led ${ledClass(statusOf(s)[1])}`;
    }

    function selectTab(t) {
      tab = t; memo.tab[id] = t;
      $$(".tabs button", main).forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === t)));
      requestAnimationFrame(() => {
        const on = $(".tabs button[aria-selected=true]", main), ink = $(".tabs .ink", main);
        if (on && ink) { ink.style.width = on.offsetWidth + "px"; ink.style.transform = `translateX(${on.offsetLeft}px)`; }
      });
      stopMetrics();
      const body = $("#tabBody");
      if (t === "stats") tabStats(body);
      else if (t === "root") tabRoot(body);
      else tabSettings(body);
    }
    $$(".tabs button", main).forEach((b) => b.addEventListener("click", () => selectTab(b.dataset.tab)));

    // Опрос статуса, пока сервер в переходном состоянии
    let lastStatus = s.status;
    timers.push(setInterval(async () => {
      if (!transitional(s) && s.password_state !== "pending") return;
      try { s = (await api("GET", `/api/servers/${id}`)).server; } catch (e) { return; }
      paintHead(); syncSide();
      if (s.status !== lastStatus) {
        if (s.status === "running" && lastStatus !== "running") AM.toast(`${s.name} работает`);
        if (s.status === "off") AM.toast(`${s.name} выключен`, "");
        lastStatus = s.status;
        if (tab === "stats") selectTab("stats");
      }
    }, 4000));

    // ── Аналитика ──
    let metricsTimer = null;
    const stopMetrics = () => { if (metricsTimer) { clearInterval(metricsTimer); metricsTimer = null; } };
    function tabStats(body) {
      if (s.status !== "running") {
        const msg = s.status === "creating" ? "Сервер создаётся. Графики появятся через пару минут после запуска."
          : s.status === "off" ? "Сервер выключен — графики появятся после включения." : "Сервер меняет состояние, подождите немного.";
        body.innerHTML = `<div class="offline view"><b>${esc(statusOf(s)[0])}</b><span>${msg}</span></div>`;
        return;
      }
      body.innerHTML = `<div class="view" style="gap:14px">
        <div class="kpis">
          <div class="kpi"><div class="k-top"><span>Процессор</span><em>${s.plan.cpu} vCPU</em></div><b id="kCpu">—</b><canvas id="sCpu"></canvas></div>
          <div class="kpi"><div class="k-top"><span>Память</span><em>RAM</em></div><b id="kRam">—</b><canvas id="sRam"></canvas></div>
          <div class="kpi"><div class="k-top"><span>Сеть</span><em>вход / выход</em></div><b id="kNet">—</b><canvas id="sNet"></canvas></div>
          <div class="kpi"><div class="k-top"><span>Диск</span><em>операций/с</em></div><b id="kIo">—</b><canvas id="sIo"></canvas></div>
        </div>
        <div class="card">
          <div class="card-head">
            <h4>Процессор и память <span class="live" id="liveTag"><span class="led on"></span>обновляется раз в минуту</span></h4>
            <div class="legend"><span><i style="background:var(--accent)"></i>CPU</span><span><i style="background:var(--series-2)"></i>RAM</span></div>
            <div class="ranges" id="ranges">${["1h", "24h", "7d"].map((r) => `<button type="button" data-r="${r}" aria-pressed="${r === memo.range}">${r.replace("h", "ч").replace("d", "д")}</button>`).join("")}</div>
          </div>
          <div class="chart-wrap"><canvas id="cpuChart"></canvas><div class="tip" id="cpuTip" style="opacity:0"></div></div>
        </div>
        <div class="card">
          <div class="card-head"><h4>Сеть</h4><div class="legend"><span><i style="background:var(--amber)"></i>Входящий</span><span><i style="background:var(--ok)"></i>Исходящий</span></div></div>
          <div class="chart-wrap"><canvas id="netChart" style="height:180px"></canvas><div class="tip" id="netTip" style="opacity:0"></div></div>
        </div>
        <div class="grid-2">
          <div class="card" id="resCard"></div>
          <div class="card" id="procCard"></div>
        </div></div>`;
      $$("#ranges button", body).forEach((b) => b.addEventListener("click", () => {
        memo.range = b.dataset.r;
        $$("#ranges button", body).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        $("#liveTag").hidden = memo.range !== "1h";
        load();
      }));
      $("#liveTag").hidden = memo.range !== "1h";
      let cpuChart, netChart;
      const xLabels = { "1h": ["−60 мин", "−45", "−30", "−15", "сейчас"], "24h": ["−24 ч", "−18", "−12", "−6", "сейчас"], "7d": ["−7 дн.", "−5", "−3", "−1", "сейчас"] };
      const spans = { "1h": 3600, "24h": 86400, "7d": 604800 };
      const pct = (v, tip) => `${v.toFixed(tip ? 1 : 0)}%`;
      async function load() {
        let m;
        try { m = await api("GET", `/api/servers/${id}/metrics?range=${memo.range}`); }
        catch (e) { AM.toast(e.error, "bad"); return; }
        if (!$("#cpuChart")) return;
        const end = Date.now() / 1000, start = end - spans[memo.range];
        const S = m.series, last = (a) => (a && a.length ? a[a.length - 1][1] : null);
        const sum = (a, b) => (a || []).map((p, i) => [p[0], p[1] + ((b || [])[i] ? b[i][1] : 0)]);
        const cpu = S.cpu || [], mem = S.mem || [];
        const cpuMax = Math.max(0, ...cpu.map((p) => p[1]));
        const cpuOpts = { series: [{ label: "CPU", color: AM.token("--accent"), data: cpu }, { label: "RAM", color: AM.token("--series-2"), data: mem }],
          start, end, yMax: cpuMax > 100 ? undefined : 100, yFmt: pct, tip: $("#cpuTip"), xLabels: xLabels[memo.range] };
        const netOpts = { series: [{ label: "Входящий", color: AM.token("--amber"), data: S.net_bps_in || [] }, { label: "Исходящий", color: AM.token("--ok"), data: S.net_bps_out || [] }],
          start, end, padL: 84, yFmt: (v) => AM.bits(v), tip: $("#netTip"), xLabels: xLabels[memo.range] };
        cpuChart ? cpuChart.update(cpuOpts) : (cpuChart = AM.charts.line($("#cpuChart"), cpuOpts));
        netChart ? netChart.update(netOpts) : (netChart = AM.charts.line($("#netChart"), netOpts));

        const a = m.agent;
        const setK = (sel, html) => { $(sel).innerHTML = html; };
        setK("#kCpu", last(cpu) == null ? "—" : `${last(cpu).toFixed(0)}<small>%</small>`);
        setK("#kRam", a ? `${AM.bytes(a.mem_used)}<small> / ${AM.bytes(a.mem_total)}</small>` : `<small>нет данных агента</small>`);
        setK("#kNet", last(S.net_bps_in) == null ? "—" : `${AM.bits(last(S.net_bps_in))}`);
        const io = sum(S.disk_iops_read, S.disk_iops_write);
        setK("#kIo", last(io) == null ? "—" : `${last(io).toFixed(0)}<small> IOPS</small>`);
        AM.charts.spark($("#sCpu"), cpu, AM.token("--accent"), 100);
        AM.charts.spark($("#sRam"), mem, AM.token("--series-2"), 100);
        AM.charts.spark($("#sNet"), S.net_bps_in || [], AM.token("--amber"));
        AM.charts.spark($("#sIo"), io, AM.token("--ok"));

        $("#resCard").innerHTML = `<div class="card-head"><h4>Ресурсы</h4></div>` + (a ? `
          <div class="row-line"><span>Диск</span><b class="mono">${AM.bytes(a.disk_used)} / ${AM.bytes(a.disk_total)}</b></div>
          <div class="bar" style="margin-bottom:16px"><i style="width:${(a.disk_used / a.disk_total * 100).toFixed(1)}%"></i></div>
          <div class="row-line"><span>Память</span><b class="mono">${AM.bytes(a.mem_used)} / ${AM.bytes(a.mem_total)}</b></div>
          <div class="bar" style="margin-bottom:16px"><i style="width:${(a.mem_used / a.mem_total * 100).toFixed(1)}%;background:var(--series-2)"></i></div>
          <div class="row-line"><span>Средняя нагрузка (1 мин)</span><b class="mono">${a.load1.toFixed(2)}</b></div>`
          : agentNote());
        $("#procCard").innerHTML = `<div class="card-head"><h4>Топ процессов</h4><span class="mono" style="font-size:12px;color:var(--muted)">${a ? "обновлено " + AM.dateTime(a.ts) : ""}</span></div>` +
          (a && a.procs.length ? `<table class="proc"><tbody>${a.procs.map((p) => `<tr><td>${esc(p.name)}</td><td>${p.cpu.toFixed(1)}% · ${AM.bytes(p.mem)}</td></tr>`).join("")}</tbody></table>`
            : `<p style="color:var(--muted);font-size:14px">${a ? "Данные появятся со следующим отчётом агента." : "Появится вместе с данными агента."}</p>`);
      }
      function agentNote() {
        return `<p style="color:var(--muted);font-size:14px">Память, диск и процессы присылает агент на сервере. Он ставится автоматически при создании и переустановке ОС и начинает отправлять данные через 1–2 минуты после загрузки.</p>`;
      }
      load();
      metricsTimer = setInterval(() => { if (memo.range === "1h") load(); }, 60000);
      timers.push(metricsTimer);
    }

    // ── Root-пароль ──
    function tabRoot(body) {
      body.innerHTML = `
        <div class="view pw-grid">
          <form class="card form" id="pwForm" novalidate>
            <div class="card-head" style="margin:0"><h4>Свой root‑пароль для ${esc(s.name)}</h4></div>
            <div class="field">
              <label for="pw1">Новый пароль</label>
              <div class="input" id="pw1Box">
                <input id="pw1" type="password" autocomplete="new-password" spellcheck="false">
                <button class="icon-btn" type="button" id="pwShow" aria-label="Показать пароль"><svg class="icon"><use href="#i-eye"/></svg></button>
                <button class="icon-btn" type="button" id="pwGen" aria-label="Сгенерировать пароль"><svg class="icon"><use href="#i-dice"/></svg></button>
                <button class="icon-btn" type="button" id="pwCopy" aria-label="Скопировать пароль"><svg class="icon"><use href="#i-copy"/></svg></button>
              </div>
              <div class="meter" id="meter"><i></i><i></i><i></i><i></i></div>
              <div class="meter-label"><span id="meterText" style="color:var(--muted)">Введите пароль</span><span class="mono" id="entropy" style="color:var(--muted)"></span></div>
            </div>
            <div class="field"><label for="pw2">Повторите пароль</label>
              <div class="input" id="pw2Box"><input id="pw2" type="password" autocomplete="new-password"></div>
              <span class="hint" id="matchHint">&nbsp;</span></div>
            <div class="field"><label for="acc">Пароль от личного кабинета</label>
              <div class="input" id="accBox"><input id="acc" type="password" autocomplete="current-password"></div>
              <span class="hint">Подтверждаем, что это вы.</span></div>
            <div class="form-error" id="pwErr"></div>
            <button class="btn btn-primary" type="submit" id="pwSubmit" disabled>Установить пароль</button>
          </form>
          <div style="display:grid;gap:12px">
            <div class="card"><div class="card-head"><h4>Требования</h4></div>
              <ul class="rules" id="rules">
                ${[["len", "Не короче 12 символов"], ["low", "Строчные буквы a–z"], ["up", "Заглавные буквы A–Z"], ["dig", "Цифры 0–9"], ["sym", "Символы !@#$%^&*"], ["lat", "Только латиница, без пробелов и кавычек"]]
                  .map(([k, t]) => `<li data-r="${k}"><span class="ck"><svg><use href="#i-check"/></svg></span>${t}</li>`).join("")}
              </ul></div>
            <div class="card" id="progressCard" hidden><div class="card-head"><h4>Применение</h4></div>
              <div class="stepper" id="stepper">
                ${[["Проверка доступа", "пароль кабинета и права на сервер"], ["Временный пароль", "сброс через API провайдера"], ["Установка вашего пароля", "по SSH, командой chpasswd"]]
                  .map(([a, b]) => `<div class="step"><span class="dot"><svg><use href="#i-check"/></svg></span><div><b>${a}</b><span>${b}</span></div></div>`).join("")}
              </div></div>
            <div class="card" style="display:grid;gap:10px">
              <h4 style="margin:0;font-size:14px">Не хотите придумывать?</h4>
              <p style="color:var(--muted);font-size:14px">Сервер сам сгенерирует случайный пароль, и мы покажем его один раз.</p>
              <button class="btn" type="button" id="pwRandom">Сгенерировать на сервере</button>
            </div>
            <div class="note"><svg class="icon"><use href="#i-shield"/></svg><span>Пароль не сохраняется в базе панели. Он уходит на сервер один раз, а в журнале остаётся только запись «пароль изменён» с датой и IP.</span></div>
          </div>
        </div>`;
      const pw1 = $("#pw1"), pw2 = $("#pw2"), acc = $("#acc");
      const allowed = /^[A-Za-z0-9!@#$%^&*()\-_=+[\]{}.,:;?~]*$/;
      const tests = { len: (p) => p.length >= 12, low: (p) => /[a-z]/.test(p), up: (p) => /[A-Z]/.test(p), dig: (p) => /\d/.test(p),
        sym: (p) => /[^A-Za-z0-9]/.test(p), lat: (p) => p.length > 0 && allowed.test(p) };
      const labels = [["Очень слабый", "--bad"], ["Слабый", "--bad"], ["Средний", "--warn"], ["Хороший", "--ok"], ["Отличный", "--ok"]];
      const running = s.status === "running" && !s.suspended;
      function check() {
        const p = pw1.value; let passed = 0;
        $$("#rules li").forEach((li) => { const ok = tests[li.dataset.r](p); li.classList.toggle("ok", ok); passed += ok; });
        let pool = 0; if (/[a-z]/.test(p)) pool += 26; if (/[A-Z]/.test(p)) pool += 26; if (/\d/.test(p)) pool += 10; if (/[^A-Za-z0-9]/.test(p)) pool += 32;
        const bits = p ? Math.round(p.length * Math.log2(pool || 1)) : 0;
        const score = !p ? -1 : bits < 40 ? 0 : bits < 56 ? 1 : bits < 72 ? 2 : bits < 96 ? 3 : 4;
        const segs = score < 0 ? 0 : Math.max(1, score), col = score >= 0 ? AM.token(labels[score][1]) : "";
        $$("#meter i").forEach((i, k) => { i.style.background = k < segs ? col : ""; i.classList.toggle("lit", k < segs); });
        $("#meterText").textContent = score < 0 ? "Введите пароль" : labels[score][0];
        $("#meterText").style.color = score < 0 ? "var(--muted)" : `var(${labels[score][1]})`;
        $("#entropy").textContent = p ? `≈ ${bits} бит` : "";
        const match = p && pw2.value === p;
        $("#matchHint").textContent = pw2.value ? (match ? "Пароли совпадают" : "Пароли не совпадают") : " ";
        $("#matchHint").style.color = pw2.value ? (match ? "var(--ok)" : "var(--bad)") : "";
        $("#pwSubmit").disabled = !(passed === 6 && match && acc.value && running);
      }
      [pw1, pw2, acc].forEach((i) => i.addEventListener("input", check));
      if (!running) $("#pwErr").textContent = "Сменить пароль можно только на включённом сервере.";
      $("#pwShow").addEventListener("click", () => { const t = pw1.type === "password" ? "text" : "password"; pw1.type = t; pw2.type = t; });
      $("#pwCopy").addEventListener("click", () => { if (pw1.value) AM.copy(pw1.value, "Пароль скопирован"); });
      $("#pwGen").addEventListener("click", () => {
        const pw = genPassword(); pw1.type = pw2.type = "text";
        let k = 0;
        const typer = () => { k += 2; pw1.value = pw.slice(0, k); check(); if (k < pw.length && !AM.reduced) requestAnimationFrame(typer); else { pw1.value = pw2.value = pw; check(); } };
        typer();
      });
      $("#pwRandom").addEventListener("click", async () => {
        if (!running) return AM.toast("Сервер должен быть включён", "busy");
        const ok = await confirmAccount({ title: "Сгенерировать новый root‑пароль?", text: "Текущий root‑пароль перестанет работать. Открытые SSH‑сессии останутся активны.", okLabel: "Сгенерировать" });
        if (!ok) return;
        try {
          const r = await api("POST", `/api/servers/${id}/password`, { mode: "generate", account_password: ok.account_password });
          showSecret("Новый root‑пароль", `Сервер ${s.name}, логин root.`, r.password);
        } catch (e) { AM.toast(e.error, "bad"); }
      });
      $("#pwForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        if ($("#pwSubmit").disabled) return;
        $("#pwSubmit").disabled = true; $("#pwErr").textContent = "";
        $("#progressCard").hidden = false;
        const steps = $$("#stepper .step");
        steps.forEach((st) => st.classList.remove("run", "done", "fail"));
        let cur = 0;
        const advance = () => { if (cur > 0) { steps[cur - 1].classList.remove("run"); steps[cur - 1].classList.add("done"); } if (cur < steps.length) steps[cur++].classList.add("run"); };
        advance();
        const t1 = setTimeout(advance, 700), t2 = setTimeout(advance, 2500);
        try {
          await api("POST", `/api/servers/${id}/password`, { mode: "custom", password: pw1.value, account_password: acc.value });
          clearTimeout(t1); clearTimeout(t2);
          while (cur < steps.length) advance();
          steps[steps.length - 1].classList.remove("run"); steps[steps.length - 1].classList.add("done");
          AM.toast(`Root‑пароль ${s.name} изменён`);
          pw1.value = pw2.value = acc.value = ""; pw1.type = pw2.type = "password"; check();
        } catch (err) {
          clearTimeout(t1); clearTimeout(t2);
          const failed = steps.find((st) => st.classList.contains("run")) || steps[0];
          failed.classList.remove("run"); failed.classList.add("fail");
          $("#pwErr").textContent = err.error;
          AM.shake($(err.field === "account_password" ? "#accBox" : "#pw1Box"));
          check();
        }
      });
      check();
    }

    // ── Настройки ──
    function tabSettings(body) {
      const c = AM.catalog;
      body.innerHTML = `<div class="view grid-2" style="align-items:start">
        <div class="card"><div class="card-head"><h4>О сервере</h4></div><dl class="kv">
          <dt>IPv4</dt><dd>${esc(s.ipv4 || "—")}</dd><dt>IPv6</dt><dd>${esc(s.ipv6 || "—")}</dd>
          <dt>ОС</dt><dd>${esc(s.image.name)}</dd><dt>Тариф</dt><dd>${esc(s.plan.name)} · ${s.plan.cpu} vCPU / ${s.plan.ram_gb} ГБ / ${s.plan.disk_gb} ГБ</dd>
          <dt>Локация</dt><dd>${esc(s.location.name)}</dd><dt>Создан</dt><dd>${AM.date(s.created_at)}</dd>
          <dt>Оплачен до</dt><dd>${AM.date(s.paid_until)}</dd><dt>Цена</dt><dd>${money(s.price)} / мес.</dd>
          <dt>Агент</dt><dd>${s.agent ? "присылает данные" : "нет данных"}</dd></dl></div>
        <div style="display:grid;gap:12px">
          <div class="card" style="display:grid;gap:12px"><h4 style="margin:0;font-size:14px">Переустановить ОС</h4>
            <p style="color:var(--muted);font-size:14px">Все данные на диске будут удалены. IP‑адреса сохранятся. Новый root‑пароль покажем один раз.</p>
            <div class="input"><select id="rbImage" aria-label="Новая ОС">${c.images.map((im) => `<option value="${esc(im.id)}" ${im.id === s.image.id ? "selected" : ""}>${esc(im.name)}</option>`).join("")}</select></div>
            <button class="btn" type="button" id="rbBtn" ${s.suspended ? "disabled" : ""}>Переустановить</button></div>
          <div class="card" style="display:grid;gap:12px;border-color:color-mix(in srgb, var(--bad) 35%, var(--line))"><h4 style="margin:0;font-size:14px">Удалить сервер</h4>
            <p style="color:var(--muted);font-size:14px">Сервер и все данные будут удалены без возможности восстановления. Неиспользованные дни не возвращаются.</p>
            <button class="btn btn-danger" type="button" id="delBtn">Удалить сервер</button></div>
        </div></div>`;
      $("#rbBtn").addEventListener("click", async () => {
        const image = $("#rbImage").value;
        const ok = await confirmAccount({ title: `Переустановить ${s.name}?`, text: `Диск будет полностью очищен и установлена ${esc(c.images.find((i) => i.id === image).name)}.`, okLabel: "Переустановить", danger: true });
        if (!ok) return;
        try {
          const r = await api("POST", `/api/servers/${id}/rebuild`, { image, account_password: ok.account_password });
          s = (await api("GET", `/api/servers/${id}`)).server; paintHead(); selectTab("settings");
          if (r.root_password) showSecret("Root‑пароль после переустановки", `Сервер ${s.name}, логин root.`, r.root_password);
        } catch (e) { AM.toast(e.error, "bad"); }
      });
      $("#delBtn").addEventListener("click", async () => {
        const ok = await confirmAccount({
          title: `Удалить ${s.name}?`, text: "Это действие нельзя отменить.", okLabel: "Удалить навсегда", danger: true,
          extraHtml: `<div class="field"><label for="delName">Введите имя сервера: <b class="mono">${esc(s.name)}</b></label><div class="input" id="delNameBox"><input id="delName" autocomplete="off"></div></div>`,
          collect: (m) => ($("#delName", m).value.trim() === s.name ? {} : (AM.shake($("#delNameBox", m)), false)),
        });
        if (!ok) return;
        try {
          await api("POST", `/api/servers/${id}/delete`, { account_password: ok.account_password });
          AM.toast(`Сервер ${s.name} удалён`, "");
          location.hash = "#/servers";
        } catch (e) { AM.toast(e.error, "bad"); }
      });
    }

    paintHead();
    selectTab(tab);
  }

  // ═══════════ Домены ═══════════
  function viewDomains() {
    const main = $("#main");
    main.innerHTML = `<div class="view">
      <div class="page-head"><div><h2>Домены</h2><p>Регистрация и DNS‑записи.</p></div><a class="btn btn-primary" href="#/domains/new"><svg class="icon"><use href="#i-plus"/></svg>Добавить домен</a></div>
      ${domains.length ? `<div class="card table-scroll"><table class="table"><thead><tr><th>Домен</th><th>Тип</th><th>Записей</th><th>Оплачен до</th></tr></thead><tbody>
        ${domains.map((d) => `<tr data-href="#/domains/${d.id}" style="cursor:pointer"><td><b class="mono">${esc(d.name)}</b></td>
          <td>${d.kind === "registered" ? `<span class="tag tag-ok">Зарегистрирован у нас</span>` : `<span class="tag tag-bad">Внешний</span>`}</td>
          <td class="mono">${d.records}</td><td class="mono">${d.kind === "registered" ? AM.date(d.expires_at) : "—"}</td></tr>`).join("")}
        </tbody></table></div>`
        : `<div class="empty"><b>Доменов пока нет</b><span>Зарегистрируйте новый или добавьте существующий, чтобы управлять DNS.</span><a class="btn btn-primary" href="#/domains/new">Добавить домен</a></div>`}
    </div>`;
    $$("tr[data-href]", main).forEach((tr) => tr.addEventListener("click", () => { location.hash = tr.dataset.href; }));
  }

  function viewDomainNew(q) {
    const main = $("#main");
    const demo = AM.config.registrar === "demo";
    main.innerHTML = `<div class="view">
      <div class="page-head"><div><h2>Добавить домен</h2><p>Новый домен или тот, что уже есть у другого регистратора.</p></div></div>
      <div class="grid-2" style="align-items:start">
        <div class="card" style="display:grid;gap:14px">
          <h4 style="margin:0;font-size:15px">Зарегистрировать новый</h4>
          ${demo ? `<div class="banner"><span>Регистрация в демо‑режиме: домен появится в кабинете, но у реестра не регистрируется. Нужен договор с регистратором.</span></div>` : ""}
          <form class="search-row" id="buyForm"><label class="search-field" for="buyInput" style="height:46px">
            <svg class="icon" style="color:var(--muted)"><use href="#i-search"/></svg>
            <input id="buyInput" placeholder="mysite" autocomplete="off" spellcheck="false" aria-label="Имя домена"></label>
            <button class="btn btn-primary" type="submit" style="height:46px">Проверить</button></form>
          <div class="results" id="buyResults"></div>
        </div>
        <form class="card" style="display:grid;gap:14px" id="extForm" novalidate>
          <h4 style="margin:0;font-size:15px">У меня уже есть домен</h4>
          <p style="color:var(--muted);font-size:14px">Бесплатно. Мы создадим DNS‑зону, а вы пропишете наши неймсерверы у своего регистратора:</p>
          <div class="kv" style="grid-template-columns:1fr">${AM.config.nameservers.map((n) => `<dd>${esc(n)}</dd>`).join("")}</div>
          <div class="field"><label for="extInput">Домен</label><div class="input" id="extBox"><input id="extInput" placeholder="example.com" autocomplete="off" spellcheck="false"></div>
            <div class="form-error" id="extErr"></div></div>
          <button class="btn" type="submit">Добавить домен</button>
        </form>
      </div></div>`;
    async function search(e) {
      e && e.preventDefault();
      const name = $("#buyInput").value.trim();
      if (!name) return AM.shake($("#buyInput").parentElement);
      const box = $("#buyResults");
      box.innerHTML = `<div class="result loading"></div><div class="result loading"></div>`;
      try {
        const { results } = await api("GET", `/api/domains/check?name=${encodeURIComponent(name)}`);
        box.innerHTML = "";
        results.forEach((r, i) => {
          const row = document.createElement("div");
          row.className = `result ${r.available ? "free" : "taken"}`;
          row.style.animationDelay = `${i * 60}ms`;
          row.innerHTML = `<span class="dn">${esc(r.domain)}</span><span class="price">${r.available ? `${money(r.price)}/год` : "занят"}</span>
            ${r.available ? `<button class="btn btn-sm" type="button">Купить</button>` : `<span class="tag tag-bad">Занят</span>`}`;
          if (r.available) $("button", row).addEventListener("click", () => modal({
            title: `Зарегистрировать ${r.domain}?`,
            html: `<p>С баланса спишется ${money(r.price)} за 1 год. Продление — автоматически, за 7 дней до окончания.</p>`,
            actions: [{ label: "Отмена" }, {
              label: `Купить за ${money(r.price)}`, kind: "btn-primary", onClick: async () => {
                try {
                  const d = (await api("POST", "/api/domains", { domain: r.domain, purchase: true })).domain;
                  AM.toast(`${d.name} зарегистрирован`); location.hash = `#/domains/${d.id}`;
                } catch (err) {
                  AM.toast(err.error, "bad");
                  if (err.status === 402) location.hash = "#/billing";
                  if (err.field === "profile") location.hash = `#/profile?need=domain&next=${encodeURIComponent("#/domains/new?buy=" + r.domain)}`;
                }
              },
            }],
          }));
          box.appendChild(row);
        });
      } catch (err) { box.innerHTML = ""; AM.toast(err.error, "bad"); }
    }
    $("#buyForm").addEventListener("submit", search);
    $("#extForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      $("#extErr").textContent = "";
      try {
        const d = (await api("POST", "/api/domains", { domain: $("#extInput").value, purchase: false })).domain;
        AM.toast(`${d.name} добавлен`); location.hash = `#/domains/${d.id}`;
      } catch (err) { $("#extErr").textContent = err.error; AM.shake($("#extBox")); }
    });
    if (q.get("buy")) { $("#buyInput").value = q.get("buy"); search(); }
  }

  const RECORD_HINTS = {
    A: "203.0.113.24", AAAA: "2001:db8::1", CNAME: "example.com", MX: "10 mail.example.com",
    TXT: "v=spf1 -all", NS: "ns1.example.com", SRV: "10 5 5060 sip.example.com", CAA: '0 issue "letsencrypt.org"',
  };
  const TTLS = [[60, "1 мин"], [300, "5 мин"], [1800, "30 мин"], [3600, "1 час"], [21600, "6 часов"], [86400, "1 день"]];
  const ttlText = (t) => (TTLS.find((x) => x[0] === t) || [0, `${t} с`])[1];

  async function viewDomain(id) {
    const data = await api("GET", `/api/domains/${id}`);
    const d = data.domain;
    let records = data.records;
    const main = $("#main");
    const reg = d.kind === "registered";
    const withIp = servers.filter((s) => s.ipv4);
    main.innerHTML = `<div class="view">
      <div class="srv-head"><div class="srv-title">
        <h3><span class="mono">${esc(d.name)}</span> <span class="status on" id="syncStatus"><span class="led on"></span><span>DNS опубликован</span></span></h3>
        <div class="meta"><span>${reg ? "Зарегистрирован у нас" : "Домен у другого регистратора"}</span></div></div></div>
      ${d.status === "expired" ? `<div class="banner bad"><span>Срок регистрации истёк ${AM.date(d.expires_at)}.</span></div>` : ""}
      <div class="dns-head">
        <div class="card"><span>${reg ? "Оплачен до" : "Регистрация"}</span><b>${reg ? AM.date(d.expires_at) : "у вашего регистратора"}</b></div>
        <div class="card"><span>Неймсерверы ${reg ? (d.custom_ns ? "— свои" : "— наши") : "— пропишите у регистратора"}</span><b>${d.nameservers.map(esc).join("<br>")}</b>
          <div style="display:flex;gap:14px">
          <button class="btn btn-sm btn-ghost" type="button" id="nsCopy" style="justify-self:start;padding:0;height:auto;border:0"><svg class="icon"><use href="#i-copy"/></svg>Скопировать</button>
          ${reg ? `<button class="btn btn-sm btn-ghost" type="button" id="nsEdit" style="padding:0;height:auto;border:0">Изменить</button>` : ""}</div></div>
        ${reg ? `<div class="card" style="display:flex;align-items:center;justify-content:space-between;gap:12px"><div style="display:grid;gap:4px"><span>Автопродление</span><b id="renewText">${d.auto_renew ? "Включено" : "Выключено"}</b></div>
          <button class="toggle" type="button" role="switch" id="renew" aria-checked="${d.auto_renew}" aria-label="Автопродление"></button></div>`
          : `<div class="card"><span>Изменения DNS</span><b>Применяются за 1–60 минут</b></div>`}
      </div>
      <div class="card">
        <div class="card-head"><h4>DNS‑записи <span class="mono" style="color:var(--muted);font-weight:400" id="recCount"></span></h4>
          ${withIp.length ? `<div style="display:flex;gap:8px;flex-wrap:wrap"><div class="input" style="height:34px"><select id="pointSrv" aria-label="Сервер">${withIp.map((s) => `<option value="${s.id}">${esc(s.name)} · ${esc(s.ipv4)}</option>`).join("")}</select></div>
            <button class="btn btn-sm" type="button" id="pointBtn">Направить домен на сервер</button></div>` : ""}</div>
        <div class="table-scroll"><table class="dns"><thead><tr><th>Тип</th><th>Имя</th><th>Значение</th><th>TTL</th><th></th></tr></thead><tbody id="dnsBody"></tbody></table></div>
        <form class="add-row" id="dnsForm" novalidate>
          <div class="input"><select id="rType" aria-label="Тип записи">${Object.keys(RECORD_HINTS).map((t) => `<option>${t}</option>`).join("")}</select></div>
          <div class="input" id="rNameBox"><input id="rName" placeholder="@ или www" aria-label="Имя"></div>
          <div class="input wide" id="rValueBox"><input id="rValue" placeholder="${RECORD_HINTS.A}" aria-label="Значение" spellcheck="false"></div>
          <div class="input"><select id="rTtl" aria-label="TTL">${TTLS.map(([v, t]) => `<option value="${v}" ${v === 3600 ? "selected" : ""}>${t}</option>`).join("")}</select></div>
          <button class="btn btn-primary" type="submit" style="height:44px">Добавить</button>
        </form>
        <div class="err-text" id="dnsErr"></div>
      </div></div>`;

    $("#nsCopy").addEventListener("click", () => AM.copy(d.nameservers.join("\n"), "Неймсерверы скопированы"));
    $("#nsEdit")?.addEventListener("click", () => modal({
      title: `Неймсерверы ${d.name}`,
      html: `<p>Свои неймсерверы нужны, если DNS домена ведётся в другом месте, например в Cloudflare. Тогда DNS‑записи в нашей панели перестанут действовать.</p>
        <div class="field"><label for="nsList">По одному в строке, от 2 до 13</label>
        <textarea id="nsList" rows="4" style="width:100%;border-radius:10px;border:1px solid var(--line);background:var(--bg-2);padding:10px 12px;font-family:var(--f-mono);font-size:14px;color:var(--fg);resize:vertical">${esc(d.nameservers.join("\n"))}</textarea></div>`,
      actions: [
        { label: "Вернуть наши", onClick: async () => { try { await api("POST", `/api/domains/${id}/nameservers`, { nameservers: null }); AM.toast("Вернули наши неймсерверы"); render(); } catch (e) { AM.toast(e.error, "bad"); return false; } } },
        { label: "Сохранить", kind: "btn-primary", onClick: async (m) => {
          const list = $("#nsList", m).value.split(/[\s,]+/).filter(Boolean);
          try { await api("POST", `/api/domains/${id}/nameservers`, { nameservers: list }); AM.toast("Неймсерверы обновлены у регистратора"); render(); }
          catch (e) { AM.toast(e.error, "bad"); return false; }
        } },
      ],
    }));
    const tbody = $("#dnsBody");
    const count = () => { $("#recCount").textContent = `· ${records.length}`; };
    function addRow(r, isNew) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td><span class="rtype t-${esc(r.type)}">${esc(r.type)}</span></td><td>${esc(r.name)}</td><td class="val"></td><td>${ttlText(r.ttl)}</td>
        <td style="text-align:right"><button class="icon-btn" type="button" aria-label="Удалить запись"><svg class="icon"><use href="#i-trash"/></svg></button></td>`;
      $(".val", tr).textContent = r.value; $(".val", tr).title = r.value;
      if (isNew) tr.className = "new";
      $("button", tr).addEventListener("click", async () => {
        publishing(true);
        try {
          await api("DELETE", `/api/domains/${id}/records/${r.id}`);
          records = records.filter((x) => x.id !== r.id);
          tr.classList.add("gone");
          setTimeout(() => { tr.remove(); count(); }, AM.reduced ? 0 : 340);
          publishing(false, `Запись ${r.type} ${r.name} удалена`);
        } catch (e) { publishing(false); AM.toast(e.error, "bad"); }
      });
      tbody.appendChild(tr);
    }
    function publishing(on, msg) {
      const st = $("#syncStatus");
      st.className = on ? "status busy" : "status on";
      st.innerHTML = on ? `<span class="led busy"></span><span>Публикация…</span>` : `<span class="led on"></span><span>DNS опубликован</span>`;
      if (msg) AM.toast(msg);
    }
    if (!records.length) tbody.innerHTML = `<tr id="noRecords"><td colspan="5" style="font-family:var(--f-body);color:var(--muted)">Записей пока нет. Добавьте A‑запись, чтобы домен открывал ваш сервер.</td></tr>`;
    records.forEach((r) => addRow(r, false));
    count();

    async function add(rec, quiet) {
      const r = (await api("POST", `/api/domains/${id}/records`, rec)).record;
      $("#noRecords")?.remove();
      records.push(r); addRow(r, true); count();
      if (!quiet) AM.toast(`Запись ${r.type} ${r.name} → ${r.value} опубликована`);
      return r;
    }

    $("#rType").addEventListener("change", (e) => { $("#rValue").placeholder = RECORD_HINTS[e.target.value]; $("#rValue").focus(); });
    $("#dnsForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      $("#dnsErr").textContent = "";
      publishing(true);
      try {
        await add({ type: $("#rType").value, name: $("#rName").value.trim() || "@", value: $("#rValue").value, ttl: +$("#rTtl").value });
        $("#rName").value = ""; $("#rValue").value = "";
        publishing(false);
      } catch (err) {
        publishing(false);
        $("#dnsErr").textContent = err.error;
        AM.shake($(err.field === "name" ? "#rNameBox" : "#rValueBox"));
      }
    });
    $("#pointBtn")?.addEventListener("click", async () => {
      const s = servers.find((x) => x.id === +$("#pointSrv").value);
      publishing(true);
      const wanted = [{ type: "A", name: "@", value: s.ipv4 }, { type: "A", name: "www", value: s.ipv4 }];
      if (s.ipv6) wanted.push({ type: "AAAA", name: "@", value: s.ipv6 }, { type: "AAAA", name: "www", value: s.ipv6 });
      let added = 0;
      for (const w of wanted) {
        try { await add({ ...w, ttl: 3600 }, true); added++; } catch (e) { if (e.status !== 409) AM.toast(e.error, "bad"); }
      }
      publishing(false, added ? `${d.name} направлен на ${s.name}` : "Записи уже есть");
    });
    $("#renew")?.addEventListener("click", async (e) => {
      const btn = e.currentTarget, v = btn.getAttribute("aria-checked") !== "true";
      try {
        await api("POST", `/api/domains/${id}/auto-renew`, { value: v });
        btn.setAttribute("aria-checked", String(v)); $("#renewText").textContent = v ? "Включено" : "Выключено";
      } catch (err) { AM.toast(err.error, "bad"); }
    });
  }

  // ═══════════ Профиль ═══════════
  function viewProfile(q) {
    const main = $("#main");
    const p = me.profile;
    const field = (id, label, value, hint = "", attrs = "") => `<div class="field"><label for="pf-${id}">${label}</label>
      <div class="input" id="pf-${id}-box"><input id="pf-${id}" value="${esc(value)}" ${attrs}></div>${hint ? `<span class="hint">${hint}</span>` : ""}</div>`;
    main.innerHTML = `<div class="view">
      <div class="page-head"><div><h2>Профиль</h2><p>${esc(me.email)}${me.verified ? ` · <span class="tag tag-ok">аккаунт подтверждён</span>` : ""}</p></div></div>
      ${q.get("need") === "domain" ? `<div class="banner"><span>Чтобы зарегистрировать домен, заполните данные владельца. Их требует регистратор.</span></div>` : ""}
      <form class="card form" id="pfForm" novalidate style="max-width:720px">
        <div class="card-head" style="margin:0"><h4>Данные владельца доменов</h4></div>
        <p style="color:var(--muted);font-size:14px;margin:0">Указывайте настоящие данные: по правилам реестров домен с ложными данными могут отключить.</p>
        <div class="grid-2">
          ${field("name", "Имя и фамилия (латиницей)", p.name, "Как в паспорте, например Alijon Mahmadjonov", 'autocomplete="name"')}
          ${field("company", "Компания", p.company, "Необязательно", 'autocomplete="organization"')}
          ${field("phone", "Телефон", p.phone ? "+" + p.phone : "", "Код страны и номер через пробел: +992 900123456", 'autocomplete="tel" inputmode="tel"')}
          ${field("country", "Страна (код)", p.country, "Две буквы: TJ, UZ, KZ, RU", 'maxlength="2" autocomplete="country"')}
          ${field("city", "Город", p.city, "", 'autocomplete="address-level2"')}
          ${field("zipcode", "Индекс", p.zipcode, "", 'autocomplete="postal-code"')}
        </div>
        ${field("address", "Адрес", p.address, "Улица и дом", 'autocomplete="street-address"')}
        <div class="form-error" id="pfErr"></div>
        <button class="btn btn-primary" type="submit" style="justify-self:start">Сохранить</button>
      </form></div>`;
    $("#pfForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      $("#pfErr").textContent = "";
      const body = {};
      ["name", "company", "phone", "country", "city", "zipcode", "address"].forEach((f) => { body[f] = $(`#pf-${f}`).value; });
      try {
        me = await api("POST", "/api/profile", body);
        AM.toast("Профиль сохранён");
        if (q.get("next")) location.hash = q.get("next"); else render();
      } catch (err) {
        $("#pfErr").textContent = err.error;
        AM.shake($(`#pf-${err.field}-box`));
      }
    });
  }

  // ═══════════ Баланс ═══════════
  const REQ_STATUS = { pending: ["На проверке", "tag-warn"], approved: ["Зачислено", "tag-ok"], rejected: ["Отклонено", "tag-bad"] };

  async function viewBilling() {
    const b = await api("GET", "/api/billing");
    const main = $("#main");
    const days = b.monthly > 0 ? Math.floor(b.balance / b.monthly * 30) : null;
    const manual = b.payment_methods.length > 0;
    main.innerHTML = `<div class="view">
      <div class="page-head"><div><h2>Баланс</h2><p>Серверы продлеваются автоматически раз в месяц, домены — раз в год.</p></div></div>
      <div class="grid-2" style="align-items:start">
        <div class="card" style="display:grid;gap:8px">
          <span style="color:var(--muted);font-size:13px;font-weight:600">На балансе</span>
          <b style="font-family:var(--f-display);font-size:34px;font-weight:600" class="mono" id="balBig">${money(b.balance)}</b>
          <span style="color:var(--muted);font-size:14px">${b.monthly > 0 ? `Серверы: ${money(b.monthly)} в месяц · хватит примерно на ${days} дн.` : "Активных серверов нет"}</span>
        </div>
        ${manual ? `<form class="card form" id="reqForm" novalidate>
          <span style="color:var(--muted);font-size:13px;font-weight:600">Пополнить переводом</span>
          ${b.payment_instructions ? `<div class="note" style="white-space:pre-wrap;display:block">${esc(b.payment_instructions)}</div>` : ""}
          <div class="grid-2">
            <div class="field"><label for="rqAmount">Сумма, ${esc(AM.config.currency)}</label><div class="input" id="rqAmountBox"><input id="rqAmount" inputmode="decimal" value="25"></div></div>
            <div class="field"><label for="rqMethod">Способ</label><div class="input"><select id="rqMethod">${b.payment_methods.map((m) => `<option>${esc(m)}</option>`).join("")}</select></div></div>
          </div>
          <div class="field"><label for="rqRef">Номер или время перевода</label><div class="input" id="rqRefBox"><input id="rqRef" placeholder="Например: 12.11 в 14:05, с карты *1234"></div>
            <span class="hint">После перевода отправьте заявку — мы проверим платёж и зачислим деньги.</span></div>
          <div class="form-error" id="rqErr"></div>
          <button class="btn btn-primary" type="submit" style="justify-self:start">Я перевёл, отправить заявку</button>
        </form>` : ""}
        ${b.demo_payments ? `<form class="card" style="display:grid;gap:12px" id="topForm" novalidate>
          <span style="color:var(--muted);font-size:13px;font-weight:600">Демо‑пополнение</span>
          <div style="display:flex;gap:8px;flex-wrap:wrap">${[10, 25, 50, 100].map((v) => `<button class="btn btn-sm" type="button" data-amount="${v}">${money(v)}</button>`).join("")}</div>
          <div style="display:flex;gap:8px"><div class="input" style="flex:1"><input id="topAmount" inputmode="decimal" value="25" aria-label="Сумма"></div>
          <button class="btn" type="submit">Зачислить</button></div>
          <span class="hint" style="font-size:12px;color:var(--muted)">Только для проверки: деньги зачисляются без оплаты. Перед запуском продаж выключите DEMO_PAYMENTS.</span>
        </form>` : ""}
        ${!manual && !b.demo_payments ? `<div class="card"><div class="banner"><span>Чтобы пополнить баланс, напишите в поддержку.</span></div></div>` : ""}
      </div>
      ${b.requests.length ? `<div class="card table-scroll"><div class="card-head"><h4>Заявки на пополнение</h4></div>
        <table class="table"><thead><tr><th>Дата</th><th>Способ</th><th>Перевод</th><th>Статус</th><th style="text-align:right">Сумма</th></tr></thead><tbody>
        ${b.requests.map((r) => `<tr><td class="mono" style="white-space:nowrap">${AM.dateTime(r.created_at)}</td><td>${esc(r.method)}</td><td>${esc(r.reference)}${r.admin_note ? `<br><span style="color:var(--muted);font-size:13px">${esc(r.admin_note)}</span>` : ""}</td>
          <td><span class="tag ${REQ_STATUS[r.status][1]}">${REQ_STATUS[r.status][0]}</span></td><td class="num">${money(r.amount)}</td></tr>`).join("")}
        </tbody></table></div>` : ""}
      <div class="card table-scroll"><div class="card-head"><h4>История операций</h4></div>
        ${b.transactions.length ? `<table class="table"><thead><tr><th>Дата</th><th>Операция</th><th style="text-align:right">Сумма</th></tr></thead><tbody>
          ${b.transactions.map((t) => `<tr><td class="mono" style="white-space:nowrap">${AM.dateTime(t.created_at)}</td><td>${esc(t.description)}</td>
            <td class="num ${t.amount > 0 ? "plus" : "minus"}">${t.amount > 0 ? "+" : "−"}${money(Math.abs(t.amount))}</td></tr>`).join("")}
          </tbody></table>` : `<p style="color:var(--muted);font-size:14px">Операций пока нет.</p>`}
      </div></div>`;
    $$("[data-amount]", main).forEach((x) => x.addEventListener("click", () => { $("#topAmount").value = x.dataset.amount; }));
    $("#topForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const amount = parseFloat(($("#topAmount") || {}).value?.replace(",", "."));
      if (!(amount > 0)) return AM.shake($("#topAmount").parentElement);
      try {
        await api("POST", "/api/billing/topup", { amount });
        AM.toast(`Баланс пополнен на ${money(Math.min(amount, 500))}`);
        render();
      } catch (err) { AM.toast(err.error, "bad"); }
    });
    $("#reqForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      $("#rqErr").textContent = "";
      const amount = parseFloat($("#rqAmount").value.replace(",", "."));
      if (!(amount > 0)) return AM.shake($("#rqAmountBox"));
      try {
        await api("POST", "/api/billing/requests", { amount, method: $("#rqMethod").value, reference: $("#rqRef").value });
        AM.toast("Заявка отправлена. Зачислим после проверки платежа.");
        render();
      } catch (err) {
        $("#rqErr").textContent = err.error;
        AM.shake($(err.field === "reference" ? "#rqRefBox" : "#rqAmountBox"));
      }
    });
  }

  // ═══════════ Админка ═══════════
  const ADMIN_TABS = [["overview", "Готовность"], ["topups", "Пополнения"], ["prices", "Цены"], ["clients", "Клиенты"], ["log", "Журнал"]];

  async function viewAdmin(tab = "overview") {
    if (!ADMIN_TABS.some(([k]) => k === tab)) tab = "overview";
    const o = await api("GET", "/api/admin/overview");
    const main = $("#main");
    const t = o.totals;
    main.innerHTML = `<div class="view">
      <div class="page-head"><div><h2>Админка</h2><p>Всё, что нужно, чтобы продавать.</p></div></div>
      <div class="kpis">
        <div class="kpi"><span>Клиенты</span><b>${t.users}</b></div><div class="kpi"><span>Серверы</span><b>${t.servers}</b></div>
        <div class="kpi"><span>Домены</span><b>${t.domains}</b></div><div class="kpi"><span>Выручка в месяц</span><b>${money(t.mrr)}</b></div>
      </div>
      <div class="tabs" role="tablist">${ADMIN_TABS.map(([k, label]) => `<a role="tab" href="#/admin/${k}" aria-selected="${k === tab}" style="padding:10px 14px;font-weight:600;font-size:14px;text-decoration:none;color:${k === tab ? "var(--fg)" : "var(--muted)"};border-bottom:2px solid ${k === tab ? "var(--accent)" : "transparent"};margin-bottom:-1px">${label}${k === "topups" && t.pending_topups ? ` <span class="tag tag-warn">${t.pending_topups}</span>` : ""}</a>`).join("")}</div>
      <div id="adminBody"><div class="loading-line"></div></div></div>`;
    const body = $("#adminBody");
    if (tab === "overview") await adminOverview(body);
    else if (tab === "topups") await adminTopups(body);
    else if (tab === "prices") await adminPrices(body);
    else if (tab === "clients") adminClients(body, o.users);
    else adminLog(body, o.audit);
  }

  async function adminOverview(body) {
    const [r, prov] = await Promise.all([api("GET", "/api/admin/readiness"), api("GET", "/api/admin/provider").catch((e) => ({ error: e.error }))]);
    const done = r.checks.filter((c) => c.ok).length;
    body.innerHTML = `<div class="view" style="gap:14px">
      <div class="card">
        <div class="card-head"><h4>Готовность к продажам · ${done} из ${r.checks.length}</h4>
          ${r.ready ? `<span class="tag tag-ok">Можно продавать</span>` : `<span class="tag tag-warn">Есть что настроить</span>`}</div>
        <ul class="rules" style="gap:12px">
          ${r.checks.map((c) => `<li class="${c.ok ? "ok" : ""}" style="align-items:flex-start"><span class="ck" style="margin-top:2px;${!c.ok && c.required ? "border-color:var(--warn)" : ""}"><svg><use href="#i-check"/></svg></span>
            <span style="display:grid;gap:2px"><b style="color:var(--fg);font-size:14px">${esc(c.title)}${c.required ? "" : ` <span style="color:var(--muted);font-weight:500">· по желанию</span>`}</b>
            <span style="color:var(--muted);font-size:13px">${esc(c.detail)}</span></span></li>`).join("")}
        </ul>
        <p style="color:var(--muted);font-size:13px;margin:14px 0 0">Настройки меняются в файле .env на сервере, после изменения перезапустите панель. Подробно — в README.</p>
      </div>
      <div class="card table-scroll"><div class="card-head"><h4>Тарифы у Hetzner</h4></div>
        ${prov.error ? `<div class="banner bad"><span>${esc(prov.error)}</span></div>` : prov.note ? `<p style="color:var(--muted);font-size:14px">${esc(prov.note)}</p>` : `
        <table class="table"><thead><tr><th>Тариф</th><th>Тип Hetzner</th><th>Есть у Hetzner</th><th style="text-align:right">Наша цена</th><th style="text-align:right">Себестоимость (fsn1)</th></tr></thead><tbody>
          ${prov.plans.map((p) => `<tr><td>${esc(p.plan)}</td><td class="mono">${esc(p.server_type)}</td><td>${p.exists ? `<span class="tag tag-ok">да</span>` : `<span class="tag tag-warn">нет — смените тип во вкладке «Цены»</span>`}</td>
            <td class="num">${money(p.our_price)}</td><td class="num">${p.hetzner_price.fsn1 != null ? "€" + p.hetzner_price.fsn1.toFixed(2) : "—"}</td></tr>`).join("")}
        </tbody></table>`}
      </div></div>`;
  }

  async function adminTopups(body) {
    const { requests } = await api("GET", "/api/admin/topups?status=all");
    const pending = requests.filter((r) => r.status === "pending"), done = requests.filter((r) => r.status !== "pending");
    const row = (r, actions) => `<tr><td class="mono" style="white-space:nowrap">${AM.dateTime(r.created_at)}</td><td>${esc(r.email)}</td><td>${esc(r.method)}</td>
      <td>${esc(r.reference)}${r.admin_note ? `<br><span style="color:var(--muted);font-size:13px">${esc(r.admin_note)}</span>` : ""}</td><td class="num">${money(r.amount)}</td>
      <td style="text-align:right;white-space:nowrap">${actions ? `<button class="btn btn-sm btn-primary" type="button" data-approve="${r.id}">Зачислить</button>
        <button class="btn btn-sm" type="button" data-reject="${r.id}">Отклонить</button>` : `<span class="tag ${REQ_STATUS[r.status][1]}">${REQ_STATUS[r.status][0]}</span>`}</td></tr>`;
    const head = `<thead><tr><th>Дата</th><th>Клиент</th><th>Способ</th><th>Перевод</th><th style="text-align:right">Сумма</th><th></th></tr></thead>`;
    body.innerHTML = `<div class="view" style="gap:14px">
      <div class="card table-scroll"><div class="card-head"><h4>Ждут проверки</h4></div>
        ${pending.length ? `<table class="table">${head}<tbody>${pending.map((r) => row(r, true)).join("")}</tbody></table>`
          : `<p style="color:var(--muted);font-size:14px">Новых заявок нет. Когда клиент отправит заявку, придёт уведомление в Telegram.</p>`}</div>
      ${done.length ? `<div class="card table-scroll"><div class="card-head"><h4>Обработанные</h4></div><table class="table">${head}<tbody>${done.map((r) => row(r, false)).join("")}</tbody></table></div>` : ""}
    </div>`;
    const decide = (id, approve) => modal({
      title: approve ? "Зачислить платёж?" : "Отклонить заявку?",
      html: `<p>${approve ? "Сначала убедитесь, что деньги действительно пришли." : "Клиент получит письмо, что платёж не найден."}</p>
        <div class="field"><label for="dnNote">Комментарий для клиента</label><div class="input"><input id="dnNote" placeholder="${approve ? "Необязательно" : "Например: перевод не найден"}"></div></div>`,
      actions: [{ label: "Отмена" }, {
        label: approve ? "Зачислить" : "Отклонить", kind: approve ? "btn-primary" : "btn-danger", onClick: async (m) => {
          try { await api("POST", `/api/admin/topups/${id}`, { approve, note: $("#dnNote", m).value }); AM.toast(approve ? "Зачислено" : "Отклонено"); render(); }
          catch (e) { AM.toast(e.error, "bad"); return false; }
        },
      }],
    });
    $$("[data-approve]", body).forEach((b) => b.addEventListener("click", () => decide(+b.dataset.approve, true)));
    $$("[data-reject]", body).forEach((b) => b.addEventListener("click", () => decide(+b.dataset.reject, false)));
  }

  async function adminPrices(body) {
    const cat = await api("GET", "/api/admin/catalog");
    body.innerHTML = `<form class="view" id="priceForm" novalidate style="gap:14px">
      <div class="card table-scroll"><div class="card-head"><h4>Тарифы серверов</h4></div>
        <table class="table"><thead><tr><th>Продаётся</th><th>Тариф</th><th>Ресурсы</th><th>Тип Hetzner</th><th>Цена в месяц</th></tr></thead><tbody>
        ${cat.plans.map((p) => `<tr data-plan="${esc(p.id)}"><td><input type="checkbox" class="pl-on" ${p.enabled !== false ? "checked" : ""} aria-label="Продаётся"></td>
          <td><b>${esc(p.name)}</b></td><td style="color:var(--muted);font-size:13px">${p.cpu} vCPU · ${p.ram_gb} ГБ · ${p.disk_gb} ГБ</td>
          <td><div class="input" style="height:36px;width:110px"><input class="pl-type" value="${esc(p.server_type)}" aria-label="Тип Hetzner"></div></td>
          <td><div class="input" style="height:36px;width:110px"><input class="pl-price" inputmode="decimal" value="${p.price_month}" aria-label="Цена"></div></td></tr>`).join("")}
        </tbody></table></div>
      <div class="card table-scroll"><div class="card-head"><h4>Доменные зоны</h4><button class="btn btn-sm" type="button" id="addZone">Добавить зону</button></div>
        <table class="table"><thead><tr><th>Продаётся</th><th>Зона</th><th>Цена за год</th><th></th></tr></thead><tbody id="zoneRows">
        ${cat.tlds.map((t) => zoneRow(t)).join("")}
        </tbody></table>
        <p style="color:var(--muted);font-size:13px;margin:10px 0 0">Добавляйте только зоны, которые поддерживает ваш регистратор, и ставьте цену выше его закупочной.</p></div>
      <div class="form-error" id="prErr"></div>
      <button class="btn btn-primary" type="submit" style="justify-self:start">Сохранить цены</button>
    </form>`;
    function zoneRow(t) {
      return `<tr><td><input type="checkbox" class="z-on" ${t.enabled !== false ? "checked" : ""} aria-label="Продаётся"></td>
        <td><div class="input" style="height:36px;width:120px"><span style="color:var(--muted)">.</span><input class="z-zone" value="${esc(t.zone)}" aria-label="Зона"></div></td>
        <td><div class="input" style="height:36px;width:110px"><input class="z-price" inputmode="decimal" value="${t.price_year}" aria-label="Цена"></div></td>
        <td style="text-align:right"><button class="icon-btn z-del" type="button" aria-label="Удалить зону"><svg class="icon"><use href="#i-trash"/></svg></button></td></tr>`;
    }
    const wire = () => $$(".z-del", body).forEach((b) => { b.onclick = () => b.closest("tr").remove(); });
    wire();
    $("#addZone").addEventListener("click", () => { $("#zoneRows").insertAdjacentHTML("beforeend", zoneRow({ zone: "", price_year: 10, enabled: true })); wire(); $("#zoneRows tr:last-child .z-zone").focus(); });
    $("#priceForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      $("#prErr").textContent = "";
      const num = (v) => parseFloat(String(v).replace(",", "."));
      const plans = $$("tr[data-plan]", body).map((tr) => ({ id: tr.dataset.plan, enabled: $(".pl-on", tr).checked, server_type: $(".pl-type", tr).value.trim(), price_month: num($(".pl-price", tr).value) }));
      const tlds = $$("#zoneRows tr", body).map((tr) => ({ zone: $(".z-zone", tr).value.trim(), enabled: $(".z-on", tr).checked, price_year: num($(".z-price", tr).value) })).filter((z) => z.zone);
      try { await api("POST", "/api/admin/catalog", { plans, tlds }); AM.catalog = await api("GET", "/api/catalog"); AM.toast("Цены сохранены и уже на сайте"); }
      catch (err) { $("#prErr").textContent = err.error; }
    });
  }

  function adminClients(body, users) {
    body.innerHTML = `<div class="card table-scroll"><table class="table"><thead><tr><th>Email</th><th>Серверы</th><th>Домены</th><th>Подтверждён</th><th style="text-align:right">Баланс</th><th></th></tr></thead><tbody>
      ${users.map((u) => `<tr><td>${esc(u.email)} ${u.is_admin ? `<span class="tag tag-warn">админ</span>` : ""}<br><span style="color:var(--muted);font-size:12px">с ${AM.date(u.created_at)}</span></td>
        <td class="mono">${u.servers}</td><td class="mono">${u.domains}</td>
        <td><button class="toggle" type="button" role="switch" data-verify="${u.id}" aria-checked="${!!u.verified}" aria-label="Подтверждён"></button></td>
        <td class="num">${money(u.balance)}</td><td style="text-align:right"><button class="btn btn-sm" type="button" data-credit="${u.id}" data-email="${esc(u.email)}">Пополнить</button></td></tr>`).join("")}
      </tbody></table>
      <p style="color:var(--muted);font-size:13px;margin:10px 0 0">Неподтверждённые клиенты могут держать серверов: ${AM.config.new_user_server_limit}. Подтверждайте тех, кого проверили, — это защищает от спамеров, из‑за которых Hetzner может заблокировать весь ваш аккаунт.</p></div>`;
    $$("[data-verify]", body).forEach((b) => b.addEventListener("click", async () => {
      const v = b.getAttribute("aria-checked") !== "true";
      try { await api("POST", `/api/admin/users/${b.dataset.verify}/verify`, { value: v }); b.setAttribute("aria-checked", String(v)); }
      catch (e) { AM.toast(e.error, "bad"); }
    }));
    $$("[data-credit]", body).forEach((b) => b.addEventListener("click", () => modal({
      title: `Пополнить баланс ${b.dataset.email}`,
      html: `<div class="field"><label for="crAmount">Сумма</label><div class="input"><input id="crAmount" inputmode="decimal" value="10"></div></div>
        <div class="field"><label for="crNote">Комментарий</label><div class="input"><input id="crNote" placeholder="Оплата наличными"></div></div>`,
      actions: [{ label: "Отмена" }, {
        label: "Зачислить", kind: "btn-primary", onClick: async (m) => {
          const amount = parseFloat($("#crAmount", m).value.replace(",", "."));
          if (!(amount > 0)) { AM.shake($("#crAmount", m).parentElement); return false; }
          try { await api("POST", `/api/admin/users/${b.dataset.credit}/credit`, { amount, note: $("#crNote", m).value }); AM.toast("Зачислено"); render(); }
          catch (e) { AM.toast(e.error, "bad"); return false; }
        },
      }],
    })));
  }

  function adminLog(body, audit) {
    body.innerHTML = `<div class="card table-scroll"><table class="table"><thead><tr><th>Когда</th><th>Кто</th><th>Действие</th><th>Объект</th><th>IP</th></tr></thead><tbody>
      ${audit.map((a) => `<tr><td class="mono" style="white-space:nowrap">${AM.dateTime(a.created_at)}</td><td>${esc(a.email || "система")}</td><td class="mono">${esc(a.action)}</td><td class="mono">${esc(a.target)}</td><td class="mono">${esc(a.ip)}</td></tr>`).join("")}
    </tbody></table></div>`;
  }

  render();
})();
