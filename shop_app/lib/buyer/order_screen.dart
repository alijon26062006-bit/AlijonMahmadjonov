import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

/// Отслеживание заказа покупателем: статус обновляется сам.
class OrderScreen extends StatelessWidget {
  const OrderScreen({super.key, required this.orderId});

  final String orderId;

  String _headline(Order o) => switch (o.status) {
    OrderStatus.placed => 'Ждём подтверждения магазина',
    OrderStatus.accepted => 'Магазин собирает заказ',
    OrderStatus.ready => o.delivery ? 'Заказ собран, ищем курьера' : 'Заказ ждёт вас в магазине',
    OrderStatus.delivering => 'Курьер едет к вам',
    OrderStatus.delivered => o.delivery ? 'Заказ доставлен' : 'Заказ получен',
    OrderStatus.cancelled => 'Заказ отменён',
  };

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final o = s.orderById(orderId);
    if (o == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const EmptyState(image: 'search', title: 'Заказ не найден', subtitle: ''),
      );
    }
    final shop = s.shopById(o.shopId);
    final courier = s.courierById(o.courierId);
    return Scaffold(
      appBar: AppBar(title: Text('Заказ №${o.id}')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: o.status == OrderStatus.cancelled
                  ? const LinearGradient(colors: [Color(0xFFE5484D), Color(0xFFFF7A59)])
                  : c.headerGradient,
              borderRadius: BorderRadius.circular(24),
            ),
            child: Row(
              children: [
                Container(
                  width: 54,
                  height: 54,
                  decoration: BoxDecoration(color: const Color(0x33FFFFFF), borderRadius: BorderRadius.circular(18)),
                  child: Icon(o.status.icon, color: Colors.white, size: 28),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _headline(o),
                        style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Обновлено ${timeAgo(o.updatedAt)}',
                        style: const TextStyle(color: Color(0xD9FFFFFF), fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          AppCard(child: OrderTimeline(order: o)),
          if (o.cancelReason != null) ...[
            const SizedBox(height: 10),
            AppCard(
              child: InfoLine(icon: Icons.info_outline_rounded, title: 'Причина отмены', text: o.cancelReason!),
            ),
          ],
          if (courier != null && o.status.isActive) ...[
            const FieldLabel('Курьер'),
            AppCard(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 24,
                    backgroundColor: c.accentSoft,
                    child: Icon(vehicleIcon(courier.vehicle), color: c.accentText),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          courier.name,
                          style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                        ),
                        Text('Рейтинг ${ratingText(courier.rating)}', style: TextStyle(color: c.muted, fontSize: 13)),
                      ],
                    ),
                  ),
                  CircleButton(
                    icon: Icons.call_rounded,
                    background: c.accentSoft,
                    color: c.accentText,
                    onTap: () => callPhone(context, courier.phone),
                  ),
                ],
              ),
            ),
          ],
          const FieldLabel('Магазин'),
          AppCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            child: Column(
              children: [
                InfoLine(
                  icon: Icons.storefront_outlined,
                  title: shop?.name ?? '',
                  text: shop?.address ?? '',
                  trailing: shop == null
                      ? null
                      : IconButton(
                          icon: Icon(Icons.call_rounded, color: c.accentText),
                          onPressed: () => callPhone(context, shop.ownerPhone),
                        ),
                ),
                InfoLine(
                  icon: o.delivery ? Icons.location_on_outlined : Icons.directions_walk_rounded,
                  title: o.delivery ? 'Доставка по адресу' : 'Самовывоз',
                  text: o.address,
                ),
                InfoLine(icon: Icons.payments_outlined, title: 'Оплата', text: o.payment),
                if (o.comment.isNotEmpty)
                  InfoLine(icon: Icons.chat_bubble_outline_rounded, title: 'Комментарий', text: o.comment),
              ],
            ),
          ),
          const FieldLabel('Состав заказа'),
          AppCard(
            child: Column(
              children: [
                OrderItemsList(order: o, categoryOf: (id) => s.productById(id)?.categoryId ?? 'electronics'),
                const Divider(height: 20),
                SummaryRow('Товары', money(o.itemsTotal)),
                if (o.discount > 0) SummaryRow('Скидка', '−${money(o.discount)}', color: c.gradientColors.last),
                SummaryRow('Доставка', o.deliveryFee == 0 ? 'бесплатно' : money(o.deliveryFee)),
                SummaryRow('Итого', money(o.total), big: true),
              ],
            ),
          ),
          if (o.status == OrderStatus.placed) ...[
            const SizedBox(height: 16),
            SoftButton(
              label: 'Отменить заказ',
              icon: Icons.close_rounded,
              color: kDanger,
              onPressed: () async {
                if (await confirm(context, title: 'Отменить заказ №${o.id}?', ok: 'Отменить', danger: true)) {
                  s.cancelMyOrder(o);
                }
              },
            ),
          ],
        ],
      ),
    );
  }
}
