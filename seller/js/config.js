// справочники

// тип магазина задаёт единицы товаров и стартовые категории
export const SHOP_KINDS = [
  { id: 'grocery', name: 'Продукты', hint: 'Овощи, фрукты, молочное, хлеб', units: ['кг', 'г', 'шт', 'л', 'упак'], expiry: 'required',
    cats: ['Овощи и зелень', 'Фрукты и ягоды', 'Молочное и яйца', 'Сыры', 'Мясо и птица', 'Колбасы и сосиски', 'Рыба и морепродукты', 'Хлеб и выпечка',
      'Крупы и макароны', 'Мука и всё для выпечки', 'Масло, соусы, специи', 'Консервы', 'Замороженные продукты', 'Конфеты и шоколад', 'Печенье и сладости',
      'Орехи и сухофрукты', 'Снеки и чипсы', 'Чай и кофе', 'Вода и напитки', 'Соки', 'Детское питание', 'Бытовая химия', 'Гигиена', 'Для животных'],
    icon: '<path d="M3 4h2l2.4 11h9.6l2-8H6"/><circle cx="9" cy="19" r="1.3"/><circle cx="17" cy="19" r="1.3"/>' },
  { id: 'perfume', name: 'Парфюмерия', hint: 'Духи, косметика, уход', units: ['шт', 'мл', 'упак'], expiry: 'optional',
    cats: ['Женская парфюмерия', 'Мужская парфюмерия', 'Унисекс', 'Парфюм на разлив', 'Уход за лицом', 'Уход за телом', 'Уход за волосами', 'Макияж',
      'Маникюр', 'Дезодоранты', 'Для бритья', 'Детская косметика', 'Подарочные наборы', 'Аксессуары'],
    icon: '<path d="M9 3h6v4H9zM7 9a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2zM10 14h4"/>' },
  { id: 'tech', name: 'Аксессуары', hint: 'Наушники, чехлы, зарядки, кабели', units: ['шт', 'компл'],
    cats: ['Наушники', 'Беспроводные наушники', 'Чехлы', 'Защитные стёкла и плёнки', 'Зарядные устройства', 'Кабели и переходники', 'Пауэрбанки',
      'Портативные колонки', 'Держатели и подставки', 'Для автомобиля', 'Ремешки для часов', 'Карты памяти и флешки', 'Мыши и клавиатуры', 'Селфи-палки и штативы'],
    icon: '<path d="M4 15v-3a8 8 0 0 1 16 0v3M4 15h3v5H5a1 1 0 0 1-1-1zM20 15h-3v5h2a1 1 0 0 0 1-1z"/>' },
  { id: 'food', name: 'Ресторан, кафе', hint: 'Готовая еда и напитки', units: ['порция', 'шт'], cats: ['Горячее', 'Супы', 'Салаты', 'Десерты', 'Напитки'],
    icon: '<path d="M4 11h16a8 8 0 0 1-16 0zM12 3v4M8 5v2M16 5v2"/>' },
]
// свежие овощи и фрукты продаются без срока на упаковке, остальные продукты — только с ним
export const NO_EXPIRY_CATS = ['Овощи и зелень', 'Фрукты и ягоды'];
export const EXPIRY_SOON = 3;     // дней до конца срока, когда предупреждаем
export const kindOf = shop => SHOP_KINDS.find(k => k.id === shop?.kind) || SHOP_KINDS.find(k => k.name === shop?.type) || SHOP_KINDS[0];
export const SHOP_TYPES = SHOP_KINDS.map(k => k.name);
// весовые единицы: цена за 1 единицу, покупатель берёт с шагом
export const WEIGHT_UNITS = ['кг', 'л'];
export const WEIGHT_STEPS = [0.1, 0.25, 0.5, 1];

