/* =========================================================
   3D-СЦЕНА: город, земля, частицы, фигура, полёт камеры
   =========================================================
   Обычный three.js без сборщиков. Модули подключены через
   import map в index.html.
   ========================================================= */

import * as THREE from 'three';
import { EffectComposer } from './postprocessing/EffectComposer.js';
import { RenderPass } from './postprocessing/RenderPass.js';
import { UnrealBloomPass } from './postprocessing/UnrealBloomPass.js';
import { OutputPass } from './postprocessing/OutputPass.js';
import { scene as sceneConfig } from '../config.js';

const BG = 0x05070d;
const FOG_DENSITY = 0.0075;
const CORRIDOR_HALF_WIDTH = 7;   // ширина «улицы», по которой летит камера
const DESCENT = 0.16;            // доля прокрутки, за которую камера снижается

/** Свой генератор случайных чисел: город одинаков при каждой загрузке */
function makeRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
}

const easeOutCubic = (x) => 1 - Math.pow(1 - x, 3);

/** Мягкая круглая точка для частиц — рисуется на canvas, файл не нужен */
function createSoftSprite() {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;

  const ctx = canvas.getContext('2d');
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.25, 'rgba(255,255,255,0.55)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/* ---------------------------------------------------------
   ГОРОД
   Все здания — один InstancedMesh: сотни отдельных объектов
   просадили бы кадры, а так это один вызов отрисовки.
   Окна рисует шейдер прямо на гранях — ни одной картинки.
   --------------------------------------------------------- */
function createCity(count) {
  const vertexShader = `
    attribute float aSeed;
    varying vec2 vUv;
    varying float vSeed;
    varying vec3 vNormalW;
    varying float vFogDepth;

    void main() {
      vUv = uv;
      vSeed = aSeed;
      vNormalW = normalize(mat3(instanceMatrix) * normal);

      vec4 instancePos = instanceMatrix * vec4(position, 1.0);
      vec4 viewPos = modelViewMatrix * instancePos;
      vFogDepth = -viewPos.z;

      gl_Position = projectionMatrix * viewPos;
    }
  `;

  const fragmentShader = `
    precision highp float;

    uniform float uTime;
    uniform vec3  uWindow;
    uniform vec3  uAccent;
    uniform vec3  uFogColor;
    uniform float uFogDensity;

    varying vec2  vUv;
    varying float vSeed;
    varying vec3  vNormalW;
    varying float vFogDepth;

    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
    }

    void main() {
      // Крыша без окон, иначе сверху здание выглядит коробкой в клетку
      float isRoof = step(0.7, abs(vNormalW.y));

      vec2 grid = vec2(5.0, 16.0);
      vec2 cell = floor(vUv * grid);
      vec2 f    = fract(vUv * grid);

      float win =
        step(0.18, f.x) * step(f.x, 0.82) *
        step(0.10, f.y) * step(f.y, 0.80);

      // Горит меньшая часть окон: дом со всеми горящими окнами
      // выглядит фальшиво и выжигает передний план
      float lit = step(0.62, hash(cell + vSeed * 37.0));

      float phase   = hash(cell + vSeed * 11.0) * 6.28318;
      float flicker = 0.78 + 0.22 * sin(uTime * 1.4 + phase);

      vec3 base  = vec3(0.010, 0.014, 0.026);
      vec3 glow  = mix(uWindow, uAccent, hash(cell + vSeed * 5.0));
      vec3 color = base + glow * win * lit * flicker * (1.0 - isRoof) * 0.95;

      float rim = pow(1.0 - abs(dot(normalize(vNormalW), vec3(0.0, 1.0, 0.0))), 3.0);
      color += uAccent * rim * 0.05;

      // Дальние кварталы растворяются в фоне — город кажется бесконечным
      float fogFactor = 1.0 - exp(-uFogDensity * uFogDensity * vFogDepth * vFogDepth);
      color = mix(color, uFogColor, clamp(fogFactor, 0.0, 1.0));

      gl_FragColor = vec4(color, 1.0);
    }
  `;

  const rand = makeRandom(1337);
  const seeds = new Float32Array(count);
  const dummy = new THREE.Object3D();
  const matrices = [];

  let placed = 0;
  let guard = 0;
  while (placed < count && guard < count * 40) {
    guard++;

    const x = (rand() - 0.5) * 300;
    const z = -rand() * 430 + 110;

    // Свободный коридор по центру — «улица» для полёта камеры
    if (Math.abs(x) < CORRIDOR_HALF_WIDTH) continue;

    // Ближе к центру выше: улица превращается в ущелье
    const nearCenter = Math.max(0, 1 - Math.abs(x) / 70);
    const height = 6 + rand() * 26 + nearCenter * 42;

    dummy.position.set(x, height / 2, z);
    dummy.scale.set(3 + rand() * 5, height, 3 + rand() * 5);
    dummy.rotation.y = Math.round(rand() * 4) * (Math.PI / 2);
    dummy.updateMatrix();

    matrices.push(dummy.matrix.clone());
    seeds[placed] = rand() * 100;
    placed++;
  }

  const geometry = new THREE.BoxGeometry(1, 1, 1);
  geometry.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seeds, 1));

  const material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uTime: { value: 0 },
      uWindow: { value: new THREE.Color('#5EA8FF') },
      uAccent: { value: new THREE.Color('#38E0FF') },
      uFogColor: { value: new THREE.Color('#05070D') },
      uFogDensity: { value: FOG_DENSITY },
    },
  });

  const mesh = new THREE.InstancedMesh(geometry, material, matrices.length);
  mesh.frustumCulled = false;
  matrices.forEach((matrix, i) => mesh.setMatrixAt(i, matrix));
  mesh.instanceMatrix.needsUpdate = true;

  return { mesh, material };
}

