import 'package:material_ui/material_ui.dart';

import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import 'buyer_common.dart';
import 'cart_screen.dart';
import 'catalog_screen.dart';
import 'favorites_screen.dart';
import 'home_screen.dart';
import 'profile_screen.dart';

/// Приложение покупателя: пять вкладок внизу.
class BuyerShell extends StatelessWidget {
  const BuyerShell({super.key});

  static const _pages = <Widget>[HomeScreen(), CatalogScreen(), FavoritesScreen(), CartScreen(), ProfileScreen()];

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final pink = c.gradientColors.last;
    return ValueListenableBuilder<int>(
      valueListenable: buyerNav.tab,
      builder: (context, tab, _) => PopScope(
        canPop: tab == BuyerNav.home,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) buyerNav.tab.value = BuyerNav.home;
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
              onDestinationSelected: (i) => buyerNav.tab.value = i,
              destinations: [
                const NavigationDestination(
                  icon: Icon(Icons.home_outlined),
                  selectedIcon: Icon(Icons.home_rounded),
                  label: 'Главная',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.grid_view_outlined),
                  selectedIcon: Icon(Icons.grid_view_rounded),
                  label: 'Каталог',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: s.favorites.isNotEmpty,
                    smallSize: 8,
                    backgroundColor: pink,
                    child: const Icon(Icons.favorite_border_rounded),
                  ),
                  selectedIcon: const Icon(Icons.favorite_rounded),
                  label: 'Избранное',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: s.cartCount > 0,
                    label: Text('${s.cartCount}'),
                    backgroundColor: pink,
                    child: const Icon(Icons.shopping_bag_outlined),
                  ),
                  selectedIcon: Badge(
                    isLabelVisible: s.cartCount > 0,
                    label: Text('${s.cartCount}'),
                    backgroundColor: pink,
                    child: const Icon(Icons.shopping_bag_rounded),
                  ),
                  label: 'Корзина',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: s.myOrders.any((o) => o.status.isActive),
                    smallSize: 8,
                    backgroundColor: pink,
                    child: const Icon(Icons.person_outline_rounded),
                  ),
                  selectedIcon: const Icon(Icons.person_rounded),
                  label: 'Профиль',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
