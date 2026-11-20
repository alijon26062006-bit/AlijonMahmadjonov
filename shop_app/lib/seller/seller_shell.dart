import 'package:material_ui/material_ui.dart';

import '../core/auth.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import 'create_shop_screen.dart';
import 'dashboard_screen.dart';
import 'orders_screen.dart';
import 'products_screen.dart';
import 'shop_profile_screen.dart';

final sellerTab = ValueNotifier<int>(0);

/// Приложение продавца: вход → (создание магазина) → четыре вкладки.
class SellerRoot extends StatelessWidget {
  const SellerRoot({super.key});

  @override
  Widget build(BuildContext context) {
    return AuthGate(
      role: Role.seller,
      child: Builder(
        builder: (context) {
          final shop = StoreScope.of(context).myShop;
          return shop == null ? const CreateShopScreen() : const SellerShell();
        },
      ),
    );
  }
}

class SellerShell extends StatelessWidget {
  const SellerShell({super.key});

  static const _pages = <Widget>[DashboardScreen(), SellerOrdersScreen(), ProductsScreen(), ShopProfileScreen()];

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final shop = s.myShop!;
    final newCount = s.ordersOf(shop.id).where((o) => o.status == OrderStatus.placed).length;
    return ValueListenableBuilder<int>(
      valueListenable: sellerTab,
      builder: (context, tab, _) => PopScope(
        canPop: tab == 0,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) sellerTab.value = 0;
        },
        child: Scaffold(
          body: IndexedStack(index: tab, children: _pages),
          bottomNavigationBar: DecoratedBox(
            decoration: BoxDecoration(
              color: c.surface,
              boxShadow: const [
                BoxShadow(color: Color(0x14000000), blurRadius: 24, offset: Offset(0, -8), spreadRadius: -12),
              ],
            ),
            child: NavigationBar(
              selectedIndex: tab,
              onDestinationSelected: (i) => sellerTab.value = i,
              destinations: [
                const NavigationDestination(
                  icon: Icon(Icons.insights_outlined),
                  selectedIcon: Icon(Icons.insights_rounded),
                  label: 'Сводка',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: newCount > 0,
                    label: Text('$newCount'),
                    backgroundColor: c.gradientColors.last,
                    child: const Icon(Icons.receipt_long_outlined),
                  ),
                  selectedIcon: Badge(
                    isLabelVisible: newCount > 0,
                    label: Text('$newCount'),
                    backgroundColor: c.gradientColors.last,
                    child: const Icon(Icons.receipt_long_rounded),
                  ),
                  label: 'Заказы',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.inventory_2_outlined),
                  selectedIcon: Icon(Icons.inventory_2_rounded),
                  label: 'Товары',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.storefront_outlined),
                  selectedIcon: Icon(Icons.storefront_rounded),
                  label: 'Магазин',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
