import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'seller_order_screen.dart';

/// Сколько продавец получит с заказа: товары − скидка − комиссия маркетплейса.
int sellerIncome(Order o) => o.itemsTotal - o.discount - o.commission;

void openSellerOrder(BuildContext context, Order o) {
  Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => SellerOrderScreen(orderId: o.id)));
}

/// Карточка заказа в списке продавца.
class SellerOrderCard extends StatelessWidget {
  const SellerOrderCard({super.key, required this.order, this.quickActions = false});

  final Order order;
  final bool quickActions;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final o = order;
    final isNew = o.status == OrderStatus.placed;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
      child: AppCard(
        padding: const EdgeInsets.all(14),
        onTap: () => openSellerOrder(context, o),
        color: isNew ? Color.alphaBlend(c.accentSoft.withValues(alpha: .6), c.surface) : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (isNew)
                  Container(
                    width: 8,
                    height: 8,
                    margin: const EdgeInsets.only(right: 8),
                    decoration: BoxDecoration(color: c.gradientColors.last, shape: BoxShape.circle),
                  ),
                Expanded(
                  child: Text(
                    'Заказ №${o.id}',
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, color: c.text),
                  ),
                ),
                StatusPill.order(o),
              ],
            ),
            const SizedBox(height: 3),
            Row(
              children: [
                Icon(
                  o.delivery ? Icons.delivery_dining_rounded : Icons.directions_walk_rounded,
                  size: 15,
                  color: c.muted,
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    '${o.delivery ? 'Доставка' : 'Самовывоз'} · ${o.buyerName} · ${timeAgo(o.createdAt)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12.5, color: c.muted),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                for (final i in o.items.take(4))
                  Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: EmojiTile(
                      emoji: i.emoji,
                      categoryId: s.productById(i.productId)?.categoryId ?? 'electronics',
                      size: 40,
                    ),
                  ),
                if (o.items.length > 4) Text('+${o.items.length - 4}', style: TextStyle(color: c.muted)),
                const Spacer(),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      money(o.total),
                      style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17, color: c.text),
                    ),
                    Text(itemsLabel(o.count), style: TextStyle(fontSize: 12, color: c.muted)),
                  ],
                ),
              ],
            ),
            if (quickActions && isNew) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: SoftButton(
                      label: 'Отклонить',
                      height: 44,
                      color: kDanger,
                      onPressed: () => rejectOrderFlow(context, o),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: GradientButton(
                      label: 'Принять',
                      height: 44,
                      onPressed: () {
                        s.acceptOrder(o);
                        showSnack(context, 'Заказ №${o.id} принят — начинайте собирать');
                      },
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

Future<void> rejectOrderFlow(BuildContext context, Order o) async {
  final s = StoreScope.read(context);
  final reason = await pickOne(
    context,
    title: 'Почему отклоняете заказ?',
    options: const ['Нет в наличии', 'Магазин закрывается', 'Не можем связаться с покупателем', 'Другое'],
  );
  if (reason == null) return;
  s.cancelOrder(o, reason);
  if (context.mounted) showSnack(context, 'Заказ №${o.id} отклонён');
}
