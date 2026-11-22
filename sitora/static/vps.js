/* Раздел VPS (Hetzner): заказ, мои серверы, карточка с живой аналитикой, блок в админке. */
(function () {
  "use strict";
  var X = window.Sitora, M = window.Motion, TG = window.Telegram && Telegram.WebApp;
  if (!X || !document.getElementById("vList")) return;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  var esc = X.esc, som = X.som, api = X.api, t = X.t, fail = X.fail;

  // тексты раздела — в общий словарь, чтобы работали data-t и переключатель языка
  var TJ = { vpsTitle: "VPS-серверҳо", vpsSub: "Сервери худ дар як дақиқа", vNew: "Сервери нав",
    vNote: "Пардохт аз баланс ҳар 30 рӯз. Дастрасии root, IPv4 ва IPv6.", vLoading: "Тарифҳо бор мешаванд…",
    vLoc: "Кишвар", vPlan: "Тариф", vImg: "Система", vNamePw: "Ном ва парол", vName: "Номи сервер",
    vGen: "Пароли root-ро худ созем", vGenSub: "Як бор нишон медиҳем — мо онро нигоҳ намедорем", vPwPh: "Пароли root (аз 12 аломат)",
    vMonth: "Барои 30 рӯз", vBuy: "Сервер сохтан", vNone: "Ҳоло сервер нест", vPaid: "Пардохт то", vIp: "IP",
    vOn: "Фаъол", vOff: "Хомӯш", vStart: "Оғоз…", vMake: "Сохта мешавад…", vStop: "Хомӯш мешавад…", vSusp: "Барои пардохт хомӯш",
    vFail: "Хато", vRebuilding: "Насб мешавад…", vPowerOn: "Фаъол кардан", vShutdown: "Хомӯш кардан", vReboot: "Аз нав",
    vLive: "LIVE", vAgentWait: "Агент пайваст мешавад — 1–2 дақиқа пас аз сохтан", vCpu: "Протсессор", vRam: "Хотира",
    vDisk: "Диск", vNet: "Шабака", vHist: "Таърих", vTraffic: "Трафик дар ин моҳ", vTop: "Равандҳо", vPwChange: "Иваз кардани пароли root",
    vRebuild: "Аз нав насб кардан", vDelete: "Нест кардани сервер", vConfirm: "Барои тасдиқ номи серверро нависед:",
    vSave: "Паролро нигоҳ доред", vSaveSub: "Мо онро нигоҳ намедорем ва дигар нишон дода наметавонем.", vDone: "Фаҳмидам",
    vCreated: "Сервер сохта мешавад", vPwSoon: "Парол дар 1–3 дақиқа насб мешавад", vDeleted: "Сервер нест карда шуд",
    vNoData: "Ҳоло маълумот нест", vLack: "Маблағ намерасад — балансро пур кунед", vToTop: "Пур кардан", vErase: "Ҳамаи маълумот нест мешавад!",
    vPwSet: "Парол насб мешавад", vCpuHz: "CPU аз Hetzner (як дақиқа)", vRx: "қабул", vTx: "фиристодан" };
  var RU = { vpsTitle: "VPS-серверы", vpsSub: "Свой сервер за минуту", vNew: "Новый сервер",
    vNote: "Оплата с баланса раз в 30 дней. Root-доступ, IPv4 и IPv6.", vLoading: "Загружаем тарифы…",
    vLoc: "Страна", vPlan: "Тариф", vImg: "Система", vNamePw: "Имя и пароль", vName: "Имя сервера",
    vGen: "Сгенерировать пароль root", vGenSub: "Покажем один раз — мы его не храним", vPwPh: "Пароль root (от 12 символов)",
    vMonth: "За 30 дней", vBuy: "Создать сервер", vNone: "Серверов пока нет", vPaid: "Оплачен до", vIp: "IP",
    vOn: "Работает", vOff: "Выключен", vStart: "Запуск…", vMake: "Создаётся…", vStop: "Выключается…", vSusp: "Выключен за неуплату",
    vFail: "Ошибка", vRebuilding: "Переустановка…", vPowerOn: "Включить", vShutdown: "Выключить", vReboot: "Перезагрузить",
    vLive: "LIVE", vAgentWait: "Агент подключится через 1–2 минуты после создания", vCpu: "Процессор", vRam: "Память",
    vDisk: "Диск", vNet: "Сеть", vHist: "История", vTraffic: "Трафик за месяц", vTop: "Процессы", vPwChange: "Сменить пароль root",
    vRebuild: "Переустановить систему", vDelete: "Удалить сервер", vConfirm: "Для подтверждения впишите имя сервера:",
    vSave: "Сохраните пароль", vSaveSub: "Мы его не храним и больше не сможем показать.", vDone: "Понятно",
    vCreated: "Сервер создаётся", vPwSoon: "Пароль установится за 1–3 минуты", vDeleted: "Сервер удалён",
    vNoData: "Пока нет данных", vLack: "Не хватает денег — пополните баланс", vToTop: "Пополнить", vErase: "Все данные будут стёрты!",
    vPwSet: "Пароль устанавливается", vCpuHz: "CPU по данным Hetzner (раз в минуту)", vRx: "приём", vTx: "отдача" };
  Object.keys(TJ).forEach(function (k) { X.T.tj[k] = TJ[k]; X.T.ru[k] = RU[k]; });

  var V = { cat: null, loc: null, plan: null, img: null, gen: true, sid: null, srv: null, ws: null, chart: null, range: "1h", timer: null };
  var ru = function () { return X.lang() === "ru"; };

  function fmtBytes(b) {
    var u = ["Б", "КБ", "МБ", "ГБ", "ТБ"], i = 0; b = +b || 0;
    while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
    return (b >= 100 || i === 0 ? Math.round(b) : b.toFixed(1)) + " " + u[i];
  }
  function fmtRate(b) { return fmtBytes(b) + "/с"; }
  function date(ts) { return ts ? new Date(ts * 1000).toLocaleDateString(ru() ? "ru-RU" : "tg-TJ", { day: "2-digit", month: "2-digit", year: "numeric" }) : "—"; }
  function go(page, back) { M.go(page, back); }

  function status(s) {
    if (s.state === "creating") return [t("vMake"), true];
    if (s.state === "suspended") return [t("vSusp"), false];
    if (s.state === "failed") return [t("vFail"), false];
    var st = s.status;
    if (st === "running") return [t("vOn"), true];
    if (st === "off") return [t("vOff"), false];
    if (st === "stopping") return [t("vStop"), false];
    if (st === "rebuilding") return [t("vRebuilding"), true];
    return [t("vStart"), true];
  }
  function pill(s) { var x = status(s); return '<span class="live"><span class="dot' + (x[1] ? "" : " off") + '"></span>' + esc(x[0]) + "</span>"; }

  // ── список ──
  function list() {
    var box = $("#vList");
    if (!box.children.length) box.innerHTML = '<div class="empty skel">…</div>';
    return api("api/vps/servers").then(function (d) {
      box.innerHTML = d.items.length ? d.items.map(function (s) {
        return '<button class="card srv" data-vsrv="' + s.id + '"><span class="ico"><svg class="i"><use href="#server"/></svg></span>' +
          '<span style="text-align:left;min-width:0"><span class="tt" style="display:block">' + esc(s.name) + '</span><span class="ss">' + pill(s) +
          (s.ipv4 ? " · " + esc(s.ipv4) : "") + '</span></span><span class="r"><svg class="i"><use href="#next"/></svg></span></button>';
      }).join("") : '<div class="empty">' + t("vNone") + "</div>";
      M.stagger(box);
    }).catch(fail);
  }

  // ── заказ ──
  function suggest() { return "srv-" + Math.random().toString(36).slice(2, 6); }
  function openNew() {
    go("vpsnew");
    $("#vName").value = suggest(); $("#vPw").value = ""; $("#vBuyHint").textContent = "";
    if (V.cat) return render();
    $("#vWait").hidden = false; $("#vForm").hidden = true;
    api("api/vps/catalog").then(function (d) {
      V.cat = d; V.loc = (d.locations[0] || {}).name; V.plan = null; V.img = null; render();
    }).catch(function (e) { $("#vWait").textContent = e.message; });
  }
  function curLoc() { return (V.cat.locations || []).filter(function (l) { return l.name === V.loc; })[0]; }
  function curPlan() { var l = curLoc(); return l && l.plans.filter(function (p) { return p.name === V.plan; })[0]; }
  function render() {
    $("#vWait").hidden = true; $("#vForm").hidden = false;
    var c = V.cat, l = curLoc();
    $("#vLoc").innerHTML = c.locations.map(function (x) {
      return '<button class="chip' + (x.name === V.loc ? " sel" : "") + '" data-vloc="' + esc(x.name) + '">' + esc(ru() ? x.country_ru : x.country_tj) +
        (x.city ? " · " + esc(x.city) : "") + "</button>";
    }).join("");
    if (!l) { $("#vPlans").innerHTML = '<div class="empty">' + t("vNoData") + "</div>"; return; }
    if (!curPlan()) V.plan = l.plans[0].name;
    $("#vPlans").innerHTML = l.plans.map(function (p) {
      return '<button class="card plan' + (p.name === V.plan ? " sel" : "") + '" data-vplan="' + esc(p.name) + '"><span style="flex:1;min-width:0"><span class="tt">' +
        esc(p.name.toUpperCase()) + '</span><span class="spec"><span>' + p.cores + " vCPU</span><span>" + p.memory + " GB RAM</span><span>" + p.disk +
        " GB SSD</span>" + (p.architecture === "arm" ? "<span>ARM</span>" : "") + (p.cpu_type === "dedicated" ? "<span>Dedicated</span>" : "") +
        '</span></span><span class="pr">' + som(p.price) + " с.<small>$" + (p.price_usd / 100).toFixed(2) + "</small></span></button>";
    }).join("");
    var plan = curPlan(), imgs = c.images.filter(function (i) { return i.architecture === plan.architecture; });
    if (!imgs.some(function (i) { return i.name === V.img; })) {
      var u = imgs.filter(function (i) { return /^ubuntu-24/.test(i.name); })[0] || imgs.filter(function (i) { return i.flavor === "ubuntu"; }).pop() || imgs[0];
      V.img = u && u.name;
    }
    $("#vImg").innerHTML = imgs.map(function (i) {
      return '<button class="chip' + (i.name === V.img ? " sel" : "") + '" data-vimg="' + esc(i.name) + '">' + esc(i.title) + "</button>";
    }).join("");
    M.count($("#vSum"), plan.price / 100, 400);
    $("#vUsd").textContent = "$" + (plan.price_usd / 100).toFixed(2);
    $("#vSpec").textContent = plan.cores + " vCPU · " + plan.memory + " GB · " + plan.disk + " GB SSD · " + (plan.traffic_tb ? plan.traffic_tb + " TB" : "");
    $("#vPw").placeholder = t("vPwPh");
  }
  function buy() {
    var plan = curPlan(), me = X.me(), btn = $("#vBuy"), hint = $("#vBuyHint");
    var name = $("#vName").value.trim().toLowerCase(), pw = V.gen ? "" : $("#vPw").value;
    if (!plan || !V.img) return;
    if (!/^[a-z0-9][a-z0-9-]{0,40}$/.test(name)) { M.shake($("#vName")); $("#vName").value = name; hint.textContent = ru() ? "Имя: латиница, цифры и дефис" : "Ном: ҳарфҳои лотинӣ, рақам ва дефис"; return; }
    if (!V.gen && pw.length < 12) { M.shake($("#vPw")); hint.textContent = t("vPwPh"); return; }
    if (me.user.balance < plan.price) {
      hint.innerHTML = esc(t("vLack")) + ' · <b>' + som(plan.price - me.user.balance) + " с.</b>";
      X.haptic("error");
      var nav = $('.nav [data-go="balance"]'); if (nav) setTimeout(function () { nav.click(); }, 900);
      return;
    }
    btn.disabled = true; hint.textContent = "";
    api("api/vps/servers", { location: V.loc, server_type: plan.name, image: V.img, name: name, password: pw }).then(function (d) {
      btn.disabled = false; X.haptic("success"); X.refresh(); V.cat = null;
      openServer(d.id);
      if (d.password) showPassword(d.password); else M.toast(t("vCreated") + " · " + t("vPwSoon"));
    }).catch(function (e) { btn.disabled = false; fail(e); hint.textContent = e.message; });
  }
  function showPassword(pw) {
    X.sheet('<div class="h1" style="font-size:18px">' + t("vSave") + '</div><p class="muted">' + t("vSaveSub") + " " + t("vPwSoon") + '.</p>' +
      '<div class="pw mono" id="vPwShow">' + esc(pw) + '</div><button class="btn ghost" id="vPwCopy"><svg class="i"><use href="#copy"/></svg>' + t("copy") +
      '</button><button class="btn" id="vPwOk">' + t("vDone") + "</button>");
    $("#vPwCopy").onclick = function () { copy(pw); };
    $("#vPwOk").onclick = X.closeSheet;
  }
  function copy(text) {
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () { M.toast(t("copied")); }, function () { M.toast(text); });
  }

  // ── карточка сервера ──
  function openServer(id) {
    stopLive(); V.sid = id; V.srv = null; V.range = "1h";
    $("#vSrv").innerHTML = '<div><button class="back" data-vback="vps"><svg class="i"><use href="#back"/></svg>' + t("vpsTitle") + '</button></div><div class="main skel" style="height:190px"></div>';
    go("vpssrv");
    load(true);
  }
  function load(first) {
    var id = V.sid;
    return api("api/vps/servers/" + id).then(function (s) {
      if (id !== V.sid) return;
      var was = V.srv; V.srv = s;
      if (first || !was || was.status !== s.status || was.state !== s.state || was.ipv4 !== s.ipv4 || was.password_state !== s.password_state) draw(s);
      if (first) { startLive(); history(); }
    }).catch(function (e) { fail(e); if (first) go("vps", true); });
  }
  function draw(s) {
    var busy = s.state !== "active" || ["running", "off"].indexOf(s.status) < 0, off = s.status === "off", susp = s.state === "suspended";
    var tr = s.traffic || {}, used = (tr.outgoing || 0), inc = tr.included || 0;
    $("#vSrv").innerHTML =
      '<div><button class="back" data-vback="vps"><svg class="i"><use href="#back"/></svg>' + t("vpsTitle") + "</button></div>" +
      '<div class="main"><div style="display:flex;justify-content:space-between;align-items:center"><span class="cap">' + esc(s.location.toUpperCase()) + " · " +
      esc(s.server_type.toUpperCase()) + '</span><span class="pill">' + pill(s) + '</span></div><div class="h1" style="margin-top:10px;font-size:24px;text-transform:none">' +
      esc(s.name) + '</div><div class="muted" style="color:rgba(255,255,255,.6);margin-top:4px">' + s.cores + " vCPU · " + s.memory + " GB · " + s.disk + " GB · " + esc(s.image) + "</div>" +
      (s.ipv4 ? '<div class="ipbox mono"><span>' + esc(s.ipv4) + '</span><button data-vcopy="' + esc(s.ipv4) + '" aria-label="' + t("copy") + '"><svg class="i"><use href="#copy"/></svg></button></div>' : "") +
      '<div class="muted" style="color:rgba(255,255,255,.6);margin-top:10px">' + t("vPaid") + " " + date(s.paid_until) + " · " + som(s.price) + " с.</div>" +
      (s.error ? '<div class="muted" style="color:#fff;margin-top:8px">⚠ ' + esc(s.error) + "</div>" : "") +
      (s.password_state === "pending" && s.state === "active" ? '<div class="muted" style="color:#fff;margin-top:8px">' + t("vPwSet") + "…</div>" : "") + "</div>" +
      '<div class="abtns" style="margin-top:0">' +
      '<button class="chip" data-vact="poweron"' + (busy || !off || susp ? " disabled" : "") + '><svg class="i" style="width:15px;height:15px;vertical-align:-3px"><use href="#power"/></svg> ' + t("vPowerOn") + "</button>" +
      '<button class="chip" data-vact="shutdown"' + (busy || off ? " disabled" : "") + ">" + t("vShutdown") + "</button>" +
      '<button class="chip" data-vact="reboot"' + (busy || off ? " disabled" : "") + '><svg class="i" style="width:15px;height:15px;vertical-align:-3px"><use href="#reboot"/></svg> ' + t("vReboot") + "</button></div>" +
      '<div style="display:flex;justify-content:space-between;align-items:center"><span class="cap" id="vLiveCap">' + (s.live ? '<span class="live"><span class="dot"></span>' + t("vLive") + "</span>" : t("vAgentWait")) + "</span></div>" +
      '<div class="meters">' + meter("cpu", t("vCpu")) + meter("ram", t("vRam")) + meter("disk", t("vDisk")) +
      '<div class="meter"><span class="cap">' + t("vNet") + '</span><b id="vm-net" style="font-size:14px;line-height:1.5">—</b><span class="muted" id="vm-net2"></span></div></div>' +
      '<div class="card col"><canvas class="chart" id="vLiveChart"></canvas><div class="legend"><span><i></i>CPU</span><span><i class="dash"></i>RAM</span></div></div>' +
      '<div class="card col"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span class="cap">' + t("vHist") + '</span><span class="chips">' +
      ["1h", "24h", "7d"].map(function (r) { return '<button class="chip' + (r === V.range ? " sel" : "") + '" data-vrange="' + r + '" style="height:30px;padding:0 11px">' + (ru() ? { "1h": "1 ч", "24h": "24 ч", "7d": "7 д" } : { "1h": "1 соат", "24h": "24 соат", "7d": "7 рӯз" })[r] + "</button>"; }).join("") +
      '</span></div><canvas class="chart" id="vHistChart" style="margin-top:10px"></canvas><div class="legend" id="vHistLegend"><span><i></i>CPU %</span><span><i class="dash"></i>RAM %</span></div></div>' +
      (inc ? '<div class="card col"><div style="display:flex;justify-content:space-between"><span class="cap">' + t("vTraffic") + '</span><b style="font-size:13px">' + fmtBytes(used) + " / " + fmtBytes(inc) +
        '</b></div><div class="progress" style="margin-top:10px"><i style="--v:' + Math.min(used / inc, 1).toFixed(3) + '"></i></div><div class="muted" style="margin-top:6px">↓ ' + fmtBytes(tr.ingoing || 0) + " · ↑ " + fmtBytes(used) + "</div></div>" : "") +
      '<div class="card col" id="vTopBox" hidden><span class="cap">' + t("vTop") + '</span><div class="procs" id="vTop" style="margin-top:10px"></div></div>' +
      (s.state === "active" ? '<button class="btn ghost" data-vdo="password"><svg class="i"><use href="#key"/></svg>' + t("vPwChange") + "</button>" +
        '<button class="btn ghost" data-vdo="rebuild"><svg class="i"><use href="#reboot"/></svg>' + t("vRebuild") + "</button>" : "") +
      (s.state !== "deleted" && s.state !== "creating" ? '<button class="btn ghost danger" data-vdo="delete"><svg class="i"><use href="#trash"/></svg>' + t("vDelete") + "</button>" : "");
    M.stagger($("#vSrv"));
    V.chart = window.Charts ? new Charts.LiveChart($("#vLiveChart"), { window: 60, max: 100, fmt: function (v) { return Math.round(v) + "%"; },
      series: [{ color: "rgb(11,11,11)" }, { color: "rgb(140,140,136)" }] }) : null;
    if (s.latest) sample(s.latest, true);
    if (V.hist) drawHist(V.hist);
  }
  function meter(k, cap) {
    return '<div class="meter"><span class="cap">' + cap + '</span><b id="vm-' + k + '">—</b><div class="progress"><i id="vb-' + k + '" style="--v:0"></i></div>' +
      '<span class="muted" id="vm-' + k + '2" style="font-size:11px"></span></div>';
  }
  function setMeter(k, pct, sub) {
    var b = $("#vm-" + k), bar = $("#vb-" + k); if (!b) return;
    b.textContent = Math.round(pct) + "%"; bar.style.setProperty("--v", Math.min(pct / 100, 1).toFixed(3));
    $("#vm-" + k + "2").textContent = sub || "";
  }
  function sample(d, noPush) {
    var ram = d.ram_total ? 100 * d.ram_used / d.ram_total : 0, disk = d.disk_total ? 100 * d.disk_used / d.disk_total : 0;
    setMeter("cpu", d.cpu, "load " + (d.load || [0])[0].toFixed(2));
    setMeter("ram", ram, fmtBytes(d.ram_used) + " / " + fmtBytes(d.ram_total));
    setMeter("disk", disk, fmtBytes(d.disk_used) + " / " + fmtBytes(d.disk_total));
    var n = $("#vm-net"); if (n) { n.textContent = "↓ " + fmtRate(d.net_in); $("#vm-net2").textContent = "↑ " + fmtRate(d.net_out); }
    if (V.chart && !noPush) V.chart.push([d.cpu, ram]);
    var top = d.top || [], box = $("#vTop");
    if (box && top.length) {
      $("#vTopBox").hidden = false;
      box.innerHTML = top.slice(0, 6).map(function (p) { return "<div><span>" + esc(p.name) + '</span><span class="mono">' + p.cpu.toFixed(1) + "% · " + fmtBytes(p.rss) + "</span></div>"; }).join("");
    }
  }
  function setLive(on) {
    var c = $("#vLiveCap"); if (!c) return;
    c.innerHTML = on ? '<span class="live"><span class="dot"></span>' + t("vLive") + "</span>" : esc(t("vAgentWait"));
  }
  function startLive() {
    var url = new URL("ws/live", location.href); url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
    var sid = V.sid, ws;
    try { ws = new WebSocket(url.href); } catch (e) { return; }
    V.ws = ws;
    ws.onopen = function () { ws.send(JSON.stringify({ init: TG ? TG.initData : "", server: sid })); };
    ws.onmessage = function (e) {
      var m; try { m = JSON.parse(e.data); } catch (x) { return; }
      if (sid !== V.sid) return;
      if (m.type === "sample") { setLive(true); sample(m.data); }
      else if (m.type === "hello") { setLive(m.online); if (m.data) sample(m.data, true); }
      else if (m.type === "offline") setLive(false);
    };
    ws.onclose = function () { if (V.ws === ws) { V.ws = null; setTimeout(function () { if (V.sid === sid && onPage() && !V.ws) startLive(); }, 5000); } };
    clearInterval(V.timer);
    V.timer = setInterval(function () {
      if (!onPage()) { stopLive(); return; }
      if (!document.hidden && V.srv && (V.srv.state === "creating" || ["running", "off"].indexOf(V.srv.status) < 0 || V.srv.password_state === "pending")) load(false);
    }, 5000);
  }
  function stopLive() {
    clearInterval(V.timer); V.timer = null;
    if (V.ws) { var w = V.ws; V.ws = null; try { w.close(); } catch (e) {} }
    if (V.chart) { V.chart.stop(); V.chart = null; }
  }
  function onPage() { var p = $('.page[data-page="vpssrv"]'); return p && p.classList.contains("on"); }
  function history() {
    var sid = V.sid, rng = V.range;
    api("api/vps/servers/" + sid + "/history?range=" + rng).then(function (d) { if (sid === V.sid && rng === V.range) { V.hist = d; drawHist(d); } }).catch(function () {});
  }
  function drawHist(d) {
    var c = $("#vHistChart"); if (!c || !window.Charts) return;
    var leg = $("#vHistLegend");
    if (!d.points.length && d.hetzner_cpu && d.hetzner_cpu.length) {
      leg.innerHTML = "<span><i></i>" + esc(t("vCpuHz")) + "</span>";
      Charts.drawHistory(c, d.hetzner_cpu, [{ index: 1, color: "rgb(11,11,11)" }], { max: 100, fmt: function (v) { return Math.round(v) + "%"; }, empty: t("vNoData") });
      return;
    }
    leg.innerHTML = '<span><i></i>CPU %</span><span><i class="dash"></i>RAM %</span>';
    Charts.drawHistory(c, d.points, [{ index: 1, color: "rgb(11,11,11)" }, { index: 2, color: "rgb(140,140,136)" }],
      { max: 100, fmt: function (v) { return Math.round(v) + "%"; }, empty: t("vNoData") });
  }

  // опасные действия: вписать имя сервера
  function confirmSheet(title, warn, extra, then) {
    var s = V.srv;
    X.sheet('<div class="h1" style="font-size:18px">' + esc(title) + "</div>" + (warn ? '<p class="hint"><svg class="i" style="width:16px;height:16px"><use href="#warn"/></svg>' + esc(warn) + "</p>" : "") +
      (extra || "") + '<label class="cap" style="text-transform:none;letter-spacing:0;font-size:12px">' + t("vConfirm") + ' <b class="mono" style="color:var(--ink)">' + esc(s.name) +
      '</b><input class="field" id="vConfirm" autocomplete="off" autocapitalize="none" spellcheck="false" style="margin-top:6px"></label>' +
      '<button class="btn" id="vConfirmGo" disabled>' + esc(title) + '</button><button class="btn ghost" id="vConfirmNo">' + t("back") + "</button>");
    var inp = $("#vConfirm"), goBtn = $("#vConfirmGo");
    inp.oninput = function () { goBtn.disabled = inp.value.trim().toLowerCase() !== s.name; };
    $("#vConfirmNo").onclick = X.closeSheet;
    goBtn.onclick = function () { goBtn.disabled = true; then(inp.value.trim(), function () { goBtn.disabled = false; }); };
  }
  function pwFields() {
    return '<div class="card"><div><div class="tt">' + t("vGen") + '</div><div class="ss">' + t("vGenSub") + '</div></div><button class="switch r" id="vSGen" role="switch" aria-checked="true"></button></div>' +
      '<input class="field" id="vSPw" type="password" hidden autocomplete="new-password" placeholder="' + esc(t("vPwPh")) + '">';
  }
  function bindPw() {
    var sw = $("#vSGen"); sw.onclick = function () { var on = sw.getAttribute("aria-checked") !== "true"; sw.setAttribute("aria-checked", on); $("#vSPw").hidden = on; };
  }
  function readPw() { return $("#vSGen").getAttribute("aria-checked") === "true" ? "" : $("#vSPw").value; }
  function doAction(kind) {
    var s = V.srv, id = s.id;
    if (kind === "password") {
      X.sheet('<div class="h1" style="font-size:18px">' + t("vPwChange") + "</div>" + pwFields() + '<button class="btn" id="vPwGo">' + t("vPwChange") + "</button>");
      bindPw();
      $("#vPwGo").onclick = function () {
        var b = this; b.disabled = true;
        api("api/vps/servers/" + id + "/password", { password: readPw() }).then(function (d) {
          if (d.password) showPassword(d.password); else { X.closeSheet(); M.toast(t("vPwSet")); }
          load(false);
        }).catch(function (e) { b.disabled = false; fail(e); });
      };
    } else if (kind === "rebuild") {
      var imgs = '<div class="chips" id="vRbImg">' + (V.images || []).map(function (i, k) { return '<button class="chip' + (i.name === s.image ? " sel" : "") + '" data-rbimg="' + esc(i.name) + '">' + esc(i.title) + "</button>"; }).join("") + "</div>";
      var open = function () {
        confirmSheet(t("vRebuild"), t("vErase"), imgs + pwFields(), function (name, undo) {
          var sel = $("#vRbImg .sel");
          api("api/vps/servers/" + id + "/rebuild", { image: sel ? sel.dataset.rbimg : s.image, password: readPw(), confirm: name }).then(function (d) {
            if (d.password) showPassword(d.password); else { X.closeSheet(); M.toast(t("vPwSet")); }
            load(false);
          }).catch(function (e) { undo(); fail(e); });
        });
        bindPw();
      };
      if (V.images) return open();
      api("api/vps/catalog").then(function (c) {
        var arch = ((c.locations.filter(function (l) { return l.name === s.location; })[0] || { plans: [] }).plans.filter(function (p) { return p.name === s.server_type; })[0] || {}).architecture || "x86";
        V.images = c.images.filter(function (i) { return i.architecture === arch; });
        imgs = '<div class="chips" id="vRbImg">' + V.images.map(function (i) { return '<button class="chip' + (i.name === s.image ? " sel" : "") + '" data-rbimg="' + esc(i.name) + '">' + esc(i.title) + "</button>"; }).join("") + "</div>";
        open();
      }).catch(fail);
    } else if (kind === "delete") {
      confirmSheet(t("vDelete"), t("vErase"), "", function (name, undo) {
        api("api/vps/servers/" + id + "/delete", { confirm: name }).then(function () {
          X.closeSheet(); stopLive(); M.toast(t("vDeleted")); X.haptic("success"); go("vps", true); list();
        }).catch(function (e) { undo(); fail(e); });
      });
    }
  }

  // ── события ──
  document.addEventListener("click", function (e) {
    var el;
    if ((el = e.target.closest("[data-vgo]"))) { go(el.dataset.vgo); list(); }
    else if ((el = e.target.closest("[data-vback]"))) {
      var to = el.dataset.vback; stopLive(); V.sid = null; V.hist = null;
      if (to === "shop") { var nb = $('.nav [data-go="shop"]'); $$(".nav button").forEach(function (x) { x.toggleAttribute("aria-current", x === nb); }); }
      go(to, true); if (to === "vps") list();
    }
    else if ((el = e.target.closest("[data-vsrv]"))) { V.images = null; openServer(+el.dataset.vsrv); }
    else if ((el = e.target.closest("[data-vloc]"))) { V.loc = el.dataset.vloc; V.plan = null; render(); }
    else if ((el = e.target.closest("[data-vplan]"))) { V.plan = el.dataset.vplan; render(); }
    else if ((el = e.target.closest("[data-vimg]"))) { V.img = el.dataset.vimg; render(); }
    else if ((el = e.target.closest("[data-rbimg]"))) { $$("#vRbImg .chip").forEach(function (x) { x.classList.toggle("sel", x === el); }); }
    else if ((el = e.target.closest("[data-vcopy]"))) copy(el.dataset.vcopy);
    else if ((el = e.target.closest("[data-vrange]"))) { V.range = el.dataset.vrange; $$("[data-vrange]").forEach(function (x) { x.classList.toggle("sel", x === el); }); history(); }
    else if ((el = e.target.closest("[data-vdo]"))) doAction(el.dataset.vdo);
    else if ((el = e.target.closest("[data-vact]"))) {
      el.disabled = true;
      api("api/vps/servers/" + V.sid + "/action", { action: el.dataset.vact }).then(function () { X.haptic("success"); setTimeout(function () { load(false); }, 1500); })
        .catch(function (err) { el.disabled = false; fail(err); });
    }
  });
  $("#vNew").onclick = openNew;
  $("#vBuy").onclick = buy;
  $("#vGenSw").onclick = function () { V.gen = !V.gen; this.setAttribute("aria-checked", V.gen); $("#vPw").hidden = V.gen; if (!V.gen) $("#vPw").focus(); };
  $("#vName").addEventListener("input", function () { var v = this.value.toLowerCase().replace(/[^a-z0-9-]/g, ""); if (v !== this.value) this.value = v; });

  // ── админка ──
  function admin() {
    var box = $("#aVps"); if (!box) return;
    api("api/admin/vps").then(function (d) {
      box.innerHTML = '<h2 class="h1" style="font-size:15px;margin-bottom:13px">VPS · Hetzner</h2>' +
        (d.token ? "" : '<div class="card col" style="margin-bottom:10px"><div class="tt">Токен Hetzner не задан</div><div class="ss">На сервере: <span class="mono">sudo bash /home/sitora/app/sitora/deploy/set-key.sh hetzner</span></div></div>') +
        '<div class="grid3" style="grid-template-columns:1fr 1fr;margin-bottom:10px">' +
        '<div class="tile"><span class="cap">Выручка, месяц</span><b>' + som(d.revenue) + "</b><small>сомони</small></div>" +
        '<div class="tile"><span class="cap">Hetzner, месяц</span><b>' + som(d.cost) + "</b><small>$" + (d.cost_usd / 100).toFixed(2) + "</small></div>" +
        '<div class="tile"><span class="cap">Прибыль</span><b>' + som(d.profit) + "</b><small>сомони</small></div>" +
        '<div class="tile"><span class="cap">Серверов</span><b>' + d.active + "</b><small>выкл. за неуплату: " + d.suspended + "</small></div></div>" +
        '<div class="card col" style="display:grid;gap:10px;margin-bottom:10px">' +
        '<div style="display:flex;justify-content:space-between;align-items:center"><span class="tt">Продажа VPS</span><button class="switch" id="aVOn" role="switch" aria-checked="' + d.enabled + '"></button></div>' +
        '<label class="cap">Наценка, %<input class="field" id="aVMk" inputmode="numeric" value="' + d.markup + '" style="margin-top:6px"></label>' +
        '<label class="cap">Курс EUR → USD (пусто — авто раз в сутки)<input class="field" id="aVEur" inputmode="decimal" value="' + esc(d.eur_usd || "") + '" style="margin-top:6px"></label>' +
        '<div class="abtns" style="margin-top:0"><button class="chip sel" id="aVSave">Сохранить</button><button class="chip" id="aVCheck">Проверить токен</button></div></div>' +
        '<div class="list" style="margin-bottom:10px">' + (d.servers.length ? d.servers.map(function (s) {
          return '<div class="card col" data-avs="' + s.id + '"><div class="tt">' + esc(s.name) + " · #" + s.id + '</div><div class="ss">клиент ' + s.user_id + " · " + esc(s.server_type) + " · " +
            esc(s.location) + " · " + esc(s.ipv4 || "без IP") + " · " + som(s.price) + ' с.</div><div class="ss">' + pill(s) + " · до " + date(s.paid_until) + '</div><div class="abtns">' +
            '<button class="chip" data-avact="poweron">Вкл.</button><button class="chip" data-avact="shutdown">Выкл.</button><button class="chip danger" data-avact="delete">Удалить</button></div></div>';
        }).join("") : '<div class="empty">Серверов пока нет</div>') + "</div>" +
        '<div class="card col"><div class="tt">Больше одного сервера</div><div class="ss">Новый клиент может держать 1 сервер, пока вы его не подтвердите.</div>' +
        '<div style="display:flex;gap:8px;margin-top:10px"><input class="field" id="aVUid" placeholder="ID клиента" inputmode="numeric">' +
        '<button class="chip" id="aVOk" style="height:56px;border-radius:18px">Разрешить</button><button class="chip" id="aVNo" style="height:56px;border-radius:18px">Запретить</button></div></div>';
      $("#aVOn").onclick = function () { this.setAttribute("aria-checked", this.getAttribute("aria-checked") !== "true"); };
      $("#aVSave").onclick = function () {
        api("api/admin/vps/settings", { enabled: $("#aVOn").getAttribute("aria-checked") === "true", markup: $("#aVMk").value, eur_usd: $("#aVEur").value })
          .then(function () { M.toast("Сохранено"); V.cat = null; X.refresh(); admin(); }).catch(fail);
      };
      $("#aVCheck").onclick = function () {
        api("api/admin/vps/check", {}).then(function (r) { M.toast(r.access === "rw" ? "Токен рабочий: Read & Write" : r.access === "ro" ? "Токен только для чтения — нужен Read & Write" : "Токен не подошёл — задайте новый через set-key.sh hetzner"); }).catch(fail);
      };
      var approve = function (ok) { var uid = $("#aVUid").value.trim(); if (!/^\d+$/.test(uid)) { M.shake($("#aVUid")); return; }
        api("api/admin/vps/approve/" + uid, { approved: ok }).then(function () { M.toast(ok ? "Разрешено" : "Запрещено"); }).catch(fail); };
      $("#aVOk").onclick = function () { approve(true); };
      $("#aVNo").onclick = function () { approve(false); };
    }).catch(function (e) { box.innerHTML = '<div class="empty">VPS: ' + esc(e.message) + "</div>"; });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-avact]"); if (!b) return;
    var id = b.closest("[data-avs]").dataset.avs, act = b.dataset.avact;
    if (act === "delete" && !window.confirm("Удалить сервер #" + id + " у Hetzner? Данные клиента пропадут.")) return;
    api("api/admin/vps/servers/" + id, { action: act }).then(function () { M.toast("Готово"); admin(); }).catch(fail);
  });

  window.SitoraVps = {
    admin: admin,
    texts: function () {
      $$("[data-ph]").forEach(function (el) { el.placeholder = t(el.dataset.ph); });
      if (V.cat && $('.page[data-page="vpsnew"]').classList.contains("on")) render();
      if (V.srv && onPage()) draw(V.srv);
    }
  };
})();
