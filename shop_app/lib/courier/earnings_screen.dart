import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

/// Заработок курьера: неделя, график и история доставок.
class EarningsScreen extends StatelessWidget {
  const EarningsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final done = s.myDeliveries;
    final now = DateTime.now();
    final days = [for (var i = 6; i >= 0; i--) DateTime(now.year, now.month, now.day).subtract(Duration(days: i))];
    final values = [
      for (final d in days) done.where((o) => sameDay(o.updatedAt, d)).fold(0, (a, o) => a + o.courierPay),
    ];
    final week = values.fold(0, (a, v) => a + v);
    final today = values.last;
    final total = done.fold(0, (a, o) => a + o.courierPay);
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          const PageTitle('Заработок'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(
                  child: StatCard(value: money(today), label: 'Сегодня', icon: Icons.today_rounded, color: kSuccess),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: StatCard(value: money(week), label: 'За 7 дней', icon: Icons.date_range_rounded),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(
                  child: StatCard(
                    value: '${done.length}',
                    label: plural(done.length, 'доставка', 'доставки', 'доставок'),
                    icon: Icons.delivery_dining_rounded,
                    color: const Color(0xFF2F80ED),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: StatCard(
                    value: money(total),
                    label: 'Всего',
                    icon: Icons.savings_outlined,
                    color: const Color(0xFFFF8A00),
                  ),
                ),
              ],
            ),
          ),
          const SectionHeader('По дням'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: AppCard(
              child: MiniBarChart(values: values, labels: [for (final d in days) weekdayShort(d)]),
            ),
          ),
          const SectionHeader('История доставок'),
          if (done.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: AppCard(
                child: Text(
                  'Здесь появятся ваши доставки. Выйдите на линию и возьмите первый заказ!',
                  style: TextStyle(color: c.muted, height: 1.4),
                ),
              ),
            )
          else
            for (final o in done.take(50))
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: AppCard(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Container(
                        width: 42,
                        height: 42,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(color: c.accentSoft, borderRadius: BorderRadius.circular(13)),
                        padding: const EdgeInsets.all(8),
                        child: AppImage(s.shopById(o.shopId)?.logo ?? 'package'),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '№${o.id} · ${s.shopById(o.shopId)?.name ?? ''}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                            ),
                            Text(
                              '${formatWhen(o.updatedAt)} · ${o.address}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 12.5, color: c.muted),
                            ),
                          ],
                        ),
                      ),
                      Text(
                        '+${money(o.courierPay)}',
                        style: const TextStyle(fontWeight: FontWeight.w800, color: kSuccess),
                      ),
                    ],
                  ),
                ),
              ),
        ],
      ),
    );
  }
}
