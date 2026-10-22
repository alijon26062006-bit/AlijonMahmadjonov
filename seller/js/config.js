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

export const CITIES = [
  { name: 'Душанбе', lat: 38.5598, lng: 68.7870 },
  { name: 'Худжанд', lat: 40.2826, lng: 69.6220 },
  { name: 'Бохтар', lat: 37.8364, lng: 68.7803 },
  { name: 'Куляб', lat: 37.9146, lng: 69.7845 },
  { name: 'Истаравшан', lat: 39.9108, lng: 69.0064 },
  { name: 'Вахдат', lat: 38.5563, lng: 69.0207 },
  { name: 'Турсунзаде', lat: 38.5108, lng: 68.2303 },
  { name: 'Гиссар', lat: 38.5266, lng: 68.5512 },
  { name: 'Пенджикент', lat: 39.4952, lng: 67.6093 },
  { name: 'Хорог', lat: 37.4897, lng: 71.5530 },
];
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
