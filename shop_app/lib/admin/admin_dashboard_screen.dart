import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'admin_shell.dart';
import 'admin_widgets.dart';

class AdminDashboardScreen extends StatelessWidget {
  const AdminDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final now = DateTime.now();
    final today = s.orders.where((o) => sameDay(o.createdAt, now)).toList();
    final todayOk = today.where((o) => o.status != OrderStatus.cancelled).toList();
    final gmv = todayOk.fold(0, (a, o) => a + o.total);
    final commission = todayOk.fold(0, (a, o) => a + o.commission);
    final active = s.orders.where((o) => o.status.isActive).length;
    final online = s.couriers.where((x) => x.online && !x.blocked).length;
    final pendingShops = s.shops.where((x) => x.status == ShopStatus.pending).toList();
    final noCourier = s.orders
        .where((o) => o.delivery && o.status == OrderStatus.ready && o.courierId == null)
        .toList();
    final stuck = s.orders
        .where((o) => o.status == OrderStatus.placed && now.difference(o.createdAt).inMinutes >= 5)
        .toList();

    final days = [for (var i = 6; i >= 0; i--) DateTime(now.year, now.month, now.day).subtract(Duration(days: i))];
    final values = [
      for (final d in days)
        s.orders
            .where((o) => sameDay(o.createdAt, d) && o.status != OrderStatus.cancelled)
            .fold(0, (a, o) => a + o.total),
    ];

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          Container(
            padding: EdgeInsets.fromLTRB(20, MediaQuery.paddingOf(context).top + 14, 20, 22),
            decoration: BoxDecoration(
              gradient: c.headerGradient,
              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(30)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('🛡️ Витрина Админ', style: TextStyle(color: Color(0xDDFFFFFF), fontSize: 14)),
                const SizedBox(height: 2),
                const Text(
                  'Обзор маркетплейса',
                  style: TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w900, letterSpacing: -0.6),
                ),
                const SizedBox(height: 16),
                Text('Оборот сегодня', style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 13.5)),
                Text(
                  money(gmv),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 34,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -1,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${ordersLabel(todayOk.length)} · комиссия ${money(commission)}',
                  style: const TextStyle(color: Color(0xDDFFFFFF), fontSize: 13.5),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: GridView(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                mainAxisExtent: 130,
              ),
              children: [
                StatCard(
                  value: '$active',
                  label: 'Активных заказов',
                  icon: Icons.receipt_long_outlined,
                  onTap: () => adminTab.value = 2,
                ),
                StatCard(
                  value: '${s.shops.where((x) => x.visible).length}',
                  label: 'Магазинов',
                  icon: Icons.storefront_outlined,
                  color: const Color(0xFFFF8A00),
                  onTap: () => adminTab.value = 1,
                ),
                StatCard(
                  value: '$online/${s.couriers.length}',
                  label: 'Курьеров онлайн',
                  icon: Icons.delivery_dining_outlined,
                  color: kSuccess,
                  onTap: () => adminTab.value = 3,
                ),
              ],
            ),
          ),
          if (pendingShops.isNotEmpty || noCourier.isNotEmpty || stuck.isNotEmpty) ...[
            const SectionHeader('Требует внимания'),
            for (final shop in pendingShops)
              _Alert(
                icon: Icons.storefront_outlined,
                color: const Color(0xFFFF8A00),
                title: 'Магазин «${shop.name}» ждёт проверки',
                subtitle: '${shop.ownerName} · ${formatPhone(shop.ownerPhone)}',
                onTap: () => openAdminShop(context, shop),
              ),
            for (final o in stuck.take(3))
              _Alert(
                icon: Icons.hourglass_bottom_rounded,
                color: c.gradientColors.last,
                title: 'Заказ №${o.id} не принят ${DateTime.now().difference(o.createdAt).inMinutes} мин',
                subtitle: s.shopById(o.shopId)?.name ?? '',
                onTap: () => openAdminOrder(context, o),
              ),
            for (final o in noCourier.take(3))
              _Alert(
                icon: Icons.person_search_outlined,
                color: const Color(0xFF2F80ED),
                title: 'Заказ №${o.id} ждёт курьера',
                subtitle: '${s.shopById(o.shopId)?.name ?? ''} · готов ${timeAgo(o.updatedAt)}',
                onTap: () => openAdminOrder(context, o),
              ),
          ],
          const SectionHeader('Оборот за неделю'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    money(values.fold(0, (a, v) => a + v)),
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, letterSpacing: -0.5, color: c.text),
                  ),
                  Text('все магазины, без отменённых заказов', style: TextStyle(color: c.muted, fontSize: 13)),
                  const SizedBox(height: 14),
                  MiniBarChart(
                    values: values,
                    labels: [for (final d in days) weekdayShort(d)],
                    format: (v) => v >= 1000 ? '${(v / 1000).toStringAsFixed(1)}к' : '$v',
                  ),
                ],
              ),
            ),
          ),
          SectionHeader('Последние заказы', action: 'Все', onAction: () => adminTab.value = 2),
          for (final o in s.sorted(s.orders).take(6)) AdminOrderTile(order: o),
        ],
      ),
    );
  }
}

class _Alert extends StatelessWidget {
  const _Alert({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: AppCard(
        padding: const EdgeInsets.all(12),
        onTap: onTap,
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(color: color.withValues(alpha: .13), borderRadius: BorderRadius.circular(12)),
              child: Icon(icon, color: color, size: 21),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                  ),
                  Text(
                    subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12.5, color: c.muted),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right_rounded, color: c.muted),
          ],
        ),
      ),
    );
  }
}
