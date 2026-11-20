import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../format.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
    final c = AppColors.of(context);
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          const PageTitle('Профиль'),
          const _ProfileHeader(),
          const SectionHeader('Мои заказы'),
          if (s.orders.isEmpty)
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 16),
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(color: c.surface, borderRadius: BorderRadius.circular(20)),
              child: Row(
                children: [
                  const Text('📦', style: TextStyle(fontSize: 32)),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Text(
                      'Заказов пока нет.\nОформите первый — с промокодом WELCOME дарим 500 $kCurrency',
                      style: TextStyle(color: c.muted, height: 1.4),
                    ),
                  ),
                ],
              ),
            )
          else
            for (final o in s.orders) _OrderCard(order: o),
          const SectionHeader('Настройки'),
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), boxShadow: c.cardShadow),
            child: Material(
              color: c.surface,
              borderRadius: BorderRadius.circular(20),
              clipBehavior: Clip.antiAlias,
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Тема оформления',
                          style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                        ),
                        const SizedBox(height: 10),
                        SizedBox(
                          width: double.infinity,
                          child: SegmentedButton<ThemeMode>(
                            showSelectedIcon: false,
                            segments: const [
                              ButtonSegment(value: ThemeMode.light, label: Text('☀️ Светлая')),
                              ButtonSegment(value: ThemeMode.dark, label: Text('🌙 Тёмная')),
                              ButtonSegment(value: ThemeMode.system, label: Text('📱 Авто')),
                            ],
                            selected: {s.themeMode},
                            onSelectionChanged: (v) => s.setThemeMode(v.first),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Divider(indent: 16, endIndent: 16),
                  _SettingsTile(
                    icon: Icons.local_offer_outlined,
                    title: 'Промокоды',
                    onTap: () => _showPromos(context),
                  ),
                  const Divider(indent: 16, endIndent: 16),
                  _SettingsTile(
                    icon: Icons.info_outline_rounded,
                    title: 'О приложении',
                    onTap: () => _showAbout(context),
                  ),
                  if (s.orders.isNotEmpty) ...[
                    const Divider(indent: 16, endIndent: 16),
                    _SettingsTile(
                      icon: Icons.delete_sweep_outlined,
                      title: 'Очистить историю заказов',
                      danger: true,
                      onTap: () async {
                        final ok = await showDialog<bool>(
                          context: context,
                          builder: (ctx) => AlertDialog(
                            title: const Text('Очистить историю?'),
                            content: const Text('Список ваших заказов будет удалён с этого телефона.'),
                            actions: [
                              TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
                              TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Очистить')),
                            ],
                          ),
                        );
                        if (ok == true) s.clearOrders();
                      },
                    ),
                  ],
                ],
              ),
            ),
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
                    child: Material(
                      color: c.accentSoft,
                      borderRadius: BorderRadius.circular(16),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(16),
                        onTap: () {
                          Clipboard.setData(ClipboardData(text: p.code));
                          Navigator.pop(ctx);
                          showSnack(context, 'Промокод ${p.code} скопирован');
                        },
                        child: Padding(
                          padding: const EdgeInsets.all(14),
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
                                      style: TextStyle(
                                        fontWeight: FontWeight.w900,
                                        color: c.accentText,
                                        letterSpacing: 1,
                                      ),
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
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showAbout(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        icon: const Text('🛍️', style: TextStyle(fontSize: 44)),
        title: const Text('Витрина 1.0'),
        content: const Text(
          'Демо-маркетплейс на Flutter.\nЗаказы, корзина и избранное хранятся на вашем телефоне.',
          textAlign: TextAlign.center,
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Понятно'))],
      ),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  const _ProfileHeader();

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
    final name = s.name.isEmpty ? 'Гость' : s.name;
    final initial = s.name.isEmpty ? '😊' : s.name.characters.first.toUpperCase();
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 0),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: kHeaderGradient,
        borderRadius: BorderRadius.circular(28),
        boxShadow: const [
          BoxShadow(color: Color(0x557B2FF7), blurRadius: 30, offset: Offset(0, 14), spreadRadius: -12),
        ],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 62,
                height: 62,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: const Color(0x33FFFFFF),
                  shape: BoxShape.circle,
                  border: Border.all(color: const Color(0x66FFFFFF), width: 2),
                ),
                child: Text(
                  initial,
                  style: const TextStyle(fontSize: 26, color: Colors.white, fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white, fontSize: 21, fontWeight: FontWeight.w800),
                    ),
                    Text(
                      s.phone.isEmpty ? 'Покупатель «Витрины»' : s.phone,
                      style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 14),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              _Stat(value: '${s.orders.length}', label: plural(s.orders.length, 'заказ', 'заказа', 'заказов')),
              const SizedBox(width: 10),
              _Stat(value: '${s.favorites.length}', label: 'в избранном'),
              const SizedBox(width: 10),
              _Stat(value: money(s.totalSaved), label: 'сэкономлено'),
            ],
          ),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) => Expanded(
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
      decoration: BoxDecoration(color: const Color(0x29FFFFFF), borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          FittedBox(
            child: Text(
              value,
              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 12),
          ),
        ],
      ),
    ),
  );
}

