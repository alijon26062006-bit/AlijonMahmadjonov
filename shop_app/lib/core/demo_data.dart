import 'dart:math';

import 'package:material_ui/material_ui.dart';

import 'models.dart';

/// Категории — общие для всех приложений.
const kCategories = <Category>[
  Category(id: 'electronics', name: 'Техника', emoji: '📱', tint: [Color(0xFFE4DBFF), Color(0xFFD5E4FF)]),
  Category(id: 'clothes', name: 'Одежда', emoji: '👗', tint: [Color(0xFFFFE1EF), Color(0xFFFFD3E3)]),
  Category(id: 'shoes', name: 'Обувь', emoji: '👟', tint: [Color(0xFFDDF7EA), Color(0xFFCBEFF5)]),
  Category(id: 'home', name: 'Дом', emoji: '🏠', tint: [Color(0xFFFFF0D3), Color(0xFFFFE0CC)]),
  Category(id: 'beauty', name: 'Красота', emoji: '💄', tint: [Color(0xFFFFE0F0), Color(0xFFF3DBFF)]),
  Category(id: 'sport', name: 'Спорт', emoji: '⚽', tint: [Color(0xFFD9F2FF), Color(0xFFD6E6FF)]),
  Category(id: 'kids', name: 'Детям', emoji: '🧸', tint: [Color(0xFFFFF4C9), Color(0xFFFFE3D1)]),
  Category(id: 'food', name: 'Продукты', emoji: '🍎', tint: [Color(0xFFE5F8D6), Color(0xFFFFF0CF)]),
];

final Map<String, Category> _categoriesById = {for (final c in kCategories) c.id: c};

Category categoryById(String id) => _categoriesById[id] ?? kCategories.first;

const kPromos = <Promo>[
  Promo('VITRINA20', 'Скидка 20% на весь заказ', percent: 20),
  Promo('SALE10', 'Скидка 10% на весь заказ', percent: 10),
  Promo('WELCOME', 'Минус 30 смн на первый заказ', fixed: 30),
];

const kPayments = ['Картой при получении', 'Наличными', 'Онлайн'];

const kCancelReasons = ['Нет в наличии', 'Магазин закрыт', 'Покупатель не отвечает', 'Покупатель передумал', 'Другое'];

const kBuyerNames = [
  'Мадина',
  'Фирдавс',
  'Нигина',
  'Парвиз',
  'Зарина',
  'Комрон',
  'Шахноза',
  'Манучехр',
  'Ситора',
  'Далер',
  'Анвар',
  'Мехрона',
  'Исмоил',
  'Тахмина',
  'Бахром',
];

const kAddresses = [
  'ул. Рудаки, 45, кв. 12',
  'ул. Айни, 8, кв. 3',
  'пр. Исмоили Сомони, 21',
  'ул. Шотемура, 3, кв. 5',
  'мкр. Сино, 14, кв. 40',
  'ул. Бохтар, 17',
  'ул. Мирзо Турсунзода, 30, кв. 9',
  'ул. Пушкина, 12',
  'мкр. Зарафшон, 6, кв. 71',
  'ул. Карамова, 52',
];

/// Демо-данные: магазины, товары, курьеры и заказы за последнюю неделю.
/// Когда подключим сервер, всё это будет приходить из базы.
class DemoData {
  DemoData._();

