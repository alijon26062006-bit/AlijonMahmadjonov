/* 3D-глобус дата-центров (three.js r128). initGlobe(box, labelsBox, points, links) */
(function () {
  "use strict";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const token = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  window.initGlobe = function (box, labelsBox, DCS, LINKS) {
    if (!window.THREE || !box) return false;
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); } catch (e) { return false; }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    box.prepend(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(0, 0, 4.4);
    const avgLat = DCS.reduce((s, d) => s + d.lat, 0) / DCS.length;
    const avgLon = DCS.reduce((s, d) => s + d.lon, 0) / DCS.length;
    const tiltX = Math.min(0.95, Math.max(0.2, avgLat * Math.PI / 180 * 0.9));
    const tilt = new THREE.Group();
    tilt.rotation.x = tiltX;
    tilt.rotation.z = -0.12;
    scene.add(tilt);
    const globe = new THREE.Group();
    tilt.add(globe);
    const baseY = (-avgLon - 90 - 25) * Math.PI / 180;

    const ll = (lat, lon, r = 1) => {
      const phi = (90 - lat) * Math.PI / 180, th = (lon + 180) * Math.PI / 180;
      return new THREE.Vector3(-r * Math.sin(phi) * Math.cos(th), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(th));
    };

    const dotCanvas = document.createElement("canvas");
    dotCanvas.width = dotCanvas.height = 64;
    const dc = dotCanvas.getContext("2d");
    dc.fillStyle = "#fff"; dc.beginPath(); dc.arc(32, 32, 28, 0, Math.PI * 2); dc.fill();
    const dotTex = new THREE.CanvasTexture(dotCanvas);

    const occMat = new THREE.MeshBasicMaterial({ color: 0x000000 });
    globe.add(new THREE.Mesh(new THREE.SphereGeometry(0.985, 64, 48), occMat));

    const N = 2600, pos = [], g = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), t = g * i;
      pos.push(Math.cos(t) * r, y, Math.sin(t) * r);
    }
    const dotGeo = new THREE.BufferGeometry();
    dotGeo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    const dotMat = new THREE.PointsMaterial({ size: 0.022, map: dotTex, alphaTest: 0.5, transparent: true, opacity: 0 });
    globe.add(new THREE.Points(dotGeo, dotMat));

    const orbitMat = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.35 });
    const satMat = new THREE.PointsMaterial({ size: 0.05, map: dotTex, alphaTest: 0.5, transparent: true });
    const orbits = [];
    [[1.32, 1.1, 0.3], [1.48, -0.5, 1.2]].forEach(([r, rx, rz]) => {
      const pts = [];
      for (let i = 0; i <= 128; i++) { const a = i / 128 * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r)); }
      const grp = new THREE.Group(); grp.rotation.set(rx, 0, rz);
      grp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), orbitMat));
      const satGeo = new THREE.BufferGeometry();
      satGeo.setAttribute("position", new THREE.Float32BufferAttribute(new Array(9).fill(0), 3));
      const sats = new THREE.Points(satGeo, satMat);
      grp.add(sats); tilt.add(grp);
      orbits.push({ r, sats, phase: Math.random() * 6 });
    });

    const markerMat = new THREE.MeshBasicMaterial({ color: 0xffb547 });
    const ringMat = new THREE.MeshBasicMaterial({ color: 0xffb547, transparent: true, side: THREE.DoubleSide });
    const markers = DCS.map((d) => {
      const p = ll(d.lat, d.lon, 1.002);
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.022, 16, 12), markerMat);
      m.position.copy(p); globe.add(m);
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.03, 0.04, 32), ringMat.clone());
      ring.position.copy(p);
      ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), p.clone().normalize());
      globe.add(ring);
      const label = document.createElement("div");
      label.className = "g-label";
      const i = document.createElement("i");
      label.append(i, document.createTextNode(d.name + " "));
      if (d.note) { const s = document.createElement("span"); s.textContent = d.note; label.append(s); }
      labelsBox.appendChild(label);
      return { m, ring, label, side: d.side || "top", off: Math.random() };
    });

    const arcMat = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.85 });
    const packetMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const arcs = LINKS.map(([a, b], i) => {
      const A = ll(DCS[a].lat, DCS[a].lon), B = ll(DCS[b].lat, DCS[b].lon);
      const mid = A.clone().add(B).multiplyScalar(0.5).normalize().multiplyScalar(1 + A.distanceTo(B) * 0.55);
      const curve = new THREE.QuadraticBezierCurve3(A, mid, B);
      const geo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(80));
      geo.setDrawRange(0, reduced ? 81 : 0);
      globe.add(new THREE.Line(geo, arcMat));
      const packet = new THREE.Mesh(new THREE.SphereGeometry(0.014, 10, 8), packetMat);
      globe.add(packet);
      return { curve, geo, packet, delay: 0.5 + i * 0.18, speed: 0.22 + (i % 3) * 0.06, off: i * 0.37 };
    });

    function applyColors() {
      occMat.color.set(token("--bg"));
      dotMat.color.set(token("--globe-dot"));
      orbitMat.color.set(token("--globe-dot"));
      satMat.color.set(token("--accent"));
      arcMat.color.set(token("--accent"));
      packetMat.color.set(token("--fg"));
      markerMat.color.set(token("--amber"));
      markers.forEach((mk) => mk.ring.material.color.set(token("--amber")));
    }
    applyColors();
    const re = () => requestAnimationFrame(applyColors);
    matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", re);
    new MutationObserver(re).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    let W = 1, H = 1;
    const resize = () => {
      const r = box.getBoundingClientRect();
      W = Math.max(1, r.width); H = Math.max(1, r.height);
      renderer.setSize(W, H, false);
      camera.aspect = W / H; camera.updateProjectionMatrix();
    };
    new ResizeObserver(resize).observe(box);
    resize();

    let dragging = false, lastX = 0, lastY = 0, velY = 0, userY = 0, userX = 0, targetX = 0, px = 0, py = 0;
    const cv = renderer.domElement;
    cv.addEventListener("pointerdown", (e) => { dragging = true; lastX = e.clientX; lastY = e.clientY; cv.setPointerCapture(e.pointerId); });
    cv.addEventListener("pointermove", (e) => {
      const r = box.getBoundingClientRect();
      px = (e.clientX - r.left) / r.width - 0.5; py = (e.clientY - r.top) / r.height - 0.5;
      if (!dragging) return;
      const dx = e.clientX - lastX, dy = e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
      velY = dx * 0.005; userY += velY;
      targetX = Math.max(-0.5, Math.min(0.5, targetX + dy * 0.004));
    });
    const end = () => { dragging = false; };
    cv.addEventListener("pointerup", end);
    cv.addEventListener("pointercancel", end);
    cv.addEventListener("pointerleave", () => { px = py = 0; });

    let visible = true;
    new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(box);
    const t0 = performance.now();
    const tmp = new THREE.Vector3(), camDir = new THREE.Vector3();
    const easeOut = (t) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

    function frame(now) {
      requestAnimationFrame(frame);
      if (!visible || document.hidden) return;
      const t = (now - t0) / 1000;
      const intro = reduced ? 1 : easeOut(t / 1.6);
      if (!dragging) { velY *= 0.94; userY += velY; }
      userX += (targetX - userX) * 0.08;
      globe.rotation.y = baseY + (reduced ? 0 : Math.sin(t * 0.08) * 0.35) + userY + px * 0.25;
      tilt.rotation.x = tiltX + userX + py * 0.12;
      tilt.scale.setScalar(0.82 + 0.18 * intro);
      dotMat.opacity = intro;
      orbits.forEach((o, k) => {
        const arr = o.sats.geometry.attributes.position.array;
        for (let j = 0; j < 3; j++) {
          const a = o.phase + (reduced ? 0 : t * (0.35 + k * 0.12)) + j * 2.1;
          arr[j * 3] = Math.cos(a) * o.r; arr[j * 3 + 1] = 0; arr[j * 3 + 2] = Math.sin(a) * o.r;
        }
        o.sats.geometry.attributes.position.needsUpdate = true;
      });
      markers.forEach((mk) => {
        const p = reduced ? 0.5 : ((t * 0.6 + mk.off) % 1);
        mk.ring.scale.setScalar(1 + p * 2.2);
        mk.ring.material.opacity = (1 - p) * 0.9;
      });
      arcs.forEach((a) => {
        const grow = reduced ? 1 : easeOut((t - a.delay) / 1.1);
        a.geo.setDrawRange(0, Math.floor(grow * 81));
        a.packet.visible = grow >= 1;
        if (grow >= 1) a.packet.position.copy(a.curve.getPoint(reduced ? 0.5 : ((t * a.speed + a.off) % 1)));
      });
      renderer.render(scene, camera);
      camDir.copy(camera.position).normalize();
      markers.forEach((mk) => {
        mk.m.getWorldPosition(tmp);
        const facing = tmp.clone().normalize().dot(camDir);
        tmp.project(camera);
        const x = (tmp.x + 1) / 2 * W, y = (1 - tmp.y) / 2 * H;
        mk.label.style.transform = mk.side === "left" ? `translate(${x - 12}px, ${y}px) translate(-100%, -50%)`
          : mk.side === "right" ? `translate(${x + 12}px, ${y}px) translate(0, -50%)`
          : mk.side === "bottom" ? `translate(${x}px, ${y + 12}px) translate(-50%, 0)`
          : `translate(${x}px, ${y - 10}px) translate(-50%, -100%)`;
        mk.label.style.opacity = intro > 0.9 && facing > 0.25 ? 1 : 0;
      });
    }
    requestAnimationFrame(frame);
    return true;
  };
})();
