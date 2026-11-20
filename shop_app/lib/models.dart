import 'package:material_ui/material_ui.dart';

class Category {
  const Category({required this.id, required this.name, required this.emoji, required this.tint});

  final String id;
  final String name;
  final String emoji;

  /// Два пастельных цвета для градиентного фона карточек товаров.
  final List<Color> tint;
}

class Product {
  const Product({
    required this.id,
    required this.title,
    required this.categoryId,
    required this.emoji,
    required this.price,
    this.oldPrice,
    required this.rating,
    required this.reviews,
    required this.seller,
    required this.description,
    this.optionsLabel,
    this.options = const [],
    this.hit = false,
  });

  final String id;
  final String title;
  final String categoryId;
  final String emoji;
  final int price;
  final int? oldPrice;
  final double rating;
  final int reviews;
  final String seller;
  final String description;
  final String? optionsLabel;
  final List<String> options;
  final bool hit;

  int get discount {
    final old = oldPrice;
    if (old == null || old <= price) return 0;
    return (100 - price * 100 / old).round();
  }
}

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

class OrderLine {
  const OrderLine({
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

  Map<String, dynamic> toJson() => {'id': productId, 't': title, 'e': emoji, 'p': price, 'q': qty, 'o': option};

  factory OrderLine.fromJson(Map<String, dynamic> j) => OrderLine(
    productId: j['id'] as String,
    title: j['t'] as String,
    emoji: j['e'] as String,
    price: (j['p'] as num).toInt(),
    qty: (j['q'] as num).toInt(),
    option: j['o'] as String?,
  );
}

enum OrderStatus { placed, packing, onTheWay, delivered }

extension OrderStatusX on OrderStatus {
  String get label => switch (this) {
    OrderStatus.placed => 'Оформлен',
    OrderStatus.packing => 'Собирается',
    OrderStatus.onTheWay => 'В пути',
    OrderStatus.delivered => 'Доставлен',
  };

  Color get color => switch (this) {
    OrderStatus.placed => const Color(0xFF7B2FF7),
    OrderStatus.packing => const Color(0xFFFF8A00),
    OrderStatus.onTheWay => const Color(0xFF2F80ED),
    OrderStatus.delivered => const Color(0xFF18A957),
  };
}

class Order {
  const Order({
    required this.id,
    required this.createdAt,
    required this.lines,
    required this.itemsTotal,
    required this.discount,
    required this.deliveryFee,
    required this.total,
    required this.name,
    required this.phone,
    required this.address,
    required this.courier,
    required this.payment,
    this.comment = '',
  });

  final String id;
  final DateTime createdAt;
  final List<OrderLine> lines;
  final int itemsTotal;
  final int discount;
  final int deliveryFee;
  final int total;
  final String name;
  final String phone;
  final String address;
  final bool courier;
  final String payment;
  final String comment;

  int get count => lines.fold(0, (s, l) => s + l.qty);

  /// Статус «двигается» со временем — чтобы история заказов выглядела живой.
  OrderStatus get status {
    final m = DateTime.now().difference(createdAt).inMinutes;
    if (m < 2) return OrderStatus.placed;
    if (m < 15) return OrderStatus.packing;
    if (m < 120) return OrderStatus.onTheWay;
    return OrderStatus.delivered;
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'at': createdAt.millisecondsSinceEpoch,
    'lines': lines.map((l) => l.toJson()).toList(),
    'items': itemsTotal,
    'disc': discount,
    'del': deliveryFee,
    'total': total,
    'name': name,
    'phone': phone,
    'addr': address,
    'courier': courier,
    'pay': payment,
    'comment': comment,
  };

  factory Order.fromJson(Map<String, dynamic> j) => Order(
    id: j['id'] as String,
    createdAt: DateTime.fromMillisecondsSinceEpoch((j['at'] as num).toInt()),
    lines: (j['lines'] as List).map((e) => OrderLine.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
    itemsTotal: (j['items'] as num).toInt(),
    discount: (j['disc'] as num).toInt(),
    deliveryFee: (j['del'] as num).toInt(),
    total: (j['total'] as num).toInt(),
    name: j['name'] as String,
    phone: j['phone'] as String,
    address: j['addr'] as String,
    courier: j['courier'] as bool,
    payment: j['pay'] as String,
    comment: (j['comment'] as String?) ?? '',
  );
}
