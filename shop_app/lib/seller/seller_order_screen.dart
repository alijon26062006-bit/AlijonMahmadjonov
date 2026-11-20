import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'seller_widgets.dart';

/// Заказ глазами продавца: покупатель, состав, деньги и кнопка следующего шага.
class SellerOrderScreen extends StatelessWidget {
  const SellerOrderScreen({super.key, required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final o = s.orderById(orderId);
    if (o == null) return Scaffold(appBar: AppBar(), body: const SizedBox());
    final courier = s.courierById(o.courierId);

    return Scaffold(
      appBar: AppBar(
        title: Text('Заказ №${o.id}'),
        actions: [Padding(padding: const EdgeInsets.only(right: 16), child: StatusPill.order(o))],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
        children: [
          Text(
            '${formatDate(o.createdAt)} · ${o.delivery ? 'доставка курьером' : 'самовывоз'}',
            style: TextStyle(color: c.muted),
          ),
          const FieldLabel('Покупатель'),
          AppCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            child: Column(
              children: [
                InfoLine(
                  icon: Icons.person_outline_rounded,
                  title: o.buyerName,
                  text: formatPhone(o.buyerPhone),
                  trailing: IconButton(
                    icon: Icon(Icons.call_rounded, color: c.accentText),
                    onPressed: () => callPhone(context, o.buyerPhone),
                  ),
                ),
                if (o.delivery) InfoLine(icon: Icons.location_on_outlined, title: 'Адрес доставки', text: o.address),
                InfoLine(icon: Icons.payments_outlined, title: 'Оплата', text: o.payment),
                if (o.comment.isNotEmpty)
                  InfoLine(icon: Icons.chat_bubble_outline_rounded, title: 'Комментарий', text: o.comment),
              ],
            ),
          ),
          if (courier != null) ...[
            const FieldLabel('Курьер'),
            AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              child: InfoLine(
                icon: Icons.delivery_dining_rounded,
                title: '${courier.vehicle} ${courier.name}',
                text: formatPhone(courier.phone),
                trailing: IconButton(
                  icon: Icon(Icons.call_rounded, color: c.accentText),
                  onPressed: () => callPhone(context, courier.phone),
                ),
              ),
            ),
          ],
          const FieldLabel('Собрать'),
          AppCard(
            child: OrderItemsList(order: o, categoryOf: (id) => s.productById(id)?.categoryId ?? 'electronics'),
          ),
          const FieldLabel('Деньги'),
          AppCard(
            child: Column(
              children: [
                SummaryRow('Товары', money(o.itemsTotal)),
                if (o.discount > 0) SummaryRow('Скидка по промокоду', '−${money(o.discount)}'),
                SummaryRow('Комиссия маркетплейса', '−${money(o.commission)}'),
                const Divider(height: 18),
                SummaryRow('Вы получите', money(sellerIncome(o)), big: true, color: kSuccess),
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Покупатель платит ${money(o.total)} (включая доставку ${money(o.deliveryFee)})',
                    style: TextStyle(fontSize: 12.5, color: c.muted),
                  ),
                ),
              ],
            ),
          ),
          const FieldLabel('История'),
          AppCard(child: OrderTimeline(order: o)),
          if (o.cancelReason != null) ...[
            const SizedBox(height: 10),
            AppCard(
              child: InfoLine(icon: Icons.info_outline_rounded, title: 'Причина отмены', text: o.cancelReason!),
            ),
          ],
        ],
      ),
      bottomNavigationBar: _actions(context, s, o),
    );
  }

  Widget? _actions(BuildContext context, MarketStore s, Order o) {
    switch (o.status) {
      case OrderStatus.placed:
        return BottomBar(
          child: Row(
            children: [
              Expanded(
                child: SoftButton(label: 'Отклонить', color: kDanger, onPressed: () => rejectOrderFlow(context, o)),
              ),
              const SizedBox(width: 10),
              Expanded(
                flex: 2,
                child: GradientButton(
                  label: 'Принять заказ',
                  icon: Icons.check_rounded,
                  onPressed: () => s.acceptOrder(o),
                ),
              ),
            ],
          ),
        );
      case OrderStatus.accepted:
        return BottomBar(
          child: Row(
            children: [
              SoftButton(label: 'Отменить', color: kDanger, onPressed: () => rejectOrderFlow(context, o)),
              const SizedBox(width: 10),
              Expanded(
                child: GradientButton(
                  label: o.delivery ? 'Собран, передать курьеру' : 'Собран, ждёт покупателя',
                  icon: Icons.inventory_2_outlined,
                  onPressed: () => s.markReady(o),
                ),
              ),
            ],
          ),
        );
      case OrderStatus.ready when !o.delivery:
        return BottomBar(
          child: GradientButton(
            label: 'Покупатель забрал заказ',
            icon: Icons.handshake_outlined,
            colors: const [Color(0xFF18A957), Color(0xFF34C77B)],
            onPressed: () => s.markHandedOver(o),
          ),
        );
      case OrderStatus.ready:
        return BottomBar(
          child: SoftButton(
            label: o.courierId == null ? 'Ищем курьера…' : 'Курьер едет в магазин',
            icon: Icons.delivery_dining_rounded,
            onPressed: null,
          ),
        );
      case OrderStatus.delivering:
      case OrderStatus.delivered:
      case OrderStatus.cancelled:
        return null;
    }
  }
}
