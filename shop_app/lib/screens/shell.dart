import 'package:material_ui/material_ui.dart';

import '../state.dart';
import '../theme.dart';
import 'cart_screen.dart';
import 'catalog_screen.dart';
import 'favorites_screen.dart';
import 'home_screen.dart';
import 'profile_screen.dart';

/// Корневой экран с нижним меню из пяти вкладок.
class RootShell extends StatelessWidget {
  const RootShell({super.key});

  static const _pages = <Widget>[HomeScreen(), CatalogScreen(), FavoritesScreen(), CartScreen(), ProfileScreen()];

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
    final c = AppColors.of(context);
    return ValueListenableBuilder<int>(
      valueListenable: appNav.tab,
      builder: (context, tab, _) => PopScope(
        canPop: tab == AppNav.home,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) appNav.tab.value = AppNav.home;
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
              onDestinationSelected: (i) => appNav.tab.value = i,
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
                    backgroundColor: kPink,
                    child: const Icon(Icons.favorite_border_rounded),
                  ),
                  selectedIcon: const Icon(Icons.favorite_rounded),
                  label: 'Избранное',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: s.cartCount > 0,
                    label: Text('${s.cartCount}'),
                    backgroundColor: kPink,
                    child: const Icon(Icons.shopping_bag_outlined),
                  ),
                  selectedIcon: Badge(
                    isLabelVisible: s.cartCount > 0,
                    label: Text('${s.cartCount}'),
                    backgroundColor: kPink,
                    child: const Icon(Icons.shopping_bag_rounded),
                  ),
                  label: 'Корзина',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.person_outline_rounded),
                  selectedIcon: Icon(Icons.person_rounded),
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