/* ---------------------------------------------------------
   ЗЕМЛЯ
   Без неё здания висят в пустоте. Сетка гаснет вдаль вместе
   с туманом и даёт линию горизонта.
   --------------------------------------------------------- */
function createGround() {
  const vertexShader = `
    varying vec2  vWorld;
    varying float vFogDepth;

    void main() {
      vec4 world = modelMatrix * vec4(position, 1.0);
      vWorld = world.xz;

      vec4 viewPos = viewMatrix * world;
      vFogDepth = -viewPos.z;

      gl_Position = projectionMatrix * viewPos;
    }
  `;

  const fragmentShader = `
    precision highp float;

    uniform vec3  uLine;
    uniform vec3  uFogColor;
    uniform float uFogDensity;

    varying vec2  vWorld;
    varying float vFogDepth;

    /** Линия толщиной в один экранный пиксель на любом расстоянии */
    float gridLine(vec2 coord, float step) {
      vec2 g = abs(fract(coord / step - 0.5) - 0.5) / fwidth(coord / step);
      return 1.0 - min(min(g.x, g.y), 1.0);
    }

    void main() {
      float fine  = gridLine(vWorld, 8.0)  * 0.30;
      float major = gridLine(vWorld, 40.0) * 0.55;

      vec3 color = vec3(0.008, 0.011, 0.020) + uLine * (fine + major);

      float fogFactor = 1.0 - exp(-uFogDensity * uFogDensity * vFogDepth * vFogDepth);
      color = mix(color, uFogColor, clamp(fogFactor, 0.0, 1.0));

      gl_FragColor = vec4(color, 1.0);
    }
  `;

  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(900, 900),
    new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        uLine: { value: new THREE.Color('#2F7BFF') },
        uFogColor: { value: new THREE.Color('#05070D') },
        uFogDensity: { value: FOG_DENSITY },
      },
    }),
  );
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(0, -0.05, -110);
  return mesh;
}

/* ---------------------------------------------------------
   ЦИФРОВЫЕ ЧАСТИЦЫ
   --------------------------------------------------------- */
