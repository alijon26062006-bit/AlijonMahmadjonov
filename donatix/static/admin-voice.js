// Голосовой помощник админки: шарик в поиске.
// Основной режим — голосовой режим OpenAI (как голос в ChatGPT): браузер говорит с OpenAI напрямую (WebRTC)
// по одноразовому ключу с нашего сервера. Вы говорите — он молчит и слушает; замолчали — отвечает живым голосом;
// заговорили во время ответа — он замолкает. Цифры магазина он спрашивает у нашего сервера (/admin/assistant/tool).
// Запасной режим (если голосовой не подключился): запись → /admin/assistant/ask → ответ голосом.
// Шар двигается в такт: слушает — вашему голосу, говорит — своему. Микрофон можно выключить, вопрос — написать.
(function () {
  "use strict";
  var trig = document.querySelector("[data-voice]"), box = document.getElementById("vo");
  if (!trig || !box) return;
  var csrf = box.dataset.csrf, orb = box.querySelector(".vo-orb"), stateEl = box.querySelector(".vo-state"),
      you = box.querySelector(".vo-you"), bot = box.querySelector(".vo-bot"), micBtn = box.querySelector(".vo-mic"),
      typeForm = box.querySelector(".vo-type");
  var ctx = null, stream = null, micAn = null, outAn = null, raf = 0, state = "idle", muted = false;
  var rec = null, chunks = [], src = null, history = [], turn = 0;              // запасной режим
  var pc = null, dc = null, remoteEl = null, rt = false, textBuf = "", goAfter = null, lastOut = 0, lastTalk = 0;
  try { history = JSON.parse(sessionStorage.getItem("dx-voice") || "[]") || []; } catch (e) { history = []; }
  var TEXT = { idle: "Нажмите на шар и говорите", listening: "Слушаю…", thinking: "Думаю…", speaking: "Говорю…",
               muted: "Микрофон выключен — нажмите на шар или напишите вопрос", connecting: "Подключаюсь…" };

  function set(s, note) { state = s; box.dataset.state = s === "connecting" ? "thinking" : s; stateEl.textContent = note || TEXT[s]; }
  function level(an) {
    var a = new Uint8Array(an.fftSize), sum = 0;
    an.getByteTimeDomainData(a);
    for (var i = 0; i < a.length; i++) { var v = (a[i] - 128) / 128; sum += v * v; }
    return Math.sqrt(sum / a.length);
  }
  function post(url, data) {
    var fd = new FormData();
    fd.append("csrf", csrf);
    Object.keys(data || {}).forEach(function (k) { fd.append(k, data[k]); });
    return fetch(url, { method: "POST", body: fd, credentials: "same-origin" }).then(function (r) { return r.json(); });
  }

  function loop() {   // анимация шара и, в голосовом режиме, «говорит / слушает» по звуку
    var now = performance.now(), lin = micAn && !muted ? level(micAn) : 0, lout = outAn ? level(outAn) : 0, l = 0;
    if (rt) {
      if (lout > 0.02) { lastOut = now; if (state !== "speaking") set("speaking"); }
      else if (state === "speaking" && now - lastOut > 800) { set(muted ? "muted" : "listening"); if (goAfter) go(); }
      if (now - lastTalk > 180000) { close(); return; }   // 3 минуты тишины — отключаемся, чтобы не тратить деньги
    }
    if (state === "listening") l = lin * 5;
    else if (state === "speaking") l = lout * 3.5;
    box.style.setProperty("--lvl", Math.min(1, l).toFixed(3));
    raf = requestAnimationFrame(loop);
  }
  function mic() {
    if (stream) return Promise.resolve(stream);
    return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      .then(function (s) {
        stream = s;
        micAn = ctx.createAnalyser(); micAn.fftSize = 1024;
        ctx.createMediaStreamSource(s).connect(micAn);
        return s;
      });
  }
  function micOff() {
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null; micAn = null;
  }
  function go() { var url = goAfter; goAfter = null; if (url && url !== location.pathname + location.search) location.href = url; }

  // ── Голосовой режим как в ChatGPT ──────────────────────────
  function realtime() {
    return post("/admin/assistant/realtime", {}).then(function (t) {
      if (!t.ok) throw new Error(t.error || "нет ключа");
      return mic().then(function () {
        pc = new RTCPeerConnection();
        remoteEl = remoteEl || document.createElement("audio");
        remoteEl.autoplay = true; remoteEl.setAttribute("playsinline", "");
        pc.ontrack = function (e) {
          remoteEl.srcObject = e.streams[0];
          try { outAn = ctx.createAnalyser(); outAn.fftSize = 1024; ctx.createMediaStreamSource(e.streams[0]).connect(outAn); } catch (er) {}
        };
        stream.getTracks().forEach(function (tr) { pc.addTrack(tr, stream); });
        dc = pc.createDataChannel("oai-events");
        dc.onmessage = function (m) { var ev; try { ev = JSON.parse(m.data); } catch (er) { return; } onEvent(ev); };
        return pc.createOffer()
          .then(function (offer) { return pc.setLocalDescription(offer).then(function () { return offer; }); })
          .then(function (offer) {
            var url = t.mode === "beta" ? "https://api.openai.com/v1/realtime?model=" + encodeURIComponent(t.model)
                                        : "https://api.openai.com/v1/realtime/calls";
            return fetch(url, { method: "POST", body: offer.sdp,
                                headers: { "Authorization": "Bearer " + t.key, "Content-Type": "application/sdp" } });
          })
          .then(function (r) { if (!r.ok) throw new Error("OpenAI " + r.status); return r.text(); })
          .then(function (sdp) { return pc.setRemoteDescription({ type: "answer", sdp: sdp }); })
          .then(function () { rt = true; lastTalk = performance.now(); set(muted ? "muted" : "listening"); });
      });
    });
  }
  function rtSend(obj) { if (dc && dc.readyState === "open") dc.send(JSON.stringify(obj)); }
  function onEvent(ev) {
    switch (ev.type) {
      case "input_audio_buffer.speech_started":            // вы заговорили — он замолкает и слушает
        lastTalk = performance.now(); set("listening"); break;
      case "input_audio_buffer.speech_stopped":
        set("thinking"); break;
      case "conversation.item.input_audio_transcription.completed":
        if (ev.transcript) you.textContent = "Вы: " + String(ev.transcript).trim(); break;
      case "response.created":
        textBuf = ""; if (state !== "speaking") set("thinking"); break;
      case "response.output_audio_transcript.delta": case "response.audio_transcript.delta":
      case "response.output_text.delta": case "response.text.delta":
        textBuf += ev.delta || ""; bot.textContent = textBuf; break;
      case "output_audio_buffer.started":
        lastOut = performance.now(); set("speaking"); break;
      case "output_audio_buffer.stopped": case "output_audio_buffer.cleared":
        if (state === "speaking") { set(muted ? "muted" : "listening"); if (goAfter) go(); }
        break;
      case "response.function_call_arguments.done":
        tool(ev); break;
      case "error":
        if (ev.error && ev.error.message) bot.textContent = ev.error.message; break;
    }
  }
  function tool(ev) {
    post("/admin/assistant/tool", { name: ev.name || "", args: ev.arguments || "{}" })
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
    if (dc) { try { dc.close(); } catch (e) {} dc = null; }
    if (pc) { try { pc.close(); } catch (e) {} pc = null; }
    if (remoteEl) remoteEl.srcObject = null;
    outAn = null;
  }

  // ── Запасной режим: запись → ответ → голос ─────────────────
  function mime() {
    var t = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
    for (var i = 0; i < t.length; i++) if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t[i])) return t[i];
    return "";
  }
  function listen() {
    if (box.hidden || rt) return;
    if (muted) { set("muted"); return; }
    if (!navigator.mediaDevices || !window.MediaRecorder) { set("idle", "Этот браузер не записывает голос — напишите вопрос"); return; }
    mic().then(function () {
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
      var t0 = performance.now(), last = 0, voiced = false;
      (function vad() {   // замолчали на 1,2 с — отправляем; 9 с тишины — ждём нажатия
        if (rec !== r || state !== "listening") return;
        var l = micAn ? level(micAn) : 0, now = performance.now();
        if (l > 0.035) { last = now; if (now - t0 > 150) voiced = true; }
        if (voiced && now - last > 1200) return stop(true);
        if (!voiced && now - t0 > 9000) return stop(false);
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
    var fd = new FormData();
    fd.append("csrf", csrf);
    fd.append("history", JSON.stringify(history.slice(-8)));
    fd.append("page", location.pathname + location.search);
    if (blob) fd.append("audio", blob, "voice." + (/mp4/.test(blob.type) ? "mp4" : /ogg/.test(blob.type) ? "ogg" : "webm"));
    if (text) fd.append("text", text);
    fetch("/admin/assistant/ask", { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .catch(function () { return { ok: false, error: "Нет связи с сайтом — попробуйте ещё раз" }; })
      .then(function (j) {
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
      var bin = atob(b64), buf = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
      ctx.decodeAudioData(buf.buffer, function (audio) {
        if (box.hidden) return done();
        src = ctx.createBufferSource(); src.buffer = audio;
        outAn = ctx.createAnalyser(); outAn.fftSize = 1024;
        src.connect(outAn); outAn.connect(ctx.destination);
        src.onended = function () { src = null; outAn = null; done(); };
        set("speaking");
        src.start();
      }, function () { done(); });
    });
  }
  function hush() {
    if (!src) return;
    var s = src; src = null; outAn = null;
    try { var end = s.onended; s.onended = null; s.stop(); if (end) end(); } catch (e) {}
  }

  // ── Окно ───────────────────────────────────────────────────
  function open() {
    box.hidden = false;
    document.documentElement.classList.add("vo-open");
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.resume) ctx.resume();   // звук разрешён: окно открыли нажатием
    cancelAnimationFrame(raf); loop();
    if (!bot.textContent && history.length) bot.textContent = history[history.length - 1].text;
    if (!window.RTCPeerConnection || !navigator.mediaDevices) { listen(); return; }
    set("connecting");
    var my = ++turn;
    realtime().catch(function (e) {   // голосовой режим не подключился — работаем по-старому
      if (window.console) console.warn("голосовой режим недоступен, запасной режим:", e && e.message);
      rtStop();
      if (!box.hidden && my === turn) listen();
    });
  }
  function close() {
    turn++;
    stop(false); hush(); rtStop(); micOff();
    goAfter = null;
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
    if (rt) {   // голосовой режим: микрофон просто молчит, соединение остаётся
      if (stream) stream.getAudioTracks().forEach(function (t) { t.enabled = !muted; });
      if (state !== "speaking" && state !== "thinking") set(muted ? "muted" : "listening");
      return;
    }
    if (muted) { var was = state; stop(false); micOff(); if (was === "listening" || was === "idle") set("muted"); }
    else if (state === "muted" || state === "idle") listen();
  }

  trig.addEventListener("click", function (e) { e.preventDefault(); open(); });
  orb.addEventListener("click", function () {
    if (rt) {
      if (state === "speaking") { rtSend({ type: "response.cancel" }); rtSend({ type: "output_audio_buffer.clear" }); set("listening"); }
      else if (muted) toggleMute();
      return;
    }
    if (state === "speaking") hush();                          // перебить: дослушивать не надо
    else if (state === "listening") stop(true);                // договорил — отправить сразу
    else if (state === "idle" || state === "muted") { if (muted) toggleMute(); else listen(); }
  });
  micBtn.addEventListener("click", toggleMute);
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
      rtSend({ type: "conversation.item.create", item: { type: "message", role: "user", content: [{ type: "input_text", text: q }] } });
      rtSend({ type: "response.create" });
      return;
    }
    if (state === "thinking") return;
    stop(false); hush();
    send(null, q);
  });
})();