  static List<Shop> shops() => [
    Shop(
      id: 's1',
      name: 'ТехноМир',
      emoji: '📱',
      categoryId: 'electronics',
      ownerName: 'Фаррух Набиев',
      ownerPhone: '900000001',
      address: 'ул. Рудаки, 102',
      description: 'Смартфоны, ноутбуки и аксессуары с гарантией.',
      rating: 4.8,
      ratingCount: 1243,
    ),
    Shop(
      id: 's2',
      name: 'Модный дом',
      emoji: '👗',
      categoryId: 'clothes',
      ownerName: 'Мадина Каримова',
      ownerPhone: '900000002',
      address: 'ТЦ «Пайкар», 2 этаж',
      description: 'Одежда и обувь для всей семьи.',
      rating: 4.7,
      ratingCount: 980,
    ),
    Shop(
      id: 's3',
      name: 'Уютный дом',
      emoji: '🏠',
      categoryId: 'home',
      ownerName: 'Бахтиёр Саидов',
      ownerPhone: '900000003',
      address: 'ул. Айни, 48',
      description: 'Всё для дома и кухни.',
      rating: 4.8,
      ratingCount: 512,
    ),
    Shop(
      id: 's4',
      name: 'Красота+',
      emoji: '💄',
      categoryId: 'beauty',
      ownerName: 'Нигора Юсупова',
      ownerPhone: '900000004',
      address: 'пр. Исмоили Сомони, 9',
      description: 'Косметика и парфюмерия.',
      rating: 4.6,
      ratingCount: 731,
    ),
    Shop(
      id: 's5',
      name: 'Спорт-Лайн',
      emoji: '⚽',
      categoryId: 'sport',
      ownerName: 'Рустам Алиев',
      ownerPhone: '900000005',
      address: 'ул. Бохтар, 3',
      description: 'Спорт, отдых и игрушки.',
      rating: 4.7,
      ratingCount: 402,
    ),
    Shop(
      id: 's6',
      name: 'Фермер',
      emoji: '🍎',
      categoryId: 'food',
      ownerName: 'Абдулло Шарипов',
      ownerPhone: '900000006',
      address: 'Зелёный базар, ряд 4',
      description: 'Свежие продукты каждый день.',
      rating: 4.9,
      ratingCount: 2045,
    ),
    Shop(
      id: 's7',
      name: 'Гаджет Плюс',
      emoji: '🎧',
      categoryId: 'electronics',
      ownerName: 'Сухроб Олимов',
      ownerPhone: '900000007',
      address: 'ул. Карамова, 15',
      description: 'Чехлы, зарядки, наушники.',
      rating: 5.0,
      ratingCount: 0,
      status: ShopStatus.pending,
    ),
    Shop(
      id: 's8',
      name: 'Дисконт 24',
      emoji: '🏷️',
      categoryId: 'home',
      ownerName: 'Иван Петров',
      ownerPhone: '900000008',
      address: 'ул. Пушкина, 1',
      description: 'Товары со скидкой.',
      rating: 3.1,
      ratingCount: 58,
      status: ShopStatus.blocked,
    ),
  ];

