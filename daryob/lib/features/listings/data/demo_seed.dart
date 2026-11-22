import '../../../core/storage/local_database.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/models/money.dart';
import '../../../shared/models/user.dart';

/// Sample data for development builds. Every record is flagged `isDemo` and
/// shown with a DEMO badge; none of it is presented as a real offer.
///
/// No photos are bundled: demo cards show the category placeholder rather
/// than stock images that could be mistaken for real goods.
class DemoSeeder {
  DemoSeeder(this._db, this._clock);

  final LocalDatabase _db;
  final DateTime Function() _clock;

  static const _seedKey = 'demo_seed_version';
  static const _version = 2;

  bool get isSeeded =>
      (_db.collection(Collections.meta).get(_seedKey)?['v'] as int?) ==
      _version;

  Future<void> seedIfNeeded() async {
    if (isSeeded) return;
    await seed();
  }

  Future<void> seed() async {
    final now = _clock();
    final users = _db.collection(Collections.users);
    for (final s in _sellers(now)) {
      await users.put(s.id, s.toJson());
    }
    final listings = _db.collection(Collections.listings);
    for (final l in _listings(now)) {
      await listings.put(l.id, l.toJson());
    }
    await _db.collection(Collections.meta).put(_seedKey, {'v': _version});
  }

  /// Removes demo records only; the user's own local data stays.
  Future<void> removeDemoData() async {
    final listings = _db.collection(Collections.listings);
    for (final json in listings.values().toList()) {
      if (json['isDemo'] == true) await listings.delete(json['id'] as String);
    }
    final users = _db.collection(Collections.users);
    for (final json in users.values().toList()) {
      if ((json['id'] as String).startsWith('demo-seller-')) {
        await users.delete(json['id'] as String);
      }
    }
    await _db.collection(Collections.meta).delete(_seedKey);
  }

  static List<AppUser> _sellers(DateTime now) => [
    AppUser(
      id: 'demo-seller-1',
      phone: '000000001',
      name: 'Демо-продавец 1',
      regionId: 'dushanbe',
      createdAt: now.subtract(const Duration(days: 420)),
      isDemo: true,
    ),
    AppUser(
      id: 'demo-seller-2',
      phone: '000000002',
      name: 'Демо-продавец 2',
      regionId: 'khujand',
      createdAt: now.subtract(const Duration(days: 150)),
      isDemo: true,
    ),
    AppUser(
      id: 'demo-seller-3',
      phone: '000000003',
      name: 'Демо-магазин',
      regionId: 'bokhtar',
      accountType: AccountType.business,
      createdAt: now.subtract(const Duration(days: 800)),
      isDemo: true,
    ),
  ];

