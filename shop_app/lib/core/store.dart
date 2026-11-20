import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'demo_data.dart';
import 'models.dart';

/// Все данные маркетплейса и все действия над ними.
///
/// Сейчас данные хранятся на телефоне (демо-режим), а действия «других сторон»
/// (продавца, курьера, покупателей) изображает [_simulate]. Когда подключим сервер,
/// этот класс будет читать и писать те же сущности в базу — экраны менять не придётся.
class MarketStore extends ChangeNotifier {
  MarketStore(this.role, {this.persist = true, this.simulate = true});

  final Role role;
  final bool persist;
  final bool simulate;

  SharedPreferences? _prefs;
  Timer? _timer;
  final _rnd = Random();

  String get _key => 'market_v2_${role.name}';

  List<Shop> shops = [];
  List<Product> products = [];
  List<Order> orders = [];
  List<Courier> couriers = [];
  MarketSettings settings = MarketSettings();
  int _nextOrderId = 100245;

  // Сессия и настройки этого телефона
  AppUser? user;
  ThemeMode themeMode = ThemeMode.light;

  /// Демо: «оживлять» данные — новые заказы и смена статусов сами по себе.
  bool demoLive = true;

  // Покупатель
  final Set<String> favorites = <String>{};
  final List<CartItem> cart = [];
  Promo? promo;
  String savedAddress = '';

  // ---------------------------------------------------------------------------
  // Загрузка и сохранение
  // ---------------------------------------------------------------------------

  Future<void> load() async {
    if (persist) {
      try {
        _prefs = await SharedPreferences.getInstance();
      } catch (_) {}
    }
    final raw = _prefs?.getString(_key);
    var ok = false;
    if (raw != null) {
      try {
        _fromJson(Map<String, dynamic>.from(jsonDecode(raw) as Map));
        ok = true;
      } catch (_) {}
    }
    if (!ok) _seed();
    if (simulate) {
      _timer = Timer.periodic(const Duration(seconds: 4), (_) => _simulate());
    }
  }

  void _seed() {
    shops = DemoData.shops();
    products = DemoData.products();
    couriers = DemoData.couriers();
    settings = MarketSettings();
    _nextOrderId = 100245;
    orders = DemoData.orders(
      shops: shops,
      products: products,
      couriers: couriers,
      settings: settings,
      nextId: () => _nextOrderId++,
    );
  }

