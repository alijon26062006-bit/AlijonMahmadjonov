import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'courier_widgets.dart';
import 'delivery_screen.dart';

class CourierHomeScreen extends StatelessWidget {
  const CourierHomeScreen({super.key});

  void _openDelivery(BuildContext context, Order o) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => DeliveryScreen(orderId: o.id)));
  }

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final me = s.me!;
    final active = s.myActiveDelivery;
    final offers = s.availableDeliveries;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(child: _Header(courier: me)),
          if (active != null) ...[
            const SliverToBoxAdapter(child: SectionHeader('Текущая доставка')),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: AppCard(
                  onTap: () => _openDelivery(context, active),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Заказ №${active.id}',
                              style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: c.text),
                            ),
                          ),
                          StatusPill(
                            label: switch (active.status) {
                              OrderStatus.accepted => 'Магазин собирает',
                              OrderStatus.ready => 'Заберите в магазине',
                              OrderStatus.delivering => 'Везёте покупателю',
                              _ => active.statusLabel,
                            },
                            color: active.status.color,
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      RouteStrip(shop: s.shopById(active.shopId), order: active),
                      const SizedBox(height: 12),
                      GradientButton(
                        label: 'Открыть доставку',
                        icon: Icons.navigation_rounded,
                        height: 48,
                        onPressed: () => _openDelivery(context, active),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
          if (!me.online)
            SliverFillRemaining(
              hasScrollBody: false,
              child: EmptyState(
                emoji: '😴',
                title: 'Вы не на линии',
                subtitle: 'Выйдите на линию, чтобы видеть\nи брать новые заказы',
                buttonLabel: 'Выйти на линию',
                onButton: () => s.setOnline(true),
              ),
            )
          else ...[
            SliverToBoxAdapter(
              child: SectionHeader(
                active == null ? 'Доступные заказы · ${offers.length}' : 'Ещё заказы рядом · ${offers.length}',
              ),
            ),
            if (active != null)
              const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(16, 0, 16, 12),
                  child: DemoNote(text: 'Сначала завершите текущую доставку — потом можно взять следующий заказ.'),
                ),
              ),
            if (offers.isEmpty)
              const SliverFillRemaining(
                hasScrollBody: false,
                child: EmptyState(
                  emoji: '🛵',
                  title: 'Пока заказов нет',
                  subtitle: 'Новые заказы появятся здесь автоматически.\nОставайтесь на линии!',
                ),
              )
            else
              SliverList.builder(
                itemCount: offers.length,
                itemBuilder: (_, i) => DeliveryOfferCard(
                  order: offers[i],
                  enabled: active == null,
                  onTake: () {
                    if (s.takeOrder(offers[i])) {
                      HapticFeedback.mediumImpact();
                      _openDelivery(context, offers[i]);
                    } else {
                      showSnack(context, 'Заказ уже взял другой курьер');
                    }
                  },
                ),
              ),
            const SliverToBoxAdapter(child: SizedBox(height: 16)),
          ],
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.courier});

  final Courier courier;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final top = MediaQuery.paddingOf(context).top;
    final today = s.myDeliveries.where((o) => sameDay(o.updatedAt, DateTime.now())).toList();
    final earned = today.fold(0, (a, o) => a + o.courierPay);
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
                child: Text(courier.vehicle, style: const TextStyle(fontSize: 28)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Курьер', style: TextStyle(color: Color(0xDDFFFFFF), fontSize: 14)),
                    Text(
                      courier.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 23,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.5,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (courier.blocked)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: const Color(0x33000000), borderRadius: BorderRadius.circular(16)),
              child: const Text(
                'Аккаунт заблокирован администратором',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
              ),
            )
          else
            Material(
              color: const Color(0x2EFFFFFF),
              borderRadius: BorderRadius.circular(16),
              child: SwitchListTile(
                value: courier.online,
                onChanged: (v) {
                  HapticFeedback.selectionClick();
                  s.setOnline(v);
                },
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                activeThumbColor: Colors.white,
                activeTrackColor: const Color(0xFF2BD47D),
                title: Text(
                  courier.online ? 'Вы на линии' : 'Вы не на линии',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800),
                ),
                subtitle: Text(
                  courier.online ? 'Получаете новые заказы' : 'Заказы не приходят',
                  style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 12.5),
                ),
              ),
            ),
          const SizedBox(height: 12),
          Row(
            children: [
              _MiniStat(value: money(earned), label: 'сегодня'),
              const SizedBox(width: 10),
              _MiniStat(value: '${today.length}', label: plural(today.length, 'доставка', 'доставки', 'доставок')),
              const SizedBox(width: 10),
              _MiniStat(value: '★ ${courier.rating.toStringAsFixed(1)}', label: 'рейтинг'),
            ],
          ),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) => Expanded(
    child: Container(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
      decoration: BoxDecoration(color: const Color(0x29FFFFFF), borderRadius: BorderRadius.circular(14)),
      child: Column(
        children: [
          FittedBox(
            child: Text(
              value,
              style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800),
            ),
          ),
          Text(label, style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 12)),
        ],
      ),
    ),
  );
}
