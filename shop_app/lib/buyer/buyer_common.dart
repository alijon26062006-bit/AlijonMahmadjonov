import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'product_screen.dart';
import 'shop_screen.dart';

/// Навигация по вкладкам приложения покупателя.
class BuyerNav {
  static const home = 0, catalog = 1, favorites = 2, cart = 3, profile = 4;

  final tab = ValueNotifier<int>(home);
  final catalogCategory = ValueNotifier<String?>(null);
  final searchRequest = ValueNotifier<int>(0);

  void openCatalog({String? category, bool focusSearch = false}) {
    catalogCategory.value = category;
    tab.value = catalog;
    if (focusSearch) searchRequest.value++;
  }
}

final buyerNav = BuyerNav();

void openProduct(BuildContext context, Product product, {String? heroTag}) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => ProductScreen(product: product, heroTag: heroTag),
    ),
  );
}

void openShop(BuildContext context, Shop shop) {
  Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ShopScreen(shop: shop)));
}

void goToTab(BuildContext context, int tab) {
  Navigator.of(context).popUntil((r) => r.isFirst);
  buyerNav.tab.value = tab;
}

void addToCartWithFeedback(BuildContext context, Product product, {String? option, int qty = 1}) {
  final s = StoreScope.read(context);
  final shop = s.shopById(product.shopId);
  if (shop == null || !shop.isOpen) {
    showSnack(context, 'Магазин «${shop?.name ?? ''}» сейчас закрыт');
    return;
  }
  if (!product.inStock) {
    showSnack(context, 'Товар закончился');
    return;
  }
  final navigator = Navigator.of(context);
  s.addToCart(product, option: option, qty: qty);
  HapticFeedback.lightImpact();
  showSnack(
    context,
    'Добавлено в корзину',
    actionLabel: 'Перейти',
    onAction: () {
      navigator.popUntil((r) => r.isFirst);
      buyerNav.tab.value = BuyerNav.cart;
    },
  );
}

class FavButton extends StatelessWidget {
  const FavButton({super.key, required this.product, this.size = 32});

  final Product product;
  final double size;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final on = s.isFavorite(product.id);
    return Material(
      color: c.dark ? const Color(0x66000000) : const Color(0xD9FFFFFF),
      shape: const CircleBorder(),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: () {
          HapticFeedback.selectionClick();
          s.toggleFavorite(product.id);
        },
        child: SizedBox.square(
          dimension: size,
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 220),
            transitionBuilder: (child, a) => ScaleTransition(scale: a, child: child),
            child: Icon(
              on ? Icons.favorite_rounded : Icons.favorite_border_rounded,
              key: ValueKey(on),
              size: size * .55,
              color: on ? const Color(0xFFF107A3) : c.text,
            ),
          ),
        ),
      ),
    );
  }
}

class RatingLine extends StatelessWidget {
  const RatingLine({super.key, required this.rating, required this.reviews, this.fontSize = 12.5, this.long = false});

  final double rating;
  final int reviews;
  final double fontSize;
  final bool long;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.star_rounded, size: fontSize + 4, color: kStar),
        const SizedBox(width: 2),
        Text(
          rating.toStringAsFixed(1),
          style: TextStyle(fontSize: fontSize, fontWeight: FontWeight.w700, color: c.text),
        ),
        Flexible(
          child: Text(
            ' · ${long ? reviewsLabel(reviews) : groupDigits(reviews)}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: fontSize, color: c.muted),
          ),
        ),
      ],
    );
  }
}

/// Карточка товара для сеток и лент.
class ProductCard extends StatelessWidget {
  const ProductCard({super.key, required this.product, this.heroPrefix = 'grid'});

  final Product product;
  final String heroPrefix;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final tag = '$heroPrefix-${product.id}';
    final out = !product.inStock;
    return Container(
      decoration: BoxDecoration(color: c.surface, borderRadius: BorderRadius.circular(22), boxShadow: c.cardShadow),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          borderRadius: BorderRadius.circular(22),
          onTap: () => openProduct(context, product, heroTag: tag),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(6, 6, 6, 0),
                  child: Stack(
                    children: [
                      Positioned.fill(
                        child: EmojiImage(
                          emoji: product.emoji,
                          categoryId: product.categoryId,
                          size: 70,
                          heroTag: tag,
                          dimmed: out,
                        ),
                      ),
                      if (product.discount > 0 && !out)
                        Positioned(left: 8, top: 8, child: DiscountBadge(product.discount)),
                      if (out)
                        Positioned(
                          left: 8,
                          top: 8,
                          child: StatusPill(label: 'Нет в наличии', color: c.muted),
                        ),
                      Positioned(right: 8, top: 8, child: FavButton(product: product)),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    PriceRow(price: product.price, oldPrice: product.oldPrice),
                    const SizedBox(height: 3),
                    SizedBox(
                      height: 34,
                      child: Text(
                        product.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 13.5, height: 1.25, color: c.text),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Expanded(
                          child: RatingLine(rating: product.rating, reviews: product.reviews),
                        ),
                        _AddButton(product: product, enabled: !out),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AddButton extends StatelessWidget {
  const _AddButton({required this.product, required this.enabled});

  final Product product;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Opacity(
      opacity: enabled ? 1 : .35,
      child: DecoratedBox(
        decoration: BoxDecoration(gradient: c.gradient, borderRadius: BorderRadius.circular(11)),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            borderRadius: BorderRadius.circular(11),
            onTap: enabled
                ? () => addToCartWithFeedback(
                    context,
                    product,
                    option: product.options.isEmpty ? null : product.options.first,
                  )
                : null,
            child: const SizedBox.square(dimension: 34, child: Icon(Icons.add_rounded, color: Colors.white, size: 22)),
          ),
        ),
      ),
    );
  }
}

/// Карточка магазина (горизонтальная лента на главной).
class ShopCard extends StatelessWidget {
  const ShopCard({super.key, required this.shop});

  final Shop shop;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final cat = categoryById(shop.categoryId);
    return AppCard(
      padding: const EdgeInsets.all(12),
      onTap: () => openShop(context, shop),
      child: Row(
        children: [
          Stack(
            clipBehavior: Clip.none,
            children: [
              EmojiTile(emoji: shop.emoji, categoryId: shop.categoryId, size: 54),
              if (!shop.isOpen)
                Positioned(
                  right: -4,
                  bottom: -4,
                  child: Container(
                    padding: const EdgeInsets.all(3),
                    decoration: BoxDecoration(color: c.surface, shape: BoxShape.circle),
                    child: const Icon(Icons.lock_clock, size: 14, color: kDanger),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  shop.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: c.text),
                ),
                const SizedBox(height: 2),
                Text(
                  shop.isOpen ? cat.name : 'Закрыт',
                  style: TextStyle(fontSize: 12.5, color: shop.isOpen ? c.muted : kDanger),
                ),
                const SizedBox(height: 4),
                RatingLine(rating: shop.rating, reviews: shop.ratingCount, fontSize: 12),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
