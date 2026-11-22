/* Графики VPS на canvas без библиотек, чёрно-белые: живой (плавно едет каждую секунду) и история. */
(function () {
  "use strict";
  var DPR = Math.min(window.devicePixelRatio || 1, 2);
  var TOP = 18, BOTTOM = 18;          // место под подписи шкалы и времени
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setup(canvas) {
    var w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * DPR) || canvas.height !== Math.round(h * DPR)) {
      canvas.width = Math.round(w * DPR); canvas.height = Math.round(h * DPR);
    }
    var ctx = canvas.getContext("2d");
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    return { ctx: ctx, w: w, h: h };
  }

  function niceMax(v, fixed) {
    if (fixed) return fixed;
    if (v <= 0) return 1;
    var p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
  }

  function grid(c, max, fmt) {
    var ctx = c.ctx;
    ctx.strokeStyle = "rgba(11,11,11,.07)"; ctx.lineWidth = 1;
    ctx.fillStyle = "#8C8C88"; ctx.font = "600 10px Onest, system-ui, sans-serif";
    for (var i = 0; i <= 4; i++) {
      var y = Math.round(TOP + (c.h - TOP - BOTTOM) * i / 4) + 0.5;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(c.w, y); ctx.stroke();
      ctx.fillText(fmt(max * (4 - i) / 4), 4, y - 3);
    }
  }

  function line(c, pts, color, max, fill, si) {
    var ctx = c.ctx;
    if (pts.length < 2) return;
    var top = TOP, H = c.h - TOP - BOTTOM;
    ctx.beginPath();
    for (var i = 0; i < pts.length; i++) {
      var x = pts[i][0], y = top + H - Math.min(pts[i][1] / max, 1) * H;
      if (i === 0) ctx.moveTo(x, y);
      else {
        var px = pts[i - 1][0], py = top + H - Math.min(pts[i - 1][1] / max, 1) * H, mx = (px + x) / 2;
        ctx.bezierCurveTo(mx, py, mx, y, x, y);
      }
    }
    ctx.strokeStyle = color; ctx.lineWidth = si === 0 ? 2 : 1.5; ctx.lineJoin = "round";
    ctx.setLineDash(si ? [4, 4] : []); ctx.stroke(); ctx.setLineDash([]);   // вторая линия — пунктир, не цвет
    if (fill) {
      ctx.lineTo(pts[pts.length - 1][0], top + H); ctx.lineTo(pts[0][0], top + H); ctx.closePath();
      var g = ctx.createLinearGradient(0, top, 0, top + H);
      g.addColorStop(0, color.replace(")", ",.28)").replace("rgb", "rgba")); g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g; ctx.fill();
    }
  }

  /* Живой график: окно window секунд, новая точка раз в секунду, сдвиг — плавный. */
  function LiveChart(canvas, opts) {
    this.canvas = canvas; this.opts = opts; this.window = opts.window || 60;
    this.data = opts.series.map(function () { return []; });
    this.last = 0; this.shown = 0; this.alive = true;
    var self = this;
    function frame(t) { if (!self.alive) return; self.draw(t); requestAnimationFrame(frame); }
    requestAnimationFrame(frame);
  }
  LiveChart.prototype.push = function (values) {
    var now = performance.now();
    for (var i = 0; i < values.length; i++) {
      this.data[i].push(values[i]);
      if (this.data[i].length > this.window + 2) this.data[i].shift();
    }
    this.last = now;
  };
  LiveChart.prototype.stop = function () { this.alive = false; };
  LiveChart.prototype.draw = function (t) {
    if (!this.canvas.isConnected) { this.alive = false; return; }
    var c = setup(this.canvas), o = this.opts;
    c.ctx.clearRect(0, 0, c.w, c.h);
    var peak = 0;
    this.data.forEach(function (d) { d.forEach(function (v) { if (v > peak) peak = v; }); });
    var max = niceMax(peak * 1.15, o.max);
    this.shown += (max - this.shown) * 0.15;               // шкала тоже меняется плавно
    if (!this.shown || !isFinite(this.shown)) this.shown = max;
    grid(c, this.shown, o.fmt || String);
    var progress = reduced ? 1 : Math.min((t - this.last) / 1000, 1);   // доля секунды с прошлой точки
    var step = c.w / (this.window - 1), self = this;
    this.data.forEach(function (d, si) {
      var pts = [];
      for (var i = 0; i < d.length; i++) {
        var x = c.w - (d.length - 1 - i + progress) * step;
        pts.push([x, d[i]]);
      }
      line(c, pts, o.series[si].color, self.shown, si === 0, si);
    });
  };

  /* История: точки [t, ...значения], ось времени по краям. */
  function drawHistory(canvas, points, series, opts) {
    var c = setup(canvas);
    c.ctx.clearRect(0, 0, c.w, c.h);
    var peak = 0;
    points.forEach(function (p) { series.forEach(function (s) { if (p[s.index] > peak) peak = p[s.index]; }); });
    var max = niceMax(peak * 1.1, opts.max);
    grid(c, max, opts.fmt || String);
    if (points.length < 2) {
      c.ctx.fillStyle = "#8C8C88"; c.ctx.font = "600 13px Onest, system-ui"; var e = opts.empty || "—"; c.ctx.fillText(e, (c.w - c.ctx.measureText(e).width) / 2, c.h / 2);
      return;
    }
    var t0 = points[0][0], t1 = points[points.length - 1][0], span = Math.max(t1 - t0, 1);
    series.forEach(function (s, si) {
      line(c, points.map(function (p) { return [(p[0] - t0) / span * c.w, p[s.index]]; }), s.color, max, si === 0, si);
    });
    var f = function (ts) {
      var d = new Date(ts * 1000);
      return span > 86400 ? d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" }) :
        d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    };
    c.ctx.fillStyle = "#8C8C88"; c.ctx.font = "600 10px Onest, system-ui";
    c.ctx.fillText(f(t0), 4, c.h - 4);
    var lbl = f(t1); c.ctx.fillText(lbl, c.w - c.ctx.measureText(lbl).width - 4, c.h - 4);
  }

  window.Charts = { LiveChart: LiveChart, drawHistory: drawHistory };
})();
