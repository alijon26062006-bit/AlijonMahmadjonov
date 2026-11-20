import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/settings_card.dart';
import '../core/store.dart';
import '../core/widgets.dart';
import 'register_courier_screen.dart';

class CourierProfileScreen extends StatelessWidget {
  const CourierProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final me = s.me!;
    final done = s.myDeliveries;
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          const PageTitle('Профиль'),
          ProfileHeader(
            title: me.name,
            subtitle: formatPhone(me.phone),
            avatar: me.name.characters.first.toUpperCase(),
            stats: [
              ('${done.length}', plural(done.length, 'доставка', 'доставки', 'доставок')),
              (ratingText(me.rating), 'рейтинг'),
              (me.online ? 'На линии' : 'Не на линии', 'статус'),
            ],
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
            child: SoftButton(
              label: 'Изменить имя и транспорт',
              icon: Icons.edit_outlined,
              onPressed: () =>
                  Navigator.of(context)
                      .push(MaterialPageRoute<void>(builder: (_) => RegisterCourierScreen(courier: me))),
            ),
          ),
          const SectionHeader('Правила'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: AppCard(
              child: Column(
                children: [
                  SummaryRow('Оплата за доставку', money(s.settings.courierPay)),
                  const SummaryRow('Заказов одновременно', '1'),
                  const SummaryRow('Деньги за наличные заказы', 'сдать в магазин'),
                ],
              ),
            ),
          ),
          const SectionHeader('Настройки'),
          const CommonSettings(),
        ],
      ),
    );
  }
}
