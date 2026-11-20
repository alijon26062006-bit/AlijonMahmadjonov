import 'package:material_ui/material_ui.dart';

import '../format.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

class SuccessScreen extends StatelessWidget {
  const SuccessScreen({super.key, required this.order});

  final Order order;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
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
                  decoration: const BoxDecoration(
                    gradient: kHeaderGradient,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(color: Color(0x667B2FF7), blurRadius: 40, offset: Offset(0, 16), spreadRadius: -8),
                    ],
                  ),
                  child: const Icon(Icons.check_rounded, color: Colors.white, size: 72),
                ),
              ),
              const SizedBox(height: 28),
              Text(
                'Заказ оформлен! 🎉',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 26, fontWeight: FontWeight.w900, letterSpacing: -0.5, color: c.text),
              ),
              const SizedBox(height: 8),
              Text(
                'Номер заказа №${order.id}',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: c.accentText),
              ),
              const SizedBox(height: 14),
              Text(
                order.courier
                    ? 'Курьер привезёт заказ завтра по адресу:\n${order.address}'
                    : 'Заберите заказ сегодня после 18:00:\n${order.address}',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 15, height: 1.45, color: c.muted),
              ),
              const SizedBox(height: 18),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: c.surface,
                  borderRadius: BorderRadius.circular(18),
                  boxShadow: c.cardShadow,
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [for (final l in order.lines.take(5)) EmojiTile(line: l, size: 40)],
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(itemsLabel(order.count), style: TextStyle(fontSize: 12.5, color: c.muted)),
                        Text(
                          money(order.total),
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: c.text),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const Spacer(flex: 2),
              GradientButton(label: 'Продолжить покупки', onPressed: () => goToTab(context, AppNav.home)),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => goToTab(context, AppNav.profile),
                child: Text(
                  'Мои заказы',
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
