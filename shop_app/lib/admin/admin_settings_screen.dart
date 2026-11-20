import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/settings_card.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

/// Правила маркетплейса: комиссия, доставка, оплата курьеру.
class AdminSettingsScreen extends StatelessWidget {
  const AdminSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final st = s.settings;
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          PageTitle('Настройки', subtitle: s.user == null ? null : 'Администратор · ${formatPhone(s.user!.phone)}'),
          const SectionHeader('Правила маркетплейса'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              child: Column(
                children: [
                  _NumberRow(
                    title: 'Комиссия с заказа',
                    value: st.commissionPercent,
                    suffix: '%',
                    step: 1,
                    max: 50,
                    onChanged: (v) {
                      st.commissionPercent = v;
                      s.saveSettings();
                    },
                  ),
                  const Divider(),
                  _NumberRow(
                    title: 'Доставка для покупателя',
                    value: st.deliveryFee,
                    suffix: ' $kCurrency',
                    step: 1,
                    max: 200,
                    onChanged: (v) {
                      st.deliveryFee = v;
                      s.saveSettings();
                    },
                  ),
                  const Divider(),
                  _NumberRow(
                    title: 'Бесплатная доставка от',
                    value: st.freeDeliveryFrom,
                    suffix: ' $kCurrency',
                    step: 50,
                    max: 5000,
                    onChanged: (v) {
                      st.freeDeliveryFrom = v;
                      s.saveSettings();
                    },
                  ),
                  const Divider(),
                  _NumberRow(
                    title: 'Оплата курьеру за доставку',
                    value: st.courierPay,
                    suffix: ' $kCurrency',
                    step: 1,
                    max: 200,
                    onChanged: (v) {
                      st.courierPay = v;
                      s.saveSettings();
                    },
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
            child: Text(
              'Новые правила действуют для новых заказов. На сервере они сразу применятся во всех приложениях.',
              style: TextStyle(color: c.muted, fontSize: 12.5),
            ),
          ),
          const SectionHeader('Приложение'),
          const CommonSettings(),
        ],
      ),
    );
  }
}

class _NumberRow extends StatelessWidget {
  const _NumberRow({
    required this.title,
    required this.value,
    required this.suffix,
    required this.step,
    required this.max,
    required this.onChanged,
  });

  final String title;
  final int value;
  final String suffix;
  final int step;
  final int max;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(fontWeight: FontWeight.w600, color: c.text),
                ),
                Text(
                  '$value$suffix',
                  style: TextStyle(fontWeight: FontWeight.w900, fontSize: 18, color: c.accentText),
                ),
              ],
            ),
          ),
          QtyStepper(
            compact: true,
            value: value ~/ step,
            min: 0,
            max: max ~/ step,
            onChanged: (v) => onChanged(v * step),
          ),
        ],
      ),
    );
  }
}
