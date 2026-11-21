/* Мини-приложение: Stars, Premium, подарки. Данные — с сервера (/api), подпись — Telegram initData. */
(function () {
  "use strict";
  var M = window.Motion, TG = window.Telegram && Telegram.WebApp;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; };
  var som = function (diram) { return M.fmt(diram / 100); };

  var T = {
    tj: { shop: "Мағоза", balance: "Баланс", somoni: "сомонӣ", gifts: "Тӯҳфаҳо", gift: "Тӯҳфа", ownQty: "Миқдори дилхоҳ", toMe: "Ба худ",
      buy: "Харидан", history: "Таърих", orders: "Фармоишҳо", wallet: "Ҳамён", available: "Дастрас", topupSum: "Маблағи пуркунӣ",
      topup: "Пур кардан", support: "Дастгирӣ", help: "Ёрӣ", h1t: "Чӣ тавр харидан", h1s: "Баста → @username → пардохт",
      h2t: "Чӣ қадар интизор шудан", h2s: "Одатан 1–5 дақиқа", h3t: "Тӯҳфа ба дӯст",
      h3s: "Агар дӯст ботро накушода бошад — пайвандро аз «Фармоишҳо» фиристед", h4t: "Пардохт",
      h4s: "Аз рӯи реквизитҳо интиқол диҳед ва чекро фиристед — санҷида пур мекунем", write: "Ба дастгирӣ навиштан",
      newBal: "Баланси нав", sendLink: "Пайвандро ба дӯст фиристед", more: "Боз харидан", myOrders: "Фармоишҳои ман",
      who: "Ба кӣ · @username", whoGift: "Ба кӣ · @username (холӣ — ба худ)", note: "Матн ба тӯҳфа (ихтиёрӣ)",
      badWho: "@username-и гирандаро нависед, масалан @ali_dev", payTitle: "Пардохти фармоиш", fromBal: "Аз баланс",
      instant: "Фавран", lack: "Намерасад", transfer: "Интиқол аз рӯи рақам", pay: "Пардохт кардан",
      sendExact: "Ин маблағро интиқол диҳед", copy: "Нусха", copied: "Нусха шуд", attach: "Чекро замима кунед",
      attachSub: "Скриншоти чек аз бонк", sent: "Чек гирифта шуд", wait: "Чек дар санҷиш — баланс баъди тасдиқ пур мешавад",
      intentNote: "Баъди тасдиқи чек фармоиш худ ба худ иҷро мешавад", done: "Харид<br>анҷом шуд",
      giftWait: "Тӯҳфа<br>пардохт шуд", item: "Мол", to: "Гиранда", paid: "Пардохт", st_done: "Расонида шуд",
      st_work: "Дар кор", st_wait: "Интизори гиранда", st_fail: "Баргардонида шуд", empty: "Ҳоло фармоиш нест",
      enterSum: "Маблағро ворид кунед", minSum: "Ҳадди ақал", stepSum: "Маблағ", stepBank: "Бонк", stepCheck: "Чек", pickBank: "Бонкро интихоб кунед", next: "Минбаъд", lowSum: "Камтар аз ҳадди ақал:", choose: "Усули пардохтро интихоб кунед", noMethods: "Ҳоло усули пардохт нест",
      back: "Бозгашт", open: "Аз Telegram кушоед", soon: "Ҳоло нест", cancel: "Бекор кардан",
      giftText: "Тӯҳфа барои ту! Ин пайвандро кушо ва Start-ро пахш кун" },
    ru: { shop: "Магазин", balance: "Баланс", somoni: "сомони", gifts: "Подарки", gift: "Подарок", ownQty: "Своё количество", toMe: "Себе",
      buy: "Купить", history: "История", orders: "Заказы", wallet: "Кошелёк", available: "Доступно", topupSum: "Сумма пополнения",
      topup: "Пополнить", support: "Поддержка", help: "Помощь", h1t: "Как купить", h1s: "Пакет → @username → оплата",
      h2t: "Сколько ждать", h2s: "Обычно 1–5 минут", h3t: "Подарок другу",
      h3s: "Если друг ещё не открывал бота — отправьте ему ссылку из «Заказов»", h4t: "Оплата",
      h4s: "Переведите по реквизитам и пришлите чек — проверим и зачислим", write: "Написать в поддержку",
      newBal: "Новый баланс", sendLink: "Отправить ссылку другу", more: "Купить ещё", myOrders: "Мои заказы",
      who: "Кому · @username", whoGift: "Кому · @username (пусто — себе)", note: "Текст к подарку (необязательно)",
      badWho: "Напишите @username получателя, например @ali_dev", payTitle: "Оплата заказа", fromBal: "С баланса",
      instant: "Мгновенно", lack: "Не хватает", transfer: "Перевод по номеру", pay: "Оплатить",
      sendExact: "Переведите эту сумму", copy: "Копировать", copied: "Скопировано", attach: "Прикрепить чек",
      attachSub: "Скриншот чека из банка", sent: "Чек получен", wait: "Чек на проверке — баланс пополнится после подтверждения",
      intentNote: "После проверки чека заказ оформится сам", done: "Покупка<br>проведена",
      giftWait: "Подарок<br>оплачен", item: "Товар", to: "Получатель", paid: "Оплачено", st_done: "Доставлено",
      st_work: "В работе", st_wait: "Ждёт получателя", st_fail: "Возврат", empty: "Заказов пока нет",
      enterSum: "Введите сумму пополнения", minSum: "Минимум", stepSum: "Сумма", stepBank: "Банк", stepCheck: "Чек", pickBank: "Выберите банк", next: "Далее", lowSum: "Меньше минимума:", choose: "Выберите способ оплаты", noMethods: "Способов оплаты пока нет",
      back: "Назад", open: "Откройте из Telegram", soon: "Пока нет", cancel: "Отменить",
      giftText: "Подарок для тебя! Открой ссылку и нажми Start" }
  };
  var S = { me: null, lang: "tj", tab: "stars", pick: 1, amount: 0 };
  var t = function (k) { return (T[S.lang] || T.ru)[k] || k; };

  // ── сервер ──
  function api(path, body, file) {
    var opt = { method: body || file ? "POST" : "GET", headers: { "X-Init-Data": TG ? TG.initData : "" } };
    if (file) { var f = new FormData(); f.append("file", file); opt.body = f; }
    else if (body) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
    return fetch(path, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok || d.ok === false) throw new Error(d.error || d.detail || ("HTTP " + r.status));
        return d;
      });
    });
  }
  function haptic(kind) { try { TG && TG.HapticFeedback.notificationOccurred(kind); } catch (e) {} }

  // ── тексты ──
  function texts() {
    $$("[data-t]").forEach(function (el) { el.textContent = t(el.dataset.t); });
    $("#lang").textContent = S.lang === "tj" ? "ТҶ · ru" : "tj · RU";
    $("#note").placeholder = t("note");
    document.documentElement.lang = S.lang === "tj" ? "tg" : "ru";
    if (S.me) checkSum();
    items();
  }

  // ── каталог ──
  function list() {
    var c = S.me ? S.me.catalog : {};
    if (S.tab === "stars") return ((c.stars || {}).packs || []).map(function (p) { return { cap: "Stars", n: M.fmt(p.qty), price: p.price, item: { kind: "stars", qty: p.qty } }; });
    if (S.tab === "premium") return (c.premium || []).map(function (p) { return { cap: "Premium", n: p.months + (S.lang === "tj" ? " моҳ" : " мес."), price: p.price, item: { kind: "premium", months: p.months } }; });
    return (c.gifts || []).map(function (g) { return { cap: "★ " + g.stars, em: g.emoji || "🎁", anim: g.anim || "", gid: g.id, n: "", price: g.price, item: { kind: "gift", gift_id: g.id } }; });
  }
  function items() {
    var box = $("#items"), rows = list(), stars = S.me && S.me.catalog.stars;
    box.className = "grid3"; box.textContent = "";
    if (!rows.length) { box.className = ""; box.innerHTML = '<div class="empty">' + esc(t("soon")) + "</div>"; }
    S.pick = Math.min(S.pick, Math.max(0, rows.length - 1));
    rows.forEach(function (p, i) {
      var b = document.createElement("button"); b.className = "tile" + (i === S.pick ? " sel" : "");
      b.innerHTML = '<span class="cap"></span>' + (p.em ? '<span class="gfx"><span class="em"></span></span>' : "<b></b>") + "<small></small>";
      b.children[0].textContent = p.cap; b.children[2].textContent = som(p.price) + " с.";
      if (p.em) { b.children[1].firstChild.textContent = p.em; if (p.anim) { b.children[1].dataset.gift = p.gid; b.children[1].dataset.fmt = p.anim; } }
      else b.children[1].textContent = p.n;
      b.style.animation = "rise .5s var(--ease) both"; b.style.animationDelay = i * 55 + "ms";
      b.addEventListener("click", function () { var g = b.querySelector(".gfx"); if (g && g._a) g._a.goToAndPlay(0, true); S.pick = i; $("#qty").value = ""; $$(".tile", box).forEach(function (x, k) { x.classList.toggle("sel", k === i); }); price(); });
      box.appendChild(b);
    });
    gifts(box);
    $("#custom").hidden = S.tab !== "stars" || !stars;
    if (stars) { $("#qty").min = stars.min; $("#qty").max = stars.max; $("#qty").placeholder = stars.min + " – " + M.fmt(stars.max); }
    $("#note").style.display = S.tab === "gifts" ? "" : "none";
    $("#who").placeholder = t(S.tab === "gifts" ? "whoGift" : "who");
    price();
  }
  // ── анимации подарков — те же, что в Telegram (Lottie-стикер подарка), играют только на экране ──
  var G = { lib: null, data: {}, live: [], io: null, still: !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) };
  function lottieLib() {
    if (!G.lib) G.lib = new Promise(function (ok, no) {
      var sc = document.createElement("script"); sc.src = "static/lottie.min.js?v=5122";
      sc.onload = function () { ok(window.lottie); }; sc.onerror = function () { G.lib = null; no(); }; document.head.appendChild(sc);
    });
    return G.lib;
  }
  function giftJson(id) {   // текст, а не объект: Lottie меняет данные, у каждой копии — свои
    if (!G.data[id]) G.data[id] = fetch("gift/" + encodeURIComponent(id)).then(function (r) { if (!r.ok) throw r.status; return r.text(); })
      .catch(function (e) { G.data[id] = null; throw e; });
    return G.data[id];
  }
  function mountGift(el) {
    el._busy = true;
    var id = el.dataset.gift, kind = el.dataset.fmt, url = "gift/" + encodeURIComponent(id);
    if (kind === "webm" || kind === "webp") {
      var m = document.createElement(kind === "webm" ? "video" : "img");
      if (kind === "webm") { m.muted = true; m.loop = true; m.autoplay = !G.still; m.setAttribute("playsinline", ""); m.onloadeddata = function () { el.classList.add("on"); }; }
      else m.onload = function () { el.classList.add("on"); };
      m.src = url; el.appendChild(m); return;
    }
    Promise.all([lottieLib(), giftJson(id)]).then(function (r) {
      if (!el.isConnected) return;
      var a = r[0].loadAnimation({ container: el, renderer: "canvas", loop: true, autoplay: !G.still, animationData: JSON.parse(r[1]),
        rendererSettings: { clearCanvas: true, dpr: Math.min(2, window.devicePixelRatio || 1) } });
      el._a = a; G.live.push(a);
      a.addEventListener("DOMLoaded", function () { el.classList.add("on"); if (G.still) a.goToAndStop(0, true); });
    }).catch(function () { el._busy = false; });   // не загрузилось — остаётся эмодзи
  }
  function gifts(box) {
    G.live.forEach(function (a) { a.destroy(); }); G.live = [];
    if (G.io) G.io.disconnect();
    var els = $$(".gfx[data-gift]", box); if (!els.length) return;
    G.io = "IntersectionObserver" in window ? new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        var el = e.target;
        if (e.isIntersecting) { if (!el._busy) mountGift(el); else if (el._a && !G.still) el._a.play(); }
        else if (el._a) el._a.pause();
      });
    }, { rootMargin: "120px" }) : null;
    els.forEach(function (el) { if (G.io) G.io.observe(el); else mountGift(el); });
  }
  function current() {
    var rows = list(), q = parseInt($("#qty").value, 10), stars = S.me && S.me.catalog.stars;
    if (S.tab === "stars" && q && stars) return { item: { kind: "stars", qty: q }, price: Math.ceil(q * stars.per_star_diram / 10 - 1e-9) * 10, title: q + " Stars" };
    var p = rows[S.pick]; if (!p) return null;
    return { item: p.item, price: p.price, title: (p.em ? t("gift") + " " + p.em : p.n + " " + p.cap) };
  }
  function price() { var c = current(); M.count($("#price"), c ? c.price / 100 : 0, 500); }

  // ── минимальная сумма: меньше — красным, кнопка не нажимается ──
  function checkSum() {
    var low = S.me ? S.me.min_topup / 100 : 1, bad = S.amount > 0 && S.amount < low;
    $("#amountBox").classList.toggle("bad", bad);
    var h = $("#minHint"); h.classList.toggle("bad", bad);
    h.textContent = (bad ? t("lowSum") : t("minSum")) + " " + M.fmt(low) + " " + t("somoni");
    $("#topup").disabled = !S.amount || bad;
    $("#steps1").innerHTML = steps(1);
    return !!S.amount && !bad;
  }

  // ── баланс ──
  function setMe(d) {
    var old = S.me ? S.me.user.balance : null; S.me = d;
    $$("[data-name]").forEach(function (el) { el.textContent = d.name; });
    document.title = d.name;
    $("#myId").textContent = "ID · " + d.user.id;
    $$("[data-balance]").forEach(function (el) { M.count(el, d.user.balance / 100); });
    $("#supportBtn").hidden = !d.support;
    orders(); pending(); checkSum();
    return old;
  }
  function refresh() { return api("api/me").then(setMe).catch(function () {}); }

  // ── заказы ──
  function shareLink(token) {
    var link = "https://t.me/" + S.me.bot + "?start=g_" + token;
    var url = "https://t.me/share/url?url=" + encodeURIComponent(link) + "&text=" + encodeURIComponent(t("giftText"));
    if (TG && TG.openTelegramLink) TG.openTelegramLink(url); else window.open(url, "_blank");
  }
  function orders() {
    var box = $("#orderList"), rows = S.me.orders;
    if (!rows.length) { box.innerHTML = '<div class="empty">' + esc(t("empty")) + "</div>"; return; }
    box.innerHTML = rows.map(function (o) {
      var ico = /Stars/.test(o.title) ? "star" : /Premium/.test(o.title) ? "dia" : "gift";
      var pill = o.status === "done" ? '<span class="pill fill">' + t("st_done") + "</span>"
        : o.status === "fail" ? '<span class="pill"><svg class="i" style="width:14px;height:14px"><use href="#warn"/></svg>' + t("st_fail") + "</span>"
        : o.status === "wait" ? '<button class="pill fill" data-share="' + esc(o.token) + '"><svg class="i" style="width:14px;height:14px"><use href="#share"/></svg>' + t("st_wait") + "</button>"
        : '<span class="pill"><span class="dot"></span>' + t("st_work") + "</span>";
      return '<div class="card" data-oid="' + o.id + '"><span class="ico"><svg class="i"><use href="#' + ico + '"/></svg></span><div><div class="tt">' + esc(o.title) +
        '</div><div class="ss">№ ' + o.id + (o.to ? " · @" + esc(o.to) : "") + " · " + som(o.price) + ' с.</div></div><div class="r">' + pill + "</div></div>";
    }).join("");
  }

  // ── лист оплаты ──
  var close = null;
  // ── шаги пополнения: 1 сумма → 2 банк → 3 чек ──
  function steps(n) {
    return '<div class="steps" role="list">' + ["stepSum", "stepBank", "stepCheck"].map(function (k, i) {
      var st = i + 1 < n ? "done" : i + 1 === n ? "now" : "";
      return '<span role="listitem" class="' + st + '"' + (st === "now" ? ' aria-current="step"' : "") + "><i>" +
        (st === "done" ? '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>' : i + 1) + "</i>" + t(k) + "</span>";
    }).join("") + "</div>";
  }
  function sheet(html) {
    $("#payBody").innerHTML = html;
    if (!close || $("#pay").hidden) close = M.sheet($("#pay")); else M.stagger($("#pay"));
  }
  function methodsHtml(need, withBalance) {
    var bal = S.me.user.balance, out = "";
    if (withBalance) out += '<button class="card' + (bal >= need ? " sel" : "") + '" data-m="balance"' + (bal >= need ? "" : " disabled style=\"opacity:.45\"") +
      '><span class="ico"><svg class="i"><use href="#wallet"/></svg></span><span style="text-align:left"><span class="tt" style="display:block">' + t("fromBal") +
      '</span><span class="ss">' + (bal >= need ? t("instant") + " · " + som(bal) + " с." : t("lack") + " " + som(need - bal) + " с.") + "</span></span></button>";
    S.me.methods.forEach(function (m, i) {
      var sel = withBalance && !(bal >= need) && i === 0;   // при пополнении банк выбирает сам клиент
      out += '<button class="card' + (sel ? " sel" : "") + '" data-m="' + m.code + '"><span class="ico"><svg class="i"><use href="#' + (m.code === "card" ? "card" : "phone") +
        '"/></svg></span><span style="text-align:left"><span class="tt" style="display:block">' + esc(m.title) + '</span><span class="ss">' + t("transfer") + "</span></span></button>";
    });
    if (!S.me.methods.length && !withBalance) out += '<div class="empty">' + t("noMethods") + "</div>";
    return out;
  }
  function picked() { var b = $("#payBody [data-m].sel"); return b && b.dataset.m; }

  function openBuy() {
    var c = current(), who = $("#who"), v = who.value.trim().replace(/^@/, "").split("/").pop();
    if (!c) return;
    var needWho = S.tab !== "gifts" || v;
    if (needWho && !/^[A-Za-z][A-Za-z0-9_]{3,31}$/.test(v)) {
      M.shake(who); haptic("error");
      $("#whoHint").innerHTML = '<svg class="i" style="width:16px;height:16px"><use href="#warn"/></svg>' + esc(t("badWho"));
      return;
    }
    $("#whoHint").textContent = "";
    var item = Object.assign({}, c.item, { to: v ? "@" + v : "" });
    if (S.tab === "gifts") item.text = $("#note").value.trim();
    sheet('<div class="cap">' + t("payTitle") + '</div><div><span class="num" id="payNum">0</span> <b>' + t("somoni") + '</b></div><p class="muted">' +
      esc(c.title) + (v ? " · @" + esc(v) : "") + "</p>" + methodsHtml(c.price, true) + '<button class="btn" id="payGo">' + t("pay") + "</button>");
    M.count($("#payNum"), c.price / 100, 600);
    $("#payGo").onclick = function () {
      var m = picked(); if (!m) { M.toast(t("choose")); return; }
      if (m === "balance") return buy(item, c, v);
      api("api/topup", { method: m, intent: item }).then(function (d) { requisites(d.topup, true); }).catch(fail);
    };
  }
  function buy(item, c, v) {
    var btn = $("#payGo"); btn.disabled = true;
    api("api/order", item).then(function (d) {
      var was = S.me.user.balance; setMe(d); close && close();
      success(c.title, v, d.order, was, d.user.balance); haptic("success");
    }).catch(function (e) { btn.disabled = false; fail(e); });
  }
  function requisites(tp, intent) {
    sheet((intent ? "" : steps(3)) + '<div class="cap">' + t("sendExact") + '</div><div><span class="num">' + esc(tp.amount_text) + '</span> <b>' + t("somoni") + '</b></div>' +
      '<p class="muted">' + esc(tp.method) + " · № " + tp.id + '</p><div class="req" id="req">' + esc(tp.details) + "</div>" +
      '<button class="btn ghost" id="copyReq"><svg class="i"><use href="#copy"/></svg>' + t("copy") + "</button>" +
      '<label class="drop"><span class="ico"><svg class="i"><use href="#up"/></svg></span><span><span class="tt" style="display:block">' + t("attach") +
      '</span><span class="muted">' + t("attachSub") + '</span></span><input type="file" accept="image/*,application/pdf" id="rcpt"></label>' +
      (intent ? '<p class="muted">' + t("intentNote") + "</p>" : "") + '<p class="hint" id="rcptHint" role="status"></p>');
    $("#copyReq").onclick = function () {
      var txt = tp.details.replace(/[^\d+]/g, "").length >= 9 ? (tp.details.match(/\+?[\d ][\d ]{7,}\d/) || [tp.details])[0].replace(/\s/g, "") : tp.details;
      (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(function () { M.toast(t("copied")); }, function () { M.toast(txt); });
    };
    $("#rcpt").onchange = function (e) {
      var f = e.target.files[0]; if (!f) return;
      $("#rcptHint").textContent = "…";
      api("api/topup/" + tp.id + "/receipt", null, f).then(function () {
        haptic("success");
        sheet('<div style="display:flex;flex-direction:column;align-items:center;text-align:center;gap:12px;padding:10px 0"><div class="ok" style="background:#0B0B0B;color:#fff"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></div>' +
          '<div class="h1">' + t("sent") + '</div><p class="muted">' + t("wait") + '</p><button class="btn" id="closeSheet">OK</button></div>');
        $("#closeSheet").onclick = function () { close && close(); };
        refresh();
      }).catch(function (err) { haptic("error"); $("#rcptHint").innerHTML = '<svg class="i" style="width:16px;height:16px"><use href="#warn"/></svg>' + esc(err.message); e.target.value = ""; });
    };
  }
  function pending() {
    var tp = S.me.topup, box = $("#pendingBox");
    if (!tp) { box.innerHTML = ""; return; }
    box.innerHTML = '<div class="card"><span class="ico"><svg class="i"><use href="#clock"/></svg></span><div><div class="tt">№ ' + tp.id + " · " + esc(tp.amount_text) +
      ' с.</div><div class="ss">' + (tp.status === "pending" ? t("wait") : t("attach")) + '</div></div><div class="r">' +
      (tp.status === "waiting" ? '<button class="pill fill" id="resume">' + t("attach") + "</button>" : '<span class="pill"><span class="dot"></span>' + t("st_work") + "</span>") + "</div></div>";
    var r = $("#resume"); if (r) r.onclick = function () { requisites(tp, false); };
  }

  // ── успех ──
  function success(title, who, order, from, to) {
    var waiting = order.status === "wait";
    $("#okTitle").innerHTML = t(waiting ? "giftWait" : "done");
    $("#okSub").textContent = "№ " + order.id + (who ? " · @" + who : "");
    $("#okRows").innerHTML = [[t("item"), title], [t("to"), who ? "@" + who : "—"], [t("paid"), som(order.price) + " с."]]
      .map(function (r) { return '<div class="row"><span>' + esc(r[0]) + "</span><b>" + esc(r[1]) + "</b></div>"; }).join("") +
      '<div class="row"><span>Статус</span><span class="pill">' + t(waiting ? "st_wait" : "st_work") + "</span></div>";
    $("#okShare").hidden = !waiting;
    $("#okShare").onclick = function () { shareLink(order.token); };
    M.go("success"); M.success($('.page[data-page="success"]'), $("#okBal"), from / 100, to / 100);
  }
  function fail(e) { haptic("error"); M.toast(e.message || String(e)); }

  // ── админ-панель ──
  var A = { method: "alif" };
  var ST = { "new": "ждёт отправки поставщику", processing: "у поставщика", attention: "⚠ нет связи — проверьте у поставщика",
    paid: "подарок отправляется", sending: "подарок отправляется", awaiting_recipient: "ждёт, пока друг откроет ссылку",
    completed: "выполнен", sent: "подарок доставлен", failed: "возврат" };
  function admin() {
    return api("api/admin/summary").then(function (d) {
      M.count($("#aToday"), d.today.sum / 100); $("#aTodayN").textContent = d.today.n + " заказов";
      M.count($("#aWeek"), d.week.sum / 100); M.count($("#aUsers"), d.users);
      $("#aSup").textContent = d.supplier == null ? "нет ключа" : d.supplier; $("#aStars").textContent = d.bot_stars == null ? "—" : M.fmt(+d.bot_stars);
      var days = {}, max = 1; d.days.forEach(function (x) { days[x.d] = x.s; max = Math.max(max, x.s); });
      var bars = ""; for (var i = 6; i >= 0; i--) { var k = new Date(Date.now() - i * 864e5).toISOString().slice(0, 10), v = days[k] || 0;
        bars += '<i class="' + (i ? "soft" : "") + '" style="--h:' + Math.max(4, Math.round(v / max * 100)) + ";--i:" + (6 - i) + ';background:' + (i ? "rgba(255,255,255,.25)" : "#fff") + '"></i>'; }
      $("#aBars").innerHTML = bars;
      $("#aTopN").textContent = d.topups.length ? "· " + d.topups.length : "";
      $("#aTopups").innerHTML = d.topups.length ? d.topups.map(function (t) {
        return '<div class="card col" data-tid="' + t.id + '"><div style="display:flex;justify-content:space-between;gap:10px"><div><div class="tt">№ ' + t.id + " · " + som(t.amount) +
          ' с.</div><div class="ss">' + esc(t.who) + " · " + esc(t.method) + '</div><div class="ss">' + esc(t.card) + "</div>" + (t.ai ? '<div class="ss">ИИ: ' + esc(t.ai) + "</div>" : "") +
          '</div></div><div class="abtns"><button class="chip" data-a="see">Открыть чек</button><button class="chip sel" data-a="ok">Зачислить</button><button class="chip" data-a="no">Отклонить</button></div><div class="img"></div></div>';
      }).join("") : '<div class="empty">Чеков нет</div>';
      $("#aOrders").innerHTML = d.attention.length ? d.attention.map(function (o) {
        return '<div class="card col" data-aoid="' + o.id + '"><div class="tt">№ ' + o.id + " · " + esc(o.title) + (o.to ? " → @" + esc(o.to) : "") +
          '</div><div class="ss">' + esc(ST[o.status] || o.status) + " · " + som(o.price) + " с." + (o.supplier ? " · поставщик " + esc(o.supplier) : "") + "</div>" + (o.error ? '<div class="ss">' + esc(o.error) + "</div>" : "") +
          '<div class="abtns">' + (o.status === "attention" ? '<button class="chip" data-o="retry">Повторить</button>' : "") +
          '<button class="chip" data-o="done">Выполнен</button><button class="chip" data-o="refund">Вернуть деньги</button></div></div>';
      }).join("") : '<div class="empty">Всё выполнено</div>';
      $("#aRate").value = d.settings.rate; $("#aMarkup").value = d.settings.markup; $("#aGift").value = d.settings.gift_star; $("#aMin").value = d.settings.min_topup;
      $("#aCards").innerHTML = d.cards.length ? d.cards.map(function (c) {
        return '<div class="card"><span class="ico"><svg class="i"><use href="#' + (c.method === "card" ? "card" : "phone") + '"/></svg></span><div><div class="tt">' + esc(c.title) +
          '</div><div class="ss">' + esc(c.details) + '</div></div><div class="r"><button class="chip" data-coff="' + c.id + '">Выкл.</button></div></div>';
      }).join("") : '<div class="empty">Добавьте карту — без неё клиенты не смогут оплатить переводом</div>';
      $("#aMethod").innerHTML = d.methods.map(function (m) { return '<button class="chip' + (m.code === A.method ? " sel" : "") + '" data-am="' + m.code + '">' + esc(m.title) + "</button>"; }).join("");
    }).catch(fail);
  }
  function adminUser(q) {
    api("api/admin/user?q=" + encodeURIComponent(q)).then(function (d) {
      var u = d.user;
      $("#aUser").innerHTML = '<div class="card col"><div class="tt">' + esc(u.name) + (u.username ? " @" + esc(u.username) : "") + " · ID " + u.id +
        '</div><div class="ss">Баланс: <b>' + som(u.balance) + " с.</b>" + (u.banned ? " · заблокирован" : "") + "</div>" +
        '<div style="display:flex;gap:8px;margin-top:10px"><input class="field" id="aAmt" placeholder="+50 или -10" inputmode="decimal"><button class="chip" id="aAmtGo" style="height:56px;border-radius:18px">Провести</button></div>' +
        '<input class="field" id="aAmtNote" placeholder="Комментарий (клиент увидит)" style="margin-top:8px">' +
        '<div class="abtns"><button class="chip" id="aBan">' + (u.banned ? "Разблокировать" : "Заблокировать") + "</button></div>" +
        '<div class="ss" style="margin-top:10px">' + d.orders.map(function (o) { return "№ " + o.id + " " + esc(o.title) + " · " + esc(ST[o.status] || o.status); }).join("<br>") + "</div></div>";
      $("#aAmtGo").onclick = function () { api("api/admin/user/" + u.id, { amount: $("#aAmt").value, note: $("#aAmtNote").value }).then(function () { M.toast("Баланс изменён"); adminUser(String(u.id)); }).catch(fail); };
      $("#aBan").onclick = function () { api("api/admin/user/" + u.id, { banned: !u.banned }).then(function () { adminUser(String(u.id)); }).catch(fail); };
    }).catch(function (e) { M.shake($("#aFind")); fail(e); });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-a]");
    if (b) { var card = b.closest("[data-tid]"), id = card.dataset.tid;
      if (b.dataset.a === "see") {
        fetch("api/admin/receipt/" + id, { headers: { "X-Init-Data": TG.initData } }).then(function (r) { return r.blob(); }).then(function (bl) {
          var box = $(".img", card); box.innerHTML = bl.type === "application/pdf" ? '<a class="chip" target="_blank" href="' + URL.createObjectURL(bl) + '">PDF</a>' : '<img class="rimg" alt="Чек" src="' + URL.createObjectURL(bl) + '">';
        });
      } else {
        var ok = b.dataset.a === "ok", note = ok ? "" : (window.prompt("Причина отказа (клиент увидит):", "Перевод не найден") || "");
        api("api/admin/topup/" + id, { ok: ok, note: note }).then(function () { M.toast(ok ? "Зачислено" : "Отклонено"); haptic("success"); admin(); }).catch(fail);
      } }
    var o = e.target.closest("[data-o]");
    if (o) { var oid = o.closest("[data-aoid]").dataset.aoid, act = o.dataset.o;
      if (act === "refund" && !window.confirm("Вернуть деньги клиенту? Делайте это, только если у поставщика заказа точно нет.")) return;
      api("api/admin/order/" + oid, { action: act }).then(function () { M.toast("Готово"); admin(); }).catch(fail); }
    var off = e.target.closest("[data-coff]"); if (off) api("api/admin/cards/" + off.dataset.coff + "/off", {}).then(admin).catch(fail);
    var am = e.target.closest("[data-am]"); if (am) { A.method = am.dataset.am; $$("#aMethod .chip").forEach(function (x) { x.classList.toggle("sel", x === am); }); }
  });
  $("#aRefresh").onclick = admin;
  $("#aSave").onclick = function () { api("api/admin/settings", { rate: $("#aRate").value, markup: $("#aMarkup").value, gift_star: $("#aGift").value, min_topup: $("#aMin").value }).then(function () { M.toast("Цены сохранены"); refresh(); }).catch(fail); };
  $("#aAddCard").onclick = function () { api("api/admin/cards", { method: A.method, details: $("#aDetails").value }).then(function () { $("#aDetails").value = ""; M.toast("Карта добавлена"); admin(); refresh(); }).catch(function (e) { M.shake($("#aDetails")); fail(e); }); };
  $("#aFindGo").onclick = function () { var q = $("#aFind").value.trim(); if (q) adminUser(q); else M.shake($("#aFind")); };
  $('.page[data-page="admin"]')._enter = admin;

  // ── запуск ──
  if (TG) { try { TG.ready(); TG.expand(); TG.setHeaderColor("#FFFFFF"); TG.setBackgroundColor("#FFFFFF"); TG.disableVerticalSwipes && TG.disableVerticalSwipes(); } catch (e) {} }
  M.stagger(document);
  var placeBar = M.nav($(".nav"));
  M.seg($("#seg"), function (tab) { S.tab = tab; S.pick = tab === "stars" ? 1 : 0; items(); });
  $('.page[data-page="shop"]')._enter = function () { placeBar(); };
  $("#qty").addEventListener("input", function () { $$("#items .tile").forEach(function (x) { x.classList.remove("sel"); }); price(); });
  $("#me").onclick = function () { if (S.me && S.me.user.username) { $("#who").value = "@" + S.me.user.username; $("#whoHint").textContent = ""; } else if (S.tab === "gifts") { $("#who").value = ""; } else M.toast(t("badWho")); };
  $("#buy").onclick = openBuy;
  $("#lang").onclick = function () { S.lang = S.lang === "tj" ? "ru" : "tj"; texts(); api("api/lang", { lang: S.lang }).catch(function () {}); };
  $("#supportBtn").onclick = function () { var s = S.me.support; if (/^@/.test(s)) s = "https://t.me/" + s.slice(1); TG && TG.openTelegramLink && /t\.me/.test(s) ? TG.openTelegramLink(s) : window.open(s, "_blank"); };
  document.addEventListener("click", function (e) {
    var m = e.target.closest("[data-m]");
    if (m && !m.disabled) { $$("#payBody [data-m]").forEach(function (x) { x.classList.toggle("sel", x === m); }); var go = $("#tpGo"); if (go) go.disabled = false; haptic("success"); }
    var sh = e.target.closest("[data-share]"); if (sh) shareLink(sh.dataset.share);
    var bk = e.target.closest("[data-back]");
    if (bk) { $$(".nav button").forEach(function (x) { x.toggleAttribute("aria-current", false); if (x.dataset.go === bk.dataset.back) x.setAttribute("aria-current", "page"); }); M.go(bk.dataset.back, true); placeBar(); }
  });
  ["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "←"].forEach(function (k) {
    var b = document.createElement("button"); b.className = "key"; b.textContent = k; b.setAttribute("aria-label", k === "←" ? "⌫" : k);
    b.onclick = function () { S.amount = k === "←" ? Math.floor(S.amount / 10) : Math.min(50000, +(String(S.amount) + k)); M.count($("#amount"), S.amount, 300); checkSum(); };
    $("#keys").appendChild(b);
  });
  $("#topup").onclick = function () {
    if (!checkSum()) { M.shake($("#amountBox")); haptic("error"); return; }
    sheet(steps(2) + '<div><span class="num">' + M.fmt(S.amount) + '</span> <b>' + t("somoni") + '</b></div><div class="cap">' + t("pickBank") + "</div>" +
      methodsHtml(S.amount * 100, false) + (S.me.methods.length ? '<button class="btn" id="tpGo" disabled>' + t("next") + "</button>" : ""));
    var go = $("#tpGo"); if (go) go.onclick = function () {
      var m = picked(); if (!m) { M.toast(t("choose")); return; }
      api("api/topup", { method: m, amount: S.amount }).then(function (d) { requisites(d.topup, false); S.amount = 0; M.count($("#amount"), 0, 300); checkSum(); }).catch(fail);
    };
  };
  setInterval(function () { if (!document.hidden && S.me) refresh(); }, 15000);

  if (!TG || !TG.initData) { document.body.innerHTML = '<div class="page dark on" style="justify-content:center;align-items:center;text-align:center"><div class="h1">' + T.ru.open + "<br><br>" + T.tj.open + "</div></div>"; return; }
  api("api/me").then(function (d) {
    S.lang = d.user.lang || "tj"; setMe(d); texts();
    if (d.admin) { $("#navAdmin").hidden = false; placeBar(); if (location.hash === "#admin") $("#navAdmin").click(); }
  }).catch(function (e) { M.toast(e.message); });
})();
