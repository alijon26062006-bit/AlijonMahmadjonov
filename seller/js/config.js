// справочники

// тип магазина задаёт единицы товаров и стартовые категории
export const SHOP_KINDS = [
  { id: 'grocery', name: 'Продукты', units: ['кг', 'г', 'шт', 'л', 'упак'], cats: ['Овощи', 'Фрукты', 'Молочное', 'Мясо', 'Хлеб', 'Напитки'],
    icon: '<path d="M3 4h2l2.4 11h9.6l2-8H6"/><circle cx="9" cy="19" r="1.3"/><circle cx="17" cy="19" r="1.3"/>' },
  { id: 'food', name: 'Ресторан, кафе', units: ['порция', 'шт'], cats: ['Горячее', 'Супы', 'Салаты', 'Десерты', 'Напитки'],
    icon: '<path d="M4 11h16a8 8 0 0 1-16 0zM12 3v4M8 5v2M16 5v2"/>' },
  { id: 'bakery', name: 'Торты и выпечка', units: ['шт', 'кг'], cats: ['Торты', 'Выпечка', 'Десерты'],
    icon: '<path d="M4 21h16M5 21v-7h14v7M5 14c0-3 3-4 7-4s7 1 7 4M12 10V6"/>' },
  { id: 'flowers', name: 'Цветы', units: ['шт', 'букет'], cats: ['Розы', 'Букеты', 'В горшках', 'Подарки'],
    icon: '<circle cx="12" cy="8" r="4"/><path d="M12 12v9M12 17c-3 0-5-2-5-4M12 17c3 0 5-2 5-4"/>' },
  { id: 'pharmacy', name: 'Аптека', units: ['упак', 'шт'], cats: ['Лекарства', 'Витамины', 'Детям', 'Гигиена'],
    icon: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 8v8M8 12h8"/>' },
  { id: 'clothes', name: 'Одежда и обувь', units: ['шт'], cats: ['Женское', 'Мужское', 'Детское', 'Обувь'],
    icon: '<path d="M8 4l4 2 4-2 4 4-3 3v9H7v-9L4 8z"/>' },
  { id: 'electronics', name: 'Электроника', units: ['шт'], cats: ['Телефоны', 'Аксессуары', 'Техника'],
    icon: '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 18h2"/>' },
  { id: 'other', name: 'Другое', units: ['шт', 'упак', 'кг'], cats: ['Основное'],
    icon: '<path d="M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M12 11v10"/>' },
];
export const kindOf = shop => SHOP_KINDS.find(k => k.id === shop?.kind) || SHOP_KINDS.find(k => k.name === shop?.type) || SHOP_KINDS.at(-1);
export const SHOP_TYPES = SHOP_KINDS.map(k => k.name);
export const UNITS = ['шт', 'букет', 'кг', 'г', 'л', 'порция', 'упак'];
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
