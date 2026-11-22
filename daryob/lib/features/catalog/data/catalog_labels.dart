import '../../../shared/models/category_schema.dart';
import '../../../shared/models/localized_text.dart';

/// Labels for option ids used in the catalog file.
///
/// The catalog stores options as stable ids only ("gasoline", "rent_long");
/// these are the Russian and Tajik texts shown to people. Keys are
/// field key → option id, because the same id can mean different things in
/// different fields ("day": day shift / per day / daily rent).
///
/// The parser fails loudly (see `CatalogParser`) if the catalog gains an
/// option id that has no label here, so nothing is shown as a raw id.
const Map<String, Map<String, LocalizedText>> catalogOptionLabels = {
  'fuel': {
    'gasoline': LocalizedText(ru: 'Бензин', tg: 'Бензин'),
    'gasoline_lpg': LocalizedText(ru: 'Бензин + газ', tg: 'Бензин + газ'),
    'lpg': LocalizedText(ru: 'Газ', tg: 'Газ'),
    'diesel': LocalizedText(ru: 'Дизель', tg: 'Дизел'),
    'hybrid': LocalizedText(ru: 'Гибрид', tg: 'Гибридӣ'),
    'phev': LocalizedText(ru: 'Подключаемый гибрид', tg: 'Гибриди барқгиранда'),
    'electric': LocalizedText(ru: 'Электро', tg: 'Барқӣ'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'transmission': {
    'manual': LocalizedText(ru: 'Механика', tg: 'Механикӣ'),
    'automatic': LocalizedText(ru: 'Автомат', tg: 'Автомат'),
    'cvt': LocalizedText(ru: 'Вариатор', tg: 'Вариатор'),
    'robot': LocalizedText(ru: 'Робот', tg: 'Робот'),
  },
  'drive': {
    'fwd': LocalizedText(ru: 'Передний', tg: 'Пеш'),
    'rwd': LocalizedText(ru: 'Задний', tg: 'Ақиб'),
    'awd': LocalizedText(ru: 'Полный', tg: 'Пурра'),
  },
  'body': {
    'sedan': LocalizedText(ru: 'Седан', tg: 'Седан'),
    'hatchback': LocalizedText(ru: 'Хэтчбек', tg: 'Хэтчбек'),
    'wagon': LocalizedText(ru: 'Универсал', tg: 'Универсал'),
    'suv': LocalizedText(ru: 'Внедорожник', tg: 'Роҳгузар'),
    'crossover': LocalizedText(ru: 'Кроссовер', tg: 'Кроссовер'),
    'pickup': LocalizedText(ru: 'Пикап', tg: 'Пикап'),
    'minivan': LocalizedText(ru: 'Минивэн', tg: 'Минивэн'),
    'van': LocalizedText(ru: 'Фургон', tg: 'Фургон'),
    'coupe': LocalizedText(ru: 'Купе', tg: 'Купе'),
    'liftback': LocalizedText(ru: 'Лифтбек', tg: 'Лифтбек'),
    'convertible': LocalizedText(ru: 'Кабриолет', tg: 'Кабриолет'),
    'other': LocalizedText(ru: 'Другой', tg: 'Дигар'),
  },
  'steering': {
    'left': LocalizedText(ru: 'Левый', tg: 'Чап'),
    'right': LocalizedText(ru: 'Правый', tg: 'Рост'),
  },
  'customs_status': {
    'cleared': LocalizedText(ru: 'Растаможен', tg: 'Аз боҷхона гузаштааст'),
    'not_cleared': LocalizedText(ru: 'Не растаможен', tg: 'Аз боҷхона нагузаштааст'),
    'unknown': LocalizedText(ru: 'Неизвестно', tg: 'Номаълум'),
  },
  'accident_history': _yesNoUnknown,
  'repair_history': _yesNoUnknown,
  'warranty': _yesNoUnknown,
  'vaccine_status': _yesNoUnknown,
  'condition': {
    'new': LocalizedText(ru: 'Новое', tg: 'Нав'),
    'like_new': LocalizedText(ru: 'Как новое', tg: 'Мисли нав'),
    'used': LocalizedText(ru: 'Б/у', tg: 'Истифодашуда'),
    'for_parts': LocalizedText(ru: 'На запчасти', tg: 'Барои қисмҳо'),
  },
  'contact_method': {
    'chat': LocalizedText(ru: 'Чат', tg: 'Чат'),
    'phone': LocalizedText(ru: 'Телефон', tg: 'Телефон'),
  },
  'season': {
    'summer': LocalizedText(ru: 'Летние', tg: 'Тобистона'),
    'winter': LocalizedText(ru: 'Зимние', tg: 'Зимистона'),
    'demi': LocalizedText(ru: 'Демисезонные', tg: 'Мавсимҳои гузариш'),
    'all_season': LocalizedText(ru: 'Всесезонные', tg: 'Ҳамамавсима'),
  },
  'transaction_type': {
    'sale': LocalizedText(ru: 'Продажа', tg: 'Фурӯш'),
    'rent_long': LocalizedText(ru: 'Долгосрочная аренда', tg: 'Иҷораи дарозмуддат'),
    'rent_short': LocalizedText(ru: 'Посуточно / краткосрочно', tg: 'Шабонарӯзӣ / кӯтоҳмуддат'),
  },
  'building_type': {
    'brick': LocalizedText(ru: 'Кирпичный', tg: 'Хиштӣ'),
    'panel': LocalizedText(ru: 'Панельный', tg: 'Панелӣ'),
    'monolithic': LocalizedText(ru: 'Монолитный', tg: 'Монолитӣ'),
    'other': LocalizedText(ru: 'Другой', tg: 'Дигар'),
  },
  'renovation': {
    'none': LocalizedText(ru: 'Без ремонта', tg: 'Бе таъмир'),
    'cosmetic': LocalizedText(ru: 'Косметический', tg: 'Косметикӣ'),
    'good': LocalizedText(ru: 'Хороший', tg: 'Хуб'),
    'designer': LocalizedText(ru: 'Дизайнерский', tg: 'Дизайнерӣ'),
  },
  'heating': {
    'central': LocalizedText(ru: 'Центральное', tg: 'Марказӣ'),
    'individual': LocalizedText(ru: 'Индивидуальное', tg: 'Инфиродӣ'),
    'electric': LocalizedText(ru: 'Электрическое', tg: 'Барқӣ'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'rent_period': {
    'day': LocalizedText(ru: 'Посуточно', tg: 'Шабонарӯзӣ'),
    'month': LocalizedText(ru: 'Помесячно', tg: 'Моҳона'),
  },
  'seller_role': {
    'owner': LocalizedText(ru: 'Собственник', tg: 'Соҳиб'),
    'agent': LocalizedText(ru: 'Агент', tg: 'Агент'),
    'developer': LocalizedText(ru: 'Застройщик', tg: 'Созанда'),
  },
  'documents_status': {
    'available': LocalizedText(ru: 'Есть', tg: 'Ҳаст'),
    'partial': LocalizedText(ru: 'Частично', tg: 'Қисман'),
    'not_specified': LocalizedText(ru: 'Не указано', tg: 'Нишон дода нашудааст'),
  },
  'construction_material': {
    'brick': LocalizedText(ru: 'Кирпич', tg: 'Хишт'),
    'block': LocalizedText(ru: 'Блок', tg: 'Блок'),
    'stone': LocalizedText(ru: 'Камень', tg: 'Санг'),
    'wood': LocalizedText(ru: 'Дерево', tg: 'Чӯб'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'water': {
    'central': LocalizedText(ru: 'Центральное', tg: 'Марказӣ'),
    'well': LocalizedText(ru: 'Скважина / колодец', tg: 'Чоҳ'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'plot_purpose': {
    'residential': LocalizedText(ru: 'Под жильё', tg: 'Барои манзил'),
    'agricultural': LocalizedText(ru: 'Сельхозназначения', tg: 'Барои кишоварзӣ'),
    'commercial': LocalizedText(ru: 'Коммерческое', tg: 'Тиҷоратӣ'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'utilities': {
    'water': LocalizedText(ru: 'Вода', tg: 'Об'),
    'electricity': LocalizedText(ru: 'Электричество', tg: 'Барқ'),
    'gas': LocalizedText(ru: 'Газ', tg: 'Газ'),
    'sewerage': LocalizedText(ru: 'Канализация', tg: 'Канализатсия'),
  },
  'commercial_type': {
    'office': LocalizedText(ru: 'Офис', tg: 'Офис'),
    'retail': LocalizedText(ru: 'Торговое помещение', tg: 'Ҷойи савдо'),
    'warehouse': LocalizedText(ru: 'Склад', tg: 'Анбор'),
    'industrial': LocalizedText(ru: 'Производственное', tg: 'Истеҳсолӣ'),
    'restaurant': LocalizedText(ru: 'Общепит', tg: 'Ошхона / тарабхона'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'sim_type': {
    'nano_sim': LocalizedText(ru: 'Nano-SIM', tg: 'Nano-SIM'),
    'esim': LocalizedText(ru: 'eSIM', tg: 'eSIM'),
    'other': LocalizedText(ru: 'Другая', tg: 'Дигар'),
  },
  'resolution': {
    'hd': LocalizedText(ru: 'HD', tg: 'HD'),
    'full_hd': LocalizedText(ru: 'Full HD', tg: 'Full HD'),
    '4k': LocalizedText(ru: '4K', tg: '4K'),
    '8k': LocalizedText(ru: '8K', tg: '8K'),
  },
  'listing_kind': {
    'vacancy': LocalizedText(ru: 'Вакансия', tg: 'Ҷойи холӣ'),
    'resume': LocalizedText(ru: 'Резюме', tg: 'Резюме'),
  },
  'employment': {
    'full_time': LocalizedText(ru: 'Полная', tg: 'Пурра'),
    'part_time': LocalizedText(ru: 'Частичная', tg: 'Нопурра'),
    'temporary': LocalizedText(ru: 'Временная', tg: 'Муваққатӣ'),
    'internship': LocalizedText(ru: 'Стажировка', tg: 'Таҷрибаомӯзӣ'),
    'contract': LocalizedText(ru: 'По договору', tg: 'Бо шартнома'),
  },
  'schedule': {
    'day': LocalizedText(ru: 'Дневной', tg: 'Рӯзона'),
    'shift': LocalizedText(ru: 'Сменный', tg: 'Навбатӣ'),
    'flexible': LocalizedText(ru: 'Гибкий', tg: 'Чандир'),
    'remote': LocalizedText(ru: 'Удалённо', tg: 'Фосилавӣ'),
    'hybrid': LocalizedText(ru: 'Гибрид', tg: 'Омехта'),
  },
  'salary_period': {
    'hour': LocalizedText(ru: 'В час', tg: 'Дар як соат'),
    'day': LocalizedText(ru: 'В день', tg: 'Дар як рӯз'),
    'month': LocalizedText(ru: 'В месяц', tg: 'Дар як моҳ'),
    'project': LocalizedText(ru: 'За проект', tg: 'Барои лоиҳа'),
  },
  'experience': {
    'none': LocalizedText(ru: 'Без опыта', tg: 'Бе таҷриба'),
    'lt_1': LocalizedText(ru: 'До 1 года', tg: 'То 1 сол'),
    '1_3': LocalizedText(ru: '1–3 года', tg: '1–3 сол'),
    '3_5': LocalizedText(ru: '3–5 лет', tg: '3–5 сол'),
    '5_plus': LocalizedText(ru: 'Более 5 лет', tg: 'Зиёда аз 5 сол'),
  },
  'education': {
    'any': LocalizedText(ru: 'Не важно', tg: 'Аҳамият надорад'),
    'secondary': LocalizedText(ru: 'Среднее', tg: 'Миёна'),
    'vocational': LocalizedText(ru: 'Среднее специальное', tg: 'Миёнаи касбӣ'),
    'higher': LocalizedText(ru: 'Высшее', tg: 'Олӣ'),
  },
  'item_type': {
    'clothing': LocalizedText(ru: 'Одежда', tg: 'Либос'),
    'footwear': LocalizedText(ru: 'Обувь', tg: 'Пойафзол'),
    'accessory': LocalizedText(ru: 'Аксессуар', tg: 'Лавозимот'),
  },
  'size_system': {
    'international': LocalizedText(ru: 'Международная (XS–XXL)', tg: 'Байналмилалӣ (XS–XXL)'),
    'eu': LocalizedText(ru: 'EU', tg: 'EU'),
    'uk': LocalizedText(ru: 'UK', tg: 'UK'),
    'us': LocalizedText(ru: 'US', tg: 'US'),
    'cm': LocalizedText(ru: 'Сантиметры', tg: 'Сантиметр'),
    'age_height': LocalizedText(ru: 'Возраст / рост ребёнка', tg: 'Синну сол / қади кӯдак'),
  },
  'gender_target': {
    'men': LocalizedText(ru: 'Мужчинам', tg: 'Барои мардон'),
    'women': LocalizedText(ru: 'Женщинам', tg: 'Барои занон'),
    'unisex': LocalizedText(ru: 'Унисекс', tg: 'Барои ҳама'),
    'boys': LocalizedText(ru: 'Мальчикам', tg: 'Барои писарон'),
    'girls': LocalizedText(ru: 'Девочкам', tg: 'Барои духтарон'),
  },
  'material': {
    'cotton': LocalizedText(ru: 'Хлопок', tg: 'Пахта'),
    'wool': LocalizedText(ru: 'Шерсть', tg: 'Пашм'),
    'leather': LocalizedText(ru: 'Кожа', tg: 'Чарм'),
    'synthetic': LocalizedText(ru: 'Синтетика', tg: 'Синтетикӣ'),
    'denim': LocalizedText(ru: 'Деним', tg: 'Ҷинс'),
    'mixed': LocalizedText(ru: 'Смешанный', tg: 'Омехта'),
    'wood': LocalizedText(ru: 'Дерево', tg: 'Чӯб'),
    'mdf': LocalizedText(ru: 'МДФ / ДСП', tg: 'МДФ / ДСП'),
    'metal': LocalizedText(ru: 'Металл', tg: 'Металл'),
    'glass': LocalizedText(ru: 'Стекло', tg: 'Шиша'),
    'plastic': LocalizedText(ru: 'Пластик', tg: 'Пластик'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'type': {
    'sofa': LocalizedText(ru: 'Диван', tg: 'Диван'),
    'bed': LocalizedText(ru: 'Кровать', tg: 'Кат'),
    'wardrobe': LocalizedText(ru: 'Шкаф', tg: 'Ҷевон'),
    'table': LocalizedText(ru: 'Стол', tg: 'Миз'),
    'chair': LocalizedText(ru: 'Стул / кресло', tg: 'Курсӣ'),
    'cabinet': LocalizedText(ru: 'Тумба / комод', tg: 'Ҷевонча'),
    'kitchen': LocalizedText(ru: 'Кухонный гарнитур', tg: 'Мебели ошхона'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'price_type': {
    'fixed': LocalizedText(ru: 'Фиксированная', tg: 'Собит'),
    'from': LocalizedText(ru: 'От', tg: 'Аз'),
    'hour': LocalizedText(ru: 'За час', tg: 'Барои як соат'),
    'day': LocalizedText(ru: 'За день', tg: 'Барои як рӯз'),
    'negotiable': LocalizedText(ru: 'Договорная', tg: 'Бо мувофиқа'),
  },
  'unit': {
    'piece': LocalizedText(ru: 'шт.', tg: 'дона'),
    'kg': LocalizedText(ru: 'кг', tg: 'кг'),
    'ton': LocalizedText(ru: 'т', tg: 'т'),
    'm': LocalizedText(ru: 'м', tg: 'м'),
    'm2': LocalizedText(ru: 'м²', tg: 'м²'),
    'm3': LocalizedText(ru: 'м³', tg: 'м³'),
    'bag': LocalizedText(ru: 'мешок', tg: 'халта'),
    'pack': LocalizedText(ru: 'упаковка', tg: 'баста'),
    'liter': LocalizedText(ru: 'л', tg: 'л'),
  },
  'business_ad_type': {
    'business_sale': LocalizedText(ru: 'Продажа бизнеса', tg: 'Фурӯши бизнес'),
    'equipment': LocalizedText(ru: 'Оборудование', tg: 'Таҷҳизот'),
    'commercial_inventory': LocalizedText(ru: 'Товарный запас', tg: 'Захираи мол'),
  },
  'industry': {
    'retail': LocalizedText(ru: 'Торговля', tg: 'Савдо'),
    'food': LocalizedText(ru: 'Общепит и продукты', tg: 'Хӯрок ва озуқа'),
    'manufacturing': LocalizedText(ru: 'Производство', tg: 'Истеҳсолот'),
    'service': LocalizedText(ru: 'Услуги', tg: 'Хизматрасонӣ'),
    'construction': LocalizedText(ru: 'Строительство', tg: 'Сохтмон'),
    'other': LocalizedText(ru: 'Другое', tg: 'Дигар'),
  },
  'listing_type': {
    'permitted_pet': LocalizedText(ru: 'Домашнее животное', tg: 'Ҳайвони хонагӣ'),
    'pet_supply': LocalizedText(ru: 'Товары для животных', tg: 'Молҳо барои ҳайвонот'),
    'plant': LocalizedText(ru: 'Растение', tg: 'Растанӣ'),
  },
};

const Map<String, LocalizedText> _yesNoUnknown = {
  'yes': LocalizedText(ru: 'Да', tg: 'Ҳа'),
  'no': LocalizedText(ru: 'Нет', tg: 'Не'),
  'unknown': LocalizedText(ru: 'Неизвестно', tg: 'Номаълум'),
};

/// Units of measure used by catalog fields.
const Map<String, LocalizedText> catalogUnitLabels = {
  'TJS': LocalizedText(ru: 'сомони', tg: 'сомонӣ'),
  'm2': LocalizedText(ru: 'м²', tg: 'м²'),
  'km': LocalizedText(ru: 'км', tg: 'км'),
  'l': LocalizedText(ru: 'л', tg: 'л'),
  'GB': LocalizedText(ru: 'ГБ', tg: 'ГБ'),
  '%': LocalizedText(ru: '%', tg: '%'),
  'inch': LocalizedText(ru: '″', tg: '″'),
  'sotka': LocalizedText(ru: 'сот.', tg: 'сотих'),
  'cm': LocalizedText(ru: 'см', tg: 'см'),
  'mm': LocalizedText(ru: 'мм', tg: 'мм'),
};

/// Colour choices for `color` fields. The catalog leaves the palette to the
/// app; these are plain colour names, not manufacturer colour names.
const List<FieldOption> catalogColorOptions = [
  FieldOption('white', LocalizedText(ru: 'Белый', tg: 'Сафед')),
  FieldOption('black', LocalizedText(ru: 'Чёрный', tg: 'Сиёҳ')),
  FieldOption('gray', LocalizedText(ru: 'Серый', tg: 'Хокистарӣ')),
  FieldOption('silver', LocalizedText(ru: 'Серебристый', tg: 'Нуқрагин')),
  FieldOption('red', LocalizedText(ru: 'Красный', tg: 'Сурх')),
  FieldOption('blue', LocalizedText(ru: 'Синий', tg: 'Кабуд')),
  FieldOption('light_blue', LocalizedText(ru: 'Голубой', tg: 'Осмонӣ')),
  FieldOption('green', LocalizedText(ru: 'Зелёный', tg: 'Сабз')),
  FieldOption('yellow', LocalizedText(ru: 'Жёлтый', tg: 'Зард')),
  FieldOption('orange', LocalizedText(ru: 'Оранжевый', tg: 'Норинҷӣ')),
  FieldOption('brown', LocalizedText(ru: 'Коричневый', tg: 'Қаҳвагӣ')),
  FieldOption('beige', LocalizedText(ru: 'Бежевый', tg: 'Беж')),
  FieldOption('gold', LocalizedText(ru: 'Золотистый', tg: 'Тиллоӣ')),
  FieldOption('purple', LocalizedText(ru: 'Фиолетовый', tg: 'Бунафш')),
  FieldOption('pink', LocalizedText(ru: 'Розовый', tg: 'Гулобӣ')),
  FieldOption('multicolor', LocalizedText(ru: 'Разноцветный', tg: 'Рангоранг')),
  FieldOption('other', LocalizedText(ru: 'Другой', tg: 'Дигар')),
];

/// Short category descriptions (the catalog file has names only).
const Map<String, LocalizedText> categoryDescriptions = {
  'vehicles': LocalizedText(
    ru: 'Легковые авто, мотоциклы, грузовики, спецтехника и запчасти',
    tg: 'Мошинҳои сабукрав, мотосиклҳо, мошинҳои боркаш ва қисмҳои эҳтиётӣ',
  ),
  'real-estate': LocalizedText(
    ru: 'Квартиры, дома, комнаты, участки и коммерческие помещения',
    tg: 'Хонаҳо, ҳавлиҳо, ҳуҷраҳо, қитъаҳои замин ва биноҳои тиҷоратӣ',
  ),
  'electronics': LocalizedText(
    ru: 'Смартфоны, компьютеры, телевизоры, планшеты и техника',
    tg: 'Смартфонҳо, компютерҳо, телевизорҳо, планшетҳо ва техника',
  ),
  'jobs': LocalizedText(
    ru: 'Вакансии, резюме, удалённая работа и стажировки',
    tg: 'Ҷойҳои холӣ, резюме, кори фосилавӣ ва таҷрибаомӯзӣ',
  ),
  'fashion': LocalizedText(
    ru: 'Мужская, женская и детская одежда, обувь и аксессуары',
    tg: 'Либоси мардона, занона ва кӯдакона, пойафзол ва лавозимот',
  ),
  'home-furniture': LocalizedText(
    ru: 'Мебель, освещение, ковры и декор',
    tg: 'Мебел, равшанӣ, қолинҳо ва ороиш',
  ),
  'services': LocalizedText(
    ru: 'Ремонт, перевозки, обучение, красота, IT и другие услуги',
    tg: 'Таъмир, боркашонӣ, омӯзиш, зебоӣ, IT ва дигар хизматҳо',
  ),
  'construction': LocalizedText(
    ru: 'Стройматериалы, инструменты, сантехника и электрика',
    tg: 'Масолеҳи сохтмонӣ, асбобҳо, сантехника ва барқтаҷҳизот',
  ),
  'kids': LocalizedText(
    ru: 'Коляски, автокресла, игрушки и школьные товары',
    tg: 'Аробачаҳо, курсиҳои мошин, бозичаҳо ва молҳои мактабӣ',
  ),
  'business': LocalizedText(
    ru: 'Готовый бизнес и оборудование для работы',
    tg: 'Бизнеси тайёр ва таҷҳизот барои кор',
  ),
  'sports-hobbies': LocalizedText(
    ru: 'Спорт, туризм, музыкальные инструменты и коллекции',
    tg: 'Варзиш, сайёҳӣ, асбобҳои мусиқӣ ва коллексияҳо',
  ),
  'agriculture': LocalizedText(
    ru: 'Урожай, семена, саженцы, орошение и техника',
    tg: 'Ҳосил, тухмиҳо, ниҳолҳо, обёрӣ ва техника',
  ),
  'animals-plants': LocalizedText(
    ru: 'Разрешённые домашние животные, зоотовары и растения',
    tg: 'Ҳайвоноти хонагии иҷозатшуда, молҳо барои онҳо ва растаниҳо',
  ),
  'free': LocalizedText(
    ru: 'Вещи для дома, одежда, книги и другое даром',
    tg: 'Ашёи рӯзгор, либос, китобҳо ва дигар чизҳо ройгон',
  ),
};
