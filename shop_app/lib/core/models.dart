import 'package:material_ui/material_ui.dart';

/// Четыре приложения маркетплейса.
enum Role { buyer, seller, courier, admin }

class Category {
  const Category({required this.id, required this.name, required this.emoji, required this.tint});

  final String id;
  final String name;
  final String emoji;

  /// Два пастельных цвета для фона карточек.
  final List<Color> tint;
}

// ---------------------------------------------------------------------------
// Магазин
// ---------------------------------------------------------------------------

enum ShopStatus { pending, active, blocked }

extension ShopStatusX on ShopStatus {
  String get label => switch (this) {
    ShopStatus.pending => 'На проверке',
    ShopStatus.active => 'Работает',
    ShopStatus.blocked => 'Заблокирован',
  };

  Color get color => switch (this) {
    ShopStatus.pending => const Color(0xFFFF8A00),
    ShopStatus.active => const Color(0xFF18A957),
    ShopStatus.blocked => const Color(0xFFE5484D),
  };
}

class Shop {
  Shop({
    required this.id,
    required this.name,
    required this.emoji,
    required this.categoryId,
    required this.ownerName,
    required this.ownerPhone,
    required this.address,
    this.description = '',
    this.rating = 5.0,
    this.ratingCount = 0,
    this.isOpen = true,
    this.status = ShopStatus.active,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  final String id;
  String name;
  String emoji;
  String categoryId;
  String ownerName;
  String ownerPhone;
  String address;
  String description;
  double rating;
  int ratingCount;
  bool isOpen;
  ShopStatus status;
  final DateTime createdAt;

  /// Покупатели видят магазин, только если он одобрен админом.
  bool get visible => status == ShopStatus.active;

  /// Принимает заказы прямо сейчас.
  bool get acceptsOrders => visible && isOpen;

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'emoji': emoji,
    'cat': categoryId,
    'owner': ownerName,
    'phone': ownerPhone,
    'addr': address,
    'desc': description,
    'rating': rating,
    'rc': ratingCount,
    'open': isOpen,
    'status': status.name,
    'at': createdAt.millisecondsSinceEpoch,
  };

  factory Shop.fromJson(Map<String, dynamic> j) => Shop(
    id: j['id'] as String,
    name: j['name'] as String,
    emoji: j['emoji'] as String,
    categoryId: j['cat'] as String,
    ownerName: j['owner'] as String,
    ownerPhone: j['phone'] as String,
    address: j['addr'] as String,
    description: (j['desc'] as String?) ?? '',
    rating: (j['rating'] as num).toDouble(),
    ratingCount: (j['rc'] as num).toInt(),
    isOpen: j['open'] as bool,
    status: ShopStatus.values.byName(j['status'] as String),
    createdAt: DateTime.fromMillisecondsSinceEpoch((j['at'] as num).toInt()),
  );
}

// ---------------------------------------------------------------------------
// Товар
// ---------------------------------------------------------------------------

class Product {
  Product({
    required this.id,
    required this.shopId,
    required this.title,
    required this.categoryId,
    required this.emoji,
    required this.price,
    this.oldPrice,
    this.stock = 20,
    this.rating = 5.0,
    this.reviews = 0,
    this.description = '',
    this.optionsLabel,
    this.options = const [],
    this.hit = false,
    this.active = true,
    this.hiddenByAdmin = false,
  });

  final String id;
  final String shopId;
  String title;
  String categoryId;
  String emoji;
  int price;
  int? oldPrice;
  int stock;
  double rating;
  int reviews;
  String description;
  String? optionsLabel;
  List<String> options;
  bool hit;

  /// Продавец может временно снять товар с продажи.
  bool active;

  /// Админ может скрыть товар (например, за нарушение правил).
  bool hiddenByAdmin;

  bool get inStock => stock > 0;

  int get discount {
    final old = oldPrice;
    if (old == null || old <= price) return 0;
    return (100 - price * 100 / old).round();
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'shop': shopId,
    't': title,
    'cat': categoryId,
    'e': emoji,
    'p': price,
    'op': oldPrice,
    'st': stock,
    'r': rating,
    'rv': reviews,
    'd': description,
    'ol': optionsLabel,
    'o': options,
    'hit': hit,
    'a': active,
    'h': hiddenByAdmin,
  };

  factory Product.fromJson(Map<String, dynamic> j) => Product(
    id: j['id'] as String,
    shopId: j['shop'] as String,
    title: j['t'] as String,
    categoryId: j['cat'] as String,
    emoji: j['e'] as String,
    price: (j['p'] as num).toInt(),
    oldPrice: (j['op'] as num?)?.toInt(),
    stock: (j['st'] as num).toInt(),
    rating: (j['r'] as num).toDouble(),
    reviews: (j['rv'] as num).toInt(),
    description: (j['d'] as String?) ?? '',
    optionsLabel: j['ol'] as String?,
    options: [for (final o in (j['o'] as List? ?? const [])) o as String],
    hit: (j['hit'] as bool?) ?? false,
    active: (j['a'] as bool?) ?? true,
    hiddenByAdmin: (j['h'] as bool?) ?? false,
  );
}

// ---------------------------------------------------------------------------
// Корзина покупателя
// ---------------------------------------------------------------------------

class CartItem {
  CartItem({required this.productId, this.option, this.qty = 1});

