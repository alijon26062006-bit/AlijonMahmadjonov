import 'dart:convert';
import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'data.dart';
import 'format.dart';
import 'models.dart';

class Promo {
  const Promo(this.code, this.title, {this.percent = 0, this.fixed = 0});

  final String code;
  final String title;
  final int percent;
  final int fixed;
}

const kPromos = <Promo>[
  Promo('VITRINA20', 'Скидка 20% на весь заказ', percent: 20),
  Promo('SALE10', 'Скидка 10% на весь заказ', percent: 10),
  Promo('WELCOME', 'Минус 500 $kCurrency на первый заказ', fixed: 500),
];

const int kFreeDeliveryFrom = 5000;
const int kDeliveryFee = 299;

/// Всё состояние магазина: избранное, корзина, заказы, настройки.
/// Сохраняется на телефоне через shared_preferences.
class ShopState extends ChangeNotifier {
  SharedPreferences? _prefs;

  final Set<String> favorites = <String>{};
  final List<CartItem> cart = [];
  final List<Order> orders = [];
  ThemeMode themeMode = ThemeMode.light;
  Promo? promo;
  String name = '';
  String phone = '';
  String address = '';

  Future<void> load() async {
    try {
      _prefs = await SharedPreferences.getInstance();
    } catch (_) {
      return;
    }
    final p = _prefs!;
    favorites.addAll((p.getStringList('favorites') ?? const []).where((id) => productById(id) != null));
    try {
      final rawCart = p.getString('cart');
      if (rawCart != null) {
        cart.addAll(
          (jsonDecode(rawCart) as List)
              .map((e) => CartItem.fromJson(Map<String, dynamic>.from(e as Map)))
              .where((i) => productById(i.productId) != null && i.qty > 0),
        );
      }
      final rawOrders = p.getString('orders');
      if (rawOrders != null) {
        orders.addAll((jsonDecode(rawOrders) as List).map((e) => Order.fromJson(Map<String, dynamic>.from(e as Map))));
      }
    } catch (_) {
      // Повреждённые данные — просто начинаем с чистого листа.
    }
    themeMode = ThemeMode.values[(p.getInt('theme') ?? 1).clamp(0, 2)];
    promo = _findPromo(p.getString('promo'));
    name = p.getString('name') ?? '';
    phone = p.getString('phone') ?? '';
    address = p.getString('address') ?? '';
  }

  void _changed() {
    final p = _prefs;
    if (p != null) {
      p.setStringList('favorites', favorites.toList());
      p.setString('cart', jsonEncode(cart.map((e) => e.toJson()).toList()));
      p.setString('orders', jsonEncode(orders.map((e) => e.toJson()).toList()));
      p.setInt('theme', themeMode.index);
      if (promo == null) {
        p.remove('promo');
      } else {
        p.setString('promo', promo!.code);
      }
      p.setString('name', name);
      p.setString('phone', phone);
      p.setString('address', address);
    }
    notifyListeners();
  }

  // ---------- Тема ----------
  void setThemeMode(ThemeMode mode) {
    themeMode = mode;
    _changed();
  }

  // ---------- Избранное ----------
  bool isFavorite(String id) => favorites.contains(id);

  void toggleFavorite(String id) {
    if (!favorites.remove(id)) favorites.add(id);
    _changed();
  }

  List<Product> get favoriteProducts => kProducts.where((p) => favorites.contains(p.id)).toList();

  // ---------- Корзина ----------
  int get cartCount => cart.fold(0, (s, i) => s + i.qty);

  int qtyInCart(String productId) => cart.where((i) => i.productId == productId).fold(0, (s, i) => s + i.qty);

  void addToCart(Product product, {String? option, int qty = 1}) {
    final key = '${product.id}|${option ?? ''}';
    final existing = cart.where((i) => i.key == key).firstOrNull;
    if (existing != null) {
      existing.qty = math.min(99, existing.qty + qty);
    } else {
      cart.add(CartItem(productId: product.id, option: option, qty: qty));
    }
    _changed();
  }