  static List<Listing> _listings(DateTime now) {
    var n = 0;
    Listing demo({
      required String category,
      required String title,
      required String description,
      required String region,
      required String seller,
      int? price,
      bool negotiable = false,
      Map<String, Object?> attributes = const {},
      Duration age = const Duration(hours: 3),
      PromotionType? promotion,
    }) {
      n++;
      final created = now.subtract(age);
      return Listing(
        id: 'demo-$n',
        ownerId: seller,
        categoryId: category,
        title: title,
        description: description,
        price: price,
        currency: Currency.tjs,
        isNegotiable: negotiable,
        attributes: attributes,
        regionId: region,
        contact: ListingContact(
          name: 'Демо-продавец',
          phone: '00000000$n'.substring(0, 9),
          phoneVisibility: PhoneVisibility.hidden,
        ),
        status: ListingStatus.active,
        createdAt: created,
        updatedAt: created,
        publishedAt: created,
        schemaId: category,
        schemaVersion: 100,
        promotion: promotion == null
            ? null
            : ListingPromotion(
                type: promotion,
                startsAt: created,
                endsAt: now.add(const Duration(days: 3650)),
                isDevelopmentOnly: true,
              ),
        isDemo: true,
      );
    }

    // Values use catalog option ids; brands/models exist in the catalog.
    return [
      demo(
        category: 'real-estate.apartment_sale',
        title: '2-комнатная квартира, 62 м², 6 этаж',
        description: 'Демонстрационное объявление для проверки приложения. '
            'Квартира с ремонтом, рядом школа и остановка.',
        region: 'dushanbe-sino',
        seller: 'demo-seller-1',
        price: 520000,
        negotiable: true,
        attributes: const {
          'transaction_type': 'sale', 'rooms': 2, 'area_m2': 62, 'floor': 6,
          'total_floors': 9, 'building_type': 'monolithic', 'renovation': 'good',
          'balcony': true, 'seller_role': 'owner', 'documents_status': 'available',
        },
        age: const Duration(hours: 5),
        promotion: PromotionType.vip,
      ),
      demo(
        category: 'vehicles.cars',
        title: 'Toyota Camry, 2015',
        description: 'Демонстрационное объявление. Один владелец, обслуживался '
            'вовремя, торг у капота.',
        region: 'khujand',
        seller: 'demo-seller-2',
        price: 105000,
        negotiable: true,
        attributes: const {
          'make_id': 'toyota', 'model_id': 'toyota/camry', 'year': 2015,
          'mileage_km': 148000, 'fuel': 'gasoline', 'transmission': 'automatic',
          'drive': 'fwd', 'body': 'sedan', 'engine_l': 2.5, 'steering': 'left',
          'customs_status': 'cleared', 'accident_history': 'no', 'color': 'white',
          'condition': 'used',
        },
        age: const Duration(hours: 9),
        promotion: PromotionType.vip,
      ),
      demo(
        category: 'electronics.smartphones',
        title: 'iPhone 13, 128 ГБ',
        description: 'Демонстрационное объявление. Полный комплект, коробка '
            'и зарядка. Без царапин.',
        region: 'dushanbe-firdavsi',
        seller: 'demo-seller-1',
        price: 4900,
        attributes: const {
          'brand_id': 'apple', 'model_id': 'apple/iphone-13', 'storage_gb': 128,
          'color': 'black', 'battery_health_pct': 86, 'screen_damage': false,
          'box_included': true, 'charger_included': true, 'condition': 'used',
        },
        age: const Duration(minutes: 40),
        promotion: PromotionType.top,
      ),
      demo(
        category: 'jobs.vacancy',
        title: 'Требуется продавец-консультант',
        description: 'Демонстрационное объявление. График сменный, обучение '
            'на месте, знание таджикского и русского языков.',
        region: 'dushanbe-somoni',
        seller: 'demo-seller-3',
        attributes: const {
          'listing_kind': 'vacancy', 'occupation_id': 'Продавец-консультант',
          'employment': ['full_time'], 'schedule': 'shift', 'salary_min_tjs': 3000,
          'salary_max_tjs': 4000, 'salary_period': 'month', 'experience': 'none',
          'employer': 'Демо-магазин', 'education': 'any',
        },
        age: const Duration(days: 1),
      ),
      demo(
        category: 'fashion.mens_clothes',
        title: 'Зимняя куртка, размер L',
        description: 'Демонстрационное объявление. Носили один сезон, '
            'тёплая, без дефектов.',
        region: 'bokhtar',
        seller: 'demo-seller-3',
        price: 350,
        attributes: const {
          'item_type': 'clothing', 'size_system': 'international', 'size': 'L',
          'gender_target': 'men', 'material': 'synthetic', 'season': 'winter',
          'color': 'black', 'condition': 'used',
        },
        age: const Duration(days: 2),
      ),
      demo(
        category: 'home-furniture.sofas',
        title: 'Диван раскладной, новый',
        description: 'Демонстрационное объявление. Доставка по городу '
            'обсуждается отдельно.',
        region: 'kulob',
        seller: 'demo-seller-3',
        price: 4200,
        attributes: const {
          'type': 'sofa', 'width_cm': 220, 'depth_cm': 95, 'material': 'mixed',
          'delivery': true, 'condition': 'new',
        },
        age: const Duration(hours: 20),
        promotion: PromotionType.vipPlus,
      ),
      demo(
        category: 'services.repair',
        title: 'Ремонт стиральных машин на дому',
        description: 'Демонстрационное объявление. Выезд по городу, '
            'гарантия на работу.',
        region: 'khujand',
        seller: 'demo-seller-2',
        price: 100,
        attributes: const {
          'price_type': 'from', 'experience_years': 7,
          'on_site': true, 'remote': false,
        },
        age: const Duration(days: 3),
      ),
      demo(
        category: 'construction.cement',
        title: 'Цемент М400, мешок 50 кг',
        description: 'Демонстрационное объявление. Оптом и в розницу.',
        region: 'vahdat',
        seller: 'demo-seller-3',
        price: 65,
        attributes: const {
          'quantity': 1, 'unit': 'bag', 'grade': 'М400',
          'bulk_sale': true, 'delivery': true, 'condition': 'new',
        },
        age: const Duration(days: 4),
      ),
      demo(
        category: 'kids.strollers',
        title: 'Детская коляска 2 в 1',
        description: 'Демонстрационное объявление. Использовали полгода, '
            'всё работает.',
        region: 'istaravshan',
        seller: 'demo-seller-2',
        price: 1100,
        attributes: const {'age_from_months': 0, 'age_to_months': 36, 'condition': 'used'},
        age: const Duration(days: 5),
      ),
      demo(
        category: 'business.retail_equipment',
        title: 'Холодильная витрина для магазина',
        description: 'Демонстрационное объявление. Рабочее состояние, '
            'самовывоз.',
        region: 'tursunzoda',
        seller: 'demo-seller-3',
        price: 6500,
        attributes: const {'business_ad_type': 'equipment', 'industry': 'retail', 'condition': 'used'},
        age: const Duration(days: 6),
      ),
      demo(
        category: 'sports-hobbies.cycling',
        title: 'Горный велосипед, рама 19"',
        description: 'Демонстрационное объявление. Обслужен, новые тормоза.',
        region: 'dushanbe-shohmansur',
        seller: 'demo-seller-1',
        price: 1800,
        attributes: const {'size': '19"', 'condition': 'used'},
        age: const Duration(hours: 2),
      ),
      demo(
        category: 'agriculture.seedlings',
        title: 'Саженцы абрикоса',
        description: 'Демонстрационное объявление. Местные сорта, '
            'весенняя посадка.',
        region: 'isfara',
        seller: 'demo-seller-2',
        price: 25,
        attributes: const {
          'variety': 'Абрикос', 'quantity': 200,
          'unit': 'piece', 'wholesale': true,
        },
        age: const Duration(days: 1, hours: 4),
      ),
      demo(
        category: 'animals-plants.indoor_plants',
        title: 'Комнатные растения в горшках',
        description: 'Демонстрационное объявление. Разные виды, '
            'неприхотливые.',
        region: 'khorugh',
        seller: 'demo-seller-1',
        price: 40,
        attributes: const {'listing_type': 'plant', 'species': 'Комнатные растения'},
        age: const Duration(days: 2, hours: 6),
      ),
      demo(
        category: 'free.books',
        title: 'Отдам детские книги',
        description: 'Демонстрационное объявление. Около 20 книг, '
            'забрать самостоятельно.',
        region: 'panjakent',
        seller: 'demo-seller-2',
        price: 0,
        attributes: const {'condition': 'used', 'pickup': true},
        age: const Duration(hours: 11),
      ),
      demo(
        category: 'electronics.laptops',
        title: 'Ноутбук Lenovo для учёбы, 8 ГБ ОЗУ',
        description: 'Демонстрационное объявление. Батарея держит 4 часа.',
        region: 'khujand',
        seller: 'demo-seller-2',
        price: 3700,
        attributes: const {'brand_id': 'lenovo', 'ram_gb': 8, 'ssd_gb': 256, 'screen_in': 15.6, 'condition': 'used'},
        age: const Duration(days: 3, hours: 2),
      ),
      demo(
        category: 'real-estate.room_rent',
        title: 'Сдаётся комната студентам',
        description: 'Демонстрационное объявление. Оплата помесячно, '
            'коммунальные включены.',
        region: 'bokhtar',
        seller: 'demo-seller-3',
        price: 900,
        attributes: const {'rooms': 1, 'area_m2': 14, 'seller_role': 'owner'},
        age: const Duration(days: 1, hours: 9),
      ),
    ];
  }
}