  final String productId;
  final String? option;
  int qty;

  String get key => '$productId|${option ?? ''}';

  Map<String, dynamic> toJson() => {'p': productId, 'o': option, 'q': qty};

  factory CartItem.fromJson(Map<String, dynamic> j) =>
      CartItem(productId: j['p'] as String, option: j['o'] as String?, qty: (j['q'] as num).toInt());
}

// ---------------------------------------------------------------------------
// Заказ
// ---------------------------------------------------------------------------

enum OrderStatus { placed, accepted, ready, delivering, delivered, cancelled }

extension OrderStatusX on OrderStatus {
  String label({bool delivery = true}) => switch (this) {
    OrderStatus.placed => 'Новый',
    OrderStatus.accepted => 'Собирается',
    OrderStatus.ready => delivery ? 'Ждёт курьера' : 'Готов к выдаче',
    OrderStatus.delivering => 'В пути',
    OrderStatus.delivered => delivery ? 'Доставлен' : 'Выдан',
    OrderStatus.cancelled => 'Отменён',
  };

  Color get color => switch (this) {
    OrderStatus.placed => const Color(0xFF7B2FF7),
    OrderStatus.accepted => const Color(0xFFFF8A00),
    OrderStatus.ready => const Color(0xFF0EA5B7),
    OrderStatus.delivering => const Color(0xFF2F80ED),
    OrderStatus.delivered => const Color(0xFF18A957),
    OrderStatus.cancelled => const Color(0xFFE5484D),
  };

  IconData get icon => switch (this) {
    OrderStatus.placed => Icons.receipt_long_rounded,
    OrderStatus.accepted => Icons.inventory_2_outlined,
    OrderStatus.ready => Icons.storefront_outlined,
    OrderStatus.delivering => Icons.delivery_dining_rounded,
    OrderStatus.delivered => Icons.check_circle_outline_rounded,
    OrderStatus.cancelled => Icons.cancel_outlined,
  };

  bool get isFinal => this == OrderStatus.delivered || this == OrderStatus.cancelled;

  bool get isActive => !isFinal;
}

class OrderItem {
  const OrderItem({
    required this.productId,
    required this.title,
    required this.emoji,
    required this.price,
    required this.qty,
    this.option,
  });

  final String productId;
  final String title;
  final String emoji;
  final int price;
  final int qty;
  final String? option;

  int get sum => price * qty;

  Map<String, dynamic> toJson() => {'id': productId, 't': title, 'e': emoji, 'p': price, 'q': qty, 'o': option};

  factory OrderItem.fromJson(Map<String, dynamic> j) => OrderItem(
    productId: j['id'] as String,
    title: j['t'] as String,
    emoji: j['e'] as String,
    price: (j['p'] as num).toInt(),
    qty: (j['q'] as num).toInt(),
    option: j['o'] as String?,
  );
}

class StatusEvent {
  const StatusEvent(this.status, this.at, [this.note]);

  final OrderStatus status;
  final DateTime at;
  final String? note;

  Map<String, dynamic> toJson() => {'s': status.name, 'at': at.millisecondsSinceEpoch, 'n': note};

  factory StatusEvent.fromJson(Map<String, dynamic> j) => StatusEvent(
    OrderStatus.values.byName(j['s'] as String),
    DateTime.fromMillisecondsSinceEpoch((j['at'] as num).toInt()),
    j['n'] as String?,
  );
}

class Order {
  Order({
    required this.id,
    required this.shopId,
    required this.createdAt,
    required this.buyerName,
    required this.buyerPhone,
    required this.address,
    required this.delivery,
    required this.payment,
    required this.items,
    required this.discount,
    required this.deliveryFee,
    required this.courierPay,
    required this.commission,
    this.comment = '',
    this.status = OrderStatus.placed,
    this.courierId,
    this.cancelReason,
    this.mine = false,
    List<StatusEvent>? history,
  }) : history = history ?? [StatusEvent(OrderStatus.placed, createdAt)];

  final String id;
  final String shopId;
  final DateTime createdAt;
  final String buyerName;
  final String buyerPhone;
  final String address;

  /// true — доставка курьером, false — самовывоз из магазина.
  final bool delivery;
  final String payment;
  final String comment;
  final List<OrderItem> items;
  final int discount;
  final int deliveryFee;

  /// Сколько получит курьер за доставку.
  final int courierPay;

  /// Комиссия маркетплейса с этого заказа.
  final int commission;

  OrderStatus status;
  String? courierId;
  String? cancelReason;

  /// Заказ оформлен покупателем на этом телефоне.
  final bool mine;
  final List<StatusEvent> history;

