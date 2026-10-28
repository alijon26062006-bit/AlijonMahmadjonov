/* Donatix: переходы внутри кабинета и админки без перезагрузки страницы.

   Ссылку начинаем грузить уже в момент касания; меняется только содержимое (<main>), а шапка, нижнее
   меню, боковое меню и фон стоят на месте — без белой вспышки и «прыжков». Подсветка в нижнем меню
   плавно переезжает к нажатой кнопке. «Назад» — мгновенно из памяти, свежие данные подтягиваются тихо.

   Страницы с таймерами и живыми графиками (оплата, номера, D-коин…) открываются как раньше — целиком:
   их скрипты рассчитаны на свежую страницу. Скрипт страницы, который умеет «уходить» сам (снимает
   свои таймеры через dxOnLeave), помечается data-soft. */
(function () {
  "use strict";
  if (window.dxNav && window.dxNav.alive()) return;
  var main = document.getElementById("main");
  if (!main || !document.querySelector(".shell") || !window.fetch || !window.DOMParser || !window.Promise ||
      !history.pushState || !window.URL || !window.FormData) return;

  var ROOTS = /^\/(panel|admin)(\/|$)/;
  var NEVER = /\/(data|push)\/|export|receipt|ticket-files|\/files?\/|\.(xlsx|csv|pdf|zip|png|jpe?g|webp|svg)$/i;
  var NO_PREFETCH = /notifications|\/api(\/|$)|ticket|skip|verify|\/save(\/|$)|\/telegram(\/|$)|logins/i;  // открытие что-то меняет
  var RISKY = /setInterval|requestAnimationFrame|EventSource|DOMContentLoaded|(?:document|window)\.addEventListener|location\.reload/;
  var TTL_PREFETCH = 20000, TTL_PAGE = 120000, MAX_PAGES = 12;
  var calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var layout = layoutOf(document), full = isFull(main), seq = 0, inflight = 0;
  var prefetched = {}, pages = {}, hooks = (window.dxLeaveQ || []).splice(0), here = bare(location.href);

  function bare(url) { return String(url).split("#")[0]; }
  // страницу переписали целиком (document.write) — этот экземпляр больше не отвечает, его сменит новый
  function alive() { return main.isConnected !== false && document.body.contains(main); }
  function layoutOf(doc) {
    var b = doc.body;
    return !b ? "" : b.classList.contains("adm") ? "adm" : b.classList.contains("cp") ? "cp" : "other";
  }
  function isFull(root) {
    if (!root || root.hasAttribute("data-full")) return true;
    var list = root.querySelectorAll("script:not([data-soft])");
    for (var i = 0; i < list.length; i++) {
      if (list[i].src || RISKY.test(list[i].textContent || "")) return true;
    }
    return false;
  }
  function urlOk(u) { return u.origin === location.origin && ROOTS.test(u.pathname) && !NEVER.test(u.pathname + u.search); }
  function linkOk(a) {
    if (typeof a.href !== "string" || a.hasAttribute("download") || a.hasAttribute("data-no-swap")) return null;
    if (a.target && a.target !== "_self") return null;
    var u = new URL(a.href, location.href);
    if (!urlOk(u)) return null;
    if (u.hash && bare(u.href) === here) return null;   // якорь на этой же странице — браузер сам
    return u;
  }

  // ── загрузка ──
  function request(url, init) {
    init = init || {};
    inflight++;
    return fetch(url, {method: init.method || "GET", body: init.body, credentials: "same-origin", redirect: "follow",
                       headers: {"X-DX-Nav": "1", "Accept": "text/html"}})
      .then(function (r) {
        var type = r.headers.get("content-type") || "";
        if (type.indexOf("text/html") < 0) { var e = new Error("not html"); e.url = r.url || url; throw e; }
        return r.text().then(function (html) { return {url: r.url || url, html: html, status: r.status}; });
      })
      .then(function (res) { inflight--; return res; }, function (err) { inflight--; throw err; });
  }
  function prefetch(url) {
    var hit = prefetched[url];
    if (hit && Date.now() - hit.t < TTL_PREFETCH) return;
    if (inflight > 2) return;
    var p = request(url);
    prefetched[url] = {t: Date.now(), p: p};
    p.catch(function () { if (prefetched[url] && prefetched[url].p === p) delete prefetched[url]; });
  }
  function take(url) {
    var hit = prefetched[url];
    delete prefetched[url];
    return hit && Date.now() - hit.t < TTL_PREFETCH ? hit.p : null;
  }
  function keep(url, html) {
    pages[bare(url)] = {t: Date.now(), html: html};
    var keys = Object.keys(pages);
    if (keys.length > MAX_PAGES) {
      keys.sort(function (a, b) { return pages[a].t - pages[b].t; });
      delete pages[keys[0]];
    }
  }

  // ── полоска загрузки сверху: только если ждём заметно ──
  var bar = document.getElementById("nav-progress");
  function barGo() { if (bar) { bar.classList.remove("done"); void bar.offsetWidth; bar.classList.add("go"); } }
  function barDone() { if (bar && bar.classList.contains("go")) { bar.classList.remove("go"); bar.classList.add("done"); } }

  // ── скрипты новой страницы ──
  function runScripts(root) {
    var list = Array.prototype.slice.call(root.querySelectorAll("script"));
    var chain = Promise.resolve();
    list.forEach(function (old) {
      var type = (old.getAttribute("type") || "").trim().toLowerCase();
      if (type && type !== "module" && !/(java|ecma)script$/.test(type)) return;   // JSON, speculationrules — не код
      chain = chain.then(function () {
        return new Promise(function (resolve) {
          var s = document.createElement("script");
          for (var i = 0; i < old.attributes.length; i++) s.setAttribute(old.attributes[i].name, old.attributes[i].value);
          if (old.src) { s.async = false; s.onload = s.onerror = function () { resolve(); }; }
          // в своём блоке: let/const страницы не столкнутся с прошлым заходом на неё же
          else s.textContent = type === "module" ? old.textContent : "{\n" + old.textContent + "\n}";
          old.parentNode.replaceChild(s, old);
          if (!old.src) resolve();
        });
      });
    });
    return chain;
  }
  function leave() {
    var list = hooks.splice(0);
    for (var i = 0; i < list.length; i++) { try { list[i](); } catch (e) {} }
  }

  // ── шапка, меню и нижняя панель: только то, что зависит от страницы ──
  function swapInner(sel, doc) {
    var a = document.querySelector(sel), b = doc.querySelector(sel);
    if (a && b) a.innerHTML = b.innerHTML;
  }
  function syncShell(doc, url) {
    swapInner("#side .side-scroll", doc);
    swapInner(".adm-rail", doc);
    var bell = document.getElementById("dx-bell"), nb = doc.getElementById("dx-bell");
    if (bell && nb) bell.replaceWith(document.importNode(nb, true));
    document.querySelectorAll(".cp-search input[name=q], .adm-search input[name=q]").forEach(function (inp) {
      if (inp === document.activeElement) return;
      var fresh = doc.querySelector(inp.closest(".cp-search") ? ".cp-search input[name=q]" : ".adm-search input[name=q]");
      inp.value = fresh ? fresh.value : "";
    });
    var u = new URL(url), back = u.pathname + u.search;
    document.querySelectorAll("#cur-sheet a[href^='/currency/']").forEach(function (a) {   // выбор валюты вернёт сюда
      var l = new URL(a.getAttribute("href"), location.href);
      l.searchParams.set("next", back);
      a.setAttribute("href", l.pathname + l.search);
    });
    var d = dock(), nd = doc.querySelector(".tabbar");
    if (d && nd) {
      var on = {};
      Array.prototype.forEach.call(nd.children, function (a) { if (a.tagName === "A" && a.classList.contains("on")) on[a.getAttribute("href")] = 1; });
      Array.prototype.forEach.call(d.children, function (a) { if (a.tagName === "A") a.classList.toggle("on", !!on[a.getAttribute("href")]); });
      placeInd(true);
    }
  }
  function closeOverlays() {
    if (document.documentElement.classList.contains("menu-open") && window.dxMenu) window.dxMenu(false);
    document.querySelectorAll(".adm-plus[open]").forEach(function (x) { x.removeAttribute("open"); });
    var cs = document.getElementById("cur-sheet");
    try { if (cs && cs.matches(":popover-open")) cs.hidePopover(); } catch (e) {}
    if (cs) cs.classList.remove("open");
  }
  function jump(y) {   // без плавной прокрутки: страница должна сразу открыться сверху
    var h = document.documentElement, was = h.style.scrollBehavior;
    h.style.scrollBehavior = "auto";
    window.scrollTo(0, y || 0);
    h.style.scrollBehavior = was;
  }
  function focusOf() {
    var a = document.activeElement;
    if (!a || !main.contains(a) || !(a.id || a.name)) return null;
    var f = {id: a.id, name: a.name, tag: a.tagName};
    try { f.start = a.selectionStart; f.end = a.selectionEnd; } catch (e) {}
    return f;
  }
  function refocus(f) {
    if (!f) return false;
    var el = f.id ? document.getElementById(f.id) : main.querySelector(f.tag + "[name='" + f.name.replace(/'/g, "") + "']");
    if (!el || !main.contains(el)) return false;
    el.focus({preventScroll: true});
    try { if (f.start != null) el.setSelectionRange(f.start, f.end); } catch (e) {}
    return true;
  }

  // ── главное: показать новую страницу ──
  function replaceMain(fresh, opt) {
    opt = opt || {};
    var keepFocus = opt.keepFocus ? focusOf() : null;
    leave();
    for (var i = main.attributes.length - 1; i >= 0; i--) {
      if (main.attributes[i].name !== "id") main.removeAttribute(main.attributes[i].name);
    }
    for (var j = 0; j < fresh.attributes.length; j++) {
      if (fresh.attributes[j].name !== "id") main.setAttribute(fresh.attributes[j].name, fresh.attributes[j].value);
    }
    var frag = document.createDocumentFragment();
    while (fresh.firstChild) frag.appendChild(document.adoptNode(fresh.firstChild));
    main.textContent = "";
    main.appendChild(frag);
    main.querySelectorAll("[data-reveal]").forEach(function (el) { el.classList.add("in", "shown", "visible"); });
    full = isFull(main);
    var done = runScripts(main);
    if (!refocus(keepFocus) && opt.focus) {
      main.setAttribute("tabindex", "-1");
      main.focus({preventScroll: true});
    }
    return done;
  }
  function show(doc, fresh, url, opt) {
    var update = function () {
      try { return apply(); } catch (e) { hard(url); }
    };
    var apply = function () {
      closeOverlays();
      document.title = doc.title;
      if (opt.history) history[opt.history]({dx: 1, y: 0}, "", url);
      here = bare(location.href);
      var done = replaceMain(fresh, {keepFocus: opt.keepFocus, focus: !opt.quiet && !opt.keepFocus});
      syncShell(doc, url);
      if (!opt.keepScroll) {
        var hash = new URL(url).hash, target = hash && document.getElementById(decodeURIComponent(hash.slice(1)));
        if (target) target.scrollIntoView(); else jump(opt.y);
      }
      document.dispatchEvent(new CustomEvent("dx:enter", {detail: {url: url}}));
      return done;
    };
    if (!opt.quiet && !calm && document.startViewTransition) {
      try { document.startViewTransition(update); return; } catch (e) {}
    }
    update();
    if (!opt.quiet && !calm && main.animate) {
      main.animate([{opacity: 0, transform: "translateY(4px)"}, {opacity: 1, transform: "none"}],
                   {duration: 220, easing: "cubic-bezier(.16, 1, .3, 1)"});
    }
  }
  function hard(url) { location.assign(url); }
  function render(html, url, opt) {
    var doc = new DOMParser().parseFromString(html, "text/html"), fresh = doc.getElementById("main");
    if (!fresh || layoutOf(doc) !== layout || isFull(fresh)) return false;
    ++seq;
    show(doc, fresh, url, {history: bare(url) === here ? "replaceState" : "pushState", y: 0});
    pages = {}; prefetched = {};
    keep(url, html);
    return true;
  }
  function remember() {
    try { history.replaceState(Object.assign({}, history.state || {}, {dx: 1, y: window.scrollY}), ""); } catch (e) {}
  }

  function visit(url, opt) {
    opt = opt || {};
    var my = ++seq;
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    if (!opt.pop) remember();
    var slow = setTimeout(barGo, 160);
    var cached = opt.pop && pages[bare(url)] && Date.now() - pages[bare(url)].t < TTL_PAGE ? pages[bare(url)] : null;
    var p = cached ? Promise.resolve({url: url, html: cached.html, cached: true})
                   : opt.body ? request(url, {method: opt.method, body: opt.body}) : take(bare(url)) || request(url);
    return p.then(function (res) {
      if (my !== seq) return;
      clearTimeout(slow);
      var doc = new DOMParser().parseFromString(res.html, "text/html");
      var fresh = doc.getElementById("main");
      if (!fresh || layoutOf(doc) !== layout || isFull(fresh)) { hard(res.url || url); return; }
      var final = res.url || url;
      if (new URL(url).hash && !new URL(final).hash) final = bare(final) + new URL(url).hash;
      var hist = opt.pop ? null : (opt.body && bare(final) === here) || opt.replace ? "replaceState" : "pushState";
      show(doc, fresh, final, {history: hist, y: opt.y, keepFocus: opt.keepFocus});
      if (opt.body) { pages = {}; prefetched = {}; }   // после действия данные на других страницах тоже могли поменяться
      if (!res.cached) keep(final, res.html);
      barDone();
      if (res.cached && Date.now() - cached.t > 8000) refresh(final, my);
    }).catch(function (err) {
      if (my !== seq) return;
      clearTimeout(slow);
      barDone();
      if (opt.body && !(err && err.url)) {
        if (opt.unlock) opt.unlock();
        note("Нет связи — проверьте интернет и нажмите ещё раз.");
        return;
      }
      hard((err && err.url) || url);
    });
  }
  // «Назад» показали из памяти — свежую версию подменяем тихо, без анимации и прокрутки
  function refresh(url, my) {
    request(url).then(function (res) {
      if (my !== seq || bare(res.url) !== here) return;
      var doc = new DOMParser().parseFromString(res.html, "text/html"), fresh = doc.getElementById("main");
      if (!fresh || layoutOf(doc) !== layout || isFull(fresh)) return;
      keep(res.url, res.html);
      if (fresh.innerHTML === main.innerHTML) return;
      show(doc, fresh, location.href, {quiet: true, keepScroll: true, keepFocus: true});
    }).catch(function () {});
  }
  function note(text) {
    var f = document.createElement("div");
    f.className = "flash error"; f.setAttribute("role", "alert");
    f.innerHTML = "<span></span>"; f.firstChild.textContent = text;
    main.insertBefore(f, main.firstChild);
    jump(0);
  }

  // ── нижнее меню: подсветка нажатой кнопки сразу; в админке «таблетка» плавно едет к ней ──
  function dock() { return document.querySelector(".tabbar"); }
  function placeInd(animate) {
    var d = dock();
    if (!d) return;
    var ind = d.querySelector(".dock-ind");
    if (!ind) return;
    var on = null;
    Array.prototype.forEach.call(d.children, function (a) { if (!on && a.tagName === "A" && a.classList.contains("on") && !a.classList.contains("tab-main")) on = a; });
    if (!on || !d.offsetWidth || !on.offsetWidth) { ind.style.opacity = "0"; d.classList.toggle("has-ind", !!on && !!d.offsetWidth); return; }
    var box = {x: on.offsetLeft, y: on.offsetTop, w: on.offsetWidth, h: on.offsetHeight};
    if (!animate || calm) ind.style.transition = "none";
    ind.style.transform = "translate(" + box.x + "px, " + box.y + "px)";
    ind.style.width = box.w + "px"; ind.style.height = box.h + "px"; ind.style.opacity = "1";
    d.classList.add("has-ind");
    if (!animate || calm) { void ind.offsetWidth; ind.style.transition = ""; }
    try { sessionStorage.setItem("dx-dock", JSON.stringify(box)); } catch (e) {}
  }
  function pressDock(a) {
    var d = dock();
    if (!d || a.parentNode !== d || a.classList.contains("tab-main")) return;
    Array.prototype.forEach.call(d.children, function (x) { if (x.tagName === "A") x.classList.toggle("on", x === a); });
    placeInd(true);
  }
  (function initDock() {   // после полной загрузки — начинаем с места прошлой кнопки и плывём к новой
    var d = dock(), ind = d && d.querySelector(".dock-ind"), last = null;
    if (!ind) return;
    try { last = JSON.parse(sessionStorage.getItem("dx-dock") || "null"); } catch (e) {}
    if (last && !calm) {
      ind.style.transition = "none";
      ind.style.transform = "translate(" + last.x + "px, " + last.y + "px)";
      ind.style.width = last.w + "px"; ind.style.height = last.h + "px"; ind.style.opacity = "1";
      d.classList.add("has-ind");
      void ind.offsetWidth; ind.style.transition = "";
      requestAnimationFrame(function () { requestAnimationFrame(function () { placeInd(true); }); });
    } else placeInd(false);
    window.addEventListener("resize", function () { if (alive()) placeInd(false); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { placeInd(false); });
  })();

  // ── перехват нажатий ──
  function intent(e) {
    if (full || !alive() || !e.target.closest) return;
    var a = e.target.closest("a[href]"), u = a && linkOk(a);
    if (u && !NO_PREFETCH.test(u.pathname)) prefetch(bare(u.href));
  }
  window.addEventListener("pointerdown", intent, {passive: true, capture: true});
  window.addEventListener("touchstart", intent, {passive: true, capture: true});
  var hover = null;
  window.addEventListener("mouseover", function (e) {
    clearTimeout(hover);
    hover = setTimeout(function () { intent(e); }, 90);
  }, {passive: true});

  window.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || full || !alive() || !e.target.closest) return;
    var a = e.target.closest("a[href]"), u = a && linkOk(a);
    if (!u) return;
    e.preventDefault();
    pressDock(a);
    visit(u.href, {});
  });

  window.addEventListener("submit", function (e) {
    var f = e.target, sub = e.submitter;
    if (e.defaultPrevented || full || !alive() || !(f instanceof HTMLFormElement) || f.hasAttribute("data-no-swap")) return;
    var method = ((sub && sub.getAttribute("formmethod")) || f.getAttribute("method") || "get").toLowerCase();
    var target = (sub && sub.getAttribute("formtarget")) || f.getAttribute("target");
    if (method === "dialog" || (target && target !== "_self")) return;
    var u = new URL((sub && sub.getAttribute("formaction")) || f.getAttribute("action") || location.href, location.href);
    if (!urlOk(u)) return;
    var data;
    try { data = sub ? new FormData(f, sub) : new FormData(f); } catch (er) {
      data = new FormData(f);
      if (sub && sub.name) data.append(sub.name, sub.value);
    }
    e.preventDefault();
    var a = document.activeElement;
    if (a && a.closest && a.closest(".cp-search, .adm-search")) a.blur();   // поиск в шапке: убрать клавиатуру
    if (method === "get") {
      var q = new URLSearchParams();
      data.forEach(function (v, k) { if (typeof v === "string") q.append(k, v); });
      u.search = q.toString();
      var live = f.hasAttribute("data-live-search");
      visit(u.href, {replace: live, keepFocus: live});
      return;
    }
    var lock = [].slice.call(f.querySelectorAll("button, input[type=submit]")).filter(function (b) { return !b.disabled; });
    lock.forEach(function (b) { b.disabled = true; b.setAttribute("aria-busy", "true"); });
    var unlock = function () { lock.forEach(function (b) { b.disabled = false; b.removeAttribute("aria-busy"); }); };
    visit(u.href, {method: "POST", body: data, unlock: unlock}).then(function () { if (f.isConnected) unlock(); });
  });

  window.addEventListener("popstate", function (e) {
    if (!alive() || bare(location.href) === here) return;   // только якорь
    var y = e.state && typeof e.state.y === "number" ? e.state.y : 0;
    if (full) { location.reload(); return; }
    visit(location.href, {pop: true, y: y});
  });

  // отметка текущей записи истории: «Назад» вернёт и прокрутку
  try { history.replaceState(Object.assign({}, history.state || {}, {dx: 1, y: window.scrollY}), ""); } catch (e) {}

  window.dxOnLeave = function (fn) { if (typeof fn === "function") hooks.push(fn); };
  window.dxLeaveQ = [];
  window.dxNav = {
    alive: alive,
    render: function (html, url) { return alive() && render(html, url); },
    visit: function (url) { var u = new URL(url, location.href); if (urlOk(u) && !full) visit(u.href, {}); else hard(u.href); },
    replaceMain: function (fresh) { return replaceMain(fresh, {keepFocus: true}); },
    handles: function (a) { return alive() && !full && !!linkOk(a); },
    handlesForm: function (f) {
      if (!alive() || full || f.hasAttribute("data-no-swap")) return false;
      var t = f.getAttribute("target");
      if ((f.getAttribute("method") || "").toLowerCase() === "dialog" || (t && t !== "_self")) return false;
      return urlOk(new URL(f.getAttribute("action") || location.href, location.href));
    },
    leave: leave,
  };
})();