  static List<Product> products() {
    Product p(
      String id,
      String shop,
      String cat,
      String e,
      String t,
      int price, {
      int? old,
      double r = 4.7,
      int rv = 300,
      String d = '',
      String? ol,
      List<String> o = const [],
      bool hit = false,
      int stock = 25,
    }) => Product(
      id: id,
      shopId: shop,
      categoryId: cat,
      emoji: e,
      title: t,
      price: price,
      oldPrice: old,
      rating: r,
      reviews: rv,
      description: d,
      optionsLabel: ol,
      options: o,
      hit: hit,
      stock: stock,
    );
    return [
      // ТехноМир
      p(
        'e1',
        's1',
        'electronics',
        '📱',
        'Смартфон Nova X12, 6.7″ AMOLED',
        2999,
        old: 3499,
        r: 4.8,
        rv: 1243,
        hit: true,
        ol: 'Память',
        o: ['128 ГБ', '256 ГБ', '512 ГБ'],
        d: 'Яркий AMOLED-экран 120 Гц, камера 108 Мп и батарея 5000 мА·ч на два дня. Быстрая зарядка 67 Вт.',
      ),
      p(
        'e2',
        's1',
        'electronics',
        '🎧',
        'Беспроводные наушники AirBeat Pro',
        449,
        old: 649,
        r: 4.8,
        rv: 3410,
        hit: true,
        ol: 'Цвет',
        o: ['Белый', 'Чёрный'],
        d: 'Активное шумоподавление и до 30 часов работы с кейсом.',
      ),
      p(
        'e3',
        's1',
        'electronics',
        '💻',
        'Ноутбук ProBook 14, лёгкий корпус',
        6999,
        old: 7999,
        r: 4.9,
        rv: 512,
        ol: 'Конфигурация',
        o: ['8/256 ГБ', '16/512 ГБ'],
        d: 'Алюминиевый корпус 1,2 кг, экран 14″ 2.8K, до 14 часов работы.',
      ),
      p(
        'e4',
        's1',
        'electronics',
        '⌚',
        'Умные часы Pulse 2',
        799,
        old: 999,
        r: 4.6,
        rv: 876,
        hit: true,
        ol: 'Цвет',
        o: ['Чёрный', 'Розовый', 'Синий'],
        d: 'Пульс, сон, 100+ тренировок и 10 дней без подзарядки.',
      ),
      p(
        'e5',
        's1',
        'electronics',
        '🔊',
        'Колонка BassBox mini',
        299,
        old: 399,
        r: 4.5,
        rv: 640,
        d: 'Мощный бас, защита от воды IP67, 12 часов музыки.',
      ),
      p(
        'e6',
        's1',
        'electronics',
        '🎮',
        'Игровая приставка GameBox S',
        4499,
        old: 4999,
        r: 4.9,
        rv: 1820,
        stock: 6,
        d: 'Игры в 4K и 120 FPS, SSD 1 ТБ и геймпад в комплекте.',
      ),
      p(
        'e7',
        's1',
        'electronics',
        '🔋',
        'Внешний аккумулятор 20 000 мА·ч',
        189,
        r: 4.7,
        rv: 905,
        d: 'Заряжает телефон 4–5 раз, два USB-порта.',
      ),
      p(
        'e8',
        's1',
        'electronics',
        '🔌',
        'Быстрая зарядка 65 Вт',
        129,
        old: 159,
        r: 4.6,
        rv: 388,
        d: 'Подходит для телефона и ноутбука.',
      ),
      // Модный дом
      p(
        'c1',
        's2',
        'clothes',
        '👕',
        'Футболка хлопковая Basic',
        89,
        old: 129,
        r: 4.7,
        rv: 2210,
        hit: true,
        ol: 'Размер',
        o: ['S', 'M', 'L', 'XL'],
        d: '100% плотный хлопок, свободный крой.',
      ),
      p(
        'c2',
        's2',
        'clothes',
        '👖',
        'Джинсы прямые классические',
        249,
        old: 329,
        r: 4.6,
        rv: 980,
        ol: 'Размер',
        o: ['28', '30', '32', '34'],
        d: 'Плотный деним с каплей эластана.',
      ),
      p(
        'c3',
        's2',
        'clothes',
        '👗',
        'Платье летнее миди',
        279,
        old: 399,
        r: 4.8,
        rv: 655,
        ol: 'Размер',
        o: ['XS', 'S', 'M', 'L'],
        d: 'Лёгкая струящаяся ткань и аккуратный пояс.',
      ),
      p(
        'c4',
        's2',
        'clothes',
        '🧥',
        'Куртка демисезонная',
        599,
        old: 899,
        r: 4.7,
        rv: 431,
        ol: 'Размер',
        o: ['S', 'M', 'L', 'XL'],
        d: 'Ветрозащитная ткань и тёплая подкладка.',
      ),
      p('c5', 's2', 'clothes', '🧢', 'Кепка City', 79, r: 4.5, rv: 312, d: 'Регулируемый размер, дышащий хлопок.'),
      p(
        'c6',
        's2',
        'clothes',
        '🎒',
        'Рюкзак Urban 20 л',
        219,
        old: 299,
        r: 4.8,
        rv: 1104,
        d: 'Отделение для ноутбука до 15″.',
      ),
      p(
        'sh1',
        's2',
        'shoes',
        '👟',
        'Кроссовки Run Pro, сетка',
        499,
        old: 699,
        r: 4.7,
        rv: 982,
        hit: true,
        ol: 'Размер',
        o: ['39', '40', '41', '42', '43', '44'],
        d: 'Лёгкие беговые кроссовки с амортизацией.',
      ),
      p(
        'sh2',
        's2',
        'shoes',
        '🥾',
        'Ботинки зимние на меху',
        649,
        old: 799,
        r: 4.6,
        rv: 377,
        ol: 'Размер',
        o: ['40', '41', '42', '43', '44'],
        d: 'Натуральная кожа, держат тепло до −30 °C.',
      ),
      p(
        'sh3',
        's2',
        'shoes',
        '👡',
        'Босоножки на плоской подошве',
        199,
        old: 279,
        r: 4.6,
        rv: 290,
        ol: 'Размер',
        o: ['36', '37', '38', '39'],
        d: 'Мягкие ремешки и удобная стелька.',
      ),
      // Уютный дом
      p(
        'h1',
        's3',
        'home',
        '☕',
        'Кофемашина Aroma с капучинатором',
        1899,
        old: 2399,
        r: 4.9,
        rv: 421,
        hit: true,
        stock: 8,
        d: 'Эспрессо, капучино и латте одной кнопкой. Давление 15 бар.',
      ),
      p('h2', 's3', 'home', '💡', 'Настольная лампа LED', 159, r: 4.6, rv: 503, d: 'Три режима света и USB-порт.'),
      p(
        'h3',
        's3',
        'home',
        '🍳',
        'Набор посуды, 8 предметов',
        349,
        old: 499,
        r: 4.7,
        rv: 689,
        d: 'Антипригарное покрытие, для всех плит.',
      ),
      p('h4', 's3', 'home', '🌿', 'Комнатное растение Монстера', 129, r: 4.8, rv: 240, d: 'Высота 50–60 см, в горшке.'),
      p(
        'h5',
        's3',
        'home',
        '🕯️',
        'Аромасвеча «Ваниль и сандал»',
        69,
        old: 89,
        r: 4.7,
        rv: 815,
        d: 'Соевый воск, до 40 часов горения.',
      ),
      p('h6', 's3', 'home', '🛏️', 'Подушка ортопедическая', 149, r: 4.6, rv: 199, d: 'Эффект памяти, съёмный чехол.'),
      // Красота+
      p(
        'b1',
        's4',
        'beauty',
        '🌸',
        'Парфюм Bloom, цветочный',
        399,
        old: 499,
        r: 4.8,
        rv: 731,
        ol: 'Объём',
        o: ['50 мл', '100 мл'],
        d: 'Ноты пиона, жасмина и белого мускуса.',
      ),
      p(
        'b2',
        's4',
        'beauty',
        '💄',
        'Помада матовая Velvet',
        59,
        old: 89,
        r: 4.6,
        rv: 1290,
        ol: 'Оттенок',
        o: ['Нюд', 'Красный', 'Ягодный'],
        d: 'Бархатный финиш, не сушит губы.',
      ),
      p(
        'b3',
        's4',
        'beauty',
        '🧴',
        'Увлажняющий крем для лица',
        119,
        r: 4.7,
        rv: 944,
        d: 'С гиалуроновой кислотой и пантенолом.',
      ),
      p('b4', 's4', 'beauty', '💅', 'Набор для маникюра', 99, old: 129, r: 4.5, rv: 210, d: '9 инструментов в чехле.'),
      // Спорт-Лайн
      p(
        'p1',
        's5',
        'sport',
        '⚽',
        'Мяч футбольный, размер 5',
        149,
        old: 199,
        r: 4.7,
        rv: 402,
        d: 'Прошит вручную, для травы и газона.',
      ),
      p(
        'p2',
        's5',
        'sport',
        '🏋️',
        'Гантели разборные 2×5 кг',
        249,
        r: 4.8,
        rv: 333,
        d: 'Вес от 1 до 5 кг, прорезиненные ручки.',
      ),
      p(
        'p3',
        's5',
        'sport',
        '🚲',
        'Велосипед городской City 28',
        2499,
        old: 2999,
        r: 4.8,
        rv: 268,
        hit: true,
        stock: 4,
        ol: 'Рама',
        o: ['M', 'L'],
        d: 'Алюминиевая рама, 7 скоростей, корзина в комплекте.',
      ),
      p('p4', 's5', 'sport', '🧘', 'Коврик для йоги, 6 мм', 99, r: 4.6, rv: 517, d: 'Нескользящий, мягкий и лёгкий.'),
      p(
        'k1',
        's5',
        'kids',
        '🧸',
        'Плюшевый мишка, 40 см',
        99,
        old: 129,
        r: 4.9,
        rv: 1532,
        d: 'Мягкий, гипоаллергенный наполнитель.',
      ),
      p(
        'k2',
        's5',
        'kids',
        '🤖',
        'Конструктор «Робот», 320 деталей',
        249,
        old: 329,
        r: 4.8,
        rv: 488,
        d: 'Развивает логику. 6+.',
      ),
      p(
        'k3',
        's5',
        'kids',
        '🏎️',
        'Машинка на радиоуправлении',
        199,
        r: 4.5,
        rv: 376,
        d: 'До 20 км/ч, аккумулятор в комплекте.',
      ),
      // Фермер
      p(
        'f1',
        's6',
        'food',
        '🍎',
        'Яблоки сезонные, 2 кг',
        25,
        r: 4.7,
        rv: 1210,
        stock: 80,
        d: 'Свежие, отобранные вручную.',
      ),
      p(
        'f2',
        's6',
        'food',
        '🍫',
        'Шоколад тёмный 72%',
        29,
        old: 35,
        r: 4.9,
        rv: 2045,
        stock: 60,
        d: 'Насыщенный вкус какао. 100 г.',
      ),
      p(
        'f3',
        's6',
        'food',
        '🍵',
        'Чай зелёный листовой, 200 г',
        49,
        r: 4.8,
        rv: 663,
        stock: 40,
        d: 'Мягкий вкус с цветочными нотками.',
      ),
      p(
        'f4',
        's6',
        'food',
        '🍯',
        'Мёд натуральный горный, 500 г',
        69,
        old: 79,
        r: 4.9,
        rv: 801,
        stock: 30,
        d: 'Собран на горных лугах, без добавок.',
      ),
      p(
        'f5',
        's6',
        'food',
        '🧀',
        'Сыр домашний, 400 г',
        45,
        r: 4.7,
        rv: 356,
        stock: 25,
        d: 'Мягкий сыр из коровьего молока.',
      ),
      p(
        'f6',
        's6',
        'food',
        '🥛',
        'Молоко фермерское, 1 л',
        14,
        r: 4.8,
        rv: 990,
        stock: 50,
        d: 'Пастеризованное, 3,2%.',
      ),
      // Гаджет Плюс (на проверке у админа)
      p(
        'g1',
        's7',
        'electronics',
        '📲',
        'Чехол прозрачный для смартфона',
        39,
        r: 5.0,
        rv: 0,
        d: 'Силикон, защита углов.',
      ),
      p('g2', 's7', 'electronics', '🎧', 'Наушники проводные', 59, r: 5.0, rv: 0, d: 'Микрофон и пульт.'),
      // Дисконт 24 (заблокирован)
      p('x1', 's8', 'home', '🧹', 'Швабра с отжимом', 89, old: 199, r: 3.0, rv: 41, d: 'Ведро и две насадки.'),
    ];
  }

