import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'courier_widgets.dart';

/// Доставка по шагам: забрать в магазине → отвезти покупателю.
class DeliveryScreen extends StatelessWidget {
  const DeliveryScreen({super.key, required this.orderId});

  final String orderId;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final o = s.orderById(orderId);
    if (o == null) return Scaffold(appBar: AppBar(), body: const SizedBox());
    final shop = s.shopById(o.shopId);
    final mine = o.courierId == s.me?.id;
    final pickedUp = o.status == OrderStatus.delivering || o.status == OrderStatus.delivered;
    final finished = o.status.isFinal;

    return Scaffold(
      appBar: AppBar(title: Text('Заказ №${o.id}')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
        children: [
          // «Карта» маршрута — схематично, пока нет карт и GPS.
          Container(
            height: 150,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(gradient: c.headerGradient, borderRadius: BorderRadius.circular(24)),
            child: Row(
              children: [
                _MapPin(image: shop?.logo ?? 'store', label: 'Магазин', done: pickedUp),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '${demoDistance(o).toStringAsFixed(1)} км',
                        style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          for (var i = 0; i < 9; i++)
                            Expanded(
                              child: Container(
                                height: 3,
                                margin: const EdgeInsets.symmetric(horizontal: 2),
                                decoration: BoxDecoration(
                                  color: Color(pickedUp && i < 5 ? 0xFFFFFFFF : 0x66FFFFFF),
                                  borderRadius: BorderRadius.circular(2),
                                ),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '~${demoMinutes(o)} мин в пути',
                        style: const TextStyle(color: Color(0xDDFFFFFF), fontSize: 13),
                      ),
                    ],
                  ),
                ),
                _MapPin(image: 'house', label: 'Покупатель', done: o.status == OrderStatus.delivered),
              ],
            ),
          ),
          const SizedBox(height: 14),
          if (o.status == OrderStatus.cancelled)
            AppCard(
              child: InfoLine(icon: Icons.cancel_outlined, title: 'Заказ отменён', text: o.cancelReason ?? ''),
            ),
          _Step(
            number: 1,
            title: 'Забрать в магазине',
            done: pickedUp,
            active: !pickedUp && !finished,
            children: [
              InfoLine(
                icon: Icons.storefront_outlined,
                title: shop?.name ?? 'Магазин',
                text: shop?.address ?? '',
                onTap: shop == null ? null : () => openMap(context, shop.address),
              ),
              if (!pickedUp && !finished) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(
                      child: SoftButton(
                        label: 'Позвонить',
                        icon: Icons.call_rounded,
                        height: 44,
                        onPressed: shop == null ? null : () => callPhone(context, shop.ownerPhone),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: SoftButton(
                        label: 'Маршрут',
                        icon: Icons.navigation_outlined,
                        height: 44,
                        onPressed: shop == null ? null : () => openMap(context, shop.address),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  'Что забрать:',
                  style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                ),
                OrderItemsList(order: o, categoryOf: (id) => s.productById(id)?.categoryId ?? 'electronics'),
              ],
            ],
          ),
          _Step(
            number: 2,
            title: 'Отвезти покупателю',
            done: o.status == OrderStatus.delivered,
            active: o.status == OrderStatus.delivering,
            children: [
              InfoLine(
                icon: Icons.location_on_outlined,
                title: o.buyerName,
                text: o.address,
                onTap: () => openMap(context, o.address),
              ),
              if (o.comment.isNotEmpty)
                InfoLine(icon: Icons.chat_bubble_outline_rounded, title: 'Комментарий', text: o.comment),
              InfoLine(
                icon: Icons.payments_outlined,
                title: 'Оплата: ${o.payment}',
                text: cashToCollect(o) == 0 ? 'Уже оплачен' : 'Взять с покупателя ${money(cashToCollect(o))}',
              ),
              if (!finished) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(
                      child: SoftButton(
                        label: 'Позвонить',
                        icon: Icons.call_rounded,
                        height: 44,
                        onPressed: () => callPhone(context, o.buyerPhone),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: SoftButton(
                        label: 'Маршрут',
                        icon: Icons.navigation_outlined,
                        height: 44,
                        onPressed: () => openMap(context, o.address),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
          const SizedBox(height: 4),
          AppCard(
            child: Row(
              children: [
                Icon(Icons.account_balance_wallet_outlined, color: c.accentText),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Вы заработаете',
                    style: TextStyle(color: c.text, fontWeight: FontWeight.w600),
                  ),
                ),
                Text(
                  money(o.courierPay),
                  style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: kSuccess),
                ),
              ],
            ),
          ),
          if (mine && !pickedUp && !finished) ...[
            const SizedBox(height: 14),
            Center(
              child: TextButton(
                onPressed: () async {
                  if (await confirm(
                    context,
                    title: 'Отказаться от заказа?',
                    text: 'Заказ вернётся в общий список.',
                    ok: 'Отказаться',
                    danger: true,
                  )) {
                    s.releaseOrder(o);
                    if (context.mounted) Navigator.of(context).pop();
                  }
                },
                child: const Text(
                  'Отказаться от заказа',
                  style: TextStyle(color: kDanger, fontWeight: FontWeight.w700),
                ),
              ),
            ),
          ],
        ],
      ),
      bottomNavigationBar: !mine || finished ? null : BottomBar(child: _action(context, s, o)),
    );
  }

