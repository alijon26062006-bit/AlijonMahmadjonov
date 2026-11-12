/* Графики на canvas: линии с заливкой, сетка, подсказка при наведении. */
(function () {
  "use strict";
  const { token } = AM;

  function setup(cv) {
    const r = cv.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(r.width * dpr)), h = Math.max(1, Math.round(r.height * dpr));
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w: r.width, h: r.height };
  }

  function rgba(color, a) {
    const h = color.replace("#", "");
    if (!/^[0-9a-f]{3,6}$/i.test(h)) return color;
    const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
    return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
  }

  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 2.5, 5, 10]) if (v <= m * p) return m * p;
    return 10 * p;
  }

  function nearest(data, t) {
    let best = -1, bd = Infinity;
    for (let i = 0; i < data.length; i++) { const d = Math.abs(data[i][0] - t); if (d < bd) { bd = d; best = i; } }
    return best;
  }

  /**
   * opts: { series: [{label, color, data:[[t,v]]}], start, end, yMax?, yFmt(v), tip?: HTMLElement, xLabels: [..5] }
   * Возвращает объект с методом hover(x) для подсказки.
   */
  function line(cv, opts) {
    const state = { hoverT: null };
    function draw() {
      const { ctx, w, h } = setup(cv);
      ctx.clearRect(0, 0, w, h);
      const padL = opts.padL || 52, padR = 10, padT = 10, padB = 22;
      const cw = w - padL - padR, ch = h - padT - padB;
      const muted = token("--muted"), lineC = token("--line");
      const all = opts.series.flatMap((s) => s.data.map((p) => p[1]));
      const yMax = opts.yMax || niceMax(Math.max(1, ...all) * 1.1);
      const span = Math.max(1, opts.end - opts.start);
      const X = (t) => padL + (t - opts.start) / span * cw;
      const Y = (v) => padT + ch - Math.min(v, yMax) / yMax * ch;
      ctx.font = `11px ${token("--f-mono") || "monospace"}`;
      ctx.textAlign = "right"; ctx.textBaseline = "middle";
      for (let i = 0; i <= 4; i++) {
        const v = yMax * i / 4, y = Y(v);
        ctx.strokeStyle = lineC; ctx.lineWidth = 1; ctx.setLineDash(i === 0 ? [] : [3, 4]);
        ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
        ctx.fillStyle = muted; ctx.fillText(opts.yFmt(v), padL - 6, y);
      }
      ctx.setLineDash([]);
      ctx.textBaseline = "top";
      (opts.xLabels || []).forEach((l, i, arr) => {
        ctx.textAlign = i === 0 ? "left" : i === arr.length - 1 ? "right" : "center";
        ctx.fillText(l, padL + cw * i / (arr.length - 1), h - padB + 6);
      });
      ctx.save(); ctx.beginPath(); ctx.rect(padL, 0, cw, h); ctx.clip();
      opts.series.forEach((s) => {
        if (!s.data.length) return;
        ctx.beginPath();
        s.data.forEach((p, i) => (i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1]))));
        ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.stroke();
        ctx.lineTo(X(s.data[s.data.length - 1][0]), padT + ch); ctx.lineTo(X(s.data[0][0]), padT + ch); ctx.closePath();
        const gr = ctx.createLinearGradient(0, padT, 0, padT + ch);
        gr.addColorStop(0, rgba(s.color, 0.2)); gr.addColorStop(1, rgba(s.color, 0));
        ctx.fillStyle = gr; ctx.fill();
        const last = s.data[s.data.length - 1];
        ctx.beginPath(); ctx.arc(X(last[0]), Y(last[1]), 3, 0, Math.PI * 2); ctx.fillStyle = s.color; ctx.fill();
      });
      ctx.restore();

      const tip = opts.tip;
      if (state.hoverT != null && tip) {
        const x = X(state.hoverT);
        ctx.strokeStyle = muted; ctx.setLineDash([2, 3]);
        ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, padT + ch); ctx.stroke(); ctx.setLineDash([]);
        const rows = [];
        opts.series.forEach((s) => {
          const i = nearest(s.data, state.hoverT);
          if (i < 0 || Math.abs(s.data[i][0] - state.hoverT) > span / 20) return;
          const p = s.data[i];
          ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 4, 0, Math.PI * 2);
          ctx.fillStyle = token("--surface"); ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = s.color; ctx.stroke();
          rows.push(`<span><i style="display:inline-block;width:8px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle;background:${s.color}"></i>${AM.esc(s.label)} <b class="mono">${AM.esc(opts.yFmt(p[1], true))}</b></span>`);
        });
        if (rows.length) {
          tip.innerHTML = `<span style="color:var(--muted)">${AM.dateTime(state.hoverT)}</span>${rows.join("")}`;
          tip.style.opacity = 1;
          const tw = tip.offsetWidth;
          tip.style.left = Math.max(0, Math.min(w - tw, x + 14 + tw > w ? x - tw - 14 : x + 14)) + "px";
        } else tip.style.opacity = 0;
      } else if (tip) tip.style.opacity = 0;
    }
    cv.onpointermove = (e) => {
      const r = cv.getBoundingClientRect(), padL = opts.padL || 52, cw = r.width - padL - 10;
      const f = Math.max(0, Math.min(1, (e.clientX - r.left - padL) / cw));
      state.hoverT = opts.start + f * (opts.end - opts.start);
      draw();
    };
    cv.onpointerleave = () => { state.hoverT = null; draw(); };
    draw();
    return { draw, update(next) { Object.assign(opts, next); draw(); } };
  }

  function spark(cv, data, color, max) {
    if (!cv) return;
    const { ctx, w, h } = setup(cv);
    ctx.clearRect(0, 0, w, h);
    const pts = data.slice(-40);
    if (pts.length < 2) return;
    const m = max || niceMax(Math.max(1, ...pts.map((p) => p[1])) * 1.1);
    const step = w / (pts.length - 1), Y = (v) => h - 3 - Math.min(v, m) / m * (h - 6);
    ctx.beginPath(); pts.forEach((p, i) => (i ? ctx.lineTo(i * step, Y(p[1])) : ctx.moveTo(0, Y(p[1]))));
    ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.lineJoin = "round"; ctx.stroke();
    ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
    const gr = ctx.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, rgba(color, 0.25)); gr.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = gr; ctx.fill();
    ctx.beginPath(); ctx.arc(w - 2, Y(pts[pts.length - 1][1]), 2.6, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
  }

  AM.charts = { line, spark };
})();