class _SettingsTile extends StatelessWidget {
  const _SettingsTile({required this.icon, required this.title, required this.onTap, this.danger = false});

  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final color = danger ? const Color(0xFFE5484D) : c.text;
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: danger ? color : c.accentText),
      title: Text(
        title,
        style: TextStyle(fontWeight: FontWeight.w600, color: color),
      ),
      trailing: Icon(Icons.chevron_right_rounded, color: c.muted),
    );
  }
}

class _OrderCard extends StatelessWidget {
  const _OrderCard({required this.order});

  final Order order;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final status = order.status;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
      child: Material(
        color: c.surface,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: () => _showDetails(context),
          child: Padding(
            padding: const EdgeInsets.all(14),
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
                    _StatusChip(status: status),
                  ],
                ),
                const SizedBox(height: 2),
                Text(formatDate(order.createdAt), style: TextStyle(fontSize: 12.5, color: c.muted)),
                const SizedBox(height: 12),
                Row(
                  children: [
                    for (final l in order.lines.take(4))
                      Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: EmojiTile(line: l, size: 42),
                      ),
                    if (order.lines.length > 4)
                      Text(
                        '+${order.lines.length - 4}',
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
        ),
      ),
    );
  }

  void _showDetails(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) {
        final c = AppColors.of(ctx);
        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: .7,
          maxChildSize: .92,
          builder: (_, scroll) => ListView(
            controller: scroll,
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Заказ №${order.id}',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: c.text),
                    ),
                  ),
                  _StatusChip(status: order.status),
                ],
              ),
              Text(formatDate(order.createdAt), style: TextStyle(color: c.muted)),
              const SizedBox(height: 14),
              for (final l in order.lines)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      EmojiTile(line: l, size: 48),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              l.title,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontWeight: FontWeight.w600, color: c.text),
                            ),
                            Text(
                              '${l.option == null ? '' : '${l.option} · '}${l.qty} шт.',
                              style: TextStyle(fontSize: 12.5, color: c.muted),
                            ),
                          ],
                        ),
                      ),
                      Text(
                        money(l.price * l.qty),
                        style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                      ),
                    ],
                  ),
                ),
              const Padding(padding: EdgeInsets.symmetric(vertical: 10), child: Divider()),
              SummaryRow('Товары', money(order.itemsTotal)),
              if (order.discount > 0) SummaryRow('Скидки', '−${money(order.discount)}', color: kPink),
              SummaryRow('Доставка', order.deliveryFee == 0 ? 'бесплатно' : money(order.deliveryFee)),
              SummaryRow('Итого', money(order.total), big: true),
              const SizedBox(height: 14),
              _InfoLine(icon: Icons.person_outline_rounded, text: '${order.name}, ${order.phone}'),
              _InfoLine(
                icon: order.courier ? Icons.local_shipping_outlined : Icons.storefront_outlined,
                text: order.address,
              ),
              _InfoLine(icon: Icons.payments_outlined, text: order.payment),
              if (order.comment.isNotEmpty) _InfoLine(icon: Icons.chat_bubble_outline_rounded, text: order.comment),
            ],
          ),
        );
      },
    );
  }
}

class _InfoLine extends StatelessWidget {
  const _InfoLine({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: c.accentText),
          const SizedBox(width: 10),
          Expanded(
            child: Text(text, style: TextStyle(color: c.text, height: 1.35)),
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final OrderStatus status;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
    decoration: BoxDecoration(color: status.color.withValues(alpha: .13), borderRadius: BorderRadius.circular(99)),
    child: Text(
      status.label,
      style: TextStyle(color: status.color, fontWeight: FontWeight.w800, fontSize: 12.5),
    ),
  );
}