  /// Сброс демо-данных к начальному состоянию (вход и тема сохраняются).
  void resetDemo() {
    _seed();
    cart.clear();
    favorites.clear();
    promo = null;
    _changed();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Map<String, dynamic> _toJson() => {
    'shops': [for (final s in shops) s.toJson()],
    'products': [for (final p in products) p.toJson()],
    'orders': [for (final o in orders) o.toJson()],
    'couriers': [for (final c in couriers) c.toJson()],
    'settings': settings.toJson(),
    'next': _nextOrderId,
    'user': user?.toJson(),
    'theme': themeMode.index,
    'live': demoLive,
    'fav': favorites.toList(),
    'cart': [for (final c in cart) c.toJson()],
    'promo': promo?.code,
    'addr': savedAddress,
  };

  void _fromJson(Map<String, dynamic> j) {
    Map<String, dynamic> m(Object? o) => Map<String, dynamic>.from(o! as Map);
    shops = [for (final s in j['shops'] as List) Shop.fromJson(m(s))];
    products = [for (final p in j['products'] as List) Product.fromJson(m(p))];
    orders = [for (final o in j['orders'] as List) Order.fromJson(m(o))];
    couriers = [for (final c in j['couriers'] as List) Courier.fromJson(m(c))];
    settings = MarketSettings.fromJson(m(j['settings']));
    _nextOrderId = (j['next'] as num).toInt();
    user = j['user'] == null ? null : AppUser.fromJson(m(j['user']));
    themeMode = ThemeMode.values[((j['theme'] as num?)?.toInt() ?? 1).clamp(0, 2)];
    demoLive = (j['live'] as bool?) ?? true;
    favorites
      ..clear()
      ..addAll([for (final f in (j['fav'] as List? ?? const [])) f as String]);
    cart
      ..clear()
      ..addAll([
        for (final c in (j['cart'] as List? ?? const []))
          if (productById(m(c)['p'] as String) != null) CartItem.fromJson(m(c)),
      ]);
    promo = kPromos.where((p) => p.code == j['promo']).firstOrNull;
    savedAddress = (j['addr'] as String?) ?? '';
  }

  void _changed() {
    if (_prefs != null) _prefs!.setString(_key, jsonEncode(_toJson()));
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Поиск
  // ---------------------------------------------------------------------------

  Shop? shopById(String id) => shops.where((s) => s.id == id).firstOrNull;

  Product? productById(String id) => products.where((p) => p.id == id).firstOrNull;

  Courier? courierById(String? id) => id == null ? null : couriers.where((c) => c.id == id).firstOrNull;

  Order? orderById(String id) => orders.where((o) => o.id == id).firstOrNull;

  /// Товар виден покупателям: магазин работает, товар в продаже и не скрыт админом.
  bool isVisible(Product p) => p.active && !p.hiddenByAdmin && (shopById(p.shopId)?.visible ?? false);

  List<Product> get catalog => products.where(isVisible).toList();

  List<Shop> get visibleShops => shops.where((s) => s.visible).toList();

  List<Product> productsOf(String shopId) => products.where((p) => p.shopId == shopId).toList();

  List<Order> ordersOf(String shopId) => orders.where((o) => o.shopId == shopId).toList();

  /// Заказы от новых к старым.
  List<Order> sorted(Iterable<Order> list) => list.toList()..sort((a, b) => b.createdAt.compareTo(a.createdAt));

  int revenueOf(Iterable<Order> list) =>
      list.where((o) => o.status == OrderStatus.delivered).fold(0, (s, o) => s + o.total);

  // ---------------------------------------------------------------------------
  // Вход по телефону (демо: код показывается на экране вместо SMS)
  // ---------------------------------------------------------------------------

  String? _pendingCode;
  String? _pendingPhone;

  /// Отправляет SMS с кодом. В демо-режиме возвращает код, чтобы показать его на экране.
  String requestCode(String phone) {
    _pendingPhone = phone;
    _pendingCode = '${1000 + _rnd.nextInt(9000)}';
    return _pendingCode!;
  }

  bool verifyCode(String phone, String code) {
    if (phone != _pendingPhone || code != _pendingCode) return false;
    user = AppUser(phone: phone, name: _nameFor(phone));
    _pendingCode = null;
    _changed();
    return true;
  }

  String _nameFor(String phone) {
    final shop = shops.where((s) => s.ownerPhone == phone).firstOrNull;
    if (shop != null) return shop.ownerName;
    final courier = couriers.where((c) => c.phone == phone).firstOrNull;
    if (courier != null) return courier.name;
    return '';
  }

  void logout() {
    user = null;
    _changed();
  }

  void setUserName(String name) {
    user?.name = name;
    _changed();
  }

  // ---------------------------------------------------------------------------
  // Настройки телефона
  // ---------------------------------------------------------------------------

  void setThemeMode(ThemeMode mode) {
    themeMode = mode;
    _changed();
  }

  void setDemoLive(bool value) {
    demoLive = value;
    _changed();
  }

  // ---------------------------------------------------------------------------
  // ПОКУПАТЕЛЬ
  // ---------------------------------------------------------------------------

  bool isFavorite(String id) => favorites.contains(id);

  void toggleFavorite(String id) {
    if (!favorites.remove(id)) favorites.add(id);
    _changed();
  }

  List<Product> get favoriteProducts => catalog.where((p) => favorites.contains(p.id)).toList();

  int get cartCount => cart.fold(0, (s, i) => s + i.qty);

  Product productOf(CartItem item) => productById(item.productId)!;

  void addToCart(Product product, {String? option, int qty = 1}) {
    final key = '${product.id}|${option ?? ''}';
    final existing = cart.where((i) => i.key == key).firstOrNull;
    final limit = max(1, product.stock);
    if (existing != null) {
      existing.qty = min(limit, existing.qty + qty);
    } else {
      cart.add(CartItem(productId: product.id, option: option, qty: min(limit, qty)));
    }
    _changed();
  }

  void setQty(CartItem item, int qty) {
    item.qty = qty.clamp(1, max(1, productOf(item).stock));
    _changed();
  }

  int removeFromCart(CartItem item) {
    final index = cart.indexOf(item);
    if (index >= 0) cart.removeAt(index);
    _changed();
    return index;
  }

  void restoreCartItem(int index, CartItem item) {
    cart.insert(index.clamp(0, cart.length), item);
    _changed();
  }

  void clearCart() {
    cart.clear();
    _changed();
  }

  /// Позиции корзины, сгруппированные по магазинам (каждый магазин — отдельный заказ).
  Map<Shop, List<CartItem>> get cartByShop {
    final map = <Shop, List<CartItem>>{};
    for (final i in cart) {
      final shop = shopById(productOf(i).shopId);
      if (shop != null) (map[shop] ??= []).add(i);
    }
    return map;
  }

  /// Есть товары, которые сейчас нельзя купить (магазин закрыт, товар закончился и т.п.).
  List<CartItem> get unavailableInCart => [
    for (final i in cart)
      if (!isVisible(productOf(i)) || !productOf(i).inStock || !(shopById(productOf(i).shopId)?.isOpen ?? false)) i,
  ];

  int get itemsTotal => cart.fold(0, (s, i) => s + productOf(i).price * i.qty);

  int get itemsOldTotal => cart.fold(0, (s, i) => s + (productOf(i).oldPrice ?? productOf(i).price) * i.qty);

  int get productDiscount => itemsOldTotal - itemsTotal;

  int get promoDiscount {
    final pr = promo;
    if (pr == null || cart.isEmpty) return 0;
    if (pr.percent > 0) return (itemsTotal * pr.percent / 100).round();
    return min(pr.fixed, itemsTotal);
  }

  int deliveryFeeFor(int itemsSum) => itemsSum >= settings.freeDeliveryFrom ? 0 : settings.deliveryFee;

  /// Доставка считается для каждого магазина отдельно.
  int cartDeliveryFee({required bool courier}) {
    if (!courier) return 0;
    return cartByShop.values.fold(
      0,
      (s, items) => s + deliveryFeeFor(items.fold(0, (a, i) => a + productOf(i).price * i.qty)),
    );
  }

  int cartTotal({bool courier = false}) => itemsTotal - promoDiscount + cartDeliveryFee(courier: courier);

  String? applyPromo(String code) {
    if (code.trim().isEmpty) return 'Введите промокод';
    final found = kPromos.where((p) => p.code == code.trim().toUpperCase()).firstOrNull;
    if (found == null) return 'Такого промокода нет';
    promo = found;
    _changed();
    return null;
  }

  void removePromo() {
    promo = null;
    _changed();
  }

  List<Order> get myOrders => sorted(orders.where((o) => o.mine));

  /// Оформляет корзину: по одному заказу на каждый магазин.
  List<Order> placeOrders({
    required String name,
    required String phone,
    required String address,
    required bool courier,
    required String payment,
    String comment = '',
  }) {
    final now = DateTime.now();
    final total = itemsTotal;
    final promoTotal = promoDiscount;
    final created = <Order>[];
    for (final entry in cartByShop.entries) {
      final items = [
        for (final i in entry.value)
          OrderItem(
            productId: i.productId,
            title: productOf(i).title,
            image: productOf(i).image,
            price: productOf(i).price,
            qty: i.qty,
            option: i.option,
          ),
      ];
      final sum = items.fold(0, (s, i) => s + i.sum);
      final share = total == 0 ? 0 : (promoTotal * sum / total).round();
      final order = buildOrder(
        id: _nextOrderId++,
        shop: entry.key,
        items: items,
        at: now,
        settings: settings,
        buyerName: name,
        buyerPhone: phone,
        address: address,
        delivery: courier,
        payment: payment,
        comment: comment,
        discount: share,
        mine: true,
      );
      orders.add(order);
      created.add(order);
      for (final i in entry.value) {
        final p = productOf(i);
        p.stock = max(0, p.stock - i.qty);
      }
    }
    user?.name = name;
    if (courier) savedAddress = address;
    cart.clear();
    promo = null;
    _changed();
    return created;
  }

  void cancelMyOrder(Order order) {
    if (order.status != OrderStatus.placed) return;
    order.cancelReason = 'Покупатель отменил заказ';
    order.setStatus(OrderStatus.cancelled, note: order.cancelReason);
    _returnStock(order);
    _changed();
  }

  // ---------------------------------------------------------------------------
  // ПРОДАВЕЦ
  // ---------------------------------------------------------------------------

  /// Магазин вошедшего продавца.
  Shop? get myShop => user == null ? null : shops.where((s) => s.ownerPhone == user!.phone).firstOrNull;

  Shop createShop({
    required String name,
    required String ownerName,
    required String logo,
    required String categoryId,
    required String address,
    String description = '',
  }) {
    final shop = Shop(
      id: 's${DateTime.now().millisecondsSinceEpoch}',
      name: name,
      logo: logo,
      categoryId: categoryId,
      ownerName: ownerName,
      ownerPhone: user!.phone,
      address: address,
      description: description,
      ratingCount: 0,
      // В демо магазин сразу одобрен, на сервере его сначала проверит админ.
      status: ShopStatus.active,
    );
    shops.add(shop);
    user!.name = ownerName;
    _changed();
    return shop;
  }

  void updateShop(Shop shop) => _changed();

  void setShopOpen(Shop shop, bool open) {
    shop.isOpen = open;
    _changed();
  }

  void acceptOrder(Order o) {
    if (o.status != OrderStatus.placed) return;
    o.setStatus(OrderStatus.accepted);
    _changed();
  }

  void markReady(Order o) {
    if (o.status != OrderStatus.accepted) return;
    o.setStatus(OrderStatus.ready);
    _changed();
  }

  /// Самовывоз: покупатель забрал заказ в магазине.
  void markHandedOver(Order o) {
    if (o.status != OrderStatus.ready || o.delivery) return;
    o.setStatus(OrderStatus.delivered);
    _changed();
  }

  void cancelOrder(Order o, String reason) {
    if (o.status.isFinal) return;
    o.cancelReason = reason;
    o.setStatus(OrderStatus.cancelled, note: reason);
    _returnStock(o);
    _changed();
  }

  void _returnStock(Order o) {
    for (final i in o.items) {
      productById(i.productId)?.stock += i.qty;
    }
  }

  Product saveProduct(Product p) {
    if (!products.contains(p)) products.add(p);
    _changed();
    return p;
  }

  String newProductId() => 'p${DateTime.now().millisecondsSinceEpoch}';

  void deleteProduct(Product p) {
    products.remove(p);
    favorites.remove(p.id);
    cart.removeWhere((i) => i.productId == p.id);
    _changed();
  }

  void setProductActive(Product p, bool active) {
    p.active = active;
    _changed();
  }

  // ---------------------------------------------------------------------------
  // КУРЬЕР
  // ---------------------------------------------------------------------------

  Courier? get me => user == null ? null : couriers.where((c) => c.phone == user!.phone).firstOrNull;

  Courier registerCourier({required String name, required String vehicle}) {
    final c = Courier(
      id: 'c${DateTime.now().millisecondsSinceEpoch}',
      name: name,
      phone: user!.phone,
      vehicle: vehicle,
    );
    couriers.add(c);
    user!.name = name;
    _changed();
    return c;
  }

  void setOnline(bool online) {
    me?.online = online;
    _changed();
  }

  /// Заказы, которые можно взять: доставка, ещё без курьера, магазин собирает или уже собрал.
  List<Order> get availableDeliveries => sorted(
    orders.where(
      (o) => o.delivery && o.courierId == null && (o.status == OrderStatus.accepted || o.status == OrderStatus.ready),
    ),
  );

  Order? get myActiveDelivery {
    final id = me?.id;
    if (id == null) return null;
    return orders.where((o) => o.courierId == id && o.status.isActive).firstOrNull;
  }

  List<Order> get myDeliveries =>
      sorted(orders.where((o) => o.courierId == me?.id && o.status == OrderStatus.delivered));

  bool takeOrder(Order o) {
    final c = me;
    if (c == null || o.courierId != null || myActiveDelivery != null) return false;
    o.courierId = c.id;
    o.history.add(StatusEvent(o.status, DateTime.now(), 'Курьер ${c.name} принял заказ'));
    _changed();
    return true;
  }

  void pickUp(Order o) {
    if (o.status != OrderStatus.ready) return;
    o.setStatus(OrderStatus.delivering);
    _changed();
  }

  void deliver(Order o) {
    if (o.status != OrderStatus.delivering) return;
    o.setStatus(OrderStatus.delivered);
    _changed();
  }

  void releaseOrder(Order o) {
    if (o.status == OrderStatus.delivering) return;
    o.courierId = null;
    o.history.add(StatusEvent(o.status, DateTime.now(), 'Курьер отказался от заказа'));
    _changed();
  }

  // ---------------------------------------------------------------------------
  // АДМИН
  // ---------------------------------------------------------------------------

  void setShopStatus(Shop s, ShopStatus status) {
    s.status = status;
    _changed();
  }

  void setCourierBlocked(Courier c, bool blocked) {
    c.blocked = blocked;
    if (blocked) c.online = false;
    _changed();
  }

  void setProductHidden(Product p, bool hidden) {
    p.hiddenByAdmin = hidden;
    _changed();
  }

  void assignCourier(Order o, Courier c) {
    o.courierId = c.id;
    o.history.add(StatusEvent(o.status, DateTime.now(), 'Админ назначил курьера ${c.name}'));
    _changed();
  }

  void saveSettings() => _changed();

  // ---------------------------------------------------------------------------
  // Демо: изображаем действия других участников
  // ---------------------------------------------------------------------------

  DateTime _lastSpawn = DateTime.now();

  void _simulate() {
    if (!demoLive) return;
    final now = DateTime.now();
    var changed = false;
    final myShopId = role == Role.seller ? myShop?.id : null;
    final myCourierId = role == Role.courier ? me?.id : null;

    bool after(Order o, int seconds) => now.difference(o.updatedAt).inSeconds >= seconds;

    for (final o in orders) {
      if (o.status.isFinal) continue;
      // В приложении покупателя «оживляем» только его заказы.
      if (role == Role.buyer && !o.mine) continue;
      final sellerIsMe = o.shopId == myShopId;
      final courierIsMe = o.courierId != null && o.courierId == myCourierId;

      switch (o.status) {
        case OrderStatus.placed:
          if (!sellerIsMe && after(o, 15)) {
            o.setStatus(OrderStatus.accepted);
            changed = true;
          }
        case OrderStatus.accepted:
          if (!sellerIsMe && after(o, 30)) {
            o.setStatus(OrderStatus.ready);
            changed = true;
          }
        case OrderStatus.ready:
          if (!o.delivery) {
            if (!sellerIsMe && after(o, 60)) {
              o.setStatus(OrderStatus.delivered);
              changed = true;
            }
          } else if (o.courierId == null) {
            // В приложении курьера даём время взять заказ самому.
            if (after(o, role == Role.courier ? 150 : 12)) {
              final free = couriers.where((c) => c.online && !c.blocked && c.id != myCourierId).toList();
              if (free.isNotEmpty) {
                final c = free[_rnd.nextInt(free.length)];
                o.courierId = c.id;
                o.history.add(StatusEvent(o.status, now, 'Курьер ${c.name} принял заказ'));
                changed = true;
              }
            }
          } else if (!courierIsMe && after(o, 15)) {
            o.setStatus(OrderStatus.delivering);
            changed = true;
          }
        case OrderStatus.delivering:
          if (!courierIsMe && after(o, 40)) {
            o.setStatus(OrderStatus.delivered);
            changed = true;
          }
        case OrderStatus.delivered:
        case OrderStatus.cancelled:
          break;
      }
    }

    // Новые заказы от «покупателей».
    final spawnEvery = switch (role) {
      Role.buyer => 0,
      Role.seller => 45,
      Role.courier => 35,
      Role.admin => 30,
    };
    if (spawnEvery > 0 && now.difference(_lastSpawn).inSeconds >= spawnEvery) {
      _lastSpawn = now;
      final candidates = role == Role.seller
          ? [if (myShop != null && myShop!.acceptsOrders) myShop!]
          : shops.where((s) => s.acceptsOrders).toList();
      if (candidates.isNotEmpty) {
        final shop = candidates[_rnd.nextInt(candidates.length)];
        final o = _randomOrder(shop, delivery: role == Role.courier ? true : _rnd.nextInt(5) != 0);
        if (o != null) {
          // Курьеру сразу показываем уже принятые магазином заказы.
          if (role == Role.courier) o.setStatus(OrderStatus.accepted);
          orders.add(o);
          changed = true;
        }
      }
    }

    // Не даём списку бесконечно расти.
    if (orders.length > 500) {
      orders.sort((a, b) => a.createdAt.compareTo(b.createdAt));
      orders.removeRange(0, orders.length - 450);
    }

    if (changed) _changed();
  }

  Order? _randomOrder(Shop shop, {required bool delivery}) {
    final pool = products.where((p) => p.shopId == shop.id && isVisible(p) && p.inStock).toList()..shuffle(_rnd);
    if (pool.isEmpty) return null;
    final items = [
      for (final p in pool.take(1 + _rnd.nextInt(min(2, pool.length))))
        OrderItem(
          productId: p.id,
          title: p.title,
          image: p.image,
          price: p.price,
          qty: 1 + (_rnd.nextInt(4) == 0 ? 1 : 0),
          option: p.options.isEmpty ? null : p.options[_rnd.nextInt(p.options.length)],
        ),
    ];
    return buildOrder(
      id: _nextOrderId++,
      shop: shop,
      items: items,
      at: DateTime.now(),
      settings: settings,
      buyerName: kBuyerNames[_rnd.nextInt(kBuyerNames.length)],
      buyerPhone: '9${_rnd.nextInt(10)}${1000000 + _rnd.nextInt(8999999)}',
      address: kAddresses[_rnd.nextInt(kAddresses.length)],
      delivery: delivery,
      payment: kPayments[_rnd.nextInt(kPayments.length)],
    );
  }
}

/// Доступ к [MarketStore] из любого виджета; виджет перестраивается при изменениях.
class StoreScope extends InheritedNotifier<MarketStore> {
  const StoreScope({super.key, required MarketStore store, required super.child}) : super(notifier: store);

  static MarketStore of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<StoreScope>()!.notifier!;

  static MarketStore read(BuildContext context) => context.getInheritedWidgetOfExactType<StoreScope>()!.notifier!;
}
