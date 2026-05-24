// ============ APP.JS — Dark immersive portfolio ============

const TG_USER = 'rutsiyax';

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

// ----- chat widget -----
const initialMessages = [
  { from: 'in', text: 'Привет! 👋 Я Алиджон.', time: '' },
  { from: 'in', text: 'Делаю Telegram-ботов под ключ. Чем могу помочь?', time: '' },
];

const replies = {
  'Нужен бот': 'Отлично! Расскажи коротко: что бот должен делать? Принимать заказы, отвечать клиентам, парсить данные?',
  'Сколько стоит?': 'Зависит от задачи. Простой бот — от 5 000 ₽, с интеграциями и AI — от 15 000 ₽. Точную цену скажу после короткого брифа.',
  'Сроки': 'Обычно 3–7 дней на простой бот, до 2–3 недель на сложный с базой и API. Срочно? Сделаем приоритет.',
  'Привет': 'Привет 🙂 Чем могу быть полезен? Опиши задачу — отвечу с предложением.',
};

let chatMessages = initialMessages.slice();
function chatBody() { return document.getElementById('chat-body'); }

function renderChat() {
  const body = chatBody();
  if (!body) return;
  body.innerHTML = chatMessages.map(m => `
    <div class="msg ${m.from}">
      <div class="bubble">${escapeHtml(m.text)}</div>
      ${m.time ? `<div class="time">${escapeHtml(m.time)}</div>` : ''}
    </div>
  `).join('');
  body.scrollTop = body.scrollHeight;
}

function addMsg(msg) { chatMessages.push(msg); renderChat(); }

function showTyping() {
  const body = chatBody();
  const node = document.createElement('div');
  node.className = 'msg in typing';
  node.id = 'typing-indicator';
  node.innerHTML = '<div class="bubble"><i></i><i></i><i></i></div>';
  body.appendChild(node);
  body.scrollTop = body.scrollHeight;
}
function hideTyping() {
  const n = document.getElementById('typing-indicator');
  if (n) n.remove();
}

function nowTime() {
  const d = new Date();
  return d.getHours().toString().padStart(2,'0') + ':' + d.getMinutes().toString().padStart(2,'0');
}

function botReply(userText) {
  showTyping();
  setTimeout(() => {
    hideTyping();
    let reply = null;
    for (const key in replies) {
      if (userText.toLowerCase().includes(key.toLowerCase())) { reply = replies[key]; break; }
    }
    if (!reply) reply = 'Понял тебя 👌 Чтобы продолжить с деталями и файлами, открой Telegram — там удобнее.';
    addMsg({ from: 'in', text: reply, time: nowTime() });
    setTimeout(() => {
      addMsg({ from: 'in', text: '➜ Продолжим в Telegram: @' + TG_USER, time: nowTime() });
    }, 700);
  }, 900);
}

function initChat() {
  renderChat();
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');

  function send(text) {
    if (!text || !text.trim()) return;
    addMsg({ from: 'out', text: text.trim(), time: nowTime() });
    if (input) input.value = '';
    botReply(text);
  }

  if (sendBtn) sendBtn.addEventListener('click', () => send(input.value));
  if (input) input.addEventListener('keydown', e => {
    if (e.key === 'Enter') send(input.value);
  });
  document.querySelectorAll('.chat-quick button[data-text]').forEach(b => {
    b.addEventListener('click', () => send(b.dataset.text));
  });

  document.querySelectorAll('[data-tg-open]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const last = chatMessages.filter(m => m.from === 'out').slice(-1)[0];
      const txt = last ? last.text : 'Привет! Пишу с сайта';
      const url = `https://t.me/${TG_USER}?text=${encodeURIComponent(txt)}`;
      window.open(url, '_blank', 'noopener');
    });
  });
}

// ----- reveal on scroll -----
function initReveal() {
  const els = document.querySelectorAll('.reveal');
  const io = new IntersectionObserver((entries) => {
    entries.forEach(en => {
      if (en.isIntersecting) {
        en.target.classList.add('in');
        io.unobserve(en.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
  els.forEach(el => io.observe(el));
}

// ----- animated counters -----
function animateCounter(el) {
  const target = parseFloat(el.dataset.count);
  const suffix = el.dataset.suffix || '';
  const dur = 1400;
  const start = performance.now();
  function step(t) {
    const p = Math.min(1, (t - start) / dur);
    const eased = 1 - Math.pow(1 - p, 3);
    const v = Math.round(target * eased);
    el.textContent = v + suffix;
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
function initCounters() {
  const els = document.querySelectorAll('[data-count]');
  const io = new IntersectionObserver((entries) => {
    entries.forEach(en => {
      if (en.isIntersecting) {
        animateCounter(en.target);
        io.unobserve(en.target);
      }
    });
  }, { threshold: 0.5 });
  els.forEach(el => io.observe(el));
}

function initSkillBars() {
  const els = document.querySelectorAll('.skill');
  const io = new IntersectionObserver((entries) => {
    entries.forEach(en => {
      if (en.isIntersecting) {
        en.target.classList.add('in');
        io.unobserve(en.target);
      }
    });
  }, { threshold: 0.3 });
  els.forEach(el => io.observe(el));
}

function initSmoothNav() {
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', (e) => {
      const id = a.getAttribute('href');
      if (id.length < 2) return;
      const t = document.querySelector(id);
      if (t) {
        e.preventDefault();
        const top = t.getBoundingClientRect().top + window.scrollY - 80;
        window.scrollTo({ top, behavior: 'smooth' });
      }
    });
  });
}

// ----- cursor spotlight -----
function initSpotlight() {
  if (window.matchMedia('(hover: none)').matches) return;
  const sp = document.createElement('div');
  sp.className = 'spotlight';
  sp.style.opacity = '0';
  document.body.appendChild(sp);
  let tx = window.innerWidth / 2, ty = window.innerHeight / 2;
  let x = tx, y = ty;
  window.addEventListener('mousemove', (e) => {
    tx = e.clientX; ty = e.clientY;
    sp.style.opacity = '1';
  });
  window.addEventListener('mouseleave', () => { sp.style.opacity = '0'; });
  function tick() {
    x += (tx - x) * 0.15;
    y += (ty - y) * 0.15;
    sp.style.left = x + 'px';
    sp.style.top = y + 'px';
    requestAnimationFrame(tick);
  }
  tick();
}

// ----- magnetic buttons -----
function initMagnetic() {
  if (window.matchMedia('(hover: none)').matches) return;
  document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('mousemove', (e) => {
      const r = btn.getBoundingClientRect();
      const x = e.clientX - r.left - r.width / 2;
      const y = e.clientY - r.top - r.height / 2;
      btn.style.transform = `translate(${x * 0.15}px, ${y * 0.2}px)`;
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.transform = '';
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initChat();
  initReveal();
  initCounters();
  initSkillBars();
  initSmoothNav();
  initSpotlight();
  initMagnetic();
});
