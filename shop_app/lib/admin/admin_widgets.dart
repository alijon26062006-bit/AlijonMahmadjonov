import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'admin_order_screen.dart';
import 'admin_shop_screen.dart';

void openAdminOrder(BuildContext context, Order o) =>
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => AdminOrderScreen(orderId: o.id)));

void openAdminShop(BuildContext context, Shop shop) =>
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => AdminShopScreen(shopId: shop.id)));

/// Строка заказа в списках админа.
class AdminOrderTile extends StatelessWidget {
  const AdminOrderTile({super.key, required this.order, this.margin = const EdgeInsets.fromLTRB(16, 0, 16, 8)});

  final Order order;
  final EdgeInsetsGeometry margin;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final o = order;
    final shop = s.shopById(o.shopId);
    final courier = s.courierById(o.courierId);
    return Padding(
      padding: margin,
      child: AppCard(
        padding: const EdgeInsets.all(12),
        onTap: () => openAdminOrder(context, o),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: o.status.color.withValues(alpha: .12),
                borderRadius: BorderRadius.circular(14),
              ),
              child: shop == null
                  ? Icon(Icons.storefront_outlined, color: o.status.color)
                  : Padding(padding: const EdgeInsets.all(8), child: AppImage(shop.logo)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        '№${o.id}',
                        style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                      ),
                      const SizedBox(width: 8),
                      Flexible(child: StatusPill.order(o)),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${shop?.name ?? ''} → ${o.buyerName}${courier != null ? ' · ${courier.name.split(' ').first}' : ''}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12.5, color: c.muted),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  money(o.total),
                  style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                ),
                Text(formatTime(o.createdAt), style: TextStyle(fontSize: 12, color: c.muted)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Строка магазина в списках админа.
class AdminShopTile extends StatelessWidget {
  const AdminShopTile({super.key, required this.shop});

  final Shop shop;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final orders = s.ordersOf(shop.id);
    final revenue = s.revenueOf(orders);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: AppCard(
        padding: const EdgeInsets.all(12),
        onTap: () => openAdminShop(context, shop),
        child: Row(
          children: [
            ImageTile(image: shop.logo, categoryId: shop.categoryId, size: 48),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    shop.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                  ),
                  Text(
                    '${shop.ownerName} · ${s.productsOf(shop.id).length} тов. · ${ordersLabel(orders.length)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12.5, color: c.muted),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      StatusPill(label: shop.status.label, color: shop.status.color),
                      if (shop.status == ShopStatus.active && !shop.isOpen) ...[
                        const SizedBox(width: 6),
                        StatusPill(label: 'Закрыт', color: c.muted),
                      ],
                    ],
                  ),
                ],
              ),
            ),
            Text(
              money(revenue),
              style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
            ),
          ],
        ),
      ),
    );
  }
}

/// Горизонтальные фильтры-таблетки.
class FilterPills<T> extends StatelessWidget {
  const FilterPills({
    super.key,
    required this.values,
    required this.selected,
    required this.label,
    required this.onChanged,
  });

  final List<T> values;
  final T selected;
  final String Function(T) label;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return SizedBox(
      height: 54,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 4),
        children: [
          for (final v in values)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text(label(v)),
                selected: v == selected,
                showCheckmark: false,
                selectedColor: c.accentSoft,
                side: BorderSide(color: v == selected ? c.accentText : c.line),
                labelStyle: TextStyle(fontWeight: FontWeight.w700, color: v == selected ? c.accentText : c.text),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(99)),
                onSelected: (_) => onChanged(v),
              ),
            ),
        ],
      ),
    );
  }
}
