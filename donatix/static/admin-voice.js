// Голосовой помощник админки: шарик в поиске. Нажали — слушает (вы говорите, он молчит), замолчали — думает
// и отвечает голосом (он говорит — вы слушаете), потом снова слушает. Шар двигается в такт голосу.
// Микрофон можно выключить; вопрос можно и написать. Ключ OpenAI — только на сервере (/admin/assistant/ask).
(function () {
  "use strict";
  var trig = document.querySelector("[data-voice]"), box = document.getElementById("vo");
  if (!trig || !box) return;
  var csrf = box.dataset.csrf, orb = box.querySelector(".vo-orb"), stateEl = box.querySelector(".vo-state"),
      you = box.querySelector(".vo-you"), bot = box.querySelector(".vo-bot"), micBtn = box.querySelector(".vo-mic"),
      typeForm = box.querySelector(".vo-type");
  var ctx = null, stream = null, micAn = null, rec = null, chunks = [], src = null, outAn = null, raf = 0,
      state = "idle", muted = false, history = [], turn = 0;   // turn — номер реплики: старый ответ не мешает новому
  try { history = JSON.parse(sessionStorage.getItem("dx-voice") || "[]") || []; } catch (e) { history = []; }
  var TEXT = { idle: "Нажмите на шар и говорите", listening: "Слушаю…", thinking: "Думаю…", speaking: "Говорю…",
               muted: "Микрофон выключен — нажмите на шар или напишите вопрос" };

  function set(s, note) { state = s; box.dataset.state = s; stateEl.textContent = note || TEXT[s]; }
  function level(an) {
    var a = new Uint8Array(an.fftSize), sum = 0;
    an.getByteTimeDomainData(a);
    for (var i = 0; i < a.length; i++) { var v = (a[i] - 128) / 128; sum += v * v; }
    return Math.sqrt(sum / a.length);
  }
  function loop() {   // шар «дышит» в такт: слушает — вашему голосу, говорит — своему
    var l = 0;
    if (state === "listening" && micAn) l = level(micAn) * 5;
    else if (state === "speaking" && outAn) l = level(outAn) * 3.5;
    box.style.setProperty("--lvl", Math.min(1, l).toFixed(3));
    raf = requestAnimationFrame(loop);
  }
  function mime() {
    var t = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
    for (var i = 0; i < t.length; i++) if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t[i])) return t[i];
    return "";
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

  function listen() {
    if (box.hidden) return;
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
          if (j.go && j.go !== location.pathname + location.search) { location.href = j.go; return; }
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

  function open() {
    box.hidden = false;
    document.documentElement.classList.add("vo-open");
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.resume) ctx.resume();   // звук разрешён: включили нажатием
    cancelAnimationFrame(raf); loop();
    if (!bot.textContent && history.length) bot.textContent = history[history.length - 1].text;
    listen();
  }
  function close() {
    turn++;
    stop(false); hush(); micOff();
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
    if (muted) { var was = state; stop(false); micOff(); if (was === "listening" || was === "idle") set("muted"); }
    else if (state === "muted" || state === "idle") listen();
  }

  trig.addEventListener("click", function (e) { e.preventDefault(); open(); });
  orb.addEventListener("click", function () {
    if (state === "speaking") { hush(); }                      // перебить: дослушивать не надо
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
    if (!q || state === "thinking") return;
    inp.value = "";
    stop(false); hush();
    send(null, q);
  });
})();
