/* Главная страница: глобус, поиск доменов, тарифы из каталога. */
(async function () {
  "use strict";
  const { $, $$, esc, api, money } = AM;
  let catalog;
  try { ({ catalog } = await AM.boot()); } catch (e) { AM.toast(e.error || "Сервер недоступен", "bad"); return; }

  // Кнопка кабинета: если уже вошли — «Мои серверы»
  api("GET", "/api/me").then(() => { $("#cabinetBtn").textContent = "Мои серверы"; }, () => {});

  // ── Глобус ──
  const sides = ["right", "left", "top", "bottom"];
  const dcs = catalog.locations.map((l, i) => ({ name: l.name, note: l.country, lat: l.lat, lon: l.lon, side: sides[i % sides.length] }));
  const links = [];
  for (let i = 0; i < dcs.length; i++) for (let j = i + 1; j < dcs.length; j++) links.push([i, j]);
  $("#dcCount").textContent = dcs.length;
  if (window.initGlobe && window.initGlobe($("#globeBox"), $("#globeLabels"), dcs, links)) $("#globeFallback").hidden = true;

  // ── Домены ──
  $("#tldChips").innerHTML = catalog.tlds.map((t) => `<span class="tld-chip"><b>.${esc(t.zone)}</b> ${money(t.price_year)}</span>`).join("");
  async function search(e) {
    e && e.preventDefault();
    const input = $("#domainInput");
    const name = input.value.trim();
    const box = $("#results");
    if (!name) { AM.shake(input.parentElement); input.focus(); return; }
    box.innerHTML = catalog.tlds.slice(0, 4).map(() => `<div class="result loading"></div>`).join("");
    try {
      const { results } = await api("GET", `/api/domains/check?name=${encodeURIComponent(name)}`);
      box.innerHTML = "";
      results.forEach((r, i) => {
        const row = document.createElement("div");
        row.className = `result ${r.available ? "free" : "taken"}`;
        row.style.animationDelay = `${i * 70}ms`;
        const [label, ...zone] = r.domain.split(".");
        row.innerHTML = `
          <span class="dn">${esc(label)}<b>.${esc(zone.join("."))}</b></span>
          <span class="price">${r.available ? `${money(r.price)}/год` : "занят"}</span>
          ${r.available ? `<a class="btn btn-sm" href="/app#/domains/new?buy=${encodeURIComponent(r.domain)}">Зарегистрировать</a>`
                        : `<span class="tag tag-bad">Занят</span>`}`;
        box.appendChild(row);
      });
    } catch (err) {
      box.innerHTML = "";
      AM.toast(err.error, "bad");
      AM.shake(input.parentElement);
    }
  }
  $("#domainForm").addEventListener("submit", search);

  // ── Тарифы ──
  $("#plans").innerHTML = catalog.plans.map((p) => `
    <article class="plan ${p.featured ? "featured" : ""}">
      ${p.featured ? `<span class="badge">Чаще берут</span>` : ""}
      <h3>${esc(p.name)}</h3>
      <div class="cost"><b>${money(p.price_month)}</b><span>/ мес.</span></div>
      <ul class="specs">
        <li><span>vCPU</span><b>${p.cpu}</b></li>
        <li><span>RAM</span><b>${p.ram_gb} ГБ</b></li>
        <li><span>NVMe</span><b>${p.disk_gb} ГБ</b></li>
        <li><span>Трафик</span><b>${p.traffic_tb} ТБ</b></li>
      </ul>
      <a class="btn ${p.featured ? "btn-primary" : ""}" href="/app#/order?plan=${encodeURIComponent(p.id)}">Заказать</a>
    </article>`).join("");

  if (matchMedia("(hover: hover)").matches && !AM.reduced) {
    $$(".plan").forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        card.classList.add("tilting");
        card.style.setProperty("--ry", `${(x - 0.5) * 14}deg`);
        card.style.setProperty("--rx", `${(0.5 - y) * 12}deg`);
        card.style.setProperty("--mx", `${x * 100}%`);
        card.style.setProperty("--my", `${y * 100}%`);
      });
      card.addEventListener("pointerleave", () => {
        card.classList.remove("tilting");
        card.style.setProperty("--rx", "0deg"); card.style.setProperty("--ry", "0deg");
      });
    });
  }
})();
