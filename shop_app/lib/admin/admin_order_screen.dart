import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'admin_widgets.dart';

/// Заказ для админа: все участники, деньги, история и ручное управление.
class AdminOrderScreen extends StatelessWidget {
  const AdminOrderScreen({super.key, required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final o = s.orderById(orderId);
    if (o == null) return Scaffold(appBar: AppBar(), body: const SizedBox());
    final shop = s.shopById(o.shopId);
    final courier = s.courierById(o.courierId);
    final canAssign =
        o.delivery && o.courierId == null && (o.status == OrderStatus.accepted || o.status == OrderStatus.ready);

    return Scaffold(
      appBar: AppBar(
        title: Text('Заказ №${o.id}'),
        actions: [Padding(padding: const EdgeInsets.only(right: 16), child: StatusPill.order(o))],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
        children: [
          Text(
            '${formatDate(o.createdAt)} · ${o.delivery ? 'доставка' : 'самовывоз'} · ${o.payment}',
            style: TextStyle(color: c.muted),
          ),
          const FieldLabel('Участники'),
          AppCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            child: Column(
              children: [
                InfoLine(
                  icon: Icons.storefront_outlined,
                  title: 'Магазин',
                  text: shop?.name ?? '—',
                  onTap: shop == null ? null : () => openAdminShop(context, shop),
                  trailing: shop == null
                      ? null
                      : IconButton(
                          icon: Icon(Icons.call_rounded, color: c.accentText),
                          onPressed: () => callPhone(context, shop.ownerPhone),
                        ),
                ),
                InfoLine(
                  icon: Icons.person_outline_rounded,
                  title: 'Покупатель',
                  text: '${o.buyerName}, ${formatPhone(o.buyerPhone)}',
                  trailing: IconButton(
                    icon: Icon(Icons.call_rounded, color: c.accentText),
                    onPressed: () => callPhone(context, o.buyerPhone),
                  ),
                ),
                InfoLine(
                  icon: Icons.location_on_outlined,
                  title: o.delivery ? 'Адрес доставки' : 'Самовывоз',
                  text: o.address,
                ),
                if (o.delivery)
                  InfoLine(
                    icon: Icons.delivery_dining_outlined,
                    title: 'Курьер',
                    text: courier == null
                        ? 'Не назначен'
                        : '${courier.vehicle} ${courier.name}, ${formatPhone(courier.phone)}',
                    trailing: courier == null
                        ? null
                        : IconButton(
                            icon: Icon(Icons.call_rounded, color: c.accentText),
                            onPressed: () => callPhone(context, courier.phone),
                          ),
                  ),
                if (o.comment.isNotEmpty)
                  InfoLine(icon: Icons.chat_bubble_outline_rounded, title: 'Комментарий', text: o.comment),
              ],
            ),
          ),
          const FieldLabel('Состав'),
          AppCard(
            child: OrderItemsList(order: o, categoryOf: (id) => s.productById(id)?.categoryId ?? 'electronics'),
          ),
          const FieldLabel('Деньги'),
          AppCard(
            child: Column(
              children: [
                SummaryRow('Товары', money(o.itemsTotal)),
                if (o.discount > 0) SummaryRow('Скидка (промокод)', '−${money(o.discount)}'),
                SummaryRow('Доставка', money(o.deliveryFee)),
                SummaryRow('Покупатель платит', money(o.total), big: true),
                const Divider(height: 18),
                SummaryRow('Магазину', money(o.itemsTotal - o.discount - o.commission)),
                if (o.delivery) SummaryRow('Курьеру', money(o.courierPay)),
                SummaryRow('Маркетплейсу', money(o.commission + o.deliveryFee - o.courierPay), color: kSuccess),
              ],
            ),
          ),
          const FieldLabel('История'),
          AppCard(child: OrderTimeline(order: o)),
          if (o.history.any((e) => e.note != null)) ...[
            const SizedBox(height: 10),
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final e in o.history.where((e) => e.note != null))
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Text('${formatTime(e.at)} — ${e.note}', style: TextStyle(color: c.muted, fontSize: 13)),
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
      bottomNavigationBar: o.status.isFinal
          ? null
          : BottomBar(
              child: Row(
                children: [
                  Expanded(
                    child: SoftButton(
                      label: 'Отменить',
                      icon: Icons.close_rounded,
                      color: kDanger,
                      onPressed: () async {
                        final reason = await pickOne(
                          context,
                          title: 'Причина отмены',
                          options: const [
                            'По просьбе покупателя',
                            'Магазин не отвечает',
                            'Нет курьеров',
                            'Подозрительный заказ',
                            'Другое',
                          ],
                        );
                        if (reason != null) s.cancelOrder(o, 'Администратор: $reason');
                      },
                    ),
                  ),
                  if (canAssign) ...[
                    const SizedBox(width: 10),
                    Expanded(
                      flex: 2,
                      child: GradientButton(
                        label: 'Назначить курьера',
                        icon: Icons.person_add_alt_rounded,
                        onPressed: () => _assign(context, s, o),
                      ),
                    ),
                  ],
                ],
              ),
            ),
    );
  }

  Future<void> _assign(BuildContext context, MarketStore s, Order o) async {
    final free = s.couriers.where((x) => x.online && !x.blocked).toList();
    if (free.isEmpty) {
      showSnack(context, 'Нет курьеров на линии');
      return;
    }
    final picked = await showModalBottomSheet<Courier>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: Text(
                'Курьеры на линии',
                style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: AppColors.of(ctx).text),
              ),
            ),
            for (final x in free)
              ListTile(
                leading: Text(x.vehicle, style: const TextStyle(fontSize: 26)),
                title: Text(x.name),
                subtitle: Text(
                  s.orders.any((d) => d.courierId == x.id && d.status.isActive)
                      ? 'Сейчас на доставке'
                      : 'Свободен · ★ ${x.rating}',
                ),
                onTap: () => Navigator.pop(ctx, x),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (picked != null) {
      s.assignCourier(o, picked);
      if (context.mounted) showSnack(context, 'Назначен курьер ${picked.name}');
    }
  }
}
