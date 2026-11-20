import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/settings_card.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'create_shop_screen.dart';
import 'seller_widgets.dart';

class ShopProfileScreen extends StatelessWidget {
  const ShopProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final shop = s.myShop!;
    final orders = s.ordersOf(shop.id);
    final done = orders.where((o) => o.status == OrderStatus.delivered).toList();
    final income = done.fold(0, (a, o) => a + sellerIncome(o));
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          const PageTitle('Магазин'),
          ProfileHeader(
            title: shop.name,
            subtitle: '${s.user?.name ?? ''} · ${formatPhone(shop.ownerPhone)}',
            avatar: shop.emoji,
            stats: [
              ('${done.length}', 'выполнено'),
              ('★ ${shop.rating.toStringAsFixed(1)}', reviewsLabel(shop.ratingCount)),
              (money(income), 'заработано'),
            ],
          ),
          const SectionHeader('О магазине'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              child: Column(
                children: [
                  InfoLine(
                    icon: Icons.category_outlined,
                    title: 'Категория',
                    text: '${categoryById(shop.categoryId).emoji} ${categoryById(shop.categoryId).name}',
                  ),
                  InfoLine(icon: Icons.location_on_outlined, title: 'Адрес (самовывоз)', text: shop.address),
                  if (shop.description.isNotEmpty)
                    InfoLine(icon: Icons.notes_rounded, title: 'Описание', text: shop.description),
                  InfoLine(
                    icon: Icons.verified_outlined,
                    title: 'Статус',
                    text: shop.status.label,
                    trailing: StatusPill(
                      label: shop.isOpen ? 'Открыт' : 'Закрыт',
                      color: shop.isOpen ? kSuccess : kDanger,
                    ),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: SoftButton(
              label: 'Изменить данные магазина',
              icon: Icons.edit_outlined,
              onPressed: () =>
                  Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => CreateShopScreen(shop: shop))),
            ),
          ),
          const SectionHeader('Условия маркетплейса'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: AppCard(
              child: Column(
                children: [
                  SummaryRow('Комиссия с заказа', '${s.settings.commissionPercent}%'),
                  SummaryRow('Доставка для покупателя', money(s.settings.deliveryFee)),
                  SummaryRow('Бесплатная доставка от', money(s.settings.freeDeliveryFrom)),
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
