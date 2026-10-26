// Голосовой помощник админки: шарик в поиске.
//
// Два режима:
//  • «Живой голос» — голосовой режим OpenAI (как в ChatGPT): браузер говорит с OpenAI напрямую (WebRTC)
//    по одноразовому ключу с нашего сервера. Строгая очередь: вы говорите — он слушает; он говорит —
//    микрофон молчит (не перебивает сам себя из-за эха и шума). Перебить — нажать на шар.
//  • «Обычный» — запись → наш сервер → ответ голосом. Перед ответом микрофон отпускается — так на iPhone
//    голос идёт в громкий динамик, а не в разговорный. На iPhone этот режим — по умолчанию.
// Живой не соединился за ~9 с (мобильный интернет его не пропускает) — сами переходим на обычный
// и 12 часов не пробуем. Ответ не пришёл — говорим об этом, а не висим. Режим можно сменить кнопкой.
(function () {
  "use strict";
  var trig = document.querySelector("[data-voice]"), box = document.getElementById("vo");
  if (!trig || !box) return;
  var IOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var csrf = box.dataset.csrf, orb = box.querySelector(".vo-orb"), stateEl = box.querySelector(".vo-state"),
      you = box.querySelector(".vo-you"), bot = box.querySelector(".vo-bot"), micBtn = box.querySelector(".vo-mic"),
      typeForm = box.querySelector(".vo-type"), modeEl = box.querySelector(".vo-mode-t"), modeBtn = box.querySelector(".vo-mode-b");
  var ctx = null, stream = null, micAn = null, outAn = null, raf = 0, state = "idle", stateAt = 0, muted = false;
  var rec = null, chunks = [], src = null, history = [], turn = 0;                        // обычный режим
  var pc = null, dc = null, remoteEl = null, rt = false, textBuf = "", goAfter = null, lastOut = 0, lastTalk = 0,
      needTap = false, dropTimer = 0, speakAt = 0, endTimer = 0;                          // живой голос
  var PREF = "dx-voice-mode", FAIL = "dx-voice-live-fail", HOUR = 36e5, liveNow = false;
  // На iPhone звук Web Audio молчит, если включён беззвучный режим, а обычный проигрыватель — нет. Проигрыватель
  // «разблокируем» при нажатии на шар (беззвучной записью), дальше ответы играют через него.
  var player = null, SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
  function unlockPlayer() {
    if (!IOS) return;
    player = player || new Audio();
    player.setAttribute("playsinline", "");
    player.src = SILENCE;
    var p = player.play(); if (p && p.catch) p.catch(function () {});
  }
  function audioSession(type) { try { if (navigator.audioSession) navigator.audioSession.type = type; } catch (e) {} }
  try { history = JSON.parse(sessionStorage.getItem("dx-voice") || "[]") || []; } catch (e) { history = []; }
  var TEXT = { idle: "Нажмите на шар и говорите", listening: "Слушаю…", thinking: "Думаю…", speaking: "Говорю…",
               muted: "Микрофон выключен — нажмите на шар или напишите вопрос", connecting: "Подключаюсь…" };

  function store(k, v) { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }
  function read(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function pref() { return read(PREF) || (IOS ? "plain" : "live"); }
  function liveAllowed() { return pref() === "live" && Date.now() - (+read(FAIL) || 0) > 12 * HOUR && !!window.RTCPeerConnection; }
  function showMode(text, live) {   // кнопка всегда предлагает другой режим, чем тот, что сейчас
    liveNow = !!live;
    if (modeEl) modeEl.textContent = text;
    if (modeBtn) modeBtn.textContent = live ? "перейти на обычный" : "попробовать живой голос";
  }
  function set(s, note) {
    if (state !== s) stateAt = performance.now();
    state = s; box.dataset.state = s === "connecting" ? "thinking" : s; stateEl.textContent = note || TEXT[s];
  }
  function level(an) {
    var a = new Uint8Array(an.fftSize), sum = 0;
    an.getByteTimeDomainData(a);
    for (var i = 0; i < a.length; i++) { var v = (a[i] - 128) / 128; sum += v * v; }
    return Math.sqrt(sum / a.length);
  }
  function timeout(p, ms, msg) {
    return Promise.race([p, new Promise(function (_, bad) { setTimeout(function () { bad(new Error(msg)); }, ms); })]);
  }
  function post(url, data, ms) {
    var fd = new FormData(), ctl = window.AbortController ? new AbortController() : null;
    fd.append("csrf", csrf);
    Object.keys(data || {}).forEach(function (k) { fd.append(k, data[k]); });
    var t = ctl && setTimeout(function () { ctl.abort(); }, ms || 20000);
    return fetch(url, { method: "POST", body: fd, credentials: "same-origin", signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.json(); })
      .finally(function () { clearTimeout(t); });
  }

  function loop() {   // анимация шара, «говорит / слушает» в живом режиме и сторож от зависаний
    var now = performance.now(), lin = micAn && !muted && state === "listening" ? level(micAn) : 0,
        lout = outAn ? level(outAn) : 0, l = 0;
    if (rt) {
      if (lout > 0.02) { lastOut = now; if (state !== "speaking") speaking(); }
      else if (state === "speaking" && outAn && now - lastOut > 900) spoke();
      if (now - lastTalk > 180000) { close(); return; }   // 3 минуты тишины — отключаемся, чтобы не тратить деньги
    }
    if (state === "thinking" && now - stateAt > (rt ? 15000 : 45000)) {   // ответ не пришёл
      turn++;
      set(rt ? (muted ? "muted" : "listening") : "idle", "Ответ не пришёл — проверьте интернет и спросите ещё раз");
    }
    if (state === "speaking" && now - stateAt > 90000) spoke();
    if (state === "listening") l = lin * 5;
    else if (state === "speaking") l = outAn ? lout * 3.5 : 0.35 + 0.25 * Math.sin(now / 160);   // нет звука для замера — просто «дышит»
    box.style.setProperty("--lvl", Math.max(0, Math.min(1, l)).toFixed(3));
    raf = requestAnimationFrame(loop);
  }
  function mic() {
    if (stream && stream.getAudioTracks().some(function (t) { return t.readyState === "live"; })) return Promise.resolve(stream);
    if (IOS) audioSession("auto");
    return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      .then(function (s) {
        stream = s;
        try { micAn = ctx.createAnalyser(); micAn.fftSize = 1024; ctx.createMediaStreamSource(s).connect(micAn); } catch (e) { micAn = null; }
        return s;
      });
  }
  function micOff() {
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null; micAn = null;
  }
  function go() { var url = goAfter; goAfter = null; if (url && url !== location.pathname + location.search) location.href = url; }

  // ── Живой голос (как в ChatGPT) ─────────────────────────────
  function realtime() {
    return timeout(post("/admin/assistant/realtime", {}, 10000), 10000, "наш сервер долго не отвечает").then(function (t) {
      if (!t.ok) throw new Error(t.error || "нет ключа");
      return mic().then(function () {
        pc = new RTCPeerConnection();
        if (!remoteEl) {   // на iPhone звук играет только элемент, который стоит на странице
          remoteEl = document.createElement("audio");
          remoteEl.className = "vo-audio"; remoteEl.autoplay = true; remoteEl.setAttribute("playsinline", "");
          box.appendChild(remoteEl);
        }
        pc.ontrack = function (e) {
          remoteEl.srcObject = e.streams[0];
          playRemote();
          if (!IOS) { try { outAn = ctx.createAnalyser(); outAn.fftSize = 1024; ctx.createMediaStreamSource(e.streams[0]).connect(outAn); } catch (er) { outAn = null; } }
        };
        stream.getTracks().forEach(function (tr) { pc.addTrack(tr, stream); });
        dc = pc.createDataChannel("oai-events");
        var opened = new Promise(function (ok) { dc.onopen = ok; });
        dc.onmessage = function (m) { var ev; try { ev = JSON.parse(m.data); } catch (er) { return; } onEvent(ev); };
        pc.onconnectionstatechange = function () {
          var s = pc && pc.connectionState;
          if (!rt) return;
          if (s === "failed" || s === "closed") lost();
          else if (s === "disconnected") { clearTimeout(dropTimer); dropTimer = setTimeout(function () { if (rt && pc && pc.connectionState !== "connected") lost(); }, 5000); }
        };
        return pc.createOffer()
          .then(function (offer) { return pc.setLocalDescription(offer).then(function () { return offer; }); })
          .then(function (offer) {
            var url = t.mode === "beta" ? "https://api.openai.com/v1/realtime?model=" + encodeURIComponent(t.model)
                                        : "https://api.openai.com/v1/realtime/calls";
            return timeout(fetch(url, { method: "POST", body: offer.sdp,
                                        headers: { "Authorization": "Bearer " + t.key, "Content-Type": "application/sdp" } }),
                           10000, "OpenAI долго не отвечает");
          })
          .then(function (r) { if (!r.ok) throw new Error("OpenAI ответил " + r.status); return r.text(); })
          .then(function (sdp) { return pc.setRemoteDescription({ type: "answer", sdp: sdp }); })
          .then(function () { return timeout(opened, 9000, "интернет не пропускает живой голос"); })
          .then(function () {
            rt = true; lastTalk = performance.now(); store(FAIL, null);
            showMode("Режим: живой голос (как в ChatGPT)", true);
            micTrack(!muted);
            set(muted ? "muted" : "listening");
          });
      });
    });
  }
  function micTrack(on) { if (stream) stream.getAudioTracks().forEach(function (t) { t.enabled = on; }); }
  function playRemote() {
    if (!remoteEl) return;
    var p = remoteEl.play();
    if (p && p.catch) p.catch(function () { needTap = true; stateEl.textContent = "Нажмите на шар, чтобы включить звук"; });
  }
  function speaking() {   // он говорит — микрофон молчит
    lastOut = performance.now();
    if (state !== "speaking") speakAt = lastOut;
    micTrack(false); set("speaking");
  }
  function spoke() {
    clearTimeout(endTimer);
    if (state !== "speaking") return;
    if (rt) micTrack(!muted);
    set(muted ? "muted" : "listening");
    if (goAfter) go();
  }
  function rtSend(obj) { if (dc && dc.readyState === "open") dc.send(JSON.stringify(obj)); }
  function onEvent(ev) {
    switch (ev.type) {
      case "input_audio_buffer.speech_started":
        lastTalk = performance.now(); if (state !== "speaking") set("listening"); break;
      case "input_audio_buffer.speech_stopped":
        if (state !== "speaking") set("thinking"); break;
      case "conversation.item.input_audio_transcription.completed":
        if (ev.transcript) you.textContent = "Вы: " + String(ev.transcript).trim(); break;
      case "response.created":
        textBuf = ""; if (state !== "speaking") set("thinking"); break;
      case "response.output_audio_transcript.delta": case "response.audio_transcript.delta":
        if (state === "thinking") speaking();   // слова пошли — значит, и голос пошёл
        textBuf += ev.delta || ""; bot.textContent = textBuf; break;
      case "response.output_text.delta": case "response.text.delta":
        textBuf += ev.delta || ""; bot.textContent = textBuf; break;
      case "output_audio_buffer.started":
        speaking(); break;
      case "output_audio_buffer.stopped": case "output_audio_buffer.cleared":
        spoke(); break;
      case "response.done":
        if (state === "thinking" && !(ev.response && (ev.response.output || []).some(function (o) { return o.type === "function_call"; })))
          set(muted ? "muted" : "listening");   // ответил без звука (или только текстом)
        else if (state === "speaking" && !outAn) {   // замерить звук нечем (iPhone) — конец речи по длине текста
          clearTimeout(endTimer);
          endTimer = setTimeout(spoke, Math.max(900, speakAt + textBuf.length * 70 - performance.now()));
        }
        break;
      case "response.function_call_arguments.done":
        tool(ev); break;
      case "error":
        if (ev.error && ev.error.message) bot.textContent = ev.error.message; break;
    }
  }
  function tool(ev) {
    post("/admin/assistant/tool", { name: ev.name || "", args: ev.arguments || "{}" }, 15000)
      .catch(function () { return { output: { error: "нет связи с сайтом" } }; })
      .then(function (j) {
        if (j.go) { goAfter = j.go; setTimeout(function () { if (goAfter && state !== "speaking") go(); }, 7000); }
        rtSend({ type: "conversation.item.create",
                 item: { type: "function_call_output", call_id: ev.call_id, output: JSON.stringify(j.output || {}) } });
        rtSend({ type: "response.create" });
      });
  }
  function rtStop() {
    rt = false;
    clearTimeout(dropTimer); clearTimeout(endTimer);
    if (dc) { try { dc.close(); } catch (e) {} dc = null; }
    if (pc) { try { pc.close(); } catch (e) {} pc = null; }
    if (remoteEl) remoteEl.srcObject = null;
    outAn = null;
  }
  function lost() {   // связь с живым голосом пропала посреди разговора — продолжаем в обычном режиме
    rtStop(); store(FAIL, String(Date.now()));
    showMode("Режим: обычный — связь с живым голосом прервалась");
    set("idle"); listen();
  }

  // ── Обычный режим: запись → ответ → голос ──────────────────
  function mime() {
    var t = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
    for (var i = 0; i < t.length; i++) if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t[i])) return t[i];
    return "";
  }
  function listen() {
    if (box.hidden || rt) return;
    if (muted) { set("muted"); return; }
    if (!navigator.mediaDevices || !window.MediaRecorder) { set("idle", "Этот браузер не записывает голос — напишите вопрос"); return; }
    var my = turn;
    mic().then(function () {
      if (box.hidden || rt || my !== turn) return;
      var type = mime();
      chunks = [];
      try { rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined); }
      catch (e) { set("idle", "Не получилось включить запись — напишите вопрос"); return; }
      var r = rec;
      r.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      r.onstop = function () {
        var blob = new Blob(chunks, { type: r.mimeType || type || "audio/webm" });
        if (rec === r) rec = null;
        if (r._send && blob.size > 1200) send(blob);
        else if (state === "listening") set(muted ? "muted" : "idle");
      };
      r.start(250);
      set("listening");
      // Порог под шум вокруг: первые 0,4 с слушаем тишину, речь — заметно громче неё
      var t0 = performance.now(), noise = 0, n = 0, th = 0.03, loud = 0, last = 0, voiced = false;
      (function vad() {
        if (rec !== r || state !== "listening") return;
        var l = micAn ? level(micAn) : 0.05, now = performance.now();
        if (now - t0 < 400) { noise += l; n++; th = Math.max(0.012, Math.min(0.06, (noise / n) * 2.2 + 0.008)); }
        else if (l > th) { loud += 60; last = now; if (loud >= 180) voiced = true; }
        else if (!voiced) loud = Math.max(0, loud - 30);
        if (voiced && now - last > 1100) return stop(true);       // замолчали — отправляем
        if (!voiced && now - t0 > 10000) return stop(false);      // 10 с ничего не сказали — ждём нажатия
        if (now - t0 > 30000) return stop(true);
        setTimeout(vad, 60);
      })();
    }).catch(function () {
      set("idle", "Нет доступа к микрофону — разрешите его в настройках браузера или напишите вопрос");
    });
  }
  function stop(sendIt) { if (rec && rec.state !== "inactive") { rec._send = sendIt; rec.stop(); } }
  function send(blob, text) {
    var my = ++turn;
    set("thinking");
    if (text) { you.textContent = "Вы: " + text; bot.textContent = ""; }
    if (IOS) micOff();   // на iPhone, пока включён микрофон, звук идёт в разговорный динамик — тихо
    var data = { history: JSON.stringify(history.slice(-8)), page: location.pathname + location.search };
    if (text) data.text = text;
    var fd = new FormData();
    fd.append("csrf", csrf);
    Object.keys(data).forEach(function (k) { fd.append(k, data[k]); });
    if (blob) fd.append("audio", blob, "voice." + (/mp4/.test(blob.type) ? "mp4" : /ogg/.test(blob.type) ? "ogg" : "webm"));
    var ctl = window.AbortController ? new AbortController() : null, t = ctl && setTimeout(function () { ctl.abort(); }, 45000);
    fetch("/admin/assistant/ask", { method: "POST", body: fd, credentials: "same-origin", signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.json(); })
      .catch(function () { return { ok: false, error: "Нет связи с сайтом или ответ долго не приходит — проверьте интернет" }; })
      .then(function (j) {
        clearTimeout(t);
        if (box.hidden || my !== turn) return;
        if (!j.ok) { bot.textContent = j.error || "Не получилось"; set("idle", "Нажмите на шар и спросите ещё раз"); return; }
        if (j.silent) { listen(); return; }
        you.textContent = "Вы: " + j.heard;
        bot.textContent = j.reply;
        history.push({ role: "user", text: j.heard }, { role: "assistant", text: j.reply });
        history = history.slice(-12);
        try { sessionStorage.setItem("dx-voice", JSON.stringify(history)); } catch (e) {}
        say(j.audio).then(function () {
          if (box.hidden || my !== turn) return;
          if (j.go) { goAfter = j.go; go(); return; }
          listen();
        });
      });
  }
  function say(b64) {
    return new Promise(function (done) {
      if (!b64 || box.hidden) return done();
      var finished = false, safety = 0;
      var end = function () { if (finished) return; finished = true; clearTimeout(safety); src = null; outAn = null; done(); };
      var bin = atob(b64), buf = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
      var viaElement = function () {   // обычный проигрыватель: на iPhone — всегда (громко и в беззвучном режиме)
        var a = player || new Audio();
        if (IOS) audioSession("playback");
        a.onended = end; a.onerror = end;
        a.src = "data:audio/mpeg;base64," + b64;
        src = { stop: function () { a.pause(); end(); } };
        set("speaking");
        safety = setTimeout(end, 60000);
        var p = a.play(); if (p && p.catch) p.catch(end);
      };
      if (IOS) return viaElement();
      Promise.resolve(ctx.resume ? ctx.resume() : null).catch(function () {}).then(function () {
        ctx.decodeAudioData(buf.buffer.slice(0), function (audio) {
          if (box.hidden) return end();
          var s = ctx.createBufferSource(); s.buffer = audio;
          outAn = ctx.createAnalyser(); outAn.fftSize = 1024;
          s.connect(outAn); outAn.connect(ctx.destination);
          s.onended = end;
          src = { stop: function () { try { s.onended = null; s.stop(); } catch (e) {} end(); } };
          set("speaking");
          safety = setTimeout(end, (audio.duration + 2) * 1000);   // не дождались конца — не зависаем
          s.start();
        }, viaElement);
      });
    });
  }
  function hush() { if (src) src.stop(); }

  // ── Окно ───────────────────────────────────────────────────
  function open() {
    box.hidden = false;
    document.documentElement.classList.add("vo-open");
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.resume) ctx.resume();   // звук разрешён: окно открыли нажатием
    unlockPlayer();
    cancelAnimationFrame(raf); loop();
    if (!bot.textContent && history.length) bot.textContent = history[history.length - 1].text;
    start();
  }
  function start() {
    if (!liveAllowed()) {
      showMode(pref() === "live" ? "Режим: обычный — живой голос недавно не соединялся" : "Режим: обычный");
      listen(); return;
    }
    set("connecting"); showMode("Подключаю живой голос…", true);
    var my = ++turn;
    realtime().catch(function (e) {   // не соединился — работаем в обычном режиме, 12 часов не пробуем
      rtStop(); store(FAIL, String(Date.now()));
      showMode("Режим: обычный — " + ((e && e.message) || "живой голос недоступен"));
      if (!box.hidden && my === turn) { set("idle"); listen(); }
    });
  }
  function close() {
    turn++;
    stop(false); hush(); rtStop(); micOff();
    goAfter = null; needTap = false;
    box.hidden = true;
    cancelAnimationFrame(raf);
    set("idle");
    document.documentElement.classList.remove("vo-open");
  }
  function toggleMute() {
    muted = !muted;
    micBtn.setAttribute("aria-pressed", String(muted));
    micBtn.classList.toggle("off", muted);
    micBtn.querySelector("span").textContent = muted ? "Микрофон выключен" : "Микрофон включён";
    if (rt) {   // живой голос: микрофон просто молчит, соединение остаётся
      if (state !== "speaking") micTrack(!muted);
      if (state !== "speaking" && state !== "thinking") set(muted ? "muted" : "listening");
      return;
    }
    if (muted) { var was = state; stop(false); micOff(); if (was === "listening" || was === "idle") set("muted"); }
    else if (state === "muted" || state === "idle") listen();
  }

  trig.addEventListener("click", function (e) { e.preventDefault(); open(); });
  orb.addEventListener("click", function () {
    if (ctx && ctx.resume) ctx.resume();
    if (IOS && state !== "speaking") unlockPlayer();
    if (needTap) { needTap = false; playRemote(); }
    if (rt) {
      if (state === "speaking") { rtSend({ type: "response.cancel" }); rtSend({ type: "output_audio_buffer.clear" }); spoke(); }
      else if (muted) toggleMute();
      return;
    }
    if (state === "speaking") hush();                          // перебить: дослушивать не надо
    else if (state === "listening") stop(true);                // договорил — отправить сразу
    else if (state === "idle" || state === "muted") { if (muted) toggleMute(); else listen(); }
  });
  micBtn.addEventListener("click", toggleMute);
  if (modeBtn) modeBtn.addEventListener("click", function () {   // сменить режим вручную
    store(PREF, liveNow ? "plain" : "live");
    if (!liveNow) store(FAIL, null);   // живой голос — попробовать заново, даже если недавно не вышло
    turn++; stop(false); hush(); rtStop();
    set("idle"); start();
  });
  box.querySelector(".vo-x").addEventListener("click", close);
  box.addEventListener("click", function (e) { if (e.target === box) close(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !box.hidden) close(); });
  typeForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var inp = typeForm.querySelector("input"), q = inp.value.trim();
    if (!q) return;
    inp.value = "";
    if (rt) {
      lastTalk = performance.now();
      you.textContent = "Вы: " + q; bot.textContent = "";
      if (state === "speaking") { rtSend({ type: "response.cancel" }); rtSend({ type: "output_audio_buffer.clear" }); }
      rtSend({ type: "conversation.item.create", item: { type: "message", role: "user", content: [{ type: "input_text", text: q }] } });
      rtSend({ type: "response.create" });
      set("thinking");
      return;
    }
    stop(false); hush();
    send(null, q);
  });
})();