function createParticles(count, sprite) {
  const SPREAD_X = 150, SPREAD_Y = 90, SPREAD_Z = 380;

  const rand = makeRandom(90210);
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const speeds = new Float32Array(count);

  const blue = new THREE.Color('#5EA8FF');
  const cyan = new THREE.Color('#38E0FF');
  const pale = new THREE.Color('#DCE8FF');
  const tmp = new THREE.Color();

  for (let i = 0; i < count; i++) {
    positions[i * 3] = (rand() - 0.5) * SPREAD_X;
    positions[i * 3 + 1] = rand() * SPREAD_Y;
    positions[i * 3 + 2] = -rand() * SPREAD_Z + 60;
    speeds[i] = 0.6 + rand() * 2.2;

    const pick = rand();
    tmp.copy(pick < 0.55 ? blue : pick < 0.85 ? cyan : pale);
    colors[i * 3] = tmp.r;
    colors[i * 3 + 1] = tmp.g;
    colors[i * 3 + 2] = tmp.b;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const points = new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      size: 0.42,
      map: sprite,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    }),
  );
  points.frustumCulled = false;

  const update = (delta) => {
    const array = geometry.attributes.position.array;
    for (let i = 0; i < count; i++) {
      const y = i * 3 + 1;
      array[y] += speeds[i] * delta;
      if (array[y] > SPREAD_Y) array[y] = -4;   // ушла за потолок — вернулась вниз
    }
    geometry.attributes.position.needsUpdate = true;
  };

  return { points, update };
}

/* ---------------------------------------------------------
   ФИГУРА ИЗ ЧАСТИЦ
   Готовой модели человека нет, а плохая модель испортила бы
   всю сцену. Фигура собирается по капсулам скелета —
   получается голограмма, выглядящая намеренной.
   --------------------------------------------------------- */
const BONES = [
  { a: [0, 1.62, 0],     b: [0, 1.84, 0],      r: 0.15, w: 1.4 },
  { a: [0, 1.5, 0],      b: [0, 1.6, 0],       r: 0.06, w: 0.4 },
  { a: [0, 0.95, 0],     b: [0, 1.5, 0],       r: 0.19, w: 2.6 },
  { a: [-0.34, 1.45, 0], b: [0.34, 1.45, 0],   r: 0.08, w: 0.9 },
  { a: [-0.34, 1.45, 0], b: [-0.46, 1.05, 0.06], r: 0.07, w: 0.8 },
  { a: [-0.46, 1.05, 0.06], b: [-0.4, 0.68, 0.16], r: 0.06, w: 0.7 },
  { a: [0.34, 1.45, 0],  b: [0.46, 1.05, 0.06], r: 0.07, w: 0.8 },
  { a: [0.46, 1.05, 0.06], b: [0.4, 0.68, 0.16], r: 0.06, w: 0.7 },
  { a: [-0.18, 0.92, 0], b: [0.18, 0.92, 0],   r: 0.09, w: 0.6 },
  { a: [-0.18, 0.92, 0], b: [-0.2, 0.48, 0],   r: 0.08, w: 1.0 },
  { a: [-0.2, 0.48, 0],  b: [-0.2, 0.04, 0],   r: 0.07, w: 0.9 },
  { a: [0.18, 0.92, 0],  b: [0.2, 0.48, 0],    r: 0.08, w: 1.0 },
  { a: [0.2, 0.48, 0],   b: [0.2, 0.04, 0],    r: 0.07, w: 0.9 },
];

