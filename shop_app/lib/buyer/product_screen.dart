import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'buyer_common.dart';

class ProductScreen extends StatefulWidget {
  const ProductScreen({super.key, required this.product, this.heroTag});

  final Product product;
  final String? heroTag;

  @override
  State<ProductScreen> createState() => _ProductScreenState();
}

class _ProductScreenState extends State<ProductScreen> {
  late String? _option = widget.product.options.isEmpty ? null : widget.product.options.first;
  int _qty = 1;

  Product get p => widget.product;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final top = MediaQuery.paddingOf(context).top;
    final cat = categoryById(p.categoryId);
    final shop = s.shopById(p.shopId);
    final similar = s.catalog.where((x) => x.categoryId == p.categoryId && x.id != p.id).take(8).toList();
    final fromShop = s.catalog.where((x) => x.shopId == p.shopId && x.id != p.id).take(8).toList();
    final canBuy = p.inStock && (shop?.isOpen ?? false) && s.isVisible(p);

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: (c.dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark).copyWith(
        statusBarColor: Colors.transparent,
      ),
      child: Scaffold(
        body: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Stack(
                children: [
                  SizedBox(
                    height: 360 + top,
                    width: double.infinity,
                    child: ClipRRect(
                      borderRadius: const BorderRadius.vertical(bottom: Radius.circular(36)),
                      child: EmojiImage(
                        emoji: p.emoji,
                        categoryId: p.categoryId,
                        size: 150,
                        radius: 0,
                        heroTag: widget.heroTag,
                      ),
                    ),
                  ),
                  Positioned(
                    top: top + 8,
                    left: 16,
                    right: 16,
                    child: Row(
                      children: [
                        CircleButton(
                          icon: Icons.arrow_back_ios_new_rounded,
                          background: c.surface.withValues(alpha: .8),
                          tooltip: 'Назад',
                          onTap: () => Navigator.of(context).maybePop(),
                        ),
                        const Spacer(),
                        CircleButton(
                          icon: Icons.ios_share_rounded,
                          background: c.surface.withValues(alpha: .8),
                          tooltip: 'Поделиться',
                          onTap: () {
                            Clipboard.setData(ClipboardData(text: '${p.title} — ${money(p.price)} в «Витрине»'));
                            showSnack(context, 'Ссылка на товар скопирована');
                          },
                        ),
                        const SizedBox(width: 10),
                        FavButton(product: p, size: 44),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: PriceRow(price: p.price, oldPrice: p.oldPrice, size: 30),
                        ),
                        if (p.discount > 0) ...[const SizedBox(width: 10), DiscountBadge(p.discount, fontSize: 13)],
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      p.title,
                      style: TextStyle(
                        fontSize: 21,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.4,
                        height: 1.2,
                        color: c.text,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 10,
                      runSpacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        RatingLine(rating: p.rating, reviews: p.reviews, fontSize: 14, long: true),
                        _Tag(text: '${cat.emoji} ${cat.name}'),
                        if (!p.inStock)
                          const StatusPill(label: 'Нет в наличии', color: kDanger)
                        else if (p.stock <= 5)
                          StatusPill(label: 'Осталось ${p.stock} шт.', color: const Color(0xFFFF8A00)),
                      ],
                    ),
                    if (shop != null) ...[
                      const SizedBox(height: 16),
                      AppCard(
                        padding: const EdgeInsets.all(12),
                        onTap: () => openShop(context, shop),
                        child: Row(
                          children: [
                            EmojiTile(emoji: shop.emoji, categoryId: shop.categoryId, size: 44),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Flexible(
                                        child: Text(
                                          shop.name,
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                                        ),
                                      ),
                                      const SizedBox(width: 4),
                                      Icon(Icons.verified_rounded, size: 16, color: c.accentText),
                                    ],
                                  ),
                                  Text(
                                    shop.isOpen ? 'Открыт · ★ ${shop.rating.toStringAsFixed(1)}' : 'Сейчас закрыт',
                                    style: TextStyle(fontSize: 12.5, color: shop.isOpen ? c.muted : kDanger),
                                  ),
                                ],
                              ),
                            ),
                            Text(
                              'В магазин',
                              style: TextStyle(color: c.accentText, fontWeight: FontWeight.w700, fontSize: 13),
                            ),
                            Icon(Icons.chevron_right_rounded, color: c.accentText),
                          ],
                        ),
                      ),
                    ],
                    if (p.options.isNotEmpty) ...[
                      FieldLabel(p.optionsLabel ?? 'Вариант'),
                      Wrap(
                        spacing: 9,
                        runSpacing: 9,
                        children: [
                          for (final o in p.options)
                            _OptionChip(label: o, selected: o == _option, onTap: () => setState(() => _option = o)),
                        ],
                      ),
                    ],
                    const SizedBox(height: 18),
                    Row(
                      children: [
                        Expanded(
                          child: _Perk(
                            icon: Icons.local_shipping_outlined,
                            title: 'Сегодня',
                            subtitle: p.price >= s.settings.freeDeliveryFrom
                                ? 'доставка бесплатно'
                                : 'бесплатно от ${money(s.settings.freeDeliveryFrom)}',
                          ),
                        ),
                        const SizedBox(width: 10),
                        const Expanded(
                          child: _Perk(icon: Icons.verified_user_outlined, title: 'Возврат', subtitle: '14 дней'),
                        ),
                      ],
                    ),
                    if (p.description.isNotEmpty) ...[
                      const FieldLabel('Описание'),
                      Text(p.description, style: TextStyle(fontSize: 15, height: 1.5, color: c.muted)),
                    ],
                  ],
                ),
              ),
            ),
            if (fromShop.isNotEmpty) ...[
              SliverToBoxAdapter(child: SectionHeader('Ещё в «${shop?.name ?? ''}»')),
              _HorizontalProducts(products: fromShop, prefix: 'shop-${p.id}'),
            ],
            if (similar.isNotEmpty) ...[
              const SliverToBoxAdapter(child: SectionHeader('Похожие товары')),
              _HorizontalProducts(products: similar, prefix: 'sim-${p.id}'),
            ],
            const SliverToBoxAdapter(child: SizedBox(height: 24)),
          ],
        ),
        bottomNavigationBar: BottomBar(
          child: canBuy
              ? Row(
                  children: [
                    QtyStepper(value: _qty, max: p.stock.clamp(1, 99), onChanged: (v) => setState(() => _qty = v)),
                    const SizedBox(width: 12),
                    Expanded(
                      child: GradientButton(
                        icon: Icons.shopping_bag_outlined,
                        label: 'В корзину',
                        trailing: money(p.price * _qty),
                        onPressed: () {
                          addToCartWithFeedback(context, p, option: _option, qty: _qty);
                          setState(() => _qty = 1);
                        },
                      ),
                    ),
                  ],
                )
              : SoftButton(
                  label: !p.inStock ? 'Товар закончился' : 'Магазин сейчас закрыт',
                  icon: Icons.info_outline_rounded,
                  onPressed: null,
                ),
        ),
      ),
    );
  }
}

