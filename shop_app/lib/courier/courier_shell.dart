import 'package:material_ui/material_ui.dart';

import '../core/auth.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import 'courier_home_screen.dart';
import 'courier_profile_screen.dart';
import 'earnings_screen.dart';
import 'register_courier_screen.dart';

final courierTab = ValueNotifier<int>(0);

/// Приложение курьера: вход → (регистрация) → три вкладки.
class CourierRoot extends StatelessWidget {
  const CourierRoot({super.key});

  @override
  Widget build(BuildContext context) {
    return AuthGate(
      role: Role.courier,
      child: Builder(
        builder: (context) => StoreScope.of(context).me == null ? const RegisterCourierScreen() : const CourierShell(),
      ),
    );
  }
}

class CourierShell extends StatelessWidget {
  const CourierShell({super.key});

  static const _pages = <Widget>[CourierHomeScreen(), EarningsScreen(), CourierProfileScreen()];

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final available = s.me!.online && s.myActiveDelivery == null ? s.availableDeliveries.length : 0;
    return ValueListenableBuilder<int>(
      valueListenable: courierTab,
      builder: (context, tab, _) => PopScope(
        canPop: tab == 0,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) courierTab.value = 0;
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
              onDestinationSelected: (i) => courierTab.value = i,
              destinations: [
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: available > 0,
                    label: Text('$available'),
                    backgroundColor: c.gradientColors.last,
                    child: const Icon(Icons.delivery_dining_outlined),
                  ),
                  selectedIcon: const Icon(Icons.delivery_dining_rounded),
                  label: 'Заказы',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.account_balance_wallet_outlined),
                  selectedIcon: Icon(Icons.account_balance_wallet_rounded),
                  label: 'Заработок',
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
