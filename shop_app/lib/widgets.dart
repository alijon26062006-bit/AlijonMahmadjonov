import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'data.dart';
import 'format.dart';
import 'models.dart';
import 'screens/product_screen.dart';
import 'state.dart';
import 'theme.dart';

/// Сетка карточек товаров: 2 колонки на телефоне, больше — на планшете.
const kProductGridDelegate = SliverGridDelegateWithMaxCrossAxisExtent(
  maxCrossAxisExtent: 240,
  mainAxisExtent: 296,
  crossAxisSpacing: 12,
  mainAxisSpacing: 12,
);

void openProduct(BuildContext context, Product product, {String? heroTag}) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => ProductScreen(product: product, heroTag: heroTag),
    ),
  );
}

void goToTab(BuildContext context, int tab) {
  Navigator.of(context).popUntil((r) => r.isFirst);
  appNav.tab.value = tab;
}

void showSnack(BuildContext context, String text, {String? actionLabel, VoidCallback? onAction}) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(text),
        duration: const Duration(milliseconds: 2200),
        persist: false,
        action: actionLabel == null ? null : SnackBarAction(label: actionLabel, onPressed: onAction ?? () {}),
      ),
    );
}

void addToCartWithFeedback(BuildContext context, Product product, {String? option, int qty = 1}) {
  final navigator = Navigator.of(context);
  ShopScope.read(context).addToCart(product, option: option, qty: qty);
  HapticFeedback.lightImpact();
  showSnack(
    context,
    'Добавлено в корзину',
    actionLabel: 'Перейти',
    onAction: () {
      navigator.popUntil((r) => r.isFirst);
      appNav.tab.value = AppNav.cart;
    },
  );
}

/// Эмодзи товара на пастельном градиенте его категории.
class ProductImage extends StatelessWidget {
  const ProductImage({super.key, required this.product, this.emojiSize = 64, this.radius = 18, this.heroTag});

  final Product product;
  final double emojiSize;
  final double radius;
  final String? heroTag;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final tint = categoryById(product.categoryId).tint;
    final colors = c.dark ? [for (final t in tint) Color.lerp(t, c.surface, .74)!] : tint;
    Widget emoji = SizedBox.square(
      dimension: emojiSize * 1.3,
      child: FittedBox(
        child: Text(
          product.emoji,
          style: const TextStyle(
            fontSize: 100,
            height: 1.15,
            shadows: [Shadow(color: Color(0x33000000), blurRadius: 24, offset: Offset(0, 12))],
          ),
        ),
      ),
    );
    if (heroTag != null) {
      emoji = Hero(
        tag: heroTag!,
        child: Material(type: MaterialType.transparency, child: emoji),
      );
    }
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: colors),
      ),
      child: Center(child: emoji),
    );
  }
}

class DiscountBadge extends StatelessWidget {
  const DiscountBadge(this.percent, {super.key, this.fontSize = 12});

  final int percent;
  final double fontSize;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(color: kPink, borderRadius: BorderRadius.circular(8)),
    child: Text(
      '−$percent%',
      style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: fontSize),
    ),
  );
}

class FavButton extends StatelessWidget {
  const FavButton({super.key, required this.product, this.size = 32});

  final Product product;
  final double size;

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
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
              color: on ? kPink : c.text,
            ),
          ),
        ),
      ),
    );
  }
}

class PriceRow extends StatelessWidget {
  const PriceRow({super.key, required this.price, this.oldPrice, this.size = 17});

  final int price;
  final int? oldPrice;
  final double size;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        Text(
          money(price),
          style: TextStyle(fontSize: size, fontWeight: FontWeight.w800, letterSpacing: -0.4, color: c.text),
        ),
        if (oldPrice != null) ...[
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              money(oldPrice!),
              maxLines: 1,
              overflow: TextOverflow.fade,
              softWrap: false,
              style: TextStyle(
                fontSize: size * .72,
                color: c.muted,
                decoration: TextDecoration.lineThrough,
                decorationColor: c.muted,
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class RatingLine extends StatelessWidget {
  const RatingLine({super.key, required this.product, this.fontSize = 12.5, this.long = false});

  final Product product;
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
          product.rating.toStringAsFixed(1),
          style: TextStyle(fontSize: fontSize, fontWeight: FontWeight.w700, color: c.text),
        ),
        Flexible(
          child: Text(
            ' · ${long ? reviewsLabel(product.reviews) : groupDigits(product.reviews)}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: fontSize, color: c.muted),
          ),
        ),
      ],
    );
  }
}

