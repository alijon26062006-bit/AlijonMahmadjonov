import 'package:material_ui/material_ui.dart';

import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'seller_widgets.dart';

/// Заказы магазина по вкладкам статусов.
class SellerOrdersScreen extends StatelessWidget {
  const SellerOrdersScreen({super.key});

  static const _tabs = <(String, List<OrderStatus>)>[
    ('Новые', [OrderStatus.placed]),
    ('Собираются', [OrderStatus.accepted]),
    ('Готовы', [OrderStatus.ready, OrderStatus.delivering]),
    ('Завершены', [OrderStatus.delivered, OrderStatus.cancelled]),
  ];

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final orders = s.ordersOf(s.myShop!.id);
    return DefaultTabController(
      length: _tabs.length,
      child: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageTitle('Заказы'),
            TabBar(
              isScrollable: true,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              tabs: [
                for (final (label, statuses) in _tabs)
                  Tab(
                    child: Row(
                      children: [
                        Text(label),
                        if (statuses.first.isActive) ...[
                          const SizedBox(width: 6),
                          _Count(n: orders.where((o) => statuses.contains(o.status)).length, colors: c),
                        ],
                      ],
                    ),
                  ),
              ],
            ),
            Expanded(
              child: TabBarView(
                children: [
                  for (final (_, statuses) in _tabs)
                    Builder(
                      builder: (context) {
                        final list = s.sorted(orders.where((o) => statuses.contains(o.status)));
                        if (list.isEmpty) {
                          return EmptyState(
                            emoji: statuses.first == OrderStatus.placed ? '📭' : '📦',
                            title: statuses.first == OrderStatus.placed ? 'Новых заказов нет' : 'Здесь пусто',
                            subtitle: statuses.first == OrderStatus.placed
                                ? 'Как только покупатель оформит заказ,\nон появится здесь'
                                : 'Заказы с этим статусом появятся здесь',
                          );
                        }
                        return ListView(
                          padding: const EdgeInsets.only(top: 12, bottom: 24),
                          children: [
                            for (final o in list.take(100))
                              SellerOrderCard(order: o, quickActions: statuses.first == OrderStatus.placed),
                          ],
                        );
                      },
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Count extends StatelessWidget {
  const _Count({required this.n, required this.colors});

  final int n;
  final AppColors colors;

  @override
  Widget build(BuildContext context) => n == 0
      ? const SizedBox.shrink()
      : Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 1),
          decoration: BoxDecoration(color: colors.accentSoft, borderRadius: BorderRadius.circular(99)),
          child: Text(
            '$n',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: colors.accentText),
          ),
        );
}