  void setQty(CartItem item, int qty) {
    item.qty = qty.clamp(1, 99);
    _changed();
  }

  /// Удаляет позицию и возвращает её индекс (для кнопки «Вернуть»).
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

  Product productOf(CartItem item) => productById(item.productId)!;

  int get itemsTotal => cart.fold(0, (s, i) => s + productOf(i).price * i.qty);

  int get itemsOldTotal => cart.fold(0, (s, i) => s + (productOf(i).oldPrice ?? productOf(i).price) * i.qty);

  int get productDiscount => itemsOldTotal - itemsTotal;

  int get promoDiscount {
    final pr = promo;
    if (pr == null || cart.isEmpty) return 0;
    if (pr.percent > 0) return (itemsTotal * pr.percent / 100).round();
    return math.min(pr.fixed, itemsTotal);
  }

  int get leftForFreeDelivery => math.max(0, kFreeDeliveryFrom - itemsTotal);

  int deliveryFee({required bool courier}) => !courier || leftForFreeDelivery == 0 ? 0 : kDeliveryFee;

  int total({bool courier = false}) => itemsTotal - promoDiscount + deliveryFee(courier: courier);

  // ---------- Промокоды ----------
  Promo? _findPromo(String? code) {
    if (code == null) return null;
    final c = code.trim().toUpperCase();
    return kPromos.where((p) => p.code == c).firstOrNull;
  }

  /// Возвращает текст ошибки или null, если промокод применён.
  String? applyPromo(String code) {
    if (code.trim().isEmpty) return 'Введите промокод';
    final found = _findPromo(code);
    if (found == null) return 'Такого промокода нет';
    promo = found;
    _changed();
    return null;
  }

  void removePromo() {
    promo = null;
    _changed();
  }

  // ---------- Заказы ----------
  int get totalSaved => orders.fold(0, (s, o) => s + o.discount);

  Order placeOrder({
    required String name,
    required String phone,
    required String address,
    required bool courier,
    required String payment,
    String comment = '',
  }) {
    final now = DateTime.now();
    final order = Order(
      id: (now.millisecondsSinceEpoch % 1000000).toString().padLeft(6, '0'),
      createdAt: now,
      lines: [
        for (final i in cart)
          OrderLine(
            productId: i.productId,
            title: productOf(i).title,
            emoji: productOf(i).emoji,
            price: productOf(i).price,
            qty: i.qty,
            option: i.option,
          ),
      ],
      itemsTotal: itemsOldTotal,
      discount: productDiscount + promoDiscount,
      deliveryFee: deliveryFee(courier: courier),
      total: total(courier: courier),
      name: name,
      phone: phone,
      address: address,
      courier: courier,
      payment: payment,
      comment: comment,
    );
    orders.insert(0, order);
    this.name = name;
    this.phone = phone;
    if (courier) this.address = address;
    cart.clear();
    promo = null;
    _changed();
    return order;
  }

  void clearOrders() {
    orders.clear();
    _changed();
  }
}

/// Даёт доступ к [ShopState] из любого виджета и перестраивает его при изменениях.
class ShopScope extends InheritedNotifier<ShopState> {
  const ShopScope({super.key, required ShopState state, required super.child}) : super(notifier: state);

  static ShopState of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<ShopScope>()!.notifier!;

  static ShopState read(BuildContext context) => context.getInheritedWidgetOfExactType<ShopScope>()!.notifier!;
}

/// Навигация между вкладками нижнего меню.
class AppNav {
  static const home = 0, catalog = 1, favorites = 2, cart = 3, profile = 4;

  final tab = ValueNotifier<int>(home);
  final catalogCategory = ValueNotifier<String?>(null);
  final searchRequest = ValueNotifier<int>(0);

  void openCatalog({String? category, bool focusSearch = false}) {
    catalogCategory.value = category;
    tab.value = catalog;
    if (focusSearch) searchRequest.value++;
  }
}

final appNav = AppNav();
