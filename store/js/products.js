/* Товары магазина.
   Фото кладём в assets/products/ и называем файл по id: iphone-15.jpg и т.д.
   Пока фото нет — карточка сама показывает заглушку. */

const CATEGORIES = [
  { id: 'phones',      ru: 'Смартфоны',   tj: 'Смартфонҳо' },
  { id: 'audio',       ru: 'Наушники',    tj: 'Гӯшмонакҳо' },
  { id: 'watch',       ru: 'Часы',        tj: 'Соатҳо' },
  { id: 'accessories', ru: 'Аксессуары',  tj: 'Аксессуарҳо' }
];

const PRODUCTS = [
  {
    id: 'iphone-15-pro-max-256',
    brand: 'Apple', category: 'phones',
    name: 'iPhone 15 Pro Max 256GB',
    specs: { ru: 'Titanium Blue · 8/256 ГБ', tj: 'Titanium Blue · 8/256 ГБ' },
    price: 13500, oldPrice: 14700, hit: true
  },
  {
    id: 'iphone-15-128',
    brand: 'Apple', category: 'phones',
    name: 'iPhone 15 128GB',
    specs: { ru: 'Black · 6/128 ГБ', tj: 'Black · 6/128 ГБ' },
    price: 7990, oldPrice: 8900, hit: true
  },
  {
    id: 'iphone-14-128',
    brand: 'Apple', category: 'phones',
    name: 'iPhone 14 128GB',
    specs: { ru: 'Midnight · 6/128 ГБ', tj: 'Midnight · 6/128 ГБ' },
    price: 6400
  },
  {
    id: 'iphone-13-128',
    brand: 'Apple', category: 'phones',
    name: 'iPhone 13 128GB',
    specs: { ru: 'Starlight · 4/128 ГБ', tj: 'Starlight · 4/128 ГБ' },
    price: 5200, oldPrice: 5600
  },
  {
    id: 'galaxy-s24-ultra-256',
    brand: 'Samsung', category: 'phones',
    name: 'Samsung Galaxy S24 Ultra',
    specs: { ru: 'Titanium Gray · 12/256 ГБ', tj: 'Titanium Gray · 12/256 ГБ' },
    price: 12900, hit: true
  },
  {
    id: 'galaxy-a55-128',
    brand: 'Samsung', category: 'phones',
    name: 'Samsung Galaxy A55',
    specs: { ru: 'Awesome Navy · 8/128 ГБ', tj: 'Awesome Navy · 8/128 ГБ' },
    price: 4300, oldPrice: 4650
  },
  {
    id: 'galaxy-a15-128',
    brand: 'Samsung', category: 'phones',
    name: 'Samsung Galaxy A15',
    specs: { ru: 'Blue Black · 4/128 ГБ', tj: 'Blue Black · 4/128 ГБ' },
    price: 1950
  },
  {
    id: 'redmi-note-13-pro-256',
    brand: 'Xiaomi', category: 'phones',
    name: 'Redmi Note 13 Pro',
    specs: { ru: 'Ocean Teal · 8/256 ГБ', tj: 'Ocean Teal · 8/256 ГБ' },
    price: 2800, oldPrice: 3100, hit: true
  },
  {
    id: 'xiaomi-14t-256',
    brand: 'Xiaomi', category: 'phones',
    name: 'Xiaomi 14T',
    specs: { ru: 'Titan Blue · 12/256 ГБ', tj: 'Titan Blue · 12/256 ГБ' },
    price: 5600
  },
  {
    id: 'redmi-13c-128',
    brand: 'Xiaomi', category: 'phones',
    name: 'Redmi 13C',
    specs: { ru: 'Navy Blue · 4/128 ГБ', tj: 'Navy Blue · 4/128 ГБ' },
    price: 1250
  },
  {
    id: 'honor-x9b-256',
    brand: 'Honor', category: 'phones',
    name: 'Honor X9b',
    specs: { ru: 'Sunrise Orange · 8/256 ГБ', tj: 'Sunrise Orange · 8/256 ГБ' },
    price: 3100
  },
  {
    id: 'infinix-hot-40i',
    brand: 'Infinix', category: 'phones',
    name: 'Infinix Hot 40i',
    specs: { ru: 'Starlit Black · 8/256 ГБ', tj: 'Starlit Black · 8/256 ГБ' },
    price: 1150
  },
  {
    id: 'airpods-pro-2',
    brand: 'Apple', category: 'audio',
    name: 'AirPods Pro 2 (USB-C)',
    specs: { ru: 'Шумоподавление, чехол MagSafe', tj: 'Пахши садо, ғилофи MagSafe' },
    price: 1890, oldPrice: 2100, hit: true
  },
  {
    id: 'airpods-3',
    brand: 'Apple', category: 'audio',
    name: 'AirPods 3',
    specs: { ru: 'Lightning, 30 часов работы', tj: 'Lightning, 30 соат кор' },
    price: 1250
  },
  {
    id: 'jbl-tune-520bt',
    brand: 'JBL', category: 'audio',
    name: 'JBL Tune 520BT',
    specs: { ru: 'Bluetooth 5.3, 57 часов', tj: 'Bluetooth 5.3, 57 соат' },
    price: 420
  },
  {
    id: 'apple-watch-se-2',
    brand: 'Apple', category: 'watch',
    name: 'Apple Watch SE 2 44mm',
    specs: { ru: 'Midnight, спортивный ремешок', tj: 'Midnight, тасмаи варзишӣ' },
    price: 2690
  },
  {
    id: 'galaxy-watch-6',
    brand: 'Samsung', category: 'watch',
    name: 'Galaxy Watch 6 44mm',
    specs: { ru: 'Graphite, Wear OS', tj: 'Graphite, Wear OS' },
    price: 2150, oldPrice: 2400
  },
  {
    id: 'anker-powerbank-20000',
    brand: 'Anker', category: 'accessories',
    name: 'Powerbank Anker 20000 мАч',
    specs: { ru: '22.5W, быстрая зарядка', tj: '22.5W, зарядкунии тез' },
    price: 390
  },
  {
    id: 'charger-20w',
    brand: 'Apple', category: 'accessories',
    name: 'Зарядка USB-C 20W',
    specs: { ru: 'Оригинал, для iPhone', tj: 'Аслӣ, барои iPhone' },
    price: 120
  },
  {
    id: 'case-iphone-15',
    brand: 'Apple', category: 'accessories',
    name: 'Чехол Silicone Case',
    specs: { ru: 'Для iPhone 15, цвета в наличии', tj: 'Барои iPhone 15, рангҳо мавҷуд' },
    price: 90
  }
];