class _HorizontalProducts extends StatelessWidget {
  const _HorizontalProducts({required this.products, required this.prefix});

  final List<Product> products;
  final String prefix;

  @override
  Widget build(BuildContext context) => SliverToBoxAdapter(
    child: SizedBox(
      height: 296,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: products.length,
        separatorBuilder: (_, _) => const SizedBox(width: 12),
        itemBuilder: (_, i) => SizedBox(
          width: 172,
          child: ProductCard(product: products[i], heroPrefix: prefix),
        ),
      ),
    ),
  );
}

class _Tag extends StatelessWidget {
  const _Tag({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: c.chip, borderRadius: BorderRadius.circular(99)),
      child: Text(
        text,
        style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: c.text),
      ),
    );
  }
}

class _OptionChip extends StatelessWidget {
  const _OptionChip({required this.label, required this.selected, required this.onTap});

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Material(
      color: selected ? c.accentSoft : c.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: selected ? c.accentText : c.line, width: 1.5),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          child: Text(
            label,
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5, color: selected ? c.accentText : c.text),
          ),
        ),
      ),
    );
  }
}

class _Perk extends StatelessWidget {
  const _Perk({required this.icon, required this.title, required this.subtitle});

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: c.surface, borderRadius: BorderRadius.circular(16), boxShadow: c.cardShadow),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(color: c.chip, borderRadius: BorderRadius.circular(11)),
            child: Icon(icon, size: 19, color: c.accentText),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5, color: c.text),
                ),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 12.5, color: c.muted),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