function createAvatar(count, sprite) {
  const rand = makeRandom(4242);
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const offsets = new Float32Array(count);

  // Частицы делятся по костям пропорционально «весу»: иначе тонкие руки
  // получат столько же точек, сколько корпус
  const totalWeight = BONES.reduce((sum, bone) => sum + bone.w, 0);

  const cyan = new THREE.Color('#38E0FF');
  const blue = new THREE.Color('#2F7BFF');
  const pale = new THREE.Color('#EAF1FF');
  const tmp = new THREE.Color();

  let i = 0;
  for (const bone of BONES) {
    const share = Math.round((bone.w / totalWeight) * count);

    for (let k = 0; k < share && i < count; k++, i++) {
      const t = rand();
      const x = bone.a[0] + (bone.b[0] - bone.a[0]) * t;
      const y = bone.a[1] + (bone.b[1] - bone.a[1]) * t;
      const z = bone.a[2] + (bone.b[2] - bone.a[2]) * t;

      const theta = rand() * Math.PI * 2;
      const phi = Math.acos(2 * rand() - 1);
      const radius = bone.r * (0.55 + rand() * 0.45);

      positions[i * 3] = x + Math.sin(phi) * Math.cos(theta) * radius;
      positions[i * 3 + 1] = y + Math.cos(phi) * radius * 0.7;
      positions[i * 3 + 2] = z + Math.sin(phi) * Math.sin(theta) * radius;
      offsets[i] = rand() * Math.PI * 2;

      // Голова и кисти светлее — взгляд цепляется за них первыми
      const bright = y > 1.55 || y < 0.15;
      const pick = rand();
      tmp.copy(bright && pick < 0.6 ? pale : pick < 0.6 ? cyan : blue);
      colors[i * 3] = tmp.r;
      colors[i * 3 + 1] = tmp.g;
      colors[i * 3 + 2] = tmp.b;
    }
  }
  // Хвост, если из-за округления долей точек не хватило
  for (; i < count; i++) {
    positions[i * 3] = 0;
    positions[i * 3 + 1] = 1.2;
    positions[i * 3 + 2] = 0;
    offsets[i] = rand() * Math.PI * 2;
    colors[i * 3] = cyan.r; colors[i * 3 + 1] = cyan.g; colors[i * 3 + 2] = cyan.b;
  }

  const base = positions.slice();

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const points = new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      size: 0.028,
      map: sprite,
      vertexColors: true,
      transparent: true,
      opacity: 0.95,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    }),
  );
  points.frustumCulled = false;

  const group = new THREE.Group();
  group.add(points);
  group.position.set(0, 0, -130);
  group.scale.setScalar(10);

  const update = (delta, time) => {
    group.rotation.y += delta * 0.16;

    // Лёгкое дрожание: фигура «дышит», а не стоит замороженной
    const array = geometry.attributes.position.array;
    for (let i = 0; i < count; i++) {
      const wobble = Math.sin(time * 1.6 + offsets[i]) * 0.012;
      array[i * 3] = base[i * 3] + wobble;
      array[i * 3 + 1] = base[i * 3 + 1] + Math.cos(time * 1.3 + offsets[i]) * 0.012;
      array[i * 3 + 2] = base[i * 3 + 2] + wobble;
    }
    geometry.attributes.position.needsUpdate = true;
  };

  return { group, update };
}

/* ---------------------------------------------------------
   ЗАПУСК СЦЕНЫ
   --------------------------------------------------------- */