/// Карточка товара для сеток и горизонтальных лент.
class ProductCard extends StatelessWidget {
  const ProductCard({super.key, required this.product, this.heroPrefix = 'grid'});

  final Product product;
  final String heroPrefix;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final tag = '$heroPrefix-${product.id}';
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
                        child: ProductImage(product: product, emojiSize: 70, heroTag: tag),
                      ),
                      if (product.discount > 0) Positioned(left: 8, top: 8, child: DiscountBadge(product.discount)),
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
                        Expanded(child: RatingLine(product: product)),
                        AddToCartButton(product: product),
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

class AddToCartButton extends StatelessWidget {
  const AddToCartButton({super.key, required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(gradient: kBrandGradient, borderRadius: BorderRadius.circular(11)),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          borderRadius: BorderRadius.circular(11),
          onTap: () =>
              addToCartWithFeedback(context, product, option: product.options.isEmpty ? null : product.options.first),
          child: const SizedBox.square(dimension: 34, child: Icon(Icons.add_rounded, color: Colors.white, size: 22)),
        ),
      ),
    );
  }
}

/// Главная кнопка с фирменным градиентом.
class GradientButton extends StatelessWidget {
  const GradientButton({super.key, required this.label, this.onPressed, this.icon, this.trailing, this.height = 54});

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final String? trailing;
  final double height;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return AnimatedOpacity(
      duration: const Duration(milliseconds: 200),
      opacity: enabled ? 1 : .45,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: kBrandGradient,
          borderRadius: BorderRadius.circular(16),
          boxShadow: enabled
              ? const [BoxShadow(color: Color(0x88B41EC8), blurRadius: 24, offset: Offset(0, 12), spreadRadius: -10)]
              : null,
        ),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: onPressed,
            child: SizedBox(
              height: height,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (icon != null) ...[Icon(icon, color: Colors.white, size: 21), const SizedBox(width: 8)],
                    Flexible(
                      child: Text(
                        label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16),
                      ),
                    ),
                    if (trailing != null)
                      Text(
                        '  ·  $trailing',
                        style: const TextStyle(color: Color(0xD9FFFFFF), fontWeight: FontWeight.w600, fontSize: 14.5),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class QtyStepper extends StatelessWidget {
  const QtyStepper({
    super.key,
    required this.value,
    required this.onChanged,
    this.min = 1,
    this.max = 99,
    this.compact = false,
  });

  final int value;
  final ValueChanged<int> onChanged;
  final int min;
  final int max;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final h = compact ? 34.0 : 54.0;
    Widget btn(IconData icon, VoidCallback? onTap) => InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: onTap == null
          ? null
          : () {
              HapticFeedback.selectionClick();
              onTap();
            },
      child: SizedBox(
        width: compact ? 32 : 42,
        height: h,
        child: Icon(icon, size: compact ? 18 : 22, color: onTap == null ? c.line : c.muted),
      ),
    );
    return Container(
      height: h,
      decoration: BoxDecoration(color: c.chip, borderRadius: BorderRadius.circular(compact ? 11 : 16)),
      child: Material(
        type: MaterialType.transparency,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            btn(Icons.remove_rounded, value > min ? () => onChanged(value - 1) : null),
            SizedBox(
              width: compact ? 22 : 30,
              child: Text(
                '$value',
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: compact ? 14 : 16, color: c.text),
              ),
            ),
            btn(Icons.add_rounded, value < max ? () => onChanged(value + 1) : null),
          ],
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.action, this.onAction});

  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 22, 8, 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, letterSpacing: -0.3, color: c.text),
            ),
          ),
          if (action != null)
            TextButton(
              onPressed: onAction,
              child: Text(
                action!,
                style: TextStyle(color: c.accentText, fontWeight: FontWeight.w700, fontSize: 14),
              ),
            ),
        ],
      ),
    );
  }
}

/// Крупный заголовок вкладки: «Корзина ³ товара».
class PageTitle extends StatelessWidget {
  const PageTitle(this.title, {super.key, this.badge, this.trailing});

