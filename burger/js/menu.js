/* Меню. Фото блюда кладём в assets/dishes/ и называем по id: cheeseburger.jpg
   Пока фото нет — в карточке рисуется знак заведения, вёрстка не ломается. */

const SECTIONS = [
  { id: 'burgers', title: 'Бургеры',   note: 'Котлета жарится на гриле после заказа' },
  { id: 'sets',    title: 'Сеты',      note: 'Собрали то, что чаще всего берут вместе' },
  { id: 'snacks',  title: 'К бургеру', note: '' },
  { id: 'sauces',  title: 'Соусы',     note: '' },
  { id: 'drinks',  title: 'Напитки',   note: '' }
];

const MENU = [
  {
    id: 'classic', section: 'burgers', name: 'Классик',
    about: 'Котлета из говядины, чеддер, салат айсберг, томат, соленый огурец, соус бургер',
    weight: 260, price: 25, tag: 'hit'
  },
  {
    id: 'double-cheese', section: 'burgers', name: 'Двойной чизбургер',
    about: 'Две котлеты, двойной чеддер, лук, огурец, горчично-медовый соус',
    weight: 380, price: 38, tag: 'hit'
  },
  {
    id: 'cheeseburger', section: 'burgers', name: 'Чизбургер',
    about: 'Котлета из говядины, чеддер, лук, огурец, кетчуп и горчица',
    weight: 210, price: 22
  },
  {
    id: 'bbq-bacon', section: 'burgers', name: 'BBQ Бекон',
    about: 'Котлета, бекон, чеддер, жареный лук, соус барбекю на угольной булочке',
    weight: 300, price: 34
  },
  {
    id: 'jalapeno', section: 'burgers', name: 'Джалапеньо',
    about: 'Котлета, перец халапеньо, чеддер, лук, острый соус чипотле',
    weight: 280, price: 32, tag: 'hot'
  },
  {
    id: 'chicken-crispy', section: 'burgers', name: 'Чикен Криспи',
    about: 'Куриное филе в хрустящей панировке, айсберг, томат, чесночный соус',
    weight: 250, price: 24
  },
  {
    id: 'crown', section: 'burgers', name: 'The Burger Crown',
    about: 'Три котлеты, тройной чеддер, бекон, жареный лук, наш фирменный соус',
    weight: 520, price: 55, tag: 'new'
  },
  {
    id: 'fish', section: 'burgers', name: 'Фишбургер',
    about: 'Филе белой рыбы, айсберг, соус тартар, булочка с кунжутом',
    weight: 230, price: 28
  },

  {
    id: 'set-duo', section: 'sets', name: 'Сет на двоих',
    about: 'Два Классика, большая картошка фри, два соуса, две колы 0,5',
    weight: 1150, price: 95, oldPrice: 112, tag: 'hit'
  },
  {
    id: 'set-company', section: 'sets', name: 'Сет для компании',
    about: 'Четыре бургера на выбор, две картошки фри, наггетсы 9 шт, четыре соуса',
    weight: 2300, price: 185, oldPrice: 220
  },
  {
    id: 'set-lunch', section: 'sets', name: 'Ланч до 16:00',
    about: 'Чизбургер, картошка фри, соус и напиток на выбор',
    weight: 620, price: 42, oldPrice: 49
  },

  { id: 'fries',        section: 'snacks', name: 'Картошка фри',        about: 'Крупная соломка, морская соль', weight: 150, price: 12 },
  { id: 'fries-cheese', section: 'snacks', name: 'Фри с сыром',          about: 'Фри, соус чеддер, бекон',       weight: 180, price: 18 },
  { id: 'nuggets',      section: 'snacks', name: 'Наггетсы 6 шт',        about: 'Куриное филе в панировке',      weight: 140, price: 16 },
  { id: 'wings',        section: 'snacks', name: 'Крылья BBQ 6 шт',      about: 'Маринад барбекю, гриль',        weight: 300, price: 26, tag: 'hot' },
  { id: 'onion-rings',  section: 'snacks', name: 'Луковые кольца',       about: 'Восемь колец, соус ранч',       weight: 130, price: 15 },

  { id: 'sauce-burger', section: 'sauces', name: 'Соус бургер',   about: '', weight: 30, price: 3 },
  { id: 'sauce-cheese', section: 'sauces', name: 'Сырный',        about: '', weight: 30, price: 4 },
  { id: 'sauce-bbq',    section: 'sauces', name: 'Барбекю',       about: '', weight: 30, price: 3 },
  { id: 'sauce-chili',  section: 'sauces', name: 'Чили',          about: '', weight: 30, price: 3, tag: 'hot' },

  { id: 'cola',      section: 'drinks', name: 'Кола 0,5',     about: '', weight: 500, price: 8 },
  { id: 'fanta',     section: 'drinks', name: 'Фанта 0,5',    about: '', weight: 500, price: 8 },
  { id: 'lemonade',  section: 'drinks', name: 'Домашний лимонад', about: 'Лимон, мята, лёд', weight: 400, price: 14 },
  { id: 'milkshake', section: 'drinks', name: 'Милкшейк',     about: 'Ваниль, шоколад или банан', weight: 400, price: 18 },
  { id: 'tea',       section: 'drinks', name: 'Чай',          about: 'Чёрный или зелёный', weight: 400, price: 5 }
];

const TAGS = {
  hit: { label: 'Хит', cls: 'is-hit' },
  hot: { label: 'Острый', cls: 'is-hot' },
  new: { label: 'Новинка', cls: 'is-new' }
};

/* доставка */
const DELIVERY = { price: 15, freeFrom: 100, minOrder: 40 };