export function initScene(canvas) {
  if (!canvas) return;

  // Проверяем WebGL: на старом устройстве вместо ошибки останется градиент
  try {
    const probe = document.createElement('canvas');
    if (!(window.WebGLRenderingContext && (probe.getContext('webgl2') || probe.getContext('webgl')))) {
      document.querySelector('.scene-root')?.classList.add('no-webgl');
      return;
    }
  } catch (error) {
    document.querySelector('.scene-root')?.classList.add('no-webgl');
    return;
  }

  const isMobile = window.matchMedia('(max-width: 768px)').matches;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: !isMobile,
    alpha: false,
    powerPreference: 'high-performance',
  });
  // Ограничиваем плотность пикселей: на Retina без этого считается
  // вчетверо больше точек и телефон греется
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile ? 1.5 : 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(BG, 1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(BG, FOG_DENSITY);

  const camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.5, 460);
  camera.position.set(0, 62, 150);

  const sprite = createSoftSprite();

  const city = createCity(isMobile ? sceneConfig.buildings.mobile : sceneConfig.buildings.desktop);
  const ground = createGround();
  const particles = createParticles(
    isMobile ? sceneConfig.particles.mobile : sceneConfig.particles.desktop,
    sprite,
  );
  const avatar = createAvatar(isMobile ? 1100 : 2400, sprite);

  scene.add(ground, city.mesh, particles.points, avatar.group);

  // Bloom дорогой: на телефонах и при отключённой анимации его нет —
  // там важнее стабильные кадры
  const useBloom = sceneConfig.bloomOnDesktop && !isMobile && !reducedMotion;
  let composer = null;
  if (useBloom) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    composer.addPass(new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      0.5,   // сила
      0.75,  // радиус
      0.5,   // порог яркости
    ));
    composer.addPass(new OutputPass());
  }

  /* ---- прокрутка ---- */
  let progress = 0;
  const readProgress = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    progress = max > 0 ? Math.min(Math.max(window.scrollY / max, 0), 1) : 0;
  };
  readProgress();
  window.addEventListener('scroll', readProgress, { passive: true });

  /* ---- параллакс за курсором ---- */
  const pointer = { x: 0, y: 0, targetX: 0, targetY: 0 };
  window.addEventListener('pointermove', (event) => {
    pointer.targetX = (event.clientX / window.innerWidth - 0.5) * 2;
    pointer.targetY = (event.clientY / window.innerHeight - 0.5) * 2;
  }, { passive: true });

  /* ---- размер окна ---- */
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const w = window.innerWidth, h = window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile ? 1.5 : 2));
      renderer.setSize(w, h);
      composer?.setSize(w, h);
      readProgress();
      if (reducedMotion) draw();
    }, 150);
  });

  const lookAt = new THREE.Vector3();

  /** Положение камеры по прокрутке. Сначала город виден силуэтом
      целиком, потом камера ныряет в ущелье между зданиями. */
  function placeCamera(delta) {
    const descent = easeOutCubic(Math.min(progress / DESCENT, 1));
    const height = 62 - descent * 52;
    const depth = 150 - progress * 235;

    // С высоты нужно смотреть далеко вперёд, иначе взгляд упирается
    // в пустую землю. У земли — коротко, тогда появляется скорость
    const lookAhead = 150 - descent * 105;
    const lookHeight = 27 - descent * 20;

    const damp = 1 - Math.pow(0.001, delta);
    pointer.x += (pointer.targetX - pointer.x) * damp;
    pointer.y += (pointer.targetY - pointer.y) * damp;

    const bob = Math.sin(clock.elapsedTime * 0.5) * 0.35;

    camera.position.set(
      pointer.x * 3.2,
      height + bob - pointer.y * 1.6,
      depth,
    );
    lookAt.set(pointer.x * 1.4, lookHeight, depth - lookAhead);
    camera.lookAt(lookAt);
  }

  function draw() {
    if (composer) composer.render();
    else renderer.render(scene, camera);
  }

  const clock = new THREE.Clock();

  // Отключённая анимация: один статичный кадр, никакого движения
  if (reducedMotion) {
    placeCamera(0.016);
    draw();
    return;
  }

  let running = true;
  document.addEventListener('visibilitychange', () => {
    running = !document.hidden;
    if (running) { clock.getDelta(); tick(); }   // сбрасываем накопленное время
  });

  function tick() {
    if (!running) return;
    requestAnimationFrame(tick);

    const delta = Math.min(clock.getDelta(), 0.05);
    const time = clock.elapsedTime;

    city.material.uniforms.uTime.value = time;
    particles.update(delta);
    avatar.update(delta, time);
    placeCamera(delta);

    draw();
  }

  tick();

  // Плавное появление после первого настоящего кадра
  canvas.style.opacity = '0';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    canvas.style.transition = 'opacity 1.1s ease';
    canvas.style.opacity = '1';
  }));
}
