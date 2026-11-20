import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'seller_shell.dart';
import 'seller_widgets.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final shop = s.myShop!;
    final orders = s.ordersOf(shop.id);
    final now = DateTime.now();
    final today = orders.where((o) => sameDay(o.createdAt, now) && o.status != OrderStatus.cancelled).toList();
    final todayDone = today.where((o) => o.status == OrderStatus.delivered).toList();
    final income = todayDone.fold(0, (a, o) => a + sellerIncome(o));
    final avg = today.isEmpty ? 0 : (today.fold(0, (a, o) => a + o.itemsTotal) / today.length).round();
    final inWork = orders.where((o) => o.status == OrderStatus.accepted || o.status == OrderStatus.ready).length;
    final fresh = s.sorted(orders.where((o) => o.status == OrderStatus.placed));

    // Выручка за 7 дней
    final days = [for (var i = 6; i >= 0; i--) DateTime(now.year, now.month, now.day).subtract(Duration(days: i))];
    final values = [
      for (final d in days)
        orders
            .where((o) => sameDay(o.createdAt, d) && o.status == OrderStatus.delivered)
            .fold(0, (a, o) => a + sellerIncome(o)),
    ];

    // Топ товаров
    final sold = <String, int>{};
    for (final o in orders.where((o) => o.status == OrderStatus.delivered)) {
      for (final i in o.items) {
        sold[i.productId] = (sold[i.productId] ?? 0) + i.qty;
      }
    }
    final top = sold.entries.toList()..sort((a, b) => b.value.compareTo(a.value));

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          _Header(shop: shop),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: GridView(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                mainAxisExtent: 124,
              ),
              children: [
                StatCard(
                  value: money(income),
                  label: 'Выручка сегодня',
                  icon: Icons.payments_outlined,
                  color: kSuccess,
                ),
                StatCard(value: '${today.length}', label: 'Заказов сегодня', icon: Icons.receipt_long_outlined),
                StatCard(
                  value: money(avg),
                  label: 'Средний чек',
                  icon: Icons.shopping_bag_outlined,
                  color: const Color(0xFF2F80ED),
                ),
                StatCard(
                  value: '$inWork',
                  label: 'В работе',
                  icon: Icons.inventory_2_outlined,
                  color: const Color(0xFFFF8A00),
                  onTap: () => sellerTab.value = 1,
                ),
              ],
            ),
          ),
          if (fresh.isNotEmpty) ...[
            SectionHeader('Новые заказы · ${fresh.length}', action: 'Все', onAction: () => sellerTab.value = 1),
            for (final o in fresh.take(3)) SellerOrderCard(order: o, quickActions: true),
          ],
          const SectionHeader('Выручка за неделю'),
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
                  Text(
                    'после комиссии маркетплейса ${s.settings.commissionPercent}%',
                    style: TextStyle(color: c.muted, fontSize: 13),
                  ),
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
          if (top.isNotEmpty) ...[
            const SectionHeader('Популярные товары'),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: AppCard(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                child: Column(
                  children: [
                    for (final (i, e) in top.take(5).indexed)
                      if (s.productById(e.key) case final p?)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: Row(
                            children: [
                              SizedBox(
                                width: 22,
                                child: Text(
                                  '${i + 1}',
                                  style: TextStyle(fontWeight: FontWeight.w800, color: c.muted),
                                ),
                              ),
                              EmojiTile(emoji: p.emoji, categoryId: p.categoryId, size: 42),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  p.title,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(fontWeight: FontWeight.w600, color: c.text),
                                ),
                              ),
                              Text(
                                '${e.value} шт.',
                                style: TextStyle(fontWeight: FontWeight.w800, color: c.accentText),
                              ),
                            ],
                          ),
                        ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.shop});

  final Shop shop;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final top = MediaQuery.paddingOf(context).top;
    final name = s.user?.name.split(' ').first ?? '';
    return Container(
      padding: EdgeInsets.fromLTRB(20, top + 14, 20, 20),
      decoration: BoxDecoration(
        gradient: c.headerGradient,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(30)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 52,
                height: 52,
                alignment: Alignment.center,
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(17)),
                child: Text(shop.emoji, style: const TextStyle(fontSize: 28)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name.isEmpty ? 'Добро пожаловать' : 'Здравствуйте, $name 👋',
                      style: const TextStyle(color: Color(0xDDFFFFFF), fontSize: 14),
                    ),
                    Text(
                      shop.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.6,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (shop.status != ShopStatus.active)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: const Color(0x33000000), borderRadius: BorderRadius.circular(16)),
              child: Row(
                children: [
                  const Icon(Icons.info_outline_rounded, color: Colors.white),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      shop.status == ShopStatus.blocked
                          ? 'Магазин заблокирован администратором. Покупатели его не видят.'
                          : 'Магазин на проверке у администратора.',
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            )
          else
            Material(
              color: const Color(0x2EFFFFFF),
              borderRadius: BorderRadius.circular(16),
              child: SwitchListTile(
                value: shop.isOpen,
                onChanged: (v) {
                  HapticFeedback.selectionClick();
                  s.setShopOpen(shop, v);
                },
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                activeThumbColor: Colors.white,
                activeTrackColor: const Color(0xFF2BD47D),
                title: Text(
                  shop.isOpen ? 'Магазин открыт' : 'Магазин закрыт',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800),
                ),
                subtitle: Text(
                  shop.isOpen ? 'Покупатели могут заказывать' : 'Новые заказы не принимаются',
                  style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 12.5),
                ),
              ),
            ),
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              '${categoryById(shop.categoryId).emoji} ${categoryById(shop.categoryId).name} · ★ ${shop.rating.toStringAsFixed(1)} · ${s.productsOf(shop.id).length} товаров',
              style: const TextStyle(color: Color(0xDDFFFFFF), fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}