  final String title;
  final String? badge;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 16, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 30,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.8,
              color: c.text,
              height: 1.1,
            ),
          ),
          if (badge != null)
            Padding(
              padding: const EdgeInsets.only(left: 6, top: 2),
              child: Text(
                badge!,
                style: TextStyle(fontSize: 14, color: c.muted, fontWeight: FontWeight.w600),
              ),
            ),
          const Spacer(),
          ?trailing,
        ],
      ),
    );
  }
}

class CircleButton extends StatelessWidget {
  const CircleButton({
    super.key,
    required this.icon,
    required this.onTap,
    this.background,
    this.color,
    this.size = 44,
    this.tooltip,
  });

  final IconData icon;
  final VoidCallback onTap;
  final Color? background;
  final Color? color;
  final double size;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final button = Material(
      color: background ?? c.chip,
      shape: const CircleBorder(),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox.square(
          dimension: size,
          child: Icon(icon, size: size * .5, color: color ?? c.text),
        ),
      ),
    );
    return tooltip == null ? button : Tooltip(message: tooltip!, child: button);
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.emoji,
    required this.title,
    required this.subtitle,
    this.buttonLabel,
    this.onButton,
  });

  final String emoji;
  final String title;
  final String subtitle;
  final String? buttonLabel;
  final VoidCallback? onButton;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 128,
              height: 128,
              decoration: BoxDecoration(color: c.accentSoft, shape: BoxShape.circle),
              alignment: Alignment.center,
              child: Text(emoji, style: const TextStyle(fontSize: 58)),
            ),
            const SizedBox(height: 22),
            Text(
              title,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800, color: c.text),
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, color: c.muted, height: 1.4),
            ),
            if (buttonLabel != null) ...[
              const SizedBox(height: 24),
              SizedBox(
                width: 240,
                child: GradientButton(label: buttonLabel!, onPressed: onButton),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Выбираемая плитка (способ доставки, оплаты и т.п.).
class ChoiceTile extends StatelessWidget {
  const ChoiceTile({
    super.key,
    required this.emoji,
    required this.title,
    this.subtitle,
    required this.selected,
    required this.onTap,
  });

  final String emoji;
  final String title;
  final String? subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: selected ? c.accentSoft : c.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: selected ? c.accentText : c.line, width: 1.5),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
            child: Row(
              children: [
                Text(emoji, style: const TextStyle(fontSize: 26)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: c.text),
                      ),
                      if (subtitle != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(subtitle!, style: TextStyle(fontSize: 13, color: c.muted)),
                        ),
                    ],
                  ),
                ),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 180),
                  child: Icon(
                    selected ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                    key: ValueKey(selected),
                    color: selected ? c.accentText : c.line,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Строка «название — сумма» в итогах заказа.
class SummaryRow extends StatelessWidget {
  const SummaryRow(this.label, this.value, {super.key, this.color, this.big = false});

  final String label;
  final String value;
  final Color? color;
  final bool big;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final style = TextStyle(
      fontSize: big ? 19 : 14.5,
      fontWeight: big ? FontWeight.w800 : FontWeight.w500,
      color: color ?? (big ? c.text : c.muted),
      letterSpacing: big ? -0.3 : 0,
    );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(label, style: style)),
          Text(
            value,
            style: style.copyWith(color: color ?? c.text, fontWeight: big ? FontWeight.w800 : FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

/// Нижняя панель с кнопкой (поверх контента, с тенью).
class BottomBar extends StatelessWidget {
  const BottomBar({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.surface,
        boxShadow: const [
          BoxShadow(color: Color(0x1A000000), blurRadius: 24, offset: Offset(0, -6), spreadRadius: -10),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 12), child: child),
      ),
    );
  }
}

String optionText(Product product, String? option) =>
    option == null ? '' : '${product.optionsLabel ?? 'Вариант'}: $option';

/// Мини-плитка с эмодзи (для заказов).
class EmojiTile extends StatelessWidget {
  const EmojiTile({super.key, required this.line, this.size = 44});

  final OrderLine line;
  final double size;

  @override
  Widget build(BuildContext context) {
    final p = productById(line.productId);
    final c = AppColors.of(context);
    final tint = p == null ? [c.chip, c.chip] : categoryById(p.categoryId).tint;
    final colors = c.dark ? [for (final t in tint) Color.lerp(t, c.surface, .74)!] : tint;
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * .3),
        gradient: LinearGradient(colors: colors, begin: Alignment.topLeft, end: Alignment.bottomRight),
      ),
      child: Text(line.emoji, style: TextStyle(fontSize: size * .52)),
    );
  }
}
