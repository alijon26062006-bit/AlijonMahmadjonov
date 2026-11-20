import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:vitrina/data.dart';
import 'package:vitrina/main.dart';
import 'package:vitrina/state.dart';

Future<ShopState> _pumpApp(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1080, 2340);
  tester.view.devicePixelRatio = 2.75;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({});
  final state = ShopState();
  await state.load();
  await tester.pumpWidget(VitrinaApp(state: state));
  await tester.pump();
  return state;
}

void main() {
  test('корзина считает суммы и промокоды', () {
    final s = ShopState();
    final phone = productById('e1')!;
    s.addToCart(phone, option: '256 ГБ', qty: 2);
    expect(s.cartCount, 2);
    expect(s.itemsTotal, phone.price * 2);
    expect(s.applyPromo('nope'), isNotNull);
    expect(s.applyPromo('vitrina20'), isNull);
    expect(s.promoDiscount, (phone.price * 2 * .2).round());
    final order = s.placeOrder(
      name: 'Тест',
      phone: '900000000',
      address: 'ул. Тестовая, 1',
      courier: true,
      payment: 'Наличными',
    );
    expect(order.total, phone.price * 2 - (phone.price * 2 * .2).round());
    expect(s.cart, isEmpty);
    expect(s.orders, hasLength(1));
  });

  testWidgets('главный экран, товар и корзина открываются', (tester) async {
    final state = await _pumpApp(tester);
    expect(find.text('Витрина'), findsWidgets);
    expect(find.text('Хиты продаж 🔥'), findsOneWidget);

    // Открываем первый товар из хитов.
    await tester.tap(find.byType(InkWell).at(3));
    await tester.pumpAndSettle(
      const Duration(milliseconds: 100),
      EnginePhase.sendSemanticsUpdate,
      const Duration(seconds: 5),
    );

    // Все вкладки рендерятся без ошибок.
    for (final tab in [AppNav.catalog, AppNav.favorites, AppNav.cart, AppNav.profile, AppNav.home]) {
      appNav.tab.value = tab;
      await tester.pump(const Duration(milliseconds: 300));
    }

    state.addToCart(productById('e2')!, option: 'Белый');
    appNav.tab.value = AppNav.cart;
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Оформить заказ'), findsOneWidget);
  });
}
