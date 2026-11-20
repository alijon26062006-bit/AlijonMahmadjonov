import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

/// Демо-расстояние (км) до точки — пока нет карт и GPS. Стабильно для одного заказа.
double demoDistance(Order o) => 1.2 + (int.parse(o.id) * 37 % 53) / 10;

/// Примерное время в пути (мин).
int demoMinutes(Order o) => (demoDistance(o) * 4 + 6).round();

/// Сколько взять с покупателя при получении (если оплата не онлайн).
int cashToCollect(Order o) => o.payment == 'Онлайн' ? 0 : o.total;

/// Схематичный маршрут «Магазин → Покупатель».
class RouteStrip extends StatelessWidget {
  const RouteStrip({super.key, required this.shop, required this.order, this.compact = false});

  final Shop? shop;
  final Order order;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    Widget point(IconData icon, Color color, String title, String text) => Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(color: color.withValues(alpha: .14), shape: BoxShape.circle),
          child: Icon(icon, size: 17, color: color),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: TextStyle(fontSize: 12.5, color: c.muted)),
              Text(
                text,
                maxLines: compact ? 1 : 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontWeight: FontWeight.w700, color: c.text, height: 1.25),
              ),
            ],
          ),
        ),
      ],
    );
    return Column(
      children: [
        point(Icons.storefront_rounded, const Color(0xFFFF8A00), shop?.name ?? 'Магазин', shop?.address ?? ''),
        Padding(
          padding: const EdgeInsets.only(left: 14),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Column(
              children: [
                for (var i = 0; i < 3; i++)
                  Container(width: 2, height: 4, margin: const EdgeInsets.symmetric(vertical: 1.5), color: c.line),
              ],
            ),
          ),
        ),
        point(Icons.location_on_rounded, c.accentText, order.buyerName, order.address),
      ],
    );
  }
}

/// Карточка доступного заказа.
class DeliveryOfferCard extends StatelessWidget {
  const DeliveryOfferCard({super.key, required this.order, required this.onTake, required this.enabled});

  final Order order;
  final VoidCallback onTake;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final shop = s.shopById(order.shopId);
    final ready = order.status == OrderStatus.ready;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: AppCard(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  '+${money(order.courierPay)}',
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: kSuccess,
                    letterSpacing: -0.5,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    '${demoDistance(order).toStringAsFixed(1)} км · ~${demoMinutes(order)} мин',
                    style: TextStyle(color: c.muted, fontWeight: FontWeight.w600),
                  ),
                ),
                StatusPill(label: ready ? 'Готов' : 'Собирается', color: ready ? kSuccess : const Color(0xFFFF8A00)),
              ],
            ),
            const SizedBox(height: 12),
            RouteStrip(shop: shop, order: order, compact: true),
            const SizedBox(height: 10),
            Row(
              children: [
                Icon(Icons.inventory_2_outlined, size: 16, color: c.muted),
                const SizedBox(width: 4),
                Text(itemsLabel(order.count), style: TextStyle(color: c.muted, fontSize: 13)),
                const SizedBox(width: 12),
                Icon(Icons.payments_outlined, size: 16, color: c.muted),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    cashToCollect(order) == 0 ? 'Оплачен онлайн' : 'Взять ${money(cashToCollect(order))}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: c.muted, fontSize: 13),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            GradientButton(
              label: 'Взять заказ',
              height: 48,
              icon: Icons.check_rounded,
              onPressed: enabled ? onTake : null,
            ),
          ],
        ),
      ),
    );
  }
}
