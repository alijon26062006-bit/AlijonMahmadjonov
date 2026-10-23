// Магазины-примеры. Когда подключим сервер, сюда придут настоящие магазины из кабинета продавца.

const week = (from, to) => Array.from({ length: 7 }, () => ({ open: true, from, to }));
const inDays = n => { const d = new Date(Date.now() + n * 864e5); return d.toISOString().slice(0, 10); };
let n = 0;
const P = (cat, name, price, unit, extra = {}) => ({ id: 'p' + ++n, cat, name, price, unit, stock: 50, minStep: unit === 'кг' ? 0.5 : 1, oldPrice: null, imgs: [], desc: '', attrs: {}, variants: [], options: [], labels: [], expiry: '', likes: null, ...extra });

export const DEMO_SHOPS = [
  {
    id: 'sabz', tile: { bg: '#2e8b57', fg: '#ffffff' }, name: 'Дехкон Маркет', kind: 'grocery', about: 'Свежие овощи и фрукты с Шохмансура каждое утро', rating: 4.8, count: 412, prep: 20, minOrder: 50,
    address: 'Душанбе, пр. Рудаки 45', schedule: week('07:00', '23:00'), color: '#e8f3df',
    products: [
      P('Овощи и зелень', 'Помидоры местные', 12, 'кг', { labels: ['Хит'], desc: 'Грунтовые, сладкие. Собраны вчера.', likes: 96, attrs: { country: 'Таджикистан' } }),
      P('Овощи и зелень', 'Огурцы хрустящие', 10, 'кг', { likes: 92 }),
      P('Овощи и зелень', 'Картофель молодой', 6, 'кг', { minStep: 1 }),
      P('Овощи и зелень', 'Лук репчатый', 4, 'кг', { minStep: 1 }),
      P('Овощи и зелень', 'Зелень: укроп, кинза', 3, 'шт', { desc: 'Пучок 100 г' }),
      P('Фрукты и ягоды', 'Яблоки «Семеренко»', 14, 'кг', { likes: 90 }),
      P('Фрукты и ягоды', 'Гранат кандибадам', 18, 'кг', { oldPrice: 22, labels: ['Новинка'] }),
      P('Фрукты и ягоды', 'Виноград «Хусайни»', 20, 'кг', { likes: 97, labels: ['Хит'] }),
      P('Молочное и яйца', 'Молоко деревенское 3,5%', 9, 'л', { minStep: 1, expiry: inDays(3) }),
      P('Молочное и яйца', 'Чакка домашняя', 11, 'шт', { attrs: { pack: '500 г' }, expiry: inDays(5) }),
      P('Молочное и яйца', 'Яйца деревенские', 13, 'упак', { expiry: inDays(14), variants: [{ id: 'v10', name: '10 шт', price: 13 }, { id: 'v30', name: '30 шт', price: 36 }] }),
      P('Хлеб и выпечка', 'Нон тандыри', 4, 'шт', { labels: ['Хит'], desc: 'Горячий, из тандыра', likes: 99, expiry: inDays(1) }),
      P('Хлеб и выпечка', 'Самбуса с мясом', 7, 'шт', { expiry: inDays(1) }),
      P('Орехи и сухофрукты', 'Курага исфаринская', 35, 'кг', { minStep: 0.25, expiry: inDays(90) }),
      P('Орехи и сухофрукты', 'Миндаль', 60, 'кг', { minStep: 0.25, expiry: inDays(120) }),
      P('Вода и напитки', 'Вода «Хоҷа Обигарм» 1,5 л', 5, 'шт', { expiry: inDays(300) }),
      P('Чай и кофе', 'Чай зелёный №95', 15, 'упак', { attrs: { pack: '100 г' }, expiry: inDays(400) }),
    ],
  },
  {
    id: 'yovar', tile: { bg: '#e53935', fg: '#ffffff' }, name: 'Супермаркет Ёвар', kind: 'grocery', about: 'Всё для дома рядом с вами, работаем круглосуточно', rating: 4.6, count: 1290, prep: 15, minOrder: 30,
    address: 'Душанбе, ул. Айни 54', schedule: week('00:00', '23:59'), color: '#fdf2c4',
    products: [
      P('Молочное и яйца', 'Кефир 2,5%', 8, 'шт', { attrs: { brand: 'Шароб', pack: '1 л' }, expiry: inDays(6) }),
      P('Сыры', 'Сыр «Российский»', 95, 'кг', { minStep: 0.25, expiry: inDays(30) }),
      P('Колбасы и сосиски', 'Колбаса докторская', 70, 'кг', { minStep: 0.25, expiry: inDays(12) }),
      P('Мясо и птица', 'Куриное филе', 42, 'кг', { expiry: inDays(3) }),
      P('Крупы и макароны', 'Рис девзира', 22, 'кг', { minStep: 1, labels: ['Для плова'], expiry: inDays(365), likes: 95 }),
      P('Масло, соусы, специи', 'Масло хлопковое', 25, 'л', { minStep: 1, expiry: inDays(200) }),
      P('Конфеты и шоколад', 'Шоколад молочный', 12, 'шт', { attrs: { brand: 'Alpen Gold', pack: '85 г' }, expiry: inDays(240) }),
      P('Печенье и сладости', 'Печенье «Юбилейное»', 9, 'упак', { expiry: inDays(180), oldPrice: 11 }),
      P('Снеки и чипсы', 'Чипсы Lay’s сметана и лук', 11, 'шт', { attrs: { pack: '140 г' }, expiry: inDays(150) }),
      P('Соки', 'Сок яблочный', 13, 'шт', { attrs: { pack: '1 л' }, expiry: inDays(200) }),
      P('Бытовая химия', 'Средство для посуды', 16, 'шт', { attrs: { brand: 'Fairy', pack: '500 мл' } }),
      P('Гигиена', 'Зубная паста', 14, 'шт', { attrs: { brand: 'Colgate' } }),
      P('Детское питание', 'Пюре яблочное', 6, 'шт', { expiry: inDays(300) }),
    ],
  },
  {
    id: 'atir', tile: { bg: '#1d1d1f', fg: '#e8c77a' }, name: 'Парфюм-хаус Атир', kind: 'perfume', about: 'Только оригиналы. Есть разлив и тестеры', rating: 4.9, count: 236, prep: 25, minOrder: 0,
    address: 'Душанбе, ТЦ «Садбарг», 2 этаж', schedule: week('09:00', '21:00'), color: '#f6ead2',
    products: [
      P('Мужская парфюмерия', 'Lattafa Khamrah', 450, 'шт', { attrs: { brand: 'Lattafa', gender: 'Унисекс', ptype: 'Парфюмерная вода', volume: '100', origin: 'Новый, в упаковке' }, labels: ['Хит'], likes: 98, desc: 'Ноты: корица, финики, ваниль, пралине. Стойкость 8–10 часов.' }),
      P('Мужская парфюмерия', 'Dior Sauvage', 1450, 'шт', { attrs: { brand: 'Dior', gender: 'Мужской', ptype: 'Туалетная вода', origin: 'Новый, в упаковке' }, variants: [{ id: 'v60', name: '60 мл', price: 1450 }, { id: 'v100', name: '100 мл', price: 1950 }], likes: 97 }),
      P('Женская парфюмерия', 'Chanel Coco Mademoiselle', 1890, 'шт', { attrs: { brand: 'Chanel', gender: 'Женский', ptype: 'Парфюмерная вода', volume: '50', origin: 'Новый, в упаковке' } }),
      P('Женская парфюмерия', 'Lancôme La Vie Est Belle', 1250, 'шт', { attrs: { brand: 'Lancôme', gender: 'Женский', ptype: 'Парфюмерная вода', volume: '50', origin: 'Тестер' }, oldPrice: 1490 }),
      P('Унисекс', 'Armaf Club de Nuit Intense', 520, 'шт', { attrs: { brand: 'Armaf', gender: 'Мужской', ptype: 'Парфюмерная вода', volume: '105', origin: 'Новый, в упаковке' }, likes: 94 }),
      P('Парфюм на разлив', 'Kilian Angels’ Share — разлив', 45, 'мл', { attrs: { brand: 'Kilian', ptype: 'Парфюмерная вода', origin: 'Разлив' }, minStep: 1, desc: 'Цена за 1 мл, от 5 мл' }),
      P('Уход за лицом', 'Крем увлажняющий', 210, 'шт', { attrs: { brand: 'CeraVe', volume: '52' } }),
      P('Макияж', 'Тушь для ресниц', 130, 'шт', { attrs: { brand: 'Maybelline' } }),
      P('Подарочные наборы', 'Набор Versace Eros', 1100, 'шт', { attrs: { brand: 'Versace', gender: 'Мужской' }, labels: ['К празднику'] }),
    ],
  },
  {
    id: 'rohat', tile: { bg: '#f3e3cf', fg: '#7a3e12' }, name: 'Чайхона Рохат', kind: 'food', about: 'Национальная кухня: плов, шашлык, самбуса', rating: 4.7, count: 870, prep: 30, minOrder: 40,
    address: 'Душанбе, ул. Рудаки 84', schedule: week('10:00', '23:00'), color: '#fbe6d4',
    products: [
      P('Горячее', 'Плов праздничный', 35, 'порция', { labels: ['Хит'], likes: 98, attrs: { portion: '350' }, desc: 'Рис девзира, баранина, морковь, нут, изюм', options: [{ id: 'o1', name: 'Большая порция', price: 15 }, { id: 'o2', name: 'Без лука', price: 0 }, { id: 'o3', name: 'Добавить перепелиные яйца', price: 6 }] }),
      P('Горячее', 'Шашлык из баранины', 28, 'шт', { attrs: { portion: '180' }, options: [{ id: 'o4', name: 'С луком и зеленью', price: 0 }, { id: 'o5', name: 'Лаваш', price: 3 }] }),
      P('Горячее', 'Курутоб', 32, 'порция', { likes: 96, attrs: { portion: '400' } }),
      P('Супы', 'Шурбо', 22, 'порция', { attrs: { portion: '400' } }),
      P('Салаты', 'Салат «Шакароб»', 12, 'порция', { attrs: { portion: '250' } }),
      P('Выпечка', 'Самбуса тандырная', 8, 'шт', { options: [{ id: 'o6', name: 'Острый соус', price: 1 }] }),
      P('Десерты', 'Халва кунжутная', 10, 'порция'),
      P('Напитки', 'Чай зелёный, чайник', 6, 'шт'),
      P('Напитки', 'Компот домашний', 7, 'шт', { attrs: { portion: '500' } }),
    ],
  },
  {
    id: 'burger', tile: { bg: '#ff7a1a', fg: '#ffffff' }, name: 'Burger Town', kind: 'food', about: 'Бургеры на гриле, картофель фри, шейки', rating: 4.5, count: 512, prep: 20, minOrder: 30,
    address: 'Душанбе, ул. Мирзо Турсунзаде 30', schedule: week('11:00', '02:00'), color: '#fde3dc',
    products: [
      P('Бургеры', 'Чизбургер', 26, 'шт', { labels: ['Хит'], likes: 93, options: [{ id: 'b1', name: 'Двойной сыр', price: 5 }, { id: 'b2', name: 'Без лука', price: 0 }, { id: 'b3', name: 'Острый соус', price: 2 }] }),
      P('Бургеры', 'Двойной бургер с говядиной', 39, 'шт', { options: [{ id: 'b4', name: 'Бекон из индейки', price: 7 }, { id: 'b1', name: 'Двойной сыр', price: 5 }] }),
      P('Закуски', 'Картофель фри', 12, 'порция', { variants: [{ id: 's', name: 'Средний', price: 12 }, { id: 'l', name: 'Большой', price: 16 }] }),
      P('Закуски', 'Наггетсы, 9 шт', 22, 'порция'),
      P('Напитки', 'Молочный шейк', 18, 'шт', { variants: [{ id: 'van', name: 'Ванильный', price: 18 }, { id: 'ch', name: 'Шоколадный', price: 18 }, { id: 'st', name: 'Клубничный', price: 19 }] }),
      P('Напитки', 'Coca-Cola 0,5 л', 7, 'шт'),
    ],
  },
];
// товары с одинаковой картинкой не путаем между магазинами
for (const s of DEMO_SHOPS) { s.demo = true; s.cats = [...new Set(s.products.map(p => p.cat))]; for (const p of s.products) p.id = s.id + '-' + p.id; }
