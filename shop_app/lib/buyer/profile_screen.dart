import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/auth.dart';
import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/settings_card.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'order_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final user = s.user;
    final orders = s.myOrders;
    final saved = orders.where((o) => o.status != OrderStatus.cancelled).fold(0, (a, o) => a + o.discount);
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          const PageTitle('Профиль'),
          ProfileHeader(
            title: user == null ? 'Гость' : (user.name.isEmpty ? 'Покупатель' : user.name),
            subtitle: user == null ? 'Войдите, чтобы видеть заказы' : formatPhone(user.phone),
            avatar: user == null || user.name.isEmpty ? '😊' : user.name.characters.first.toUpperCase(),
            stats: [
              ('${orders.length}', plural(orders.length, 'заказ', 'заказа', 'заказов')),
              ('${s.favorites.length}', 'в избранном'),
              (money(saved), 'сэкономлено'),
            ],
            action: user == null
                ? FilledButton(
                    style: FilledButton.styleFrom(backgroundColor: Colors.white, foregroundColor: c.accent),
                    onPressed: () => showLogin(context, Role.buyer),
                    child: const Text('Войти', style: TextStyle(fontWeight: FontWeight.w800)),
                  )
                : null,
          ),
          const SectionHeader('Мои заказы'),
          if (orders.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: AppCard(
                child: Row(
                  children: [
                    const Text('📦', style: TextStyle(fontSize: 32)),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Text(
                        'Заказов пока нет.\nС промокодом WELCOME — минус 30 смн на первый заказ',
                        style: TextStyle(color: c.muted, height: 1.4),
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            for (final o in orders) BuyerOrderCard(order: o),
          const SectionHeader('Настройки'),
          CommonSettings(
            extra: [
              SettingsTile(icon: Icons.local_offer_outlined, title: 'Промокоды', onTap: () => _showPromos(context)),
            ],
          ),
        ],
      ),
    );
  }

  void _showPromos(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) {
        final c = AppColors.of(ctx);
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Промокоды',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: c.text),
                ),
                const SizedBox(height: 4),
                Text('Нажмите, чтобы скопировать, и введите в корзине', style: TextStyle(color: c.muted)),
                const SizedBox(height: 14),
                for (final p in kPromos)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: AppCard(
                      color: c.accentSoft,
                      padding: const EdgeInsets.all(14),
                      onTap: () {
                        Clipboard.setData(ClipboardData(text: p.code));
                        Navigator.pop(ctx);
                        showSnack(context, 'Промокод ${p.code} скопирован');
                      },
                      child: Row(
                        children: [
                          const Text('🎁', style: TextStyle(fontSize: 26)),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  p.code,
                                  style: TextStyle(fontWeight: FontWeight.w900, color: c.accentText, letterSpacing: 1),
                                ),
                                Text(p.title, style: TextStyle(fontSize: 13, color: c.muted)),
                              ],
                            ),
                          ),
                          Icon(Icons.copy_rounded, color: c.muted, size: 20),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class BuyerOrderCard extends StatelessWidget {
  const BuyerOrderCard({super.key, required this.order});

  final Order order;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final shop = s.shopById(order.shopId);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
      child: AppCard(
        padding: const EdgeInsets.all(14),
        onTap: () =>
            Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => OrderScreen(orderId: order.id))),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Заказ №${order.id}',
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, color: c.text),
                  ),
                ),
                StatusPill.order(order),
              ],
            ),
            const SizedBox(height: 2),
            Text(
              '${shop?.name ?? ''} · ${formatWhen(order.createdAt)}',
              style: TextStyle(fontSize: 12.5, color: c.muted),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                for (final i in order.items.take(4))
                  Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: EmojiTile(
                      emoji: i.emoji,
                      categoryId: s.productById(i.productId)?.categoryId ?? 'electronics',
                      size: 42,
                    ),
                  ),
                if (order.items.length > 4)
                  Text(
                    '+${order.items.length - 4}',
                    style: TextStyle(color: c.muted, fontWeight: FontWeight.w700),
                  ),
                const Spacer(),
                Text(
                  money(order.total),
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17, color: c.text),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
