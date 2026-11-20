import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'admin_widgets.dart';

/// Карточка магазина для админа: проверка, блокировка, модерация товаров.
class AdminShopScreen extends StatelessWidget {
  const AdminShopScreen({super.key, required this.shopId});

  final String shopId;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final shop = s.shopById(shopId);
    if (shop == null) return Scaffold(appBar: AppBar(), body: const SizedBox());
    final orders = s.ordersOf(shop.id);
    final done = orders.where((o) => o.status == OrderStatus.delivered).toList();
    final cancelled = orders.where((o) => o.status == OrderStatus.cancelled).length;
    final products = s.productsOf(shop.id);
    return Scaffold(
      appBar: AppBar(title: Text(shop.name)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
        children: [
          AppCard(
            child: Row(
              children: [
                ImageTile(image: shop.logo, categoryId: shop.categoryId, size: 60),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        shop.name,
                        style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: c.text),
                      ),
                      Text(
                        '${categoryById(shop.categoryId).name} · рейтинг ${ratingText(shop.rating)} · с ${two(shop.createdAt.day)}.${two(shop.createdAt.month)}.${shop.createdAt.year}',
                        style: TextStyle(color: c.muted, fontSize: 13),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          StatusPill(label: shop.status.label, color: shop.status.color),
                          const SizedBox(width: 6),
                          if (shop.visible)
                            StatusPill(
                              label: shop.isOpen ? 'Открыт' : 'Закрыт',
                              color: shop.isOpen ? kSuccess : c.muted,
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: StatCard(value: money(s.revenueOf(orders)), label: 'Оборот'),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: StatCard(
                  value: money(done.fold(0, (a, o) => a + o.commission)),
                  label: 'Комиссия',
                  color: kSuccess,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: StatCard(value: '${done.length}/$cancelled', label: 'Выполн./отмен.'),
              ),
            ],
          ),
          const FieldLabel('Владелец'),
          AppCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            child: Column(
              children: [
                InfoLine(
                  icon: Icons.person_outline_rounded,
                  title: shop.ownerName,
                  text: formatPhone(shop.ownerPhone),
                  trailing: IconButton(
                    icon: Icon(Icons.call_rounded, color: c.accentText),
                    onPressed: () => callPhone(context, shop.ownerPhone),
                  ),
                ),
                InfoLine(icon: Icons.location_on_outlined, title: 'Адрес', text: shop.address),
                if (shop.description.isNotEmpty)
                  InfoLine(icon: Icons.notes_rounded, title: 'Описание', text: shop.description),
              ],
            ),
          ),
          FieldLabel('Товары · ${products.length}'),
          if (products.isEmpty)
            AppCard(
              child: Text('Товаров пока нет', style: TextStyle(color: c.muted)),
            )
          else
            AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Column(
                children: [
                  for (final p in products)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        children: [
                          ImageTile(image: p.image, categoryId: p.categoryId, size: 42),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  p.title,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontWeight: FontWeight.w600,
                                    color: p.hiddenByAdmin ? c.muted : c.text,
                                    decoration: p.hiddenByAdmin ? TextDecoration.lineThrough : null,
                                  ),
                                ),
                                Text(
                                  '${money(p.price)} · остаток ${p.stock}${p.active ? '' : ' · снят продавцом'}',
                                  style: TextStyle(fontSize: 12, color: c.muted),
                                ),
                              ],
                            ),
                          ),
                          TextButton(
                            onPressed: () => s.setProductHidden(p, !p.hiddenByAdmin),
                            child: Text(
                              p.hiddenByAdmin ? 'Вернуть' : 'Скрыть',
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                color: p.hiddenByAdmin ? kSuccess : kDanger,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          if (orders.isNotEmpty) ...[
            const FieldLabel('Последние заказы'),
            for (final o in s.sorted(orders).take(5))
              AdminOrderTile(order: o, margin: const EdgeInsets.only(bottom: 8)),
          ],
        ],
      ),
      bottomNavigationBar: BottomBar(child: _actions(context, s, shop)),
    );
  }

  Widget _actions(BuildContext context, MarketStore s, Shop shop) {
    switch (shop.status) {
      case ShopStatus.pending:
        return Row(
          children: [
            Expanded(
              child: SoftButton(
                label: 'Отклонить',
                color: kDanger,
                onPressed: () => s.setShopStatus(shop, ShopStatus.blocked),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              flex: 2,
              child: GradientButton(
                label: 'Одобрить магазин',
                icon: Icons.verified_outlined,
                onPressed: () {
                  s.setShopStatus(shop, ShopStatus.active);
                  showSnack(context, '«${shop.name}» одобрен — покупатели его видят');
                },
              ),
            ),
          ],
        );
      case ShopStatus.active:
        return SoftButton(
          label: 'Заблокировать магазин',
          icon: Icons.block_rounded,
          color: kDanger,
          onPressed: () async {
            if (await confirm(
              context,
              title: 'Заблокировать «${shop.name}»?',
              text: 'Покупатели перестанут видеть магазин и его товары.',
              ok: 'Заблокировать',
              danger: true,
            )) {
              s.setShopStatus(shop, ShopStatus.blocked);
            }
          },
        );
      case ShopStatus.blocked:
        return GradientButton(
          label: 'Разблокировать',
          icon: Icons.lock_open_rounded,
          onPressed: () => s.setShopStatus(shop, ShopStatus.active),
        );
    }
  }
}
