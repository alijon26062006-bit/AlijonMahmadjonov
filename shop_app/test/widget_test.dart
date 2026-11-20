import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import 'package:vitrina/admin/admin_shell.dart';
import 'package:vitrina/buyer/buyer_common.dart';
import 'package:vitrina/buyer/buyer_shell.dart';
import 'package:vitrina/core/app.dart';
import 'package:vitrina/core/models.dart';
import 'package:vitrina/core/store.dart';
import 'package:vitrina/courier/courier_shell.dart';
import 'package:vitrina/seller/seller_shell.dart';

Future<MarketStore> _store(Role role, {String? phone}) async {
  final s = MarketStore(role, persist: false, simulate: false);
  await s.load();
  if (phone != null) s.user = AppUser(phone: phone, name: 'Тест');
  return s;
}

Future<void> _pump(WidgetTester tester, MarketStore store, Widget home) async {
  tester.view.physicalSize = const Size(1080, 2340);
  tester.view.devicePixelRatio = 2.75;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(MarketApp(store: store, home: home));
  await tester.pump(const Duration(milliseconds: 500));
}

void main() {
  group('Логика маркетплейса', () {
    test('корзина из двух магазинов → два заказа, промокод делится', () async {
      final s = await _store(Role.buyer, phone: '901112233');
      final phone = s.productById('e1')!;
      final tea = s.productById('f3')!;
      s.addToCart(phone, option: '256 ГБ');
      s.addToCart(tea, qty: 2);
      expect(s.cartByShop.length, 2);
      expect(s.applyPromo('vitrina20'), isNull);
      final total = s.itemsTotal;
      final promo = s.promoDiscount;
      final orders = s.placeOrders(name: 'Тест', phone: '901112233', address: 'ул. Тестовая, 1', courier: true, payment: 'Наличными');
      expect(orders, hasLength(2));
      expect(orders.fold(0, (a, o) => a + o.discount), closeTo(promo, 1));
      expect(orders.fold(0, (a, o) => a + o.itemsTotal), total);
      expect(s.cart, isEmpty);
      expect(s.myOrders, hasLength(2));
      // Остатки уменьшились.
      expect(s.productById('f3')!.stock, 38);
    });

    test('полный путь заказа: продавец → курьер → доставлен', () async {
      final seller = await _store(Role.seller, phone: '900000001');
      final o = seller.ordersOf('s1').firstWhere((o) => o.status == OrderStatus.placed && o.delivery);
      seller.acceptOrder(o);
      expect(o.status, OrderStatus.accepted);
      seller.markReady(o);
      expect(o.status, OrderStatus.ready);

      final courier = await _store(Role.courier, phone: '930000001');
      // Курьер видит заказы, готовые к доставке.
      expect(courier.availableDeliveries, isNotEmpty);
      final d = courier.availableDeliveries.firstWhere((o) => o.status == OrderStatus.ready);
      expect(courier.takeOrder(d), isTrue);
      expect(courier.myActiveDelivery, d);
      courier.pickUp(d);
      expect(d.status, OrderStatus.delivering);
      courier.deliver(d);
      expect(d.status, OrderStatus.delivered);
      expect(courier.myDeliveries, contains(d));
    });

    test('админ блокирует магазин — его товары пропадают из каталога', () async {
      final s = await _store(Role.admin, phone: '900000000');
      final before = s.catalog.where((p) => p.shopId == 's1').length;
      expect(before, greaterThan(0));
      s.setShopStatus(s.shopById('s1')!, ShopStatus.blocked);
      expect(s.catalog.where((p) => p.shopId == 's1'), isEmpty);
      s.setProductHidden(s.productById('f1')!, true);
      expect(s.catalog.any((p) => p.id == 'f1'), isFalse);
    });

    test('вход по коду', () async {
      final s = await _store(Role.buyer);
      final code = s.requestCode('901234567');
      expect(s.verifyCode('901234567', '0000'), code == '0000');
      expect(s.verifyCode('901234567', code), isTrue);
      expect(s.user?.phone, '901234567');
    });
  });

  group('Экраны', () {
    testWidgets('покупатель: все вкладки', (tester) async {
      final s = await _store(Role.buyer);
      await _pump(tester, s, const BuyerShell());
      expect(find.text('Магазины'), findsOneWidget);
      s.addToCart(s.productById('e2')!, option: 'Белый');
      for (final tab in [BuyerNav.catalog, BuyerNav.favorites, BuyerNav.cart, BuyerNav.profile, BuyerNav.home]) {
        buyerNav.tab.value = tab;
        await tester.pump(const Duration(milliseconds: 300));
      }
      buyerNav.tab.value = BuyerNav.cart;
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.text('Оформить заказ'), findsOneWidget);
      buyerNav.tab.value = BuyerNav.home;
    });

    testWidgets('продавец: вход и все вкладки', (tester) async {
      final s = await _store(Role.seller);
      await _pump(tester, s, const SellerRoot());
      expect(find.text('Получить код'), findsOneWidget);
      s.user = AppUser(phone: '900000001', name: 'Фаррух');
      s.setThemeMode(ThemeMode.light);
      await tester.pump(const Duration(milliseconds: 600));
      expect(find.text('ТехноМир'), findsWidgets);
      for (final tab in [1, 2, 3, 0]) {
        sellerTab.value = tab;
        await tester.pump(const Duration(milliseconds: 300));
      }
    });

    testWidgets('курьер: все вкладки', (tester) async {
      final s = await _store(Role.courier, phone: '930000001');
      await _pump(tester, s, const CourierRoot());
      expect(find.textContaining('Доступные заказы'), findsOneWidget);
      for (final tab in [1, 2, 0]) {
        courierTab.value = tab;
        await tester.pump(const Duration(milliseconds: 300));
      }
    });

    testWidgets('админ: все вкладки', (tester) async {
      final s = await _store(Role.admin, phone: '900000000');
      await _pump(tester, s, const AdminRoot());
      expect(find.text('Обзор маркетплейса'), findsOneWidget);
      for (final tab in [1, 2, 3, 4, 0]) {
        adminTab.value = tab;
        await tester.pump(const Duration(milliseconds: 300));
      }
    });
  });
}