  Widget _action(BuildContext context, MarketStore s, Order o) {
    switch (o.status) {
      case OrderStatus.placed:
      case OrderStatus.accepted:
        return const SoftButton(label: 'Магазин собирает заказ…', icon: Icons.hourglass_top_rounded, onPressed: null);
      case OrderStatus.ready:
        return GradientButton(
          label: 'Забрал заказ',
          icon: Icons.inventory_2_outlined,
          onPressed: () {
            HapticFeedback.mediumImpact();
            s.pickUp(o);
          },
        );
      case OrderStatus.delivering:
        return GradientButton(
          label: 'Доставил',
          icon: Icons.check_circle_outline_rounded,
          colors: const [Color(0xFF18A957), Color(0xFF34C77B)],
          onPressed: () async {
            final cash = cashToCollect(o);
            final ok = await confirm(
              context,
              title: 'Заказ передан покупателю?',
              text: cash > 0 ? 'Не забудьте взять ${money(cash)}.' : null,
              ok: 'Да, доставил',
            );
            if (!ok) return;
            s.deliver(o);
            HapticFeedback.heavyImpact();
            if (context.mounted) {
              Navigator.of(context).pop();
              showSnack(context, 'Заказ доставлен, +${money(o.courierPay)}');
            }
          },
        );
      case OrderStatus.delivered:
      case OrderStatus.cancelled:
        return const SizedBox.shrink();
    }
  }
}

class _MapPin extends StatelessWidget {
  const _MapPin({required this.image, required this.label, required this.done});

  final String image;
  final String label;
  final bool done;

  @override
  Widget build(BuildContext context) => Column(
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            width: 56,
            height: 56,
            alignment: Alignment.center,
            decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
            padding: const EdgeInsets.all(10),
            child: AppImage(image),
          ),
          if (done)
            const Positioned(
              right: -4,
              bottom: -4,
              child: CircleAvatar(
                radius: 11,
                backgroundColor: kSuccess,
                child: Icon(Icons.check_rounded, size: 15, color: Colors.white),
              ),
            ),
        ],
      ),
      const SizedBox(height: 6),
      Text(
        label,
        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12.5),
      ),
    ],
  );
}

class _Step extends StatelessWidget {
  const _Step({
    required this.number,
    required this.title,
    required this.done,
    required this.active,
    required this.children,
  });

  final int number;
  final String title;
  final bool done;
  final bool active;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppCard(
        color: active ? Color.alphaBlend(c.accentSoft.withValues(alpha: .5), c.surface) : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: done ? kSuccess : (active ? c.accent : c.chip),
                    shape: BoxShape.circle,
                  ),
                  child: done
                      ? const Icon(Icons.check_rounded, size: 17, color: Colors.white)
                      : Text(
                          '$number',
                          style: TextStyle(fontWeight: FontWeight.w800, color: active ? Colors.white : c.muted),
                        ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    title,
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: done || active ? c.text : c.muted,
                    ),
                  ),
                ),
                if (done) const StatusPill(label: 'Готово', color: kSuccess),
              ],
            ),
            const SizedBox(height: 8),
            ...children,
          ],
        ),
      ),
    );
  }
}
