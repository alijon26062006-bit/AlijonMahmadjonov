import 'package:material_ui/material_ui.dart';

import '../core/auth.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import 'admin_couriers_screen.dart';
import 'admin_dashboard_screen.dart';
import 'admin_orders_screen.dart';
import 'admin_settings_screen.dart';
import 'admin_shops_screen.dart';

final adminTab = ValueNotifier<int>(0);

class AdminRoot extends StatelessWidget {
  const AdminRoot({super.key});

  @override
  Widget build(BuildContext context) => const AuthGate(role: Role.admin, child: AdminShell());
}

class AdminShell extends StatelessWidget {
  const AdminShell({super.key});

  static const _pages = <Widget>[
    AdminDashboardScreen(),
    AdminShopsScreen(),
    AdminOrdersScreen(),
    AdminCouriersScreen(),
    AdminSettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final pending = s.shops.where((x) => x.status == ShopStatus.pending).length;
    final waiting = s.orders.where((o) => o.status == OrderStatus.placed).length;
    return ValueListenableBuilder<int>(
      valueListenable: adminTab,
      builder: (context, tab, _) => PopScope(
        canPop: tab == 0,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) adminTab.value = 0;
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
              onDestinationSelected: (i) => adminTab.value = i,
              destinations: [
                const NavigationDestination(
                  icon: Icon(Icons.space_dashboard_outlined),
                  selectedIcon: Icon(Icons.space_dashboard_rounded),
                  label: 'Обзор',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: pending > 0,
                    label: Text('$pending'),
                    backgroundColor: const Color(0xFFFF8A00),
                    child: const Icon(Icons.storefront_outlined),
                  ),
                  selectedIcon: const Icon(Icons.storefront_rounded),
                  label: 'Магазины',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: waiting > 0,
                    label: Text('$waiting'),
                    backgroundColor: c.gradientColors.last,
                    child: const Icon(Icons.receipt_long_outlined),
                  ),
                  selectedIcon: const Icon(Icons.receipt_long_rounded),
                  label: 'Заказы',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.delivery_dining_outlined),
                  selectedIcon: Icon(Icons.delivery_dining_rounded),
                  label: 'Курьеры',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.tune_outlined),
                  selectedIcon: Icon(Icons.tune_rounded),
                  label: 'Настройки',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