  int get itemsTotal => items.fold(0, (s, i) => s + i.sum);

  int get total => itemsTotal - discount + deliveryFee;

  int get count => items.fold(0, (s, i) => s + i.qty);

  DateTime get updatedAt => history.last.at;

  String get statusLabel => status.label(delivery: delivery);

  void setStatus(OrderStatus s, {String? note, DateTime? at}) {
    status = s;
    history.add(StatusEvent(s, at ?? DateTime.now(), note));
  }

  DateTime? timeOf(OrderStatus s) {
    for (final e in history.reversed) {
      if (e.status == s) return e.at;
    }
    return null;
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'shop': shopId,
    'at': createdAt.millisecondsSinceEpoch,
    'bn': buyerName,
    'bp': buyerPhone,
    'addr': address,
    'del': delivery,
    'pay': payment,
    'cm': comment,
    'items': [for (final i in items) i.toJson()],
    'disc': discount,
    'fee': deliveryFee,
    'cp': courierPay,
    'com': commission,
    'st': status.name,
    'cr': courierId,
    'cr_reason': cancelReason,
    'mine': mine,
    'h': [for (final e in history) e.toJson()],
  };

  factory Order.fromJson(Map<String, dynamic> j) => Order(
    id: j['id'] as String,
    shopId: j['shop'] as String,
    createdAt: DateTime.fromMillisecondsSinceEpoch((j['at'] as num).toInt()),
    buyerName: j['bn'] as String,
    buyerPhone: j['bp'] as String,
    address: j['addr'] as String,
    delivery: j['del'] as bool,
    payment: j['pay'] as String,
    comment: (j['cm'] as String?) ?? '',
    items: [for (final i in j['items'] as List) OrderItem.fromJson(Map<String, dynamic>.from(i as Map))],
    discount: (j['disc'] as num).toInt(),
    deliveryFee: (j['fee'] as num).toInt(),
    courierPay: (j['cp'] as num).toInt(),
    commission: (j['com'] as num).toInt(),
    status: OrderStatus.values.byName(j['st'] as String),
    courierId: j['cr'] as String?,
    cancelReason: j['cr_reason'] as String?,
    mine: (j['mine'] as bool?) ?? false,
    history: [for (final e in j['h'] as List) StatusEvent.fromJson(Map<String, dynamic>.from(e as Map))],
  );
}

// ---------------------------------------------------------------------------
// Курьер
// ---------------------------------------------------------------------------

class Courier {
  Courier({
    required this.id,
    required this.name,
    required this.phone,
    this.vehicle = '🛵',
    this.online = false,
    this.rating = 5.0,
    this.blocked = false,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  final String id;
  String name;
  String phone;
  String vehicle;
  bool online;
  double rating;
  bool blocked;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'phone': phone,
    'v': vehicle,
    'on': online,
    'r': rating,
    'b': blocked,
    'at': createdAt.millisecondsSinceEpoch,
  };

  factory Courier.fromJson(Map<String, dynamic> j) => Courier(
    id: j['id'] as String,
    name: j['name'] as String,
    phone: j['phone'] as String,
    vehicle: j['v'] as String,
    online: j['on'] as bool,
    rating: (j['r'] as num).toDouble(),
    blocked: j['b'] as bool,
    createdAt: DateTime.fromMillisecondsSinceEpoch((j['at'] as num).toInt()),
  );
}

// ---------------------------------------------------------------------------
// Настройки маркетплейса (меняет админ)
// ---------------------------------------------------------------------------

class MarketSettings {
  MarketSettings({
    this.deliveryFee = 10,
    this.freeDeliveryFrom = 200,
    this.commissionPercent = 10,
    this.courierPay = 8,
  });

  int deliveryFee;
  int freeDeliveryFrom;
  int commissionPercent;
  int courierPay;

  Map<String, dynamic> toJson() => {
    'fee': deliveryFee,
    'free': freeDeliveryFrom,
    'com': commissionPercent,
    'cp': courierPay,
  };

  factory MarketSettings.fromJson(Map<String, dynamic> j) => MarketSettings(
    deliveryFee: (j['fee'] as num).toInt(),
    freeDeliveryFrom: (j['free'] as num).toInt(),
    commissionPercent: (j['com'] as num).toInt(),
    courierPay: (j['cp'] as num).toInt(),
  );
}

// ---------------------------------------------------------------------------
// Вошедший пользователь
// ---------------------------------------------------------------------------

class AppUser {
  AppUser({required this.phone, this.name = ''});

  final String phone;
  String name;

  Map<String, dynamic> toJson() => {'phone': phone, 'name': name};

  factory AppUser.fromJson(Map<String, dynamic> j) =>
      AppUser(phone: j['phone'] as String, name: (j['name'] as String?) ?? '');
}

class Promo {
  const Promo(this.code, this.title, {this.percent = 0, this.fixed = 0});

  final String code;
  final String title;
  final int percent;
  final int fixed;
}
