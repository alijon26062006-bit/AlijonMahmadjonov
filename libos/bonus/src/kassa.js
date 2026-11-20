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
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => { const r = crypto.getRandomValues(new Uint8Array(1))[0] % 16; return (c === 'x' ? r : (r & 3) | 8).toString(16); }));

  /* ---------- languages: Russian text is the key, [Kazakh, English] ---------- */
  const TR = {
    'КАССА': ['КАССА', 'CASHIER'], 'Введите PIN-код': ['PIN-кодты енгізіңіз', 'Enter your PIN'], 'Неверный PIN-код': ['PIN-код қате', 'Wrong PIN'],
    'Слишком много попыток. Касса закрыта на 15 минут': ['Әрекет тым көп. Касса 15 минутқа жабылды', 'Too many attempts. The till is locked for 15 minutes'],
    'Нет интернета. Проверьте связь': ['Интернет жоқ. Байланысты тексеріңіз', 'No internet. Check your connection'], 'Ошибка сервера. Попробуйте ещё раз': ['Сервер қатесі. Қайталап көріңіз', 'Server error. Please try again'],
    'Смена закрыта. Войдите снова': ['Ауысым жабылды. Қайта кіріңіз', 'The shift is closed. Log in again'],
    'Смена открыта в {0}': ['Ауысым {0}-де ашылды', 'Shift opened at {0}'], 'Смена': ['Ауысым', 'Shift'], 'Эта смена': ['Осы ауысым', 'This shift'],
    'Сканировать карту клиента': ['Клиент картасын сканерлеу', "Scan the customer's card"], 'Наведите камеру на штрихкод в приложении': ['Камераны қолданбадағы штрих-кодқа бағыттаңыз', 'Point the camera at the barcode in the app'],
    'По номеру телефона': ['Телефон нөмірі бойынша', 'By phone number'], 'Новый клиент': ['Жаңа клиент', 'New customer'],
    'Все операции': ['Барлық операция', 'All activity'], 'Чеков': ['Чектер', 'Receipts'], 'Начислено': ['Есептелді', 'Earned'], 'Списано': ['Шегерілді', 'Redeemed'],
    'Операции': ['Операциялар', 'Activity'], 'Все': ['Барлығы', 'All'], 'Покупки': ['Сатып алулар', 'Purchases'], 'Списания': ['Шегерімдер', 'Redemptions'], 'Возвраты': ['Қайтарулар', 'Refunds'],
    'Пока пусто': ['Әзірге бос', 'Nothing here yet'], 'Операции появятся после первой покупки': ['Операциялар алғашқы сатып алудан кейін пайда болады', 'Activity appears after the first purchase'], 'Таких операций в этой смене нет': ['Бұл ауысымда мұндай операция жоқ', 'No such activity in this shift'],
    'Смена открыта в': ['Ауысым ашылған уақыт:', 'Shift opened at'], 'Выручка': ['Түсім', 'Revenue'], 'Средний чек': ['Орташа чек', 'Average receipt'],
    'Начислено бонусов': ['Есептелген бонус', 'Bonuses earned'], 'Списано бонусов': ['Шегерілген бонус', 'Bonuses redeemed'], 'Новых клиентов': ['Жаңа клиенттер', 'New customers'], 'Возвратов': ['Қайтарулар', 'Refunds'],
    'Продажи по часам': ['Сағат бойынша сату', 'Sales by hour'], 'тыс. ₸': ['мың ₸', 'thousand ₸'], 'Закрыть смену': ['Ауысымды жабу', 'Close shift'],
    'Профиль': ['Профиль', 'Profile'], 'Кассир · {0}': ['Кассир · {0}', 'Cashier · {0}'], 'Правила начисления': ['Есептеу ережелері', 'Bonus rules'], 'Язык': ['Тіл', 'Language'], 'Настройки': ['Баптаулар', 'Settings'],
    'Звук сканера': ['Сканер дыбысы', 'Scanner sound'], 'Вибрация': ['Діріл', 'Vibration'], 'Заблокировать кассу': ['Кассаны құлыптау', 'Lock the till'],
    'Касса': ['Касса', 'Till'], 'Язык приложения': ['Қолданба тілі', 'App language'], 'Язык изменён': ['Тіл өзгертілді', 'Language changed'],
    'Поиск клиента': ['Клиентті іздеу', 'Find a customer'], 'Введите первые цифры номера или последние четыре': ['Нөмірдің алғашқы немесе соңғы төрт санын енгізіңіз', 'Type the first digits of the number or the last four'],
    'Нет совпадений': ['Сәйкестік жоқ', 'No matches'], 'Клиента с таким номером нет': ['Мұндай нөмірлі клиент жоқ', 'No customer with this number'], 'Выдать карту на этот номер': ['Осы нөмірге карта беру', 'Issue a card for this number'], 'бонусов': ['бонус', 'bonuses'],
    'Выдайте карту': ['Картаны бір минутта', 'Issue a card'], 'за минуту': ['беріңіз', 'in a minute'], 'Телефон': ['Телефон', 'Phone'], 'Имя': ['Аты', 'First name'], 'Фамилия': ['Тегі', 'Last name'],
    'Например, Алихан': ['Мысалы, Алихан', 'For example, Alikhan'], 'Необязательно': ['Міндетті емес', 'Optional'],
    'Клиент сразу получит приветственные бонусы. Вы увидите код для входа в приложение: скажите его клиенту.': ['Клиент бірден сәлемдесу бонусын алады. Қолданбаға кіру кодын көресіз: оны клиентке айтыңыз.', 'The customer gets welcome bonuses right away. You will see a login code for the app: tell it to the customer.'],
    'Выдать карту': ['Карта беру', 'Issue card'], 'Клиент с таким номером уже есть': ['Мұндай нөмірлі клиент бар', 'This number already has a card'],
    'Проверьте номер: нужно 10 цифр после +7': ['Нөмірді тексеріңіз: +7-ден кейін 10 сан керек', 'Check the number: 10 digits after +7'],
    'Карта выдана': ['Карта берілді', 'Card issued'], 'Код для входа в приложение': ['Қолданбаға кіру коды', 'App login code'],
    'Скажите клиенту: установить приложение ISTANBUL, войти по номеру телефона и этому коду.': ['Клиентке айтыңыз: ISTANBUL қолданбасын орнатып, телефон нөмірі мен осы кодпен кірсін.', 'Tell the customer to install the ISTANBUL app and log in with their phone number and this code.'],
    'Код показывается один раз. Если клиент его потеряет, выдайте новый в карте клиента.': ['Код бір рет көрсетіледі. Клиент жоғалтса, клиент картасында жаңасын беріңіз.', 'The code is shown once. If the customer loses it, issue a new one on the customer card.'],
    'Понятно': ['Түсінікті', 'Got it'], 'Новый код для входа': ['Жаңа кіру коды', 'New login code'], 'Старый код больше не работает': ['Ескі код енді жұмыс істемейді', 'The old code no longer works'],
    'Клиент': ['Клиент', 'Customer'], 'Бонусный счёт': ['Бонус шоты', 'Bonus balance'], 'Покупки за год': ['Жылдық сатып алу', 'Purchases, 12 mo'], 'Рейтинг': ['Рейтинг', 'Rating'], 'Визитов': ['Келу саны', 'Visits'],
    'До уровня «{0}»': ['«{0}» деңгейіне дейін', 'To {0} level'], 'Максимальный уровень': ['Ең жоғары деңгей', 'Top level'], 'кешбэк {0}%': ['кешбэк {0}%', '{0}% cashback'],
    'Базовый': ['Базалық', 'Basic'], 'Серебро': ['Күміс', 'Silver'], 'Золото': ['Алтын', 'Gold'],
    'Операции клиента': ['Клиент операциялары', 'Customer activity'], 'Операций пока нет': ['Әзірге операция жоқ', 'No activity yet'],
    'Возврат': ['Қайтару', 'Refund'], 'Провести покупку': ['Сатып алуды өткізу', 'New purchase'], 'Покупка': ['Сатып алу', 'Purchase'], 'Новая карта': ['Жаңа карта', 'New card'], 'возврат оформлен': ['қайтарылды', 'refunded'],
    'чек': ['чек', 'bill'], 'Сегодня': ['Бүгін', 'Today'], 'Вчера': ['Кеше', 'Yesterday'],
    'Сумма чека': ['Чек сомасы', 'Bill total'], 'Кешбэк {0}%': ['Кешбэк {0}%', 'Cashback {0}%'], 'Далее': ['Әрі қарай', 'Next'],
    'Списать бонусы': ['Бонус шегеру', 'Redeem bonuses'], 'На счёте {0} · можно списать до {1}': ['Шотта {0} · {1} дейін шегеруге болады', '{0} on the card · up to {1} can be redeemed'],
    'Бонусов пока недостаточно для списания': ['Шегеруге бонус әлі жеткіліксіз', 'Not enough bonuses to redeem yet'],
    'Не списывать': ['Шегермеу', 'None'], 'Половина': ['Жартысы', 'Half'], 'Максимум': ['Барынша', 'Maximum'],
    'Оплата бонусами': ['Бонуспен төлеу', 'Paid with bonuses'], 'К оплате': ['Төлеуге', 'To pay'], 'Будет начислено': ['Есептеледі', 'Will be earned'],
    'Ввести код клиента': ['Клиент кодын енгізу', "Enter the customer's code"], 'Подтверждение': ['Растау', 'Confirmation'], 'Код от клиента': ['Клиенттің коды', 'Code from customer'],
    'Попросите клиента открыть приложение, нажать на карту и «Списать бонусы». Введите код, который он назовёт, чтобы списать {0} бонусов.': ['Клиенттен қолданбаны ашып, картаны және «Бонус жұмсау» батырмасын басуын сұраңыз. {0} бонус шегеру үшін ол айтқан кодты енгізіңіз.', 'Ask the customer to open the app, tap the card and "Pay with bonuses". Enter the code they tell you to redeem {0} bonuses.'],
    'Неверный код. Попросите клиента проверить код': ['Код қате. Клиенттен кодты тексеруді сұраңыз', 'Wrong code. Ask the customer to check it'],
    'Код устарел. Попросите клиента получить новый': ['Код ескірді. Клиенттен жаңасын алуды сұраңыз', 'The code expired. Ask the customer to get a new one'],
    'Нельзя списать столько бонусов': ['Мұнша бонусты шегеруге болмайды', 'That many bonuses cannot be redeemed'],
    'Покупка проведена': ['Сатып алу өткізілді', 'Purchase complete'], 'чек № {0}': ['чек № {0}', 'receipt no. {0}'], 'Новый баланс клиента': ['Клиенттің жаңа балансы', "Customer's new balance"],
    'Следующий клиент': ['Келесі клиент', 'Next customer'], 'Карта клиента': ['Клиент картасы', 'Customer card'],
    'Новый уровень клиента: {0} · кешбэк {1}%': ['Клиенттің жаңа деңгейі: {0} · кешбэк {1}%', 'New customer level: {0} · {1}% cashback'],
    'Чек №': ['Чек №', 'Receipt no.'], 'Закрыть': ['Жабу', 'Close'], 'Оформить возврат': ['Қайтаруды рәсімдеу', 'Make a refund'],
    'Какую покупку вернуть?': ['Қай сатып алуды қайтару керек?', 'Which purchase to refund?'], 'У клиента нет покупок для возврата': ['Клиентте қайтаратын сатып алу жоқ', 'This customer has no purchases to refund'],
    'Возврат покупки': ['Сатып алуды қайтару', 'Purchase refund'], 'Вернуть клиенту': ['Клиентке қайтару', 'Return to customer'], 'Снять начисленные бонусы': ['Есептелген бонусты алып тастау', 'Take back earned bonuses'],
    'Вернуть списанные бонусы': ['Шегерілген бонусты қайтару', 'Return redeemed bonuses'], 'Отмена': ['Болдырмау', 'Cancel'], 'Возврат оформлен · {0} ₸': ['Қайтару рәсімделді · {0} ₸', 'Refund done · {0} ₸'],
    'Эта покупка уже возвращена': ['Бұл сатып алу қайтарылған', 'This purchase is already refunded'],
    'Закрыть смену?': ['Ауысымды жабасыз ба?', 'Close the shift?'], 'Сформируем отчёт за смену и заблокируем кассу.': ['Ауысым есебі жасалып, касса құлыпталады.', 'We will make the shift report and lock the till.'],
    'Смена закрыта': ['Ауысым жабылды', 'Shift closed'], '{0} ч {1} мин': ['{0} сағ {1} мин', '{0} h {1} min'], 'Готово': ['Дайын', 'Done'],
    'Правила': ['Ережелер', 'Rules'], 'Как начисляются бонусы': ['Бонус қалай есептеледі', 'How bonuses work'], 'с первой покупки': ['алғашқы сатып алудан', 'from the first purchase'], 'от {0} ₸': ['{0} ₸-ден', 'from {0} ₸'],
    'Уровень считается по сумме покупок за 12 месяцев': ['Деңгей 12 айдағы сатып алу сомасы бойынша есептеледі', 'The level depends on purchases over 12 months'],
    '1 бонус = 1 тенге при оплате': ['Төлегенде 1 бонус = 1 теңге', '1 bonus = 1 tenge when paying'], 'Бонусами можно оплатить до {0}% чека': ['Бонуспен чектің {0}%-ына дейін төлеуге болады', 'Bonuses cover up to {0}% of a bill'],
    'Списание подтверждается кодом из приложения клиента': ['Шегеру клиент қолданбасындағы кодпен расталады', "Redemption is confirmed with a code from the customer's app"],
    'Кешбэк начисляется на сумму, оплаченную деньгами': ['Кешбэк ақшамен төленген сомаға есептеледі', 'Cashback is earned on the part paid with money'],
    'При возврате начисленные бонусы снимаются, списанные возвращаются': ['Қайтарғанда есептелген бонус алынып, шегерілген бонус қайтарылады', 'On a refund, earned bonuses are taken back and redeemed ones are returned'],
    'Новый клиент получает {0} приветственных бонусов': ['Жаңа клиент {0} сәлемдесу бонусын алады', 'A new customer gets {0} welcome bonuses'],
    'Карта не найдена': ['Карта табылмады', 'Card not found'], 'Номер карты или телефона': ['Карта немесе телефон нөмірі', 'Card or phone number'],
    'Камера доступна только в приложении. Введите номер под штрихкодом или телефон клиента.': ['Камера тек қолданбада жұмыс істейді. Штрих-код астындағы нөмірді немесе клиент телефонын енгізіңіз.', "The camera works only in the app. Type the number under the barcode or the customer's phone."],
    'Найти': ['Табу', 'Find'],
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
    $$('[placeholder]', app).forEach(e => { if (/[А-Яа-яЁё]/.test(e.getAttribute('placeholder'))) statics.push({ e, ru: e.getAttribute('placeholder') }); });
  })();

  const P = {
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    userplus: '<circle cx="10" cy="8" r="4"/><path d="M2 21a8 8 0 0 1 16 0M19 8v6M16 11h6"/>',
    gift: '<rect x="3" y="8" width="18" height="13" rx="2"/><path d="M12 8v13M3 12h18M12 8S10.5 3 8 3.5 7.5 8 12 8zM12 8s1.5-5 4-4.5S16.5 8 12 8z"/>',
    back: '<path d="m15 18-6-6 6-6"/>', next: '<path d="m9 18 6-6-6-6"/>', check: '<path d="M5 12.5 10 17 19 7"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    sms: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.4A8 8 0 1 1 21 12z"/><path d="M8 12h.01M12 12h.01M16 12h.01"/>',
    del: '<path d="M21 5H9l-6 7 6 7h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1z"/><path d="m16 9-6 6M10 9l6 6"/>',
    scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
    bag: '<path d="M5 8h14l-1 12H6zM9 8V6a3 3 0 0 1 6 0v2"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-8M21 20H3"/>',
    lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2.5"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
    sound: '<path d="M4 9v6h4l5 4V5L8 9zM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>',
    vib: '<rect x="8" y="3" width="8" height="18" rx="2"/><path d="M4 9v6M20 9v6"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="m10.8 12.2 8.7-8.7M17 6l2.5 2.5M14.5 8.5 16 10"/>',
  };
  const ic = k => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${P[k]}</svg>`;
  $$('[data-ic]').forEach(e => { e.innerHTML = ic(e.dataset.ic); });
  $$('.back').forEach(b => { b.innerHTML = ic('back'); });
  $('#wm').innerHTML = [...'ISTANBUL'].map((c, i) => `<span style="--i:${i}">${c}</span>`).join('');

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
    if (d && d.error) { const er = new ApiError(d.error); er.data = d; throw er; }
    return d;
  }
  let busyN = 0;
  const busy = on => { busyN = Math.max(0, busyN + (on ? 1 : -1)); $('#busy').classList.toggle('on', busyN > 0); };
  const ERR = { net: 'Нет интернета. Проверьте связь', locked: 'Слишком много попыток. Касса закрыта на 15 минут', pin: 'Неверный PIN-код', auth: 'Смена закрыта. Войдите снова', code: 'Неверный код. Попросите клиента проверить код', code_expired: 'Код устарел. Попросите клиента получить новый', spend: 'Нельзя списать столько бонусов', exists: 'Клиент с таким номером уже есть', phone: 'Проверьте номер: нужно 10 цифр после +7', not_found: 'Карта не найдена', refunded: 'Эта покупка уже возвращена' };
  const errText = c => t(ERR[c] || 'Ошибка сервера. Попробуйте ещё раз');
  /* every call after login: on a lost session go back to the PIN screen */
  async function call(fn, args = {}, { quiet = false } = {}) {
    if (!quiet) busy(true);
    try { return await rpc(fn, { p_token: token, ...args }); }
    catch (e) { if (e.code === 'auth') { lockLocal(); toast(errText('auth')); } else if (!quiet && !e.handled) toast(errText(e.code)); throw e; }
    finally { if (!quiet) busy(false); }
  }

  /* ---------- state ---------- */
  let token = store.get('istanbul-kassa-token');
  let cashier = null, settings = null, shift = null, shiftOps = [];
  const prefs = { sound: store.get('istanbul-kassa-sound') !== '0', vibro: store.get('istanbul-kassa-vibro') !== '0' };
  const hm = iso => { const d = new Date(iso); return two(d.getHours()) + ':' + two(d.getMinutes()); };
  function dayLabel(iso) {
    const d = new Date(iso), n = new Date();
    const diff = Math.round((new Date(n.getFullYear(), n.getMonth(), n.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
    if (diff === 0) return t('Сегодня'); if (diff === 1) return t('Вчера');
    return dateText(d);
  }
  const cname = c => c.first_name + (c.last_name ? ' ' + c.last_name : '');
  const cinit = c => (c.first_name[0] + (c.last_name ? c.last_name[0] : '')).toUpperCase();
  const fmtPhone = d => `+7 ${d.slice(0, 3)} ${d.slice(3, 6)} ${d.slice(6, 8)} ${d.slice(8)}`;
  const cardNo = c => `IST ${c.phone.slice(2, 6)} ${c.phone.slice(6)}`;
  const durText = ms => t('{0} ч {1} мин', Math.floor(ms / 3600000), Math.floor(ms % 3600000 / 60000));

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
  function toast(m) { const el = $('#toast'); el.textContent = m; el.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('on'), 2800); }
  let audio = null;
  function beep() {
    if (prefs.vibro && navigator.vibrate) { try { navigator.vibrate(40); } catch (e) { /* optional */ } }
    if (!prefs.sound) return;
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const o = audio.createOscillator(), g = audio.createGain(), now = audio.currentTime;
      o.frequency.value = 1250; g.gain.setValueAtTime(.08, now); g.gain.exponentialRampToValueAtTime(.0001, now + .13);
      o.connect(g); g.connect(audio.destination); o.start(now); o.stop(now + .14);
    } catch (e) { /* sound is optional */ }
  }

  /* ---------- sheet ---------- */
  const sheet = $('#sheet'), dim = $('#dim');
  function openSheet(html, cls = '') {
    const was = sheet.classList.contains('on');
    sheet.className = 'sheet pad ' + cls + (was ? ' on' : ''); sheet.innerHTML = '<div class="grab"></div>' + html; sheet.scrollTop = 0;
    requestAnimationFrame(() => { sheet.classList.add('on'); dim.classList.add('on'); });
  }
  function closeSheet() { sheet.classList.remove('on'); dim.classList.remove('on'); }
  dim.addEventListener('click', () => { if (!sheet.classList.contains('locked')) closeSheet(); });
  sheet.addEventListener('click', e => { if (e.target.closest('[data-close]')) closeSheet(); });

  /* ---------- navigation ---------- */
  let stack = [], curTab = 'scan', cur = null, curOps = [];
  const curView = () => stack[stack.length - 1];
  const syncDark = () => app.classList.toggle('is-dark', $('#' + curView()).hasAttribute('data-dark'));
  function showView(id, dir) {
    $$('.view').forEach(v => v.classList.toggle('on', v.id === id));
    const v = $('#' + id); v.classList.remove('from-r', 'from-l'); void v.offsetWidth; if (dir) v.classList.add(dir === 'back' ? 'from-l' : 'from-r');
    parts = []; syncDark(); app.scrollTop = 0;
  }
  function push(id) { stack.push(id); showView(id, 'fwd'); }
  function pop() {
    if (stack.length < 2) return;
    stack.pop(); showView(curView(), 'back');
    if (curView() === 'v-main') showTab(curTab);
    if (curView() === 'v-client') renderClient(false);
  }
  function reset(id) { stack = [id]; showView(id, 'fwd'); }
  function goHome() { stack = ['v-main']; showView('v-main', 'back'); showTab('scan'); }
  app.addEventListener('click', e => {
    if (e.target.closest('[data-back]')) pop();
    const g = e.target.closest('[data-go]'); if (g) openSub(g.dataset.go);
    const tb = e.target.closest('[data-tab]'); if (tb && stack.length) showTab(tb.dataset.tab);
  });
  window.__back = () => {
    if (sheet.classList.contains('on')) { if (!sheet.classList.contains('locked')) closeSheet(); return true; }
    if (curView() === 'v-sale') { $('#saleBack').click(); return true; }
    if (curView() === 'v-done') { goHome(); return true; }
    if (stack.length > 1) { pop(); return true; }
    if (curView() === 'v-main' && curTab !== 'scan') { showTab('scan'); return true; }
    return false;
  };

  /* ---------- keypads ---------- */
  $$('.keypad').forEach(k => {
    const mid = k.dataset.pad === 'amt' ? '00' : '';
    k.innerHTML = ['1', '2', '3', '4', '5', '6', '7', '8', '9', mid, '0', 'del'].map(d => d === '' ? '<span></span>' : `<button class="key ${d === 'del' ? 'x' : ''}" data-k="${d}" aria-label="${d === 'del' ? 'Delete' : d}">${d === 'del' ? ic('del') : d}</button>`).join('');
  });
  const PADS = { pin: k => pressPin(k), find: k => pressFind(k), amt: k => pressAmt(k), code: k => pressCode(k) };
  app.addEventListener('click', e => { const k = e.target.closest('.key'); if (k) PADS[k.closest('.keypad').dataset.pad](k.dataset.k); });
  addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || sheet.classList.contains('on')) return;
    const v = curView(), pad = v === 'v-lock' ? 'pin' : v === 'v-find' ? 'find' : v === 'v-sale' && sale.step === 'amt' ? 'amt' : v === 'v-sale' && sale.step === 'code' ? 'code' : null;
    if (!pad) return;
    if (/^\d$/.test(e.key)) PADS[pad](e.key); else if (e.key === 'Backspace') PADS[pad]('del'); else if (e.key === 'Enter' && pad === 'amt') $('#amtNext').click();
  });

  /* ---------- lock screen ---------- */
  let pin = '', pinBusy = false;
  const pins = $('#pins');
  const drawPins = () => $$('i', pins).forEach((d, i) => d.classList.toggle('f', i < pin.length));
  function pressPin(k) {
    if (pinBusy) return;
    if (k === 'del') pin = pin.slice(0, -1); else if (pin.length < 6) pin += k;
    drawPins(); $('#lockMsg').textContent = '';
    if (pin.length === 6) checkPin();
  }
  async function checkPin() {
    pinBusy = true; busy(true);
    try {
      const r = await rpc('cashier_login', { p_pin: pin });
      token = r.token; store.set('istanbul-kassa-token', token);
      cashier = r.name; settings = r.settings; shift = r.shift; shiftOps = [];
      pins.classList.add('ok');
      setTimeout(() => { pin = ''; pins.classList.remove('ok'); drawPins(); reset('v-main'); showTab('scan'); toast(t('Смена открыта в {0}', hm(shift.opened_at))); pinBusy = false; }, 600);
      loadMe(true);
    } catch (e) {
      replay(pins, 'bad'); pin = ''; setTimeout(drawPins, 350); $('#lockMsg').textContent = errText(e.code); pinBusy = false;
    } finally { busy(false); }
  }
  function lockLocal() { token = null; store.set('istanbul-kassa-token', null); closeSheet(); pin = ''; drawPins(); reset('v-lock'); }

  async function loadMe(quiet) {
    const r = await call('cashier_me', {}, { quiet });
    cashier = r.name; settings = r.settings; shift = r.shift; shiftOps = r.ops;
    $('#lockStore').textContent = settings.store_name;
    if (curView() === 'v-main') showTab(curTab, true);
    return r;
  }

  /* ---------- operations ---------- */
  const opIcon = o => o.kind === 'refund' ? 'undo' : o.kind === 'welcome' ? 'userplus' : 'bag';
  const opKind = o => t(o.kind === 'refund' ? 'Возврат' : o.kind === 'welcome' ? 'Новая карта' : 'Покупка');
  function opRow(o, i, byClient) {
    const neg = o.kind === 'refund';
    const sub = (byClient ? `${dayLabel(o.created_at)}, ` : '') + hm(o.created_at) + (o.kind === 'welcome' ? (byClient ? '' : ` · ${t('Новая карта')}`) : ` · ${t('чек')} ${fmt(o.amount)} ${CUR}` + (o.spend && !neg ? ` · −${fmt(o.spend)}` : ''));
    return `<button class="op a${o.refunded ? ' ref' : ''}" style="--i:${i}" data-op="${o.id}"><span class="ic ${neg ? 'neg' : ''}">${ic(opIcon(o))}</span><span class="t"><b>${byClient ? opKind(o) : esc(cname(o))}</b><span>${sub}${o.refunded ? ` · ${t('возврат оформлен')}` : ''}</span></span><span class="amt ${neg ? 'neg' : ''}">${neg ? '−' : '+'}${fmt(o.earn)}</span></button>`;
  }
  const kvRow = (k, v, big) => `<div><span>${k}</span><b${big ? ' class="big"' : ''}>${v}</b></div>`;
  const findOp = id => shiftOps.find(o => o.id === id) || curOps.find(o => o.id === id);
  function opSheet(o) {
    const neg = o.kind === 'refund', canRefund = o.kind === 'sale' && !o.refunded;
    openSheet(`<h3>${opKind(o)}</h3><div class="amt">${neg ? '−' : '+'}${fmt(o.earn)} <small>${t('бонусов')}</small></div><div class="when">${dayLabel(o.created_at)}, ${hm(o.created_at)}</div>
      <div class="kv">${kvRow(t('Клиент'), esc(cname(o)))}${kvRow(t('Чек №'), o.id)}${o.kind === 'welcome' ? '' : kvRow(t('Сумма чека'), `${fmt(o.amount)} ${CUR}`) + (o.spend ? kvRow(t(neg ? 'Вернуть списанные бонусы' : 'Оплата бонусами'), (neg ? '+' : '−') + fmt(o.spend)) : '') + kvRow(t(neg ? 'Вернуть клиенту' : 'К оплате'), `${fmt(o.pay)} ${CUR}`)}</div>
      ${canRefund ? `<button class="cta ghost" data-refund="${o.id}">${ic('undo')}${t('Оформить возврат')}</button>` : ''}<button class="cta ${canRefund ? '' : 'ghost'}" style="margin-top:10px" data-close>${t('Закрыть')}</button>`);
  }
  app.addEventListener('click', e => { const b = e.target.closest('[data-op]'); if (b) { const o = findOp(+b.dataset.op); if (o) opSheet(o); } });
  function refundSheet(o) {
    openSheet(`<h3>${t('Возврат покупки')}</h3><div class="when">${esc(cname(o))} · ${dayLabel(o.created_at)}, ${hm(o.created_at)}</div>
      <div class="kv">${kvRow(t('Вернуть клиенту'), `${fmt(o.pay)} ${CUR}`, true)}${kvRow(t('Снять начисленные бонусы'), '−' + fmt(o.earn))}${o.spend ? kvRow(t('Вернуть списанные бонусы'), '+' + fmt(o.spend)) : ''}</div>
      <button class="cta" data-dorefund="${o.id}">${ic('undo')}${t('Оформить возврат')}</button><button class="cta ghost" style="margin-top:10px" data-close>${t('Отмена')}</button>`);
  }
  let refunding = false;
  async function doRefund(id) {
    if (refunding) return; refunding = true;
    try {
      const r = await call('cashier_refund', { p_op: id });
      closeSheet(); toast(t('Возврат оформлен · {0} ₸', fmt(r.op.pay)));
      if (cur && cur.id === r.customer.id) { cur = r.customer; curOps = r.ops; }
      loadMe(true).catch(() => {});
      if (curView() === 'v-client') renderClient(false);
    } catch (e) { /* message shown */ } finally { refunding = false; }
  }
  sheet.addEventListener('click', e => {
    const r = e.target.closest('[data-refund]'); if (r) { const o = findOp(+r.dataset.refund); if (o) refundSheet(o); }
    const d = e.target.closest('[data-dorefund]'); if (d) doRefund(+d.dataset.dorefund);
  });

  /* ---------- till tab ---------- */
  function refreshScan(anim) {
    $('#cName').textContent = cashier || ''; $('#storeName').textContent = settings ? settings.store_name : '';
    if (!shift) return;
    setNum($('#sCnt'), shift.cnt, anim); setNum($('#sEarn'), shift.earn, anim, n => '+' + fmt(n)); setNum($('#sSpend'), shift.spend, anim, n => (Math.round(n) ? '−' : '') + fmt(n));
    $('#lastOps').innerHTML = shiftOps.slice(0, 3).map((o, i) => opRow(o, 6 + i)).join('');
  }
  /* card barcode: 29 + phone (10 digits) + check digit */
  function parseCode(raw) {
    let d = String(raw || '').replace(/\D/g, '');
    if (d.length === 13 && d.startsWith('29')) {
      let s = 0; [...d.slice(0, 12)].forEach((c, i) => { s += +c * (i % 2 ? 3 : 1); });
      if ((10 - s % 10) % 10 !== +d[12]) return null;
      return d.slice(2, 12);
    }
    if (d.length === 11 && (d[0] === '7' || d[0] === '8')) d = d.slice(1);
    return d.length === 10 ? d : null;
  }
  async function openByCode(raw) {
    const ph = parseCode(raw);
    if (!ph) { toast(t('Карта не найдена')); return false; }
    try {
      const r = await call('cashier_customer', { p_id: null, p_phone: ph });
      beep(); stack = ['v-main']; openClient(r.customer, r.ops); return true;
    } catch (e) { return false; }
  }
  const scanner = $('#scanner');
  window.__onScan = code => {
    scanner.classList.remove('scanning');
    if (!code) return;
    scanner.classList.add('hit'); setTimeout(() => scanner.classList.remove('hit'), 700);
    openByCode(code);
  };
  scanner.addEventListener('click', () => {
    if (window.IstanbulNative) { scanner.classList.add('scanning'); window.IstanbulNative.postMessage('scan'); return; }
    openSheet(`<h3>${t('Номер карты или телефона')}</h3><p class="lead">${t('Камера доступна только в приложении. Введите номер под штрихкодом или телефон клиента.')}</p>
      <label class="field"><input id="manual" inputmode="numeric" autocomplete="off" maxlength="20" placeholder="2 970123 456788"></label><button class="cta" id="manualGo">${t('Найти')}</button>`);
    setTimeout(() => { const i = $('#manual'); if (i) i.focus(); }, 400);
  });
  sheet.addEventListener('click', async e => { if (e.target.closest('#manualGo')) { const v = $('#manual').value; if (await openByCode(v)) closeSheet(); } });
  sheet.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.id === 'manual') $('#manualGo').click(); });

  /* ---------- search by phone ---------- */
  let fq = '', findT = 0, findSeq = 0;
  function pressFind(k) { if (k === 'del') fq = fq.slice(0, -1); else if (fq.length < 10) fq += k; drawFind(); }
  function drawFind() {
    $('#fDigits').textContent = [fq.slice(0, 3), fq.slice(3, 6), fq.slice(6, 8), fq.slice(8)].filter(Boolean).join(' ');
    const box = $('#found');
    clearTimeout(findT);
    if (fq.length < 2) { box.innerHTML = `<p class="nf">${t('Введите первые цифры номера или последние четыре')}</p>`; return; }
    const q = fq, seq = ++findSeq;
    findT = setTimeout(async () => {
      let list = [];
      try { list = (await call('cashier_find', { p_q: q }, { quiet: true })).list; } catch (e) { if (e.code !== 'auth') box.innerHTML = `<p class="nf">${errText(e.code)}</p>`; return; }
      if (seq !== findSeq) return;
      box.innerHTML = list.map((c, i) => `<button class="cl" style="--i:${i}" data-cl="${c.id}"><span class="av">${esc(cinit(c))}</span><span class="t"><b>${esc(cname(c))}</b><span>${fmtPhone(c.phone)}</span></span><span class="r">${fmt(c.balance)}<small>${t('бонусов')}</small></span></button>`).join('')
        || (q.length === 10 ? `<p class="nf">${t('Клиента с таким номером нет')}</p><button class="cta ghost" id="regFound">${ic('userplus')}${t('Выдать карту на этот номер')}</button>` : `<p class="nf">${t('Нет совпадений')}</p>`);
    }, 250);
  }
  $('#goFind').addEventListener('click', () => { fq = ''; drawFind(); push('v-find'); });
  $('#found').addEventListener('click', async e => {
    const b = e.target.closest('[data-cl]');
    if (b) { try { const r = await call('cashier_customer', { p_id: +b.dataset.cl, p_phone: null }); stack = ['v-main']; openClient(r.customer, r.ops); } catch (err) { /* message shown */ } }
    if (e.target.closest('#regFound')) { stack = ['v-main']; openNew(fq); }
  });

  /* ---------- new customer ---------- */
  let nd = '', registering = false;
  const nPhone = $('#nPhone'), nName = $('#nName'), nLast = $('#nLast');
  const drawNew = () => { nPhone.value = nd ? fmtPhone(nd).trimEnd() : ''; $('#nGo').disabled = nd.length !== 10 || nName.value.trim().length < 2; };
  function openNew(phone) { nd = phone || ''; nName.value = ''; nLast.value = ''; drawNew(); push('v-new'); }
  nPhone.addEventListener('input', () => {
    const v = nPhone.value; let d = v.replace(/\D/g, '');
    if (v.startsWith('+7')) d = d.slice(1); else if (d.length > 10 && (d[0] === '7' || d[0] === '8')) d = d.slice(1);
    d = d.slice(0, 10);
    if (d === nd && v.length < fmtPhone(nd).trimEnd().length) d = d.slice(0, -1);
    nd = d; drawNew();
  });
  nName.addEventListener('input', drawNew);
  $('#goNew').addEventListener('click', () => openNew(''));
  function codeSheet(code, title, note) {
    openSheet(`<div class="okc">${ic('key')}</div><h3>${t(title)}</h3><div class="when">${t('Код для входа в приложение')}</div>
      <div class="codebig"><b>${code.split('').map((d, i) => `<i style="--i:${i}">${d}</i>`).join('')}</b></div>
      <p class="lead">${t(note)}</p><button class="cta" data-close>${t('Понятно')}</button>`, 'center locked');
  }
  $('#nGo').addEventListener('click', async () => {
    if (registering) return; registering = true;
    try {
      const r = await call('cashier_register', { p_phone: nd, p_first: nName.value.trim(), p_last: nLast.value.trim() });
      stack = ['v-main']; openClient(r.customer, r.ops); loadMe(true).catch(() => {});
      setTimeout(() => { codeSheet(r.login_code, 'Карта выдана', 'Скажите клиенту: установить приложение ISTANBUL, войти по номеру телефона и этому коду.'); burst(W / 2, H * .35, 110); }, 450);
    } catch (e) {
      if (e.code === 'exists' && e.data && e.data.customer_id) { try { const c = await call('cashier_customer', { p_id: e.data.customer_id, p_phone: null }); stack = ['v-main']; openClient(c.customer, c.ops); } catch (err) { /* message shown */ } }
    } finally { registering = false; }
  });

  /* ---------- customer card ---------- */
  function openClient(c, ops) { cur = c; curOps = ops || []; renderClient(true); push('v-client'); }
  function renderClient(anim) {
    const c = cur, L = c.level;
    $('#clientBody').innerHTML = `<div class="topbar"><button class="back" data-back aria-label="Back">${ic('back')}</button>${t('Клиент')}</div>
      <div class="ccard${anim ? ' in' : ''}"><div class="nm">${esc(cname(c))}</div>
        <div class="r lb"><small>${t('Бонусный счёт')}</small><span class="lvl">${t(L.name)} · ${L.pct}%</span></div><div class="bal"><b id="cBal">${fmt(c.balance)}</b><span>${t('бонусов')}</span></div>
        <div class="r ft"><span class="num">${cardNo(c)}</span><span>${fmtPhone(c.phone)}</span></div></div>
      <div class="stats3 a" style="--i:2"><div><small>${t('Покупки за год')}</small><b>${fmt(c.year_total)} ${CUR}</b></div><div><small>${t('Рейтинг')}</small><b>${c.place ? '#' + fmt(c.place) : '—'}</b></div><div><small>${t('Визитов')}</small><b>${c.visits}</b></div></div>
      <div class="box a" style="--i:3"><h5>${L.next_name ? t('До уровня «{0}»', t(L.next_name)) : t('Максимальный уровень')}<span>${L.next_name ? `${fmt(L.next_from - c.year_total)} ${CUR}` : t('кешбэк {0}%', L.pct)}</span></h5><div class="pbar"><i id="cBar"></i></div></div>
      <button class="linkbtn a" style="--i:4" id="newCode">${ic('key')}${t('Новый код для входа')}</button>
      <div class="sec a" style="--i:5"><h4>${t('Операции клиента')}</h4></div>${curOps.slice(0, 15).map((o, i) => opRow(o, 6 + i, true)).join('') || `<p class="nf">${t('Операций пока нет')}</p>`}`;
    if (anim) count($('#cBal'), 0, c.balance, 900);
    requestAnimationFrame(() => { const b = $('#cBar'); if (b) b.style.width = (L.next_from ? Math.min(100, c.year_total / L.next_from * 100) : 100) + '%'; });
  }
  $('#clientBody').addEventListener('click', async e => {
    if (!e.target.closest('#newCode')) return;
    try { const r = await call('cashier_new_code', { p_id: cur.id }); codeSheet(r.login_code, 'Новый код для входа', 'Старый код больше не работает'); } catch (err) { /* message shown */ }
  });
  $('#cRefund').addEventListener('click', () => {
    const list = curOps.filter(o => o.kind === 'sale' && !o.refunded).slice(0, 6);
    openSheet(`<h3>${t('Какую покупку вернуть?')}</h3>` + (list.map(o => `<button class="op" data-refund="${o.id}"><span class="ic">${ic('bag')}</span><span class="t"><b>${fmt(o.amount)} ${CUR}</b><span>${dayLabel(o.created_at)}, ${hm(o.created_at)} · ${t('чек № {0}', o.id)}</span></span><span class="amt">+${fmt(o.earn)}</span></button>`).join('') || `<p class="lead">${t('У клиента нет покупок для возврата')}</p>`) + `<button class="cta ghost" data-close>${t('Закрыть')}</button>`);
  });

  /* ---------- purchase: amount, bonuses, code ---------- */
  let sale = { step: '' }, selling = false;
  const STEP = 500;
  function calc() {
    const a = +sale.amt || 0, pct = sale.c.level.pct;
    const maxSpend = Math.floor(Math.min(sale.c.balance, a * settings.max_spend_pct / 100) / STEP) * STEP;
    const spend = Math.min(sale.spend, maxSpend), pay = a - spend;
    return { a, maxSpend, spend, pay, pct, earn: Math.round(pay * pct / 100) };
  }
  function setStep(s) {
    sale.step = s; $$('.step').forEach(x => x.classList.toggle('on', x.id === 'st-' + s));
    $('#stepNo').textContent = s === 'amt' ? '1 / 2' : s === 'bon' ? '2 / 2' : ''; $('#saleTitle').textContent = t(s === 'code' ? 'Подтверждение' : 'Покупка');
  }
  function drawAmt() { const r = calc(); $('#amt').textContent = fmt(r.a); $('#amtNext').disabled = r.a < 1; $('#amtCalc').textContent = t('Кешбэк {0}%', r.pct) + ` · +${fmt(r.earn)}`; }
  function pressAmt(k) {
    if (k === 'del') sale.amt = sale.amt.slice(0, -1); else if ((sale.amt + k).length <= 8 && (sale.amt || !/^0+$/.test(k))) sale.amt += k;
    drawAmt();
  }
  $('#cSale').addEventListener('click', () => {
    sale = { c: cur, amt: '', spend: 0, typed: '', step: 'amt', key: null };
    $('#saleWho').innerHTML = `<span class="av">${esc(cinit(cur))}</span><span class="t"><b>${esc(cname(cur))}</b><span>${t(cur.level.name)} · ${cardNo(cur)}</span></span><span class="bl">${fmt(cur.balance)}</span>`;
    setStep('amt'); drawAmt(); push('v-sale');
  });
  const range = $('#range');
  function drawBon(anim) {
    const r = calc(); sale.spend = r.spend;
    setNum($('#spendV'), r.spend, anim, n => (Math.round(n) ? '−' : '') + fmt(n));
    range.value = r.spend; range.style.setProperty('--p', (r.maxSpend ? r.spend / r.maxSpend * 100 : 0) + '%');
    $('#avail').textContent = r.maxSpend ? t('На счёте {0} · можно списать до {1}', fmt(sale.c.balance), fmt(r.maxSpend)) : t('Бонусов пока недостаточно для списания');
    const half = Math.floor(r.maxSpend / 2 / STEP) * STEP;
    $$('#quick button').forEach(b => b.classList.toggle('on', (b.dataset.q === '0' ? 0 : b.dataset.q === 'half' ? half : r.maxSpend) === r.spend && (b.dataset.q !== 'half' || half > 0 && half < r.maxSpend)));
    $('#saleKv').innerHTML = kvRow(t('Сумма чека'), `${fmt(r.a)} ${CUR}`) + (r.spend ? kvRow(t('Оплата бонусами'), '−' + fmt(r.spend)) : '') + kvRow(t('К оплате'), `${fmt(r.pay)} ${CUR}`, true) + kvRow(t('Будет начислено'), '+' + fmt(r.earn));
    $('#saleGo').innerHTML = r.spend ? ic('sms') + t('Ввести код клиента') : ic('check') + t('Провести покупку');
  }
  $('#amtNext').addEventListener('click', () => {
    sale.spend = 0; sale.key = null; const r = calc();
    range.max = r.maxSpend || STEP; range.disabled = !r.maxSpend; $('#quick').hidden = !r.maxSpend; $('#spendV')._v = undefined;
    setStep('bon'); drawBon(false);
  });
  range.addEventListener('input', () => { sale.spend = +range.value; sale.key = null; drawBon(false); });
  $('#quick').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return; const max = calc().maxSpend;
    sale.spend = b.dataset.q === '0' ? 0 : b.dataset.q === 'half' ? Math.floor(max / 2 / STEP) * STEP : max; sale.key = null; drawBon(true);
  });
  const drawOtp = () => $$('#otp span').forEach((s, i) => { s.textContent = sale.typed[i] || ''; s.className = i < sale.typed.length ? 'f' : i === sale.typed.length ? 'cur' : ''; });
  $('#saleGo').addEventListener('click', () => {
    const r = calc(); if (!r.spend) { finishSale(); return; }
    sale.typed = ''; $('#otp').className = 'otp'; drawOtp();
    $('#codeLead').textContent = t('Попросите клиента открыть приложение, нажать на карту и «Списать бонусы». Введите код, который он назовёт, чтобы списать {0} бонусов.', fmt(r.spend));
    setStep('code');
  });
  function pressCode(k) {
    if (selling || $('#otp').classList.contains('ok')) return;
    if (k === 'del') sale.typed = sale.typed.slice(0, -1); else if (sale.typed.length < 4) sale.typed += k;
    drawOtp(); if (sale.typed.length === 4) finishSale();
  }
  $('#saleBack').addEventListener('click', () => { if (selling) return; if (sale.step === 'code') { setStep('bon'); drawBon(false); } else if (sale.step === 'bon') { setStep('amt'); drawAmt(); } else pop(); });
  async function finishSale() {
    if (selling) return; selling = true;
    const r = calc(), c = sale.c;
    /* the same key on a retry: the server never records one purchase twice */
    sale.key = sale.key || uuid();
    try {
      const res = await call('cashier_sale', { p_customer: c.id, p_amount: r.a, p_spend: r.spend, p_code: r.spend ? sale.typed : null, p_key: sale.key });
      if (sale.step === 'code') $('#otp').classList.add('ok');
      const o = res.op, bal0 = res.balance_before != null ? res.balance_before : c.balance;
      cur = res.customer;
      call('cashier_customer', { p_id: cur.id, p_phone: null }, { quiet: true }).then(x => { cur = x.customer; curOps = x.ops; }).catch(() => {});
      loadMe(true).catch(() => {});
      const up = res.level_up;
      $('#doneBody').innerHTML = `<div class="okc">${ic('check')}</div><h2>${t('Покупка проведена')}</h2><div class="when">${esc(cname(c))} · ${t('чек № {0}', o.id)}</div>
        <div class="kv">${kvRow(t('Сумма чека'), `${fmt(o.amount)} ${CUR}`)}${o.spend ? kvRow(t('Оплата бонусами'), '−' + fmt(o.spend)) : ''}${kvRow(t('К оплате'), `${fmt(o.pay)} ${CUR}`, true)}${kvRow(t('Кешбэк {0}%', res.pct || r.pct), '+' + fmt(o.earn))}</div>
        <div class="newbal"><small>${t('Новый баланс клиента')}</small><b id="dBal">${fmt(bal0)}</b></div>
        <div class="acts"><button class="cta" id="dNext">${ic('scan')}${t('Следующий клиент')}</button><button class="cta ghost" id="dCard">${t('Карта клиента')}</button></div>`;
      setTimeout(() => {
        stack = ['v-main', 'v-client', 'v-done']; showView('v-done', 'fwd'); beep();
        setTimeout(() => {
          const el = $('#dBal'); if (!el || curView() !== 'v-done') return;
          count(el, bal0, cur.balance, 1000); const p = center($('.okc')); burst(p.x, p.y, 70);
          if (up) { toast(t('Новый уровень клиента: {0} · кешбэк {1}%', t(up.name), up.pct)); rain(140, 2200); }
        }, 600);
      }, sale.step === 'code' ? 500 : 0);
    } catch (e) {
      if (e.code === 'code' || e.code === 'code_expired') { replay($('#otp'), 'bad'); sale.typed = ''; sale.key = null; setTimeout(drawOtp, 350); }
      else if (e.code === 'spend') { sale.key = null; setStep('bon'); drawBon(false); }
    } finally { selling = false; }
  }
  $('#doneBody').addEventListener('click', e => {
    if (e.target.closest('#dNext')) goHome();
    if (e.target.closest('#dCard')) { stack = ['v-main', 'v-client']; renderClient(false); showView('v-client', 'back'); }
  });

  /* ---------- operations tab ---------- */
  let oFilter = 'all';
  function renderOps() {
    const list = shiftOps.filter(o => oFilter === 'all' || (oFilter === 'spend' ? o.kind === 'sale' && o.spend > 0 : o.kind === oFilter));
    $('#opsList').innerHTML = list.map((o, i) => opRow(o, 2 + i)).join('') || `<div class="empty a" style="--i:2"><h3>${t('Пока пусто')}</h3><p>${t(oFilter === 'all' ? 'Операции появятся после первой покупки' : 'Таких операций в этой смене нет')}</p></div>`;
  }
  $('#oFilter').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; oFilter = b.dataset.f; $$('#oFilter button').forEach(x => x.classList.toggle('on', x === b)); renderOps(); });

  /* ---------- shift tab ---------- */
  function renderShift() {
    if (!shift) return;
    const s = shift, h = new Date().getHours();
    $('#shOpen').textContent = hm(s.opened_at); $('#shWho').textContent = cashier; $('#shStore').textContent = settings.store_name;
    setNum($('#zRev'), s.revenue, true); setNum($('#zCnt'), s.cnt, true); setNum($('#zAvg'), s.cnt ? s.gross / s.cnt : 0, true);
    setNum($('#zEarn'), s.earn, true, n => '+' + fmt(n)); setNum($('#zSpend'), s.spend, true, n => (Math.round(n) ? '−' : '') + fmt(n)); setNum($('#zNew'), s.news, true); setNum($('#zRef'), s.refunds, true);
    const hours = Array.from({ length: 6 }, (_, i) => ({ h: (h - 5 + i + 24) % 24, v: 0 }));
    shiftOps.forEach(o => { if (o.kind !== 'sale') return; const b = hours.find(x => x.h === new Date(o.created_at).getHours()); if (b) b.v += o.pay; });
    const max = Math.max(1, ...hours.map(x => x.v));
    $('#hours').innerHTML = hours.map((x, i) => `<div class="${i === 5 ? 'now' : ''}"><em>${x.v ? fmt(x.v / 1000) : ''}</em><i style="--h:${Math.round(x.v / max * 100)}%;--i:${i}"></i>${two(x.h)}</div>`).join('');
  }
  (function tick() {
    if (shift) { const d = Math.max(0, Math.floor((Date.now() - new Date(shift.opened_at)) / 1000)), hmv = two(Math.floor(d / 3600)) + ':' + two(Math.floor(d % 3600 / 60)); $('#shTimer').textContent = hmv + ':' + two(d % 60); $('#shiftDur').textContent = hmv; }
    setTimeout(tick, 1000);
  })();
  $('#closeShift').addEventListener('click', () => {
    openSheet(`<h3>${t('Закрыть смену?')}</h3><p class="lead">${t('Сформируем отчёт за смену и заблокируем кассу.')}</p><div class="kv">${kvRow(t('Выручка'), `${fmt(shift.revenue)} ${CUR}`, true)}${kvRow(t('Чеков'), shift.cnt)}</div><button class="cta" id="doClose">${ic('lock')}${t('Закрыть смену')}</button><button class="cta ghost" style="margin-top:10px" data-close>${t('Отмена')}</button>`);
  });
  sheet.addEventListener('click', async e => {
    if (!e.target.closest('#doClose')) return;
    try {
      const s = (await call('cashier_close_shift')).shift, end = new Date(s.closed_at);
      closeSheet();
      $('#zBody').innerHTML = `<div class="okc">${ic('check')}</div><h2>${t('Смена закрыта')}</h2><div class="when">${hm(s.opened_at)} – ${hm(s.closed_at)} · ${durText(end - new Date(s.opened_at))}</div>
        <div class="newbal"><small>${t('Выручка')}</small><b><span id="zTotal">0</span> ${CUR}</b></div>
        <div class="kv">${kvRow(t('Чеков'), s.cnt)}${kvRow(t('Средний чек'), `${fmt(s.cnt ? s.gross / s.cnt : 0)} ${CUR}`)}${kvRow(t('Начислено бонусов'), '+' + fmt(s.earn))}${kvRow(t('Списано бонусов'), (s.spend ? '−' : '') + fmt(s.spend))}${kvRow(t('Новых клиентов'), s.news)}${kvRow(t('Возвратов'), s.refunds)}</div>
        <div class="acts"><button class="cta" id="zDone">${t('Готово')}</button></div>`;
      token = null; store.set('istanbul-kassa-token', null); shift = null;
      reset('v-z');
      setTimeout(() => { if (curView() !== 'v-z') return; count($('#zTotal'), 0, s.revenue, 1300); rain(110, 2400); }, 500);
    } catch (err) { /* message shown */ }
  });
  $('#zBody').addEventListener('click', e => { if (e.target.closest('#zDone')) lockLocal(); });

  /* ---------- profile, language, rules ---------- */
  function refreshMore() {
    $('#pAv').textContent = (cashier || '').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase(); $('#pName').textContent = cashier;
    $('#pStore').textContent = t('Кассир · {0}', settings.store_name);
    $$('.toggle').forEach(x => x.setAttribute('aria-checked', String(!!prefs[x.dataset.t])));
  }
  app.addEventListener('click', e => {
    const x = e.target.closest('.toggle'); if (!x) return;
    const k = x.dataset.t; prefs[k] = !prefs[k]; store.set('istanbul-kassa-' + k, prefs[k] ? '1' : '0'); x.setAttribute('aria-checked', String(prefs[k])); if (prefs[k]) beep();
  });
  $('#lockBtn').addEventListener('click', () => { const tk = token; lockLocal(); rpc('cashier_logout', { p_token: tk }).catch(() => {}); });
  function openLang() { openSheet(`<h3>${t('Язык приложения')}</h3><div class="langs">${LANGS.map(([c, short, name]) => `<button class="lopt ${c === lang ? 'on' : ''}" data-lang="${c}"><b>${short}</b><span>${name}</span>${c === lang ? ic('check') : ''}</button>`).join('')}</div>`); }
  function applyLang() {
    statics.forEach(x => { if (x.n) x.n.nodeValue = x.pre + t(x.ru) + x.post; else x.e.setAttribute('placeholder', t(x.ru)); });
    document.documentElement.lang = lang; app.dataset.lang = lang;
    const now = LANGS.find(x => x[0] === lang); $('#langBtn b').textContent = now[1]; $('#pLang').textContent = now[2];
    if (stack.length && curView() === 'v-main') showTab(curTab, true);
  }
  $('#langBtn').addEventListener('click', openLang);
  $('#langRow').addEventListener('click', openLang);
  sheet.addEventListener('click', e => {
    const l = e.target.closest('.lopt[data-lang]'); if (!l) return;
    lang = l.dataset.lang; store.set('istanbul-lang', lang); closeSheet(); applyLang(); toast(t('Язык изменён'));
  });
  function openSub(id) {
    if (id !== 'v-rules') return;
    const rules = ['Уровень считается по сумме покупок за 12 месяцев', '1 бонус = 1 тенге при оплате', t('Бонусами можно оплатить до {0}% чека', settings.max_spend_pct), 'Списание подтверждается кодом из приложения клиента', 'Кешбэк начисляется на сумму, оплаченную деньгами', 'При возврате начисленные бонусы снимаются, списанные возвращаются', t('Новый клиент получает {0} приветственных бонусов', fmt(settings.welcome_bonus))];
    $('#rulesBody').innerHTML = `<div class="topbar"><button class="back" data-back aria-label="Back">${ic('back')}</button>${t('Правила')}</div><h2 class="big-t a" style="font-size:22px;margin-top:10px">${t('Как начисляются бонусы')}</h2>` +
      settings.levels.map((L, i) => `<div class="lc ${i === settings.levels.length - 1 ? 'gold' : ''} a" style="--i:${1 + i}"><div><small>${i ? t('от {0} ₸', fmt(L.from)) : t('с первой покупки')}</small><div class="n">${t(L.name)}</div></div><div class="p">${L.pct}%</div></div>`).join('') +
      `<div class="rules" style="margin-top:14px">${rules.map((r, i) => `<div class="a" style="--i:${4 + i}"><b>${i + 1}</b>${t(r)}</div>`).join('')}</div>`;
    push(id);
  }

  /* ---------- tabs ---------- */
  const TABS = ['scan', 'ops', 'shift', 'more'];
  function showTab(name, quiet) {
    curTab = name;
    $$('.tab').forEach(x => x.classList.toggle('on', x.id === 't-' + name));
    $$('#nav button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
    $('#navInd').style.transform = `translateX(${TABS.indexOf(name) * 100}%)`;
    parts = [];
    if (name === 'scan') refreshScan(true);
    if (name === 'ops') renderOps();
    if (name === 'shift') renderShift();
    if (name === 'more') refreshMore();
    if (!quiet && token) loadMe(true).catch(() => {});
  }

  applyLang();
  if (token) {
    reset('v-lock');
    loadMe(false).then(() => { reset('v-main'); showTab('scan', true); }).catch(() => {});
  } else reset('v-lock');
  rpc('app_settings').then(s => { if (!settings) settings = s; $('#lockStore').textContent = s.store_name; }).catch(() => {});
})();