// Работаем только в Шахритусском районе: центр — посёлок Тус (бывш. Шахритус). Зона — круг 15 км вокруг посёлка.
// То же значение стоит в приложении покупателя (client/js/config.js) — меняются вместе.
export const SERVICE_AREA = { name: 'Шахритус', lat: 37.267, lng: 68.133, radiusKm: 15 };
export const CITIES = [{ name: 'Шахритус', lat: 37.267, lng: 68.133 }];
/** Точка в зоне работы? Без метки считаем, что магазин в посёлке. */
export function inZone(p) {
  if (p?.lat == null || p?.lng == null) return true;
  const r = d => d * Math.PI / 180, dLat = r(p.lat - SERVICE_AREA.lat), dLng = r(p.lng - SERVICE_AREA.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(r(SERVICE_AREA.lat)) * Math.cos(r(p.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h)) <= SERVICE_AREA.radiusKm;
}
export const LABELS = ['Хит', 'Новинка', 'Выбор магазина', 'К празднику'];
export const EXP_CATS = ['Аренда', 'Зарплата', 'Закупка товара', 'Доставка товара', 'Коммунальные', 'Реклама', 'Упаковка', 'Прочее'];
export const CANCEL_REASONS = ['Нет товара', 'Магазин закрыт', 'Не успеваем собрать', 'Клиент попросил отменить', 'Другое'];
export const DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
export const STATUS = { new: 'Новый', accepted: 'Собирается', ready: 'Готов, ждёт курьера', done: 'Выполнен', cancelled: 'Отменён' };
export const CUR = 'смн';
export const LOW = 5;
export const FEE = 0.20;          // комиссия сервиса с заказов из приложения

// характеристики товара по типу магазина: req — обязательно, opts — выбор из списка, chips — быстрые значения
export const ATTRS = {
  grocery: [
    { k: 'brand', label: 'Бренд или производитель', ph: 'Например, Шароб, Saodat, Nestle', list: true },
    { k: 'pack', label: 'Вес или объём упаковки', ph: 'Например, 500 г, 1 л, 10 шт' },
    { k: 'country', label: 'Страна', ph: 'Таджикистан', chips: ['Таджикистан', 'Узбекистан', 'Казахстан', 'Россия', 'Турция', 'Иран'] },
  ],
  perfume: [
    { k: 'brand', label: 'Бренд', req: true, ph: 'Начните вводить: Chanel, Dior, Lattafa…', list: true },
    { k: 'gender', label: 'Для кого', opts: ['Женский', 'Мужской', 'Унисекс'] },
    { k: 'ptype', label: 'Тип', opts: ['Парфюмерная вода', 'Туалетная вода', 'Духи', 'Масляные духи', 'Одеколон', 'Другое'] },
    { k: 'volume', label: 'Объём, мл', req: true, numeric: true, ph: '50', chips: ['5', '10', '30', '50', '75', '100'] },
    { k: 'origin', label: 'Состояние', req: true, opts: ['Новый, в упаковке', 'Тестер', 'Разлив'] },
    { k: 'country', label: 'Страна производства', ph: 'Франция', chips: ['Франция', 'ОАЭ', 'Италия', 'Турция', 'США', 'Россия'] },
  ],
  tech: [
    { k: 'brand', label: 'Бренд', req: true, ph: 'Начните вводить: Baseus, Anker, Hoco…', list: true },
    { k: 'compat', label: 'Для каких устройств', ph: 'iPhone 15, Samsung A55, Type-C, Lightning', chips: ['Type-C', 'Lightning', 'iPhone', 'Samsung', 'Xiaomi', 'Универсальный'] },
    { k: 'color', label: 'Цвет', ph: 'Чёрный', chips: ['Чёрный', 'Белый', 'Прозрачный', 'Синий', 'Розовый'] },
    { k: 'power', label: 'Мощность или ёмкость', ph: '20 Вт, 10 000 мАч, кабель 1 м' },
    { k: 'warranty', label: 'Гарантия, месяцев', numeric: true, ph: '6', chips: ['0', '1', '3', '6', '12'] },
    { k: 'origin', label: 'Оригинальность', req: true, opts: ['Оригинал', 'Копия высокого качества', 'Без бренда'] },
  ],
  food: [
    { k: 'portion', label: 'Вес порции, г', numeric: true, ph: '350', chips: ['250', '350', '500'] },
    { k: 'spicy', label: 'Острота', opts: ['Не острое', 'Слегка острое', 'Острое'] },
  ],
};
// популярные марки парфюма — подсказка при вводе, свой вариант тоже можно
export const PERFUME_BRANDS = ['Ajmal', 'Al Haramain', 'Armaf', 'Armani', 'Azzaro', 'Bvlgari', 'Burberry', 'Byredo', 'Calvin Klein', 'Carolina Herrera',
  'Cartier', 'Chanel', 'Chloé', 'Clinique', 'Creed', 'Davidoff', 'Dior', 'Dolce & Gabbana', 'Escentric Molecules', 'Estée Lauder', 'Givenchy', 'Gucci',
  'Guerlain', 'Hermès', 'Hugo Boss', 'Initio', 'Jean Paul Gaultier', 'Jo Malone', 'Kenzo', 'Kilian', 'Lacoste', 'Lancôme', 'Lattafa', 'Maison Francis Kurkdjian',
  'Mancera', 'Marc Jacobs', 'Montale', 'Montblanc', 'Narciso Rodriguez', 'Nina Ricci', 'Paco Rabanne', 'Parfums de Marly', 'Prada', 'Rasasi', 'Swiss Arabian',
  'Tiziana Terenzi', 'Tom Ford', 'Valentino', 'Versace', 'Yves Saint Laurent', 'Zara', 'Zielinski & Rozen',
  'Garnier', 'L’Oréal', 'Maybelline', 'NIVEA', 'Vichy', 'La Roche-Posay', 'CeraVe', 'The Ordinary', 'Bioderma', 'Dove', 'Gillette', 'Rexona', 'Old Spice'];

// отзывы: быстрые причины, которые отмечает покупатель
export const REVIEW_GOOD = ['Всё как на фото', 'Свежее, качественное', 'Хорошо упаковано', 'Быстро собрали', 'Вежливо'];
export const REVIEW_BAD = ['Не тот товар', 'Несвежее', 'Не хватало товара', 'Плохо упаковано', 'Долго собирали'];
export const REPLY_TEMPLATES = [
  'Спасибо за отзыв! Рады, что вам понравилось. Ждём вас снова.',
  'Спасибо, что выбрали нас! Передадим добрые слова команде.',
  'Извините, что так получилось. Мы уже разбираемся. Напишите нам — предложим компенсацию.',
  'Спасибо, что сообщили. Передали замечание сотрудникам, такого больше не повторится.',
];
export const COMPLAINT_REASONS = ['Оскорбления или нецензурные слова', 'Отзыв не о нашем магазине', 'Отзыв о курьере, а не о магазине', 'Похоже на отзыв конкурента', 'Другое'];
export const RATING_DAYS = 90;    // рейтинг считаем по оценкам за последние 3 месяца
export const RATING_MIN = 10;     // меньше оценок — показываем «Новый магазин»

// сотрудники: какие разделы открыты каждой роли (владелец видит всё)
export const ROLES = {
  manager: { name: 'Управляющий', hint: 'Всё, кроме денег и сотрудников', views: ['home', 'orders', 'catalog', 'stats', 'reviews', 'expenses', 'preview', 'shop', 'more'] },
  cashier: { name: 'Кассир', hint: 'Заказы, товары, продажи в магазине', views: ['home', 'orders', 'catalog', 'reviews', 'preview', 'more'] },
  picker: { name: 'Сборщик', hint: 'Только заказы: принять, собрать, отдать курьеру', views: ['orders', 'more'] },
};
// популярные марки аксессуаров
export const TECH_BRANDS = ['Apple', 'Samsung', 'Xiaomi', 'Huawei', 'Honor', 'Realme', 'OPPO', 'JBL', 'Marshall', 'Beats', 'Sony', 'Sennheiser', 'Anker', 'Baseus',
  'Ugreen', 'Hoco', 'Borofone', 'Remax', 'Usams', 'XO', 'Joyroom', 'Spigen', 'ESR', 'Nillkin', 'Belkin', 'Logitech', 'Razer', 'Defender', 'A4Tech',
  'Kingston', 'SanDisk', 'Transcend', 'Amazfit', 'Haylou', 'QCY', 'Lenovo', 'Edifier'];
