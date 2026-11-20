import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'buyer_common.dart';
import 'order_screen.dart';

class SuccessScreen extends StatelessWidget {
  const SuccessScreen({super.key, required this.orders});

  final List<Order> orders;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final total = orders.fold(0, (a, o) => a + o.total);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const Spacer(),
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: 1),
                duration: const Duration(milliseconds: 900),
                curve: Curves.elasticOut,
                builder: (_, v, child) => Transform.scale(scale: v, child: child),
                child: Container(
                  width: 132,
                  height: 132,
                  decoration: BoxDecoration(
                    gradient: c.headerGradient,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: c.accent.withValues(alpha: .4),
                        blurRadius: 40,
                        offset: const Offset(0, 16),
                        spreadRadius: -8,
                      ),
                    ],
                  ),
                  child: const Icon(Icons.check_rounded, color: Colors.white, size: 72),
                ),
              ),
              const SizedBox(height: 28),
              Text(
                orders.length > 1 ? 'Оформлено ${ordersLabel(orders.length)}' : 'Заказ оформлен',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, letterSpacing: -0.5, color: c.text),
              ),
              const SizedBox(height: 8),
              Text(
                orders.map((o) => '№${o.id}').join(', '),
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: c.accentText),
              ),
              const SizedBox(height: 14),
              Text(
                'Магазин подтвердит заказ в течение пары минут.\nСледите за статусом в разделе «Мои заказы».',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 15, height: 1.45, color: c.muted),
              ),
              const SizedBox(height: 18),
              AppCard(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                child: Column(
                  children: [
                    for (final o in orders)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          children: [
                            ImageTile(
                              image: s.shopById(o.shopId)?.logo ?? 'bags',
                              categoryId: s.shopById(o.shopId)?.categoryId ?? 'electronics',
                              size: 34,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                s.shopById(o.shopId)?.name ?? '',
                                style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                              ),
                            ),
                            Text(
                              money(o.total),
                              style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                            ),
                          ],
                        ),
                      ),
                    if (orders.length > 1) ...[const Divider(height: 16), SummaryRow('Всего', money(total), big: true)],
                  ],
                ),
              ),
              const Spacer(flex: 2),
              GradientButton(
                label: orders.length == 1 ? 'Следить за заказом' : 'Мои заказы',
                onPressed: () {
                  if (orders.length == 1) {
                    Navigator.of(
                      context,
                    ).pushReplacement(MaterialPageRoute<void>(builder: (_) => OrderScreen(orderId: orders.first.id)));
                  } else {
                    goToTab(context, BuyerNav.profile);
                  }
                },
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => goToTab(context, BuyerNav.home),
                child: Text(
                  'Продолжить покупки',
                  style: TextStyle(color: c.accentText, fontWeight: FontWeight.w700, fontSize: 15),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
