(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const app = $('#app');
  const API = '__API__', API_KEY = '__KEY__';
  const CUR = '₸';
  const fmt = n => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const two = n => String(n).padStart(2, '0');
  const replay = (el, cls) => { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); };
  const store = {
    get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* storage is optional */ } },
  };

  /* ---------- languages: Russian text is the key, [Kazakh, English] ---------- */
  const TR = {
    'Бонусная карта магазинов одежды. Получайте бонусы с каждой покупки и оплачивайте ими до половины чека.': ['Киім дүкендерінің бонус картасы. Әр сатып алудан бонус жинап, чектің жартысына дейін бонуспен төлеңіз.', 'A bonus card for our clothing stores. Earn bonuses on every purchase and pay up to half of the bill with them.'],
    'Кешбэк бонусами с первой покупки': ['Алғашқы сатып алудан бонуспен кешбэк', 'Cashback in bonuses from the first purchase'],
    'Приветственные бонусы на карту': ['Картаға сәлемдесу бонустары', 'Welcome bonuses on your card'],
    'Карту выдаёт кассир в магазине и говорит код для входа.': ['Картаны дүкендегі кассир береді және кіру кодын айтады.', 'The cashier in the store issues the card and tells you the login code.'],
    'Войти': ['Кіру', 'Log in'], 'Ваш номер': ['Телефон', 'Your phone'], 'телефона': ['нөміріңіз', 'number'],
    'Введите номер, который вы назвали кассиру.': ['Кассирге айтқан нөміріңізді енгізіңіз.', 'Enter the number you gave the cashier.'], 'Далее': ['Әрі қарай', 'Next'],
    'Код от кассира': ['Кассирдің коды', 'Code from the cashier'],
    'Кассир назвал вам 6 цифр, когда выдавал карту. Если код потерялся, попросите на кассе новый.': ['Кассир картаны бергенде 6 сан айтты. Код жоғалса, кассадан жаңасын сұраңыз.', 'The cashier told you 6 digits when issuing the card. If you lost the code, ask for a new one at the till.'],
    'Номер: {0}': ['Нөмір: {0}', 'Number: {0}'],
    'Неверный код': ['Код қате', 'Wrong code'], 'Слишком много попыток. Попробуйте через 15 минут': ['Әрекет тым көп. 15 минуттан кейін көріңіз', 'Too many attempts. Try again in 15 minutes'],
    'Нет интернета. Проверьте связь': ['Интернет жоқ. Байланысты тексеріңіз', 'No internet. Check your connection'], 'Ошибка сервера. Попробуйте ещё раз': ['Сервер қатесі. Қайталап көріңіз', 'Server error. Please try again'],
    'Войдите снова': ['Қайта кіріңіз', 'Please log in again'], 'С возвращением, {0}': ['Қайта келуіңізбен, {0}', 'Welcome back, {0}'],
    'Доброй ночи': ['Қайырлы түн', 'Good night'], 'Доброе утро': ['Қайырлы таң', 'Good morning'], 'Добрый день': ['Қайырлы күн', 'Good afternoon'], 'Добрый вечер': ['Қайырлы кеш', 'Good evening'],
    'Бонусный счёт': ['Бонус шоты', 'Bonus balance'], 'бонусов': ['бонус', 'bonuses'], 'Нажмите, чтобы показать кассиру': ['Кассирге көрсету үшін басыңыз', 'Tap to show the cashier'],
    'Рейтинг · {0}': ['Рейтинг · {0}', 'Rating · {0}'], 'Вы лидер месяца': ['Сіз ай көшбасшысысыз', 'You lead this month'], 'Вы скрыты из рейтинга': ['Сіз рейтингте жасырылғансыз', 'You are hidden from the rating'],
    'До {0}-го места {1} ₸ покупок': ['{0}-орынға дейін {1} ₸', '{1} ₸ more to reach place {0}'], 'Сделайте покупку, чтобы попасть в рейтинг': ['Рейтингке кіру үшін сатып алу жасаңыз', 'Make a purchase to join the rating'],
    'До уровня «{0}»': ['«{0}» деңгейіне дейін', 'To {0} level'], 'Максимальный уровень': ['Ең жоғары деңгей', 'Top level'], 'кешбэк {0}%': ['кешбэк {0}%', '{0}% cashback'],
    'Базовый': ['Базалық', 'Basic'], 'Серебро': ['Күміс', 'Silver'], 'Золото': ['Алтын', 'Gold'],
    'Операции': ['Операциялар', 'Activity'], 'Все': ['Барлығы', 'All'], 'История': ['Тарих', 'History'], 'Начисления': ['Есептелген', 'Earned'], 'Списания': ['Жұмсалған', 'Spent'],
    'Начислено всего': ['Барлығы есептелді', 'Total earned'], 'Потрачено': ['Жұмсалды', 'Spent'], 'Пока пусто': ['Әзірге бос', 'Nothing here yet'],
    'Покажите карту на кассе, и здесь появятся бонусы': ['Кассада картаны көрсетіңіз, бонустар осында пайда болады', 'Show your card at the till and bonuses will appear here'],
    'Вы ещё не оплачивали покупки бонусами': ['Сіз әлі бонуспен төлеген жоқсыз', 'You have not paid with bonuses yet'],
    'Покупка': ['Сатып алу', 'Purchase'], 'Оплата бонусами': ['Бонуспен төлеу', 'Paid with bonuses'], 'Возврат покупки': ['Сатып алуды қайтару', 'Purchase refund'], 'Приветственные бонусы': ['Сәлемдесу бонустары', 'Welcome bonuses'],
    'чек': ['чек', 'bill'], 'возврат': ['қайтарылды', 'refunded'], 'Сегодня': ['Бүгін', 'Today'], 'Вчера': ['Кеше', 'Yesterday'],
    'Операция': ['Операция', 'Operation'], 'Сумма чека': ['Чек сомасы', 'Bill total'], 'Списано': ['Шегерілді', 'Deducted'], 'Начислено': ['Есептелді', 'Earned'], 'Оплачено деньгами': ['Ақшамен төленді', 'Paid in money'],
    'Снято начисленных': ['Есептелгені алынды', 'Earned taken back'], 'Возвращено бонусов': ['Қайтарылған бонус', 'Bonuses returned'], '1 бонус': ['1 бонус', '1 bonus'], 'Закрыть': ['Жабу', 'Close'],
    'Покажите кассиру': ['Кассирге көрсетіңіз', 'Show the cashier'], 'Бонусы начислятся сразу после оплаты': ['Бонустар төлемнен кейін бірден есептеледі', 'Bonuses are credited right after payment'],
    'Номер карты': ['Карта нөмірі', 'Card number'], 'Списать бонусы': ['Бонус жұмсау', 'Pay with bonuses'],
    'Чтобы оплатить бонусами, получите код и назовите его кассиру': ['Бонуспен төлеу үшін код алып, оны кассирге айтыңыз', 'To pay with bonuses, get a code and tell it to the cashier'],
    'Получить код': ['Код алу', 'Get code'], 'Код для кассира': ['Кассирге арналған код', 'Code for the cashier'], 'Назовите этот код кассиру. Действует {0}': ['Осы кодты кассирге айтыңыз. Жарамды: {0}', 'Tell this code to the cashier. Valid for {0}'],
    'Код устарел. Получите новый': ['Код ескірді. Жаңасын алыңыз', 'The code expired. Get a new one'], 'Новый код': ['Жаңа код', 'New code'],
    '+{0} бонусов на карту': ['Картаға +{0} бонус', '+{0} bonuses on your card'], 'Новый уровень: {0} · кешбэк {1}%': ['Жаңа деңгей: {0} · кешбэк {1}%', 'New level: {0} · {1}% cashback'],
    'Рейтинг': ['Рейтинг', 'Rating'], '{0} · до итогов': ['{0} · қорытындыға дейін', '{0} · results in'], '{0} д': ['{0} к', '{0} d'], 'Ваше место': ['Сіздің орныңыз', 'Your place'], 'очков': ['ұпай', 'points'], 'Вы': ['Сіз', 'You'],
    'Вы лидер': ['Сіз көшбасшысыз', 'You are the leader'], 'держите первое место': ['бірінші орынды сақтаңыз', 'hold the first place'], 'обгоните: {0}': ['басып озыңыз: {0}', 'overtake: {0}'],
    'Пока никто не покупал в этом месяце': ['Бұл айда әзірге ешкім сатып алмады', 'No purchases this month yet'], 'из {0} покупателей': ['{0} сатып алушыдан', 'out of {0} shoppers'],
    '1 тенге покупок = 1 очко. Рейтинг обнуляется 1-го числа каждого месяца.': ['1 теңге сатып алу = 1 ұпай. Рейтинг әр айдың 1-інде нөлденеді.', '1 tenge spent = 1 point. The rating resets on the 1st of every month.'],
    'Включите участие в профиле, чтобы видеть своё место': ['Орныңызды көру үшін профильде қатысуды қосыңыз', 'Turn on participation in your profile to see your place'],
    'Профиль': ['Профиль', 'Profile'], 'Уровни и правила': ['Деңгейлер мен ережелер', 'Levels and rules'], 'Язык': ['Тіл', 'Language'], 'Настройки': ['Баптаулар', 'Settings'],
    'Участвовать в рейтинге': ['Рейтингке қатысу', 'Take part in the rating'], 'Выйти': ['Шығу', 'Log out'], 'Вы снова в рейтинге': ['Сіз қайтадан рейтингтесіз', 'You are back in the rating'], 'Ваше имя скрыто из рейтинга': ['Атыңыз рейтингтен жасырылды', 'Your name is hidden from the rating'],
    'Выйти из аккаунта?': ['Аккаунттан шығасыз ба?', 'Log out?'], 'Карта и бонусы сохранятся. Чтобы войти снова, понадобится код от кассира.': ['Карта мен бонустар сақталады. Қайта кіру үшін кассирдің коды керек болады.', 'Your card and bonuses stay. To log in again you will need a code from the cashier.'], 'Остаться': ['Қалу', 'Stay'],
    'Язык приложения': ['Қолданба тілі', 'App language'], 'Язык изменён': ['Тіл өзгертілді', 'Language changed'], 'Карта': ['Карта', 'Card'],
    'Уровни': ['Деңгейлер', 'Levels'], 'Больше покупок, больше бонусов': ['Көбірек сатып алу, көбірек бонус', 'More purchases, more bonuses'],
    'Уровень зависит от суммы покупок за последние 12 месяцев.': ['Деңгей соңғы 12 айдағы сатып алу сомасына байланысты.', 'Your level depends on purchases over the last 12 months.'],
    'с первой покупки': ['алғашқы сатып алудан', 'from the first purchase'], 'от {0} ₸': ['{0} ₸-ден', 'from {0} ₸'], 'ваш': ['сіздікі', 'yours'], 'осталось {0} ₸': ['{0} ₸ қалды', '{0} ₸ to go'],
    '{0}% бонусами с каждой покупки': ['әр сатып алудан {0}% бонус', '{0}% back in bonuses on every purchase'],
    '1 бонус = 1 тенге при оплате': ['Төлегенде 1 бонус = 1 теңге', '1 bonus = 1 tenge when paying'], 'Бонусами можно оплатить до {0}% чека': ['Бонуспен чектің {0}%-ына дейін төлеуге болады', 'Bonuses cover up to {0}% of a bill'],
    'Списание подтверждается кодом из приложения': ['Шегеру қолданбадағы кодпен расталады', 'Paying with bonuses is confirmed with a code from the app'],
    'Кешбэк начисляется на сумму, оплаченную деньгами': ['Кешбэк ақшамен төленген сомаға есептеледі', 'Cashback is earned on the part paid with money'],
    'Обновлено': ['Жаңартылды', 'Updated'],
  };
  const LANGS = [['ru', 'RU', 'Русский'], ['kk', 'ҚАЗ', 'Қазақша'], ['en', 'EN', 'English']];
  let lang = 'ru';
  { const l = store.get('istanbul-lang'); if (LANGS.some(x => x[0] === l)) lang = l; }
  const t = (s, ...a) => { const e = TR[s]; let r = lang === 'ru' || !e ? s : e[lang === 'kk' ? 0 : 1]; a.forEach((v, i) => { r = r.split('{' + i + '}').join(v); }); return r; };
  const MONTHS = {
    ru: [['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'], ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']],
    kk: [['қаңтар', 'ақпан', 'наурыз', 'сәуір', 'мамыр', 'маусым', 'шілде', 'тамыз', 'қыркүйек', 'қазан', 'қараша', 'желтоқсан']],
    en: [['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']],
  };
  const dateText = d => { const m = MONTHS[lang]; return lang === 'en' ? `${d.getDate()} ${m[0][d.getMonth()]}` : `${d.getDate()} ${(m[1] || m[0])[d.getMonth()]}`; };
  const statics = [];
  (() => {
    const w = document.createTreeWalker(app, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { const s = n.nodeValue.trim(); if (/[А-Яа-яЁё]/.test(s)) statics.push({ n, ru: s, pre: n.nodeValue.match(/^\s*/)[0], post: n.nodeValue.match(/\s*$/)[0] }); }
  })();

  const P = {
    card: '<rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M2.5 10h19"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    trophy: '<path d="M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4v1a3 3 0 0 0 3 3M17 6h3v1a3 3 0 0 1-3 3M12 14v4M8 21h8M9 18h6"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    plus: '<path d="M12 5v14M5 12h14"/>', minus: '<path d="M5 12h14"/>',
    gift: '<rect x="3" y="8" width="18" height="13" rx="2"/><path d="M12 8v13M3 12h18M12 8S10.5 3 8 3.5 7.5 8 12 8zM12 8s1.5-5 4-4.5S16.5 8 12 8z"/>',
    back: '<path d="m15 18-6-6 6-6"/>', next: '<path d="m9 18 6-6-6-6"/>', check: '<path d="M5 12.5 10 17 19 7"/>',
    alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.01"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    out: '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3"/>',
    del: '<path d="M21 5H9l-6 7 6 7h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1z"/><path d="m16 9-6 6M10 9l6 6"/>',
    scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    wave: '<path d="M7 8a6 6 0 0 1 0 8M11 5.5a10 10 0 0 1 0 13M15 3a14 14 0 0 1 0 18"/>',
    refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    crown: '<path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5z"/>',
  };
  const ic = k => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${P[k]}</svg>`;
  $$('[data-ic]').forEach(e => { e.innerHTML = ic(e.dataset.ic); });
  $$('.back').forEach(b => { b.innerHTML = ic('back'); });
  $('#wmbig').innerHTML = [...'ISTANBUL'].map((c, i) => `<span style="--i:${i}">${c}</span>`).join('');

  function count(el, from, to, ms = 900, f = fmt) {
    cancelAnimationFrame(el._raf);
    if (calm || from === to) { el.textContent = f(to); return; }
    const t0 = performance.now();
    const step = now => { const k = Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - k, 3); el.textContent = f(from + (to - from) * e); if (k < 1) el._raf = requestAnimationFrame(step); };
    el._raf = requestAnimationFrame(step);
  }
  function setNum(el, v, anim, f = fmt) {
    if (el._v === undefined || !anim) { cancelAnimationFrame(el._raf); el.textContent = f(v); }
    else if (el._v !== v) count(el, el._v, v, 900, f);
    el._v = v;
  }

  /* ---------- server ---------- */
  class ApiError extends Error { constructor(code) { super(code); this.code = code; } }
  async function rpc(fn, args = {}) {
    let r;
    try { r = await fetch(API + fn, { method: 'POST', headers: { apikey: API_KEY, 'Content-Type': 'application/json' }, body: JSON.stringify(args) }); }
    catch (e) { throw new ApiError('net'); }
    let d = null; try { d = await r.json(); } catch (e) { /* empty body */ }
    if (!r.ok) throw new ApiError('server');
    if (d && d.error) throw new ApiError(d.error);
    return d;
  }
  const errText = c => t({ net: 'Нет интернета. Проверьте связь', code: 'Неверный код', locked: 'Слишком много попыток. Попробуйте через 15 минут', auth: 'Войдите снова' }[c] || 'Ошибка сервера. Попробуйте ещё раз');
  let busyN = 0;
  const busy = on => { busyN = Math.max(0, busyN + (on ? 1 : -1)); $('#busy').classList.toggle('on', busyN > 0); };

  /* ---------- state ---------- */
  let token = store.get('istanbul-client-token');
  let me = null, ops = [], rating = null;
  let settings = { welcome_bonus: 1000, max_spend_pct: 50, levels: [{ name: 'Базовый', pct: 3, from: 0 }, { name: 'Серебро', pct: 5, from: 100000 }, { name: 'Золото', pct: 7, from: 250000 }] };
  const fmtPhone = d => `+7 ${d.slice(0, 3)} ${d.slice(3, 6)} ${d.slice(6, 8)} ${d.slice(8)}`;
  const cardNo = () => `IST ${me.phone.slice(2, 6)} ${me.phone.slice(6)}`;
  const fullName = () => me.first_name + (me.last_name ? ' ' + me.last_name : '');
  const initials = () => (me.first_name[0] + (me.last_name ? me.last_name[0] : '')).toUpperCase();
  const hm = iso => { const d = new Date(iso); return two(d.getHours()) + ':' + two(d.getMinutes()); };
  function dayLabel(iso) {
    const d = new Date(iso), n = new Date();
    const diff = Math.round((new Date(n.getFullYear(), n.getMonth(), n.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
    if (diff === 0) return t('Сегодня'); if (diff === 1) return t('Вчера');
    return dateText(d);
  }
  const monthName = () => { const s = MONTHS[lang][0][new Date().getMonth()]; return s[0].toUpperCase() + s.slice(1); };

  /* ---------- barcode (EAN-13) ---------- */
  const EL = ['0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011'];
  const EG = ['0100111', '0110011', '0011011', '0100001', '0011101', '0111001', '0000101', '0010001', '0001001', '0010111'];
  const ER = ['1110010', '1100110', '1101100', '1000010', '1011100', '1001110', '1010000', '1000100', '1001000', '1110100'];
  const PAR = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL'];
  function ean13(d12) {
    let s = 0; [...d12].forEach((c, i) => { s += +c * (i % 2 ? 3 : 1); });
    const d = d12 + ((10 - s % 10) % 10), par = PAR[+d[0]]; let b = '101';
    for (let i = 1; i <= 6; i++) b += (par[i - 1] === 'L' ? EL : EG)[+d[i]];
    b += '01010'; for (let i = 7; i <= 12; i++) b += ER[+d[i]];
    return { digits: d, bits: b + '101' };
  }
  const cardCode = () => ean13('29' + me.phone);
  function barsSvg(bits) {
    let x = 0, n = 0, out = '';
    bits.match(/1+|0+/g).forEach(r => { if (r[0] === '1') out += `<rect x="${x}" y="0" width="${r.length}" height="10" style="--i:${n++}"/>`; x += r.length; });
    return `<svg class="bars" viewBox="0 0 95 10" preserveAspectRatio="none" aria-hidden="true">${out}</svg>`;
  }
  const spaced = d => `${d[0]} ${d.slice(1, 7)} ${d.slice(7)}`;

  /* ---------- effects ---------- */
  const fx = $('#fx'), ctx = fx.getContext('2d');
  let parts = [], raf = 0, W = 0, H = 0;
  function size() { const r = app.getBoundingClientRect(), d = Math.min(window.devicePixelRatio || 1, 2); W = r.width; H = r.height; fx.width = W * d; fx.height = H * d; ctx.setTransform(d, 0, 0, d, 0, 0); }
  size(); addEventListener('resize', size);
  const palette = () => app.classList.contains('is-dark') ? ['#FFFFFF', '#BDBDB8', '#6A6A66'] : ['#0B0B0B', '#5C5C58', '#BDBDB8'];
  function particle(x, y, vx, vy) {
    const c = palette();
    parts.push({ x, y, vx, vy, r: 3 + Math.random() * 5, rot: Math.random() * 6, vr: (Math.random() - .5) * .4, life: 1, c: c[Math.floor(Math.random() * c.length)], round: Math.random() < .4 });
    if (!raf) raf = requestAnimationFrame(frame);
  }
  function burst(x, y, n) { if (calm) return; for (let i = 0; i < n; i++) particle(x, y, (Math.random() - .5) * 11, -Math.random() * 10 - 2); }
  function rain(n, ms) { if (calm) return; for (let i = 0; i < n; i++) setTimeout(() => particle(Math.random() * W, -10, (Math.random() - .5) * 1.6, 1.5 + Math.random() * 3), Math.random() * ms); }
  function frame() {
    ctx.clearRect(0, 0, W, H);
    parts.forEach(p => {
      p.vy += .13; p.x += p.vx; p.y += p.vy; p.vx *= .985; p.rot += p.vr; p.life -= .008;
      ctx.save(); ctx.globalAlpha = Math.max(0, Math.min(1, p.life * 2)); ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.fillStyle = p.c;
      if (p.round) { ctx.beginPath(); ctx.arc(0, 0, p.r / 2, 0, 7); ctx.fill(); } else ctx.fillRect(-p.r / 2, -p.r / 4, p.r, p.r / 2);
      ctx.restore();
    });
    parts = parts.filter(p => p.life > 0 && p.y < H + 20);
    raf = parts.length ? requestAnimationFrame(frame) : 0;
    if (!raf) ctx.clearRect(0, 0, W, H);
  }
  const center = el => { const a = app.getBoundingClientRect(), r = el.getBoundingClientRect(); return { x: r.left - a.left + r.width / 2, y: r.top - a.top + r.height / 2 }; };
  let toastT;
  function toast(m) { const el = $('#toast'); el.textContent = m; el.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('on'), 2600); }

  /* ---------- sheet ---------- */
  const sheet = $('#sheet'), dim = $('#dim');
  let onSheetClose = null;
  function openSheet(html, cls = '', onClose = null) {
    const was = sheet.classList.contains('on');
    sheet.className = 'sheet pad ' + cls + (was ? ' on' : ''); sheet.innerHTML = '<div class="grab"></div>' + html; sheet.scrollTop = 0; onSheetClose = onClose;
    requestAnimationFrame(() => { sheet.classList.add('on'); dim.classList.add('on'); });
  }
  function closeSheet() { sheet.classList.remove('on'); dim.classList.remove('on'); const f = onSheetClose; onSheetClose = null; if (f) f(); }
  dim.addEventListener('click', closeSheet);
  sheet.addEventListener('click', e => { if (e.target.closest('[data-close]')) closeSheet(); });

  /* ---------- navigation ---------- */
  let stack = [], curTab = 'card';
  const curView = () => stack[stack.length - 1];
  const syncDark = () => app.classList.toggle('is-dark', $('#' + curView()).hasAttribute('data-dark'));
  function showView(id, dir) {
    $$('.view').forEach(v => v.classList.toggle('on', v.id === id));
    const v = $('#' + id); v.classList.remove('from-r', 'from-l'); void v.offsetWidth; if (dir) v.classList.add(dir === 'back' ? 'from-l' : 'from-r');
    parts = []; syncDark(); app.scrollTop = 0;
  }
  function push(id) { stack.push(id); showView(id, 'fwd'); }
  function pop() { if (stack.length > 1) { stack.pop(); showView(curView(), 'back'); if (curView() === 'v-main') showTab(curTab); } }
  function reset(id) { stack = [id]; showView(id, 'fwd'); }
  app.addEventListener('click', e => { if (e.target.closest('[data-back]')) pop(); const g = e.target.closest('[data-go]'); if (g) openSub(g.dataset.go); });
  /* the Android back button asks the page first */
  window.__back = () => {
    if (sheet.classList.contains('on')) { closeSheet(); return true; }
    if (stack.length > 1) { pop(); return true; }
    if (curView() === 'v-main' && curTab !== 'card') { showTab('card'); return true; }
    return false;
  };

  /* ---------- keypads, phone, code ---------- */
  $$('.keypad').forEach(k => { k.innerHTML = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'del'].map(d => d === '' ? '<span></span>' : `<button class="key ${d === 'del' ? 'x' : ''}" data-k="${d}" aria-label="${d === 'del' ? 'Delete' : d}">${d === 'del' ? ic('del') : d}</button>`).join(''); });
  app.addEventListener('click', e => { const k = e.target.closest('.key'); if (k) press(k.closest('.keypad').dataset.pad, k.dataset.k); });
  addEventListener('keydown', e => {
    const pad = curView() === 'v-phone' ? 'phone' : curView() === 'v-otp' ? 'otp' : null;
    if (!pad) return;
    if (/^\d$/.test(e.key)) press(pad, e.key); else if (e.key === 'Backspace') press(pad, 'del'); else if (e.key === 'Enter' && pad === 'phone') $('#phNext').click();
  });
  let phone = '', typed = '', checking = false;
  function press(pad, k) {
    if (pad === 'phone') {
      if (k === 'del') phone = phone.slice(0, -1); else if (phone.length < 10) phone += k;
      $('#phDigits').textContent = [phone.slice(0, 3), phone.slice(3, 6), phone.slice(6, 8), phone.slice(8)].filter(Boolean).join(' ');
      $('#phNext').disabled = phone.length !== 10;
    } else {
      if (checking || $('#otp').classList.contains('ok')) return;
      if (k === 'del') typed = typed.slice(0, -1); else if (typed.length < 6) typed += k;
      drawOtp(); if (typed.length === 6) checkCode();
    }
  }
  function drawOtp() { $$('#otp span').forEach((s, i) => { s.textContent = typed[i] || ''; s.className = i < typed.length ? 'f' : i === typed.length ? 'cur' : ''; }); }
  $('#wGo').addEventListener('click', () => { phone = ''; press('phone', 'del'); push('v-phone'); });
  $('#phNext').addEventListener('click', () => {
    if (phone.length !== 10) return;
    typed = ''; $('#otp').className = 'otp six'; drawOtp(); $('#otpPhone').textContent = t('Номер: {0}', fmtPhone(phone)); push('v-otp');
  });
  async function checkCode() {
    checking = true; busy(true);
    try {
      const r = await rpc('customer_login', { p_phone: phone, p_code: typed });
      token = r.token; store.set('istanbul-client-token', token);
      $('#otp').classList.add('ok');
      await load(false);
      setTimeout(() => { enterMain(); toast(t('С возвращением, {0}', me.first_name)); }, 500);
    } catch (e) {
      replay($('#otp'), 'bad'); typed = ''; setTimeout(drawOtp, 350); toast(errText(e.code));
    } finally { checking = false; busy(false); }
  }

  /* ---------- data ---------- */
  let loading = null, lastLoad = 0;
  function load(quiet) {
    if (loading) return loading;
    if (!quiet) busy(true);
    loading = rpc('customer_me', { p_token: token }).then(d => {
      const prev = me ? me.balance : +(store.get('istanbul-client-bal') || NaN);
      const prevLevel = me ? me.level.idx : null;
      me = d.customer; ops = d.ops; rating = d.rating; settings = d.settings || settings; lastLoad = Date.now();
      store.set('istanbul-client-bal', String(me.balance));
      return { prev, prevLevel };
    }).catch(e => {
      if (e.code === 'auth') { logoutLocal(); toast(errText('auth')); }
      else if (!quiet) toast(errText(e.code));
      throw e;
    }).finally(() => { loading = null; if (!quiet) busy(false); });
    return loading;
  }
  function refresh(quiet = true) {
    if (!token) return;
    load(quiet).then(({ prev, prevLevel }) => {
      if (curView() === 'v-main') showTab(curTab, true);
      if (!isNaN(prev) && me.balance > prev) {
        toast(t('+{0} бонусов на карту', fmt(me.balance - prev)));
        if (curTab === 'card') setTimeout(() => { const c = center($('#bcard')); burst(c.x, c.y, 90); }, 500);
      }
      if (prevLevel !== null && me.level.idx > prevLevel) { setTimeout(() => toast(t('Новый уровень: {0} · кешбэк {1}%', t(me.level.name), me.level.pct)), 2700); rain(120, 2200); }
    }).catch(() => {});
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden && token && Date.now() - lastLoad > 5000) refresh(true); });
  setInterval(() => { if (!document.hidden && token && curView() === 'v-main') refresh(true); }, 30000);
  $('#reload').addEventListener('click', () => { replay($('#reload'), 'spin'); refresh(false); });

  /* ---------- home ---------- */
  function opRows(o) {
    const day = dayLabel(o.created_at) + ', ' + hm(o.created_at), rows = [];
    if (o.kind === 'welcome') rows.push({ o, ic: 'gift', title: 'Приветственные бонусы', sub: day, amt: '+' + fmt(o.earn) });
    if (o.kind === 'sale') {
      rows.push({ o, ic: 'plus', title: 'Покупка', sub: `${day} · ${t('чек')} ${fmt(o.amount)} ${CUR}` + (o.refunded ? ` · ${t('возврат')}` : ''), amt: '+' + fmt(o.earn), ref: o.refunded });
      if (o.spend) rows.push({ o, ic: 'minus', neg: true, title: 'Оплата бонусами', sub: `${day} · ${t('чек')} ${fmt(o.amount)} ${CUR}`, amt: '−' + fmt(o.spend), ref: o.refunded });
    }
    if (o.kind === 'refund') { const net = o.spend - o.earn; rows.push({ o, ic: 'undo', neg: net < 0, title: 'Возврат покупки', sub: `${day} · ${t('чек')} ${fmt(o.amount)} ${CUR}`, amt: (net < 0 ? '−' : '+') + fmt(Math.abs(net)) }); }
    return rows;
  }
  const rowHtml = (r, i) => `<button class="op a${r.ref ? ' ref' : ''}" style="--i:${i}" data-op="${r.o.id}"><span class="ic ${r.neg ? 'neg' : ''}">${ic(r.ic)}</span><span class="t"><b>${t(r.title)}</b><span>${r.sub}</span></span><span class="amt ${r.neg ? 'neg' : ''}">${r.amt}</span></button>`;
  const allRows = () => ops.flatMap(opRows);
  function refreshHome(anim) {
    const h = new Date().getHours();
    $('#hiTime').textContent = t(h < 5 ? 'Доброй ночи' : h < 12 ? 'Доброе утро' : h < 18 ? 'Добрый день' : 'Добрый вечер');
    $('#hiName').textContent = fullName(); $('#holder').textContent = fullName();
    setNum($('#bal'), me.balance, anim); $('#balBox').classList.toggle('sm', me.balance >= 100000);
    const L = me.level;
    $('#lvlPill').textContent = `${t(L.name)} · ${L.pct}%`;
    $$('.cardnum').forEach(e => { e.textContent = cardNo(); });
    const c = cardCode(); $('#bcBars').innerHTML = barsSvg(c.bits); $('#bcDigits').textContent = spaced(c.digits);
    $('#lvT').textContent = L.next_name ? t('До уровня «{0}»', t(L.next_name)) : t('Максимальный уровень');
    $('#lvR').textContent = L.next_name ? `${fmt(me.year_total)} / ${fmt(L.next_from)} ${CUR}` : t('кешбэк {0}%', L.pct);
    requestAnimationFrame(() => { $('#lvBar').style.width = (L.next_from ? Math.min(100, me.year_total / L.next_from * 100) : 100) + '%'; });
    $('#steps').innerHTML = settings.levels.map((l, i) => `<span class="${i === L.idx ? 'on' : ''}">${t(l.name)} ${l.pct}%</span>`).join('');
    $('#rwT').textContent = t('Рейтинг · {0}', monthName());
    const pl = me.place;
    $('#rwPl').textContent = pl ? '#' + fmt(pl) : '—'; $('#rwPl').classList.toggle('sm', pl > 99);
    $('#rwS').textContent = !me.in_rating ? t('Вы скрыты из рейтинга') : !rating.me ? t('Сделайте покупку, чтобы попасть в рейтинг') : !rating.above ? t('Вы лидер месяца') : t('До {0}-го места {1} ₸ покупок', rating.above.place, fmt(rating.above.score - rating.me.score + 1));
    $('#homeOps').innerHTML = allRows().slice(0, 3).map((r, i) => rowHtml(r, 6 + i)).join('');
  }

  /* ---------- show the card, code for paying with bonuses ---------- */
  let codeTimer = 0;
  function openPay() {
    const c = cardCode();
    openSheet(`<h3>${t('Покажите кассиру')}</h3><div class="when">${t('Бонусы начислятся сразу после оплаты')}</div>
      <div class="paycode">${barsSvg(c.bits)}</div><div class="digits big">${spaced(c.digits)}</div>
      <div class="payrow"><div><small>${t('Номер карты')}</small><b>${cardNo()}</b><span>${t('Чтобы оплатить бонусами, получите код и назовите его кассиру')}</span></div></div>
      <div id="codeBox"><button class="cta" id="getCode">${ic('star')}${t('Списать бонусы')}</button></div><button class="cta ghost" style="margin-top:10px" data-close>${t('Закрыть')}</button>`, 'center', () => clearInterval(codeTimer));
  }
  async function getCode() {
    busy(true);
    try {
      const r = await rpc('customer_redeem_code', { p_token: token });
      let left = r.seconds;
      const box = $('#codeBox'); if (!box) return;
      box.innerHTML = `<div class="codebig"><small>${t('Код для кассира')}</small><b>${r.code.split('').map((d, i) => `<i style="--i:${i}">${d}</i>`).join('')}</b><span id="codeLeft"></span></div>`;
      const draw = () => {
        const el = $('#codeLeft'); if (!el) { clearInterval(codeTimer); return; }
        if (left <= 0) { clearInterval(codeTimer); box.innerHTML = `<p class="lead">${t('Код устарел. Получите новый')}</p><button class="cta" id="getCode">${t('Новый код')}</button>`; return; }
        el.textContent = t('Назовите этот код кассиру. Действует {0}', `${Math.floor(left / 60)}:${two(left % 60)}`); left--;
      };
      clearInterval(codeTimer); draw(); codeTimer = setInterval(draw, 1000);
    } catch (e) { toast(errText(e.code)); if (e.code === 'auth') { closeSheet(); logoutLocal(); } } finally { busy(false); }
  }
  $('#bcard').addEventListener('click', openPay);
  sheet.addEventListener('click', e => { if (e.target.closest('#getCode')) getCode(); });

  /* ---------- history ---------- */
  let hFilter = 'all';
  function renderOps() {
    let earned = 0, spent = 0;
    ops.forEach(o => {
      if (o.kind === 'sale' || o.kind === 'welcome') { earned += o.earn; spent += o.spend; }
      if (o.kind === 'refund') { earned -= o.earn; spent -= o.spend; }
    });
    setNum($('#hEarn'), earned, true, n => '+' + fmt(n)); setNum($('#hSpend'), spent, true, n => (Math.round(n) ? '−' : '') + fmt(n));
    const list = allRows().filter(r => hFilter === 'all' || (hFilter === 'spend' ? r.neg : !r.neg));
    let day = '', html = '';
    list.forEach((r, i) => { const d = dayLabel(r.o.created_at); if (d !== day) { day = d; html += `<div class="day a" style="--i:${3 + i}">${d}</div>`; } html += rowHtml(r, 3 + i); });
    $('#opsList').innerHTML = html || `<div class="empty a" style="--i:3"><div class="c"><img src="__BAGS__" alt=""></div><h3>${t('Пока пусто')}</h3><p>${t(hFilter === 'spend' ? 'Вы ещё не оплачивали покупки бонусами' : 'Покажите карту на кассе, и здесь появятся бонусы')}</p></div>`;
  }
  $('#hFilter').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; hFilter = b.dataset.f; $$('#hFilter button').forEach(x => x.classList.toggle('on', x === b)); renderOps(); });
  app.addEventListener('click', e => {
    const b = e.target.closest('[data-op]'); if (!b) return;
    const o = ops.find(x => x.id === +b.dataset.op); if (!o) return;
    const title = o.kind === 'welcome' ? 'Приветственные бонусы' : o.kind === 'refund' ? 'Возврат покупки' : 'Покупка';
    const kv = (k, v) => `<div><span>${t(k)}</span><b>${v}</b></div>`;
    let rows = '';
    if (o.kind === 'sale') rows = kv('Сумма чека', `${fmt(o.amount)} ${CUR}`) + (o.spend ? kv('Оплата бонусами', '−' + fmt(o.spend)) : '') + kv('Оплачено деньгами', `${fmt(o.pay)} ${CUR}`) + kv('Начислено', '+' + fmt(o.earn));
    if (o.kind === 'refund') rows = kv('Сумма чека', `${fmt(o.amount)} ${CUR}`) + kv('Снято начисленных', '−' + fmt(o.earn)) + (o.spend ? kv('Возвращено бонусов', '+' + fmt(o.spend)) : '');
    if (o.kind === 'welcome') rows = kv('Начислено', '+' + fmt(o.earn));
    openSheet(`<h3>${t(title)}</h3><div class="when">${dayLabel(o.created_at)}, ${hm(o.created_at)}</div><div class="kv">${rows}${kv('1 бонус', '1 ' + CUR)}</div><button class="cta ghost" data-close>${t('Закрыть')}</button>`);
  });

  /* ---------- rating ---------- */
  function renderRating() {
    const r = rating, top = r.top, H = ['58px', '76px', '46px'], order = [1, 0, 2];
    $('#podium').innerHTML = order.map(i => {
      const p = top[i];
      return `<div class="pd r${i + 1}${p && p.me ? ' mine' : ''}" style="--h:${H[order.indexOf(i)]};--d:${[.25, .4, .1][order.indexOf(i)]}s"><div class="who">${i === 0 ? `<svg class="crown" viewBox="0 0 24 24" aria-hidden="true">${P.crown}</svg>` : ''}<div class="av">${p ? esc(p.initials) : '—'}</div><div class="nm">${p ? (p.me ? t('Вы') : esc(p.name)) : '—'}</div><div class="pts">${p ? fmt(p.score) : ''}</div></div><div class="bar"><b>${i + 1}</b></div></div>`;
    }).join('');
    const mine = r.me;
    $('#mecard').hidden = !me.in_rating;
    if (me.in_rating) {
      const place = me.place || 1;
      $('#place').textContent = fmt(place); $('#place').classList.toggle('sm', place > 99);
      setNum($('#myScore'), mine ? mine.score : 0, true);
      if (mine && !r.above) { $('#gapLine').textContent = t('Вы лидер'); $('#target').textContent = t('держите первое место'); }
      else if (r.above) { const gap = r.above.score - (mine ? mine.score : 0) + 1; $('#gapLine').textContent = t('До {0}-го места {1} ₸ покупок', r.above.place, fmt(gap)); $('#target').textContent = t('обгоните: {0}', r.above.name); }
      else { $('#gapLine').textContent = t('Сделайте покупку, чтобы попасть в рейтинг'); $('#target').textContent = t('Пока никто не покупал в этом месяце'); }
      const prog = !mine ? .04 : !r.above ? 1 : Math.max(.04, mine.score / r.above.score);
      requestAnimationFrame(() => { $('#ring').style.strokeDashoffset = 169.65 * (1 - prog); });
    }
    const max = top.length ? top[0].score : 1;
    let html = top.slice(3).map((p, i) => `<div class="rk${p.me ? ' mine' : ''}" style="--i:${i}"><div class="pl">${p.place}</div><div class="av">${esc(p.initials)}</div><div class="t"><b>${p.me ? t('Вы') + ' · ' : ''}${esc(p.name)}</b><div class="lane"><i style="width:${p.score / max * 100}%"></i></div></div><div class="s"><b>${fmt(p.score)}</b></div></div>`).join('');
    if (me.in_rating && mine && mine.place > 10) html += `<div class="gapdots">···</div><div class="rk mine" style="--i:8"><div class="pl">${fmt(mine.place)}</div><div class="av">${esc(initials())}</div><div class="t"><b>${t('Вы')}</b><div class="lane"><i style="width:${mine.score / max * 100}%"></i></div></div><div class="s"><b>${fmt(mine.score)}</b></div></div>`;
    if (!top.length) html = `<p class="nf">${t('Пока никто не покупал в этом месяце')}</p>`;
    if (!me.in_rating) html = `<p class="nf">${t('Включите участие в профиле, чтобы видеть своё место')}</p>` + html;
    $('#rlist').innerHTML = html;
    $('#monthName').textContent = t('{0} · до итогов', monthName());
  }
  (function tick() {
    const n = new Date(), end = new Date(n.getFullYear(), n.getMonth() + 1, 1), left = Math.max(0, Math.floor((end - n) / 1000));
    const d = Math.floor(left / 86400), h = Math.floor(left % 86400 / 3600), m = Math.floor(left % 3600 / 60), s = left % 60;
    $('#timer').textContent = `${t('{0} д', d)} ${two(h)}:${two(m)}:${two(s)}`;
    setTimeout(tick, 1000);
  })();

  /* ---------- profile, language, levels ---------- */
  function refreshProfile() {
    $('#pAv').textContent = initials(); $('#pName').textContent = fullName(); $('#pPhone').textContent = fmtPhone(me.phone);
    $('#pLvl').textContent = t(me.level.name); $('#tRating').setAttribute('aria-checked', String(me.in_rating));
  }
  $('#tRating').addEventListener('click', async () => {
    const v = !me.in_rating; $('#tRating').setAttribute('aria-checked', String(v)); busy(true);
    try { await rpc('customer_settings', { p_token: token, p_in_rating: v }); me.in_rating = v; toast(t(v ? 'Вы снова в рейтинге' : 'Ваше имя скрыто из рейтинга')); refresh(true); }
    catch (e) { $('#tRating').setAttribute('aria-checked', String(me.in_rating)); toast(errText(e.code)); } finally { busy(false); }
  });
  function logoutLocal() { token = null; me = null; store.set('istanbul-client-token', null); store.set('istanbul-client-bal', null); reset('v-welcome'); }
  $('#logout').addEventListener('click', () => openSheet(`<h3>${t('Выйти из аккаунта?')}</h3><p class="lead">${t('Карта и бонусы сохранятся. Чтобы войти снова, понадобится код от кассира.')}</p><button class="cta" id="doLogout">${t('Выйти')}</button><button class="cta ghost" style="margin-top:10px" data-close>${t('Остаться')}</button>`));
  function openLang() { openSheet(`<h3>${t('Язык приложения')}</h3><div class="langs">${LANGS.map(([c, short, name]) => `<button class="lopt ${c === lang ? 'on' : ''}" data-lang="${c}"><b>${short}</b><span>${name}</span>${c === lang ? ic('check') : ''}</button>`).join('')}</div>`); }
  function applyLang() {
    statics.forEach(x => { x.n.nodeValue = x.pre + t(x.ru) + x.post; });
    document.documentElement.lang = lang; app.dataset.lang = lang;
    const cur = LANGS.find(x => x[0] === lang); $('#langBtn b').textContent = cur[1]; $('#pLang').textContent = cur[2];
    if (me && curView() === 'v-main') showTab(curTab, true);
  }
  $('#langBtn').addEventListener('click', openLang);
  $('#langRow').addEventListener('click', openLang);
  sheet.addEventListener('click', e => {
    const l = e.target.closest('.lopt[data-lang]');
    if (l) { lang = l.dataset.lang; store.set('istanbul-lang', lang); closeSheet(); applyLang(); toast(t('Язык изменён')); }
    if (e.target.closest('#doLogout')) { const tk = token; closeSheet(); logoutLocal(); rpc('customer_logout', { p_token: tk }).catch(() => {}); }
  });
  function openSub(id) {
    if (id !== 'v-levels') return;
    const li = me.level.idx, L = me.level;
    const rules = ['1 бонус = 1 тенге при оплате', t('Бонусами можно оплатить до {0}% чека', settings.max_spend_pct), 'Списание подтверждается кодом из приложения', 'Кешбэк начисляется на сумму, оплаченную деньгами'];
    $('#levelsBody').innerHTML = `<div class="topbar"><button class="back" data-back aria-label="Back">${ic('back')}</button>${t('Уровни')}</div><h2 class="big-t a" style="font-size:22px;margin-top:10px">${t('Больше покупок, больше бонусов')}</h2><p class="lead a" style="--i:1">${t('Уровень зависит от суммы покупок за последние 12 месяцев.')}</p>` +
      settings.levels.map((l, i) => `<div class="lc ${i === li ? 'cur' : ''} ${i === settings.levels.length - 1 ? 'gold' : ''} a" style="--i:${3 + i * 2}"><div><small>${i ? t('от {0} ₸', fmt(l.from)) : t('с первой покупки')}</small><div class="n">${t(l.name)}${i === li ? `<span class="badge">${t('ваш')}</span>` : ''}</div><div class="d">${t('{0}% бонусами с каждой покупки', l.pct)}</div></div><div class="p">${l.pct}%</div></div>`).join('') +
      (L.next_name ? `<div class="box a" style="--i:9"><h5>${t('До уровня «{0}»', t(L.next_name))}<span>${t('осталось {0} ₸', fmt(L.next_from - me.year_total))}</span></h5><div class="pbar"><i id="lvBar2"></i></div></div>` : '') +
      `<div class="rules" style="margin-top:12px">${rules.map((r, i) => `<div class="a" style="--i:${10 + i}"><b>${i + 1}</b>${t(r)}</div>`).join('')}</div>`;
    push(id); setTimeout(() => { const b = $('#lvBar2'); if (b) b.style.width = Math.min(100, me.year_total / L.next_from * 100) + '%'; }, 50);
  }
  $('#rw').addEventListener('click', () => showTab('rating'));
  $('#allOps').addEventListener('click', () => showTab('history'));

  /* ---------- tabs ---------- */
  const TABS = ['card', 'history', 'rating', 'profile'];
  function showTab(name, quiet) {
    if (!me) return;
    curTab = name;
    $$('.tab').forEach(x => x.classList.toggle('on', x.id === 't-' + name));
    $$('#nav button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
    $('#navInd').style.transform = `translateX(${TABS.indexOf(name) * 100}%)`;
    parts = [];
    if (name === 'card') refreshHome(true);
    if (name === 'history') renderOps();
    if (name === 'rating') renderRating();
    if (name === 'profile') refreshProfile();
    if (!quiet && Date.now() - lastLoad > 15000) refresh(true);
  }
  $('#nav').addEventListener('click', e => { const b = e.target.closest('button'); if (b) showTab(b.dataset.tab); });
  function enterMain() { $('#bal')._v = 0; $('#bal').textContent = '0'; hFilter = 'all'; $$('#hFilter button').forEach((b, i) => b.classList.toggle('on', i === 0)); reset('v-main'); showTab('card', true); }

  function drawWelcome() {
    $('#wPct').textContent = settings.levels[0].pct + '%'; $('#wWelcome').textContent = '+' + fmt(settings.welcome_bonus);
  }
  applyLang();
  if (token) {
    reset('v-welcome'); $('#wGo').disabled = true;
    load(false).then(() => enterMain()).catch(() => {}).finally(() => { $('#wGo').disabled = false; });
  } else reset('v-welcome');
  rpc('app_settings').then(s => { settings = s; drawWelcome(); }).catch(() => {});
})();
