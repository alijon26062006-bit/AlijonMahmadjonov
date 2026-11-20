import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../data.dart';
import '../format.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

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

  List<Product> get _similar {
    final same = kProducts.where((x) => x.categoryId == p.categoryId && x.id != p.id).toList();
    if (same.length < 4) {
      same.addAll(kProducts.where((x) => x.hit && x.id != p.id && !same.contains(x)).take(6 - same.length));
    }
    return same;
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final top = MediaQuery.paddingOf(context).top;
    final cat = categoryById(p.categoryId);

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
                      child: Padding(
                        padding: EdgeInsets.zero,
                        child: ProductImage(product: p, emojiSize: 150, radius: 0, heroTag: widget.heroTag),
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
                          size: 44,
                          tooltip: 'Назад',
                          onTap: () => Navigator.of(context).maybePop(),
                        ),
                        const Spacer(),
                        CircleButton(
                          icon: Icons.ios_share_rounded,
                          background: c.surface.withValues(alpha: .8),
                          tooltip: 'Поделиться',
                          onTap: () {
                            Clipboard.setData(
                              ClipboardData(text: '${p.title} — ${money(p.price)} в приложении «Витрина»'),
                            );
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
                        RatingLine(product: p, fontSize: 14, long: true),
                        _Tag(text: p.seller, icon: Icons.verified_rounded),
                        _Tag(text: '${cat.emoji} ${cat.name}'),
                      ],
                    ),
                    if (p.options.isNotEmpty) ...[
                      _Label(p.optionsLabel ?? 'Вариант'),
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
                            title: 'Завтра',
                            subtitle: p.price >= kFreeDeliveryFrom
                                ? 'бесплатно'
                                : 'бесплатно от ${money(kFreeDeliveryFrom)}',
                          ),
                        ),
                        const SizedBox(width: 10),
                        const Expanded(
                          child: _Perk(icon: Icons.verified_user_outlined, title: 'Возврат', subtitle: '14 дней'),
                        ),
                      ],
                    ),
                    const _Label('Описание'),
                    Text(p.description, style: TextStyle(fontSize: 15, height: 1.5, color: c.muted)),
                  ],
                ),
              ),
            ),
            const SliverToBoxAdapter(child: SectionHeader('Похожие товары')),
            SliverToBoxAdapter(
              child: SizedBox(
                height: 296,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: _similar.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 12),
                  itemBuilder: (_, i) => SizedBox(
                    width: 172,
                    child: ProductCard(product: _similar[i], heroPrefix: 'sim-${p.id}'),
                  ),
                ),
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 24)),
          ],
        ),
        bottomNavigationBar: BottomBar(
          child: Row(
            children: [
              QtyStepper(value: _qty, onChanged: (v) => setState(() => _qty = v)),
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
          ),
        ),
      ),
    );
  }
}

class _Label extends StatelessWidget {
  const _Label(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 20, bottom: 10),
    child: Text(
      text,
      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: AppColors.of(context).text),
    ),
  );
}

class _Tag extends StatelessWidget {
  const _Tag({required this.text, this.icon});

  final String text;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: c.chip, borderRadius: BorderRadius.circular(99)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            text,
            style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: c.text),
          ),
          if (icon != null) ...[const SizedBox(width: 4), Icon(icon, size: 15, color: c.accentText)],
        ],
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
