import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'buyer_common.dart';
import 'catalog_screen.dart';

/// Витрина одного магазина.
class ShopScreen extends StatefulWidget {
  const ShopScreen({super.key, required this.shop});

  final Shop shop;

  @override
  State<ShopScreen> createState() => _ShopScreenState();
}

class _ShopScreenState extends State<ShopScreen> {
  SortMode _sort = SortMode.popular;
  String? _category;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final shop = widget.shop;
    final top = MediaQuery.paddingOf(context).top;
    final all = s.catalog.where((p) => p.shopId == shop.id).toList();
    final cats = {for (final p in all) p.categoryId}.toList();
    final products = sortProducts(all.where((p) => _category == null || p.categoryId == _category).toList(), _sort);

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: Scaffold(
        body: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Container(
                padding: EdgeInsets.fromLTRB(16, top + 8, 16, 22),
                decoration: BoxDecoration(
                  gradient: c.headerGradient,
                  borderRadius: const BorderRadius.vertical(bottom: Radius.circular(30)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CircleButton(
                      icon: Icons.arrow_back_ios_new_rounded,
                      background: const Color(0x2EFFFFFF),
                      color: Colors.white,
                      onTap: () => Navigator.of(context).maybePop(),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Container(
                          width: 72,
                          height: 72,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(22),
                            boxShadow: const [
                              BoxShadow(color: Color(0x33000000), blurRadius: 18, offset: Offset(0, 8)),
                            ],
                          ),
                          padding: const EdgeInsets.all(12),
                          child: AppImage(shop.logo),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                shop.name,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 24,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.5,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'Рейтинг ${ratingText(shop.rating)} · ${reviewsLabel(shop.ratingCount)}',
                                style: const TextStyle(color: Color(0xE6FFFFFF), fontSize: 13.5),
                              ),
                              const SizedBox(height: 6),
                              StatusPillOnDark(open: shop.isOpen),
                            ],
                          ),
                        ),
                      ],
                    ),
                    if (shop.description.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      Text(
                        shop.description,
                        style: const TextStyle(color: Color(0xE6FFFFFF), fontSize: 14.5, height: 1.4),
                      ),
                    ],
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        const Icon(Icons.location_on_outlined, color: Color(0xCCFFFFFF), size: 17),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(shop.address, style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 13.5)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            if (cats.length > 1)
              SliverToBoxAdapter(
                child: SizedBox(
                  height: 58,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
                    children: [
                      Pill(label: 'Все', selected: _category == null, onTap: () => setState(() => _category = null)),
                      for (final id in cats)
                        Pill(
                          label: categoryById(id).name,
                          selected: _category == id,
                          onTap: () => setState(() => _category = id),
                        ),
                    ],
                  ),
                ),
              ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 10, 8, 4),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        itemsLabel(products.length),
                        style: TextStyle(color: c.muted, fontWeight: FontWeight.w500),
                      ),
                    ),
                    SortButton(value: _sort, onChanged: (v) => setState(() => _sort = v)),
                  ],
                ),
              ),
            ),
            if (products.isEmpty)
              const SliverFillRemaining(
                hasScrollBody: false,
                child: EmptyState(image: 'package', title: 'Товаров пока нет', subtitle: 'Загляните позже'),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 6, 16, 24),
                sliver: SliverGrid.builder(
                  gridDelegate: kProductGridDelegate,
                  itemCount: products.length,
                  itemBuilder: (_, i) => ProductCard(product: products[i], heroPrefix: 'shop'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class StatusPillOnDark extends StatelessWidget {
  const StatusPillOnDark({super.key, required this.open});

  final bool open;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
    decoration: BoxDecoration(color: const Color(0x33FFFFFF), borderRadius: BorderRadius.circular(99)),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: open ? const Color(0xFF5CFF9D) : const Color(0xFFFF8A8A),
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 6),
        Text(
          open ? 'Открыт, принимает заказы' : 'Закрыт',
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12.5),
        ),
      ],
    ),
  );
}