  static List<Courier> couriers() => [
    Courier(id: 'c1', name: 'Рустам Каримов', phone: '930000001', vehicle: '🛵', online: true, rating: 4.9),
    Courier(id: 'c2', name: 'Далер Назаров', phone: '930000002', vehicle: '🚗', online: true, rating: 4.8),
    Courier(id: 'c3', name: 'Шахзод Рахимов', phone: '930000003', vehicle: '🚲', online: false, rating: 4.7),
    Courier(id: 'c4', name: 'Бехруз Юсуфов', phone: '930000004', vehicle: '🛵', online: true, rating: 4.9),
    Courier(id: 'c5', name: 'Сухроб Мирзоев', phone: '930000005', vehicle: '🚗', online: false, rating: 4.6),
  ];

  /// Заказы за последние 7 дней + несколько «живых» заказов прямо сейчас.
  static List<Order> orders({
    required List<Shop> shops,
    required List<Product> products,
    required List<Courier> couriers,
    required MarketSettings settings,
    required int Function() nextId,
  }) {
    final rnd = Random(7);
    final now = DateTime.now();
    final active = shops.where((s) => s.visible).toList();
    final list = <Order>[];

    Order make(Shop shop, DateTime at, {bool? delivery}) {
      final pool = products.where((p) => p.shopId == shop.id).toList();
      final items = <OrderItem>[];
      final n = 1 + rnd.nextInt(min(3, pool.length));
      for (final pr in (pool..shuffle(rnd)).take(n)) {
        items.add(
          OrderItem(
            productId: pr.id,
            title: pr.title,
            emoji: pr.emoji,
            price: pr.price,
            qty: 1 + (rnd.nextInt(4) == 0 ? 1 : 0),
            option: pr.options.isEmpty ? null : pr.options[rnd.nextInt(pr.options.length)],
          ),
        );
      }
      return buildOrder(
        id: nextId(),
        shop: shop,
        items: items,
        at: at,
        settings: settings,
        buyerName: kBuyerNames[rnd.nextInt(kBuyerNames.length)],
        buyerPhone: '9${rnd.nextInt(10)}${(1000000 + rnd.nextInt(8999999))}',
        address: kAddresses[rnd.nextInt(kAddresses.length)],
        delivery: delivery ?? rnd.nextInt(5) != 0,
        payment: kPayments[rnd.nextInt(kPayments.length)],
      );
    }

    String courierId() => couriers[rnd.nextInt(couriers.length)].id;

    // История: 6 прошлых дней + сегодня до текущего часа.
    for (var d = 6; d >= 0; d--) {
      final day = DateTime(now.year, now.month, now.day).subtract(Duration(days: d));
      final count = 5 + rnd.nextInt(6);
      final times = <DateTime>[
        for (var i = 0; i < count; i++) day.add(Duration(minutes: 9 * 60 + rnd.nextInt(12 * 60))),
      ]..sort();
      for (final at in times) {
        if (at.isAfter(now.subtract(const Duration(hours: 1)))) continue;
        final o = make(active[rnd.nextInt(active.length)], at);
        final cancelled = rnd.nextInt(12) == 0;
        if (cancelled) {
          o.setStatus(
            OrderStatus.cancelled,
            at: at.add(const Duration(minutes: 4)),
            note: kCancelReasons[rnd.nextInt(3)],
          );
          o.cancelReason = o.history.last.note;
        } else {
          o.setStatus(OrderStatus.accepted, at: at.add(Duration(minutes: 2 + rnd.nextInt(4))));
          o.setStatus(OrderStatus.ready, at: at.add(Duration(minutes: 12 + rnd.nextInt(10))));
          if (o.delivery) {
            o.courierId = courierId();
            o.setStatus(OrderStatus.delivering, at: at.add(Duration(minutes: 25 + rnd.nextInt(10))));
          }
          o.setStatus(OrderStatus.delivered, at: at.add(Duration(minutes: 45 + rnd.nextInt(30))));
        }
        list.add(o);
      }
    }

    // «Живые» заказы прямо сейчас — чтобы продавцу, курьеру и админу было что делать.
    Shop shop(String id) => shops.firstWhere((s) => s.id == id);
    DateTime ago(int minutes) => now.subtract(Duration(minutes: minutes));

    final a = make(shop('s1'), ago(12), delivery: true)
      ..setStatus(OrderStatus.accepted, at: ago(10))
      ..setStatus(OrderStatus.ready, at: ago(3));
    final b = make(shop('s1'), ago(7), delivery: true)..setStatus(OrderStatus.accepted, at: ago(5));
    final c = make(shop('s1'), ago(2), delivery: true);
    final d = make(shop('s1'), ago(1), delivery: false);
    final e = make(shop('s2'), ago(15), delivery: true)
      ..setStatus(OrderStatus.accepted, at: ago(13))
      ..setStatus(OrderStatus.ready, at: ago(4));
    final f = make(shop('s6'), ago(9), delivery: true)
      ..setStatus(OrderStatus.accepted, at: ago(8))
      ..setStatus(OrderStatus.ready, at: ago(2));
    final g = make(shop('s4'), ago(25), delivery: true)
      ..setStatus(OrderStatus.accepted, at: ago(23))
      ..setStatus(OrderStatus.ready, at: ago(14))
      ..courierId = 'c2'
      ..setStatus(OrderStatus.delivering, at: ago(8));
    final h = make(shop('s3'), ago(6), delivery: true)..setStatus(OrderStatus.accepted, at: ago(4));
    list.addAll([a, b, c, d, e, f, g, h]);
    return list;
  }
}

/// Создаёт заказ и считает все суммы по правилам маркетплейса.
Order buildOrder({
  required int id,
  required Shop shop,
  required List<OrderItem> items,
  required DateTime at,
  required MarketSettings settings,
  required String buyerName,
  required String buyerPhone,
  required String address,
  required bool delivery,
  required String payment,
  String comment = '',
  int discount = 0,
  bool mine = false,
}) {
  final itemsTotal = items.fold(0, (s, i) => s + i.sum);
  final fee = !delivery || itemsTotal >= settings.freeDeliveryFrom ? 0 : settings.deliveryFee;
  return Order(
    id: '$id',
    shopId: shop.id,
    createdAt: at,
    buyerName: buyerName,
    buyerPhone: buyerPhone,
    address: delivery ? address : shop.address,
    delivery: delivery,
    payment: payment,
    comment: comment,
    items: items,
    discount: discount,
    deliveryFee: fee,
    courierPay: delivery ? settings.courierPay : 0,
    commission: (itemsTotal * settings.commissionPercent / 100).round(),
    mine: mine,
  );
}
