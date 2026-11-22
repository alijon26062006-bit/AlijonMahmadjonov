import 'package:material_ui/material_ui.dart';

import '../../app/theme/tokens.dart';
import '../models/category.dart';
import '../models/localized_text.dart';

IconData categoryIconData(CategoryIcon icon) => switch (icon) {
  CategoryIcon.house => Icons.home_work_outlined,
  CategoryIcon.car => Icons.directions_car_outlined,
  CategoryIcon.smartphone => Icons.smartphone_outlined,
  CategoryIcon.briefcase => Icons.work_outline_rounded,
  CategoryIcon.shirt => Icons.checkroom_outlined,
  CategoryIcon.sofa => Icons.chair_outlined,
  CategoryIcon.wrench => Icons.build_outlined,
  CategoryIcon.hardHat => Icons.construction_outlined,
  CategoryIcon.baby => Icons.child_friendly_outlined,
  CategoryIcon.building => Icons.storefront_outlined,
  CategoryIcon.dumbbell => Icons.fitness_center_outlined,
  CategoryIcon.sprout => Icons.eco_outlined,
  CategoryIcon.pawPrint => Icons.pets_outlined,
  CategoryIcon.gift => Icons.card_giftcard_outlined,
  CategoryIcon.generic => Icons.category_outlined,
};

DaryobTint categoryTint(CategoryIcon icon) => switch (icon) {
  CategoryIcon.house => DaryobTints.blue,
  CategoryIcon.car => DaryobTints.violet,
  CategoryIcon.smartphone => DaryobTints.cyan,
  CategoryIcon.briefcase => DaryobTints.amber,
  CategoryIcon.shirt => DaryobTints.pink,
  CategoryIcon.sofa => DaryobTints.orange,
  CategoryIcon.wrench => DaryobTints.slate,
  CategoryIcon.hardHat => DaryobTints.yellow,
  CategoryIcon.baby => DaryobTints.coral,
  CategoryIcon.building => DaryobTints.teal,
  CategoryIcon.dumbbell => DaryobTints.red,
  CategoryIcon.sprout => DaryobTints.green,
  CategoryIcon.pawPrint => DaryobTints.brown,
  CategoryIcon.gift => DaryobTints.lime,
  CategoryIcon.generic => DaryobTints.neutral,
};

/// Background and foreground of a category accent in the current theme.
/// In dark mode the hue is laid thinly over the dark surface and the
/// foreground is lightened so it stays readable.
({Color background, Color foreground}) categoryColors(
  BuildContext context,
  CategoryIcon icon,
) {
  final tint = categoryTint(icon);
  if (Theme.of(context).brightness == Brightness.dark) {
    return (
      background: Color.alphaBlend(
        tint.strong.withValues(alpha: 0.26),
        DaryobColors.darkSurface,
      ),
      foreground: Color.lerp(tint.strong, Colors.white, 0.6)!,
    );
  }
  return (background: tint.soft, foreground: tint.strong);
}

/// 3D picture of a top-level category (assets/categories), or null when
/// the category has none.
String? categoryArtAsset(CategoryIcon icon) =>
    icon == CategoryIcon.generic ? null : 'assets/categories/${icon.name}.png';

/// The category's 3D picture; falls back to the line icon when there is no
/// picture for it.
class DaryobCategoryArt extends StatelessWidget {
  const DaryobCategoryArt({super.key, required this.icon, required this.size});

  final CategoryIcon icon;
  final double size;

  @override
  Widget build(BuildContext context) {
    final fallback = Icon(
      categoryIconData(icon),
      size: size * 0.62,
      color: categoryColors(context, icon).foreground,
    );
    final asset = categoryArtAsset(icon);
    if (asset == null) return SizedBox.square(dimension: size, child: Center(child: fallback));
    final dpr = MediaQuery.devicePixelRatioOf(context);
    return Image.asset(
      asset,
      width: size,
      height: size,
      fit: BoxFit.contain,
      filterQuality: FilterQuality.medium,
      cacheWidth: (size * dpr).round().clamp(48, 288),
      excludeFromSemantics: true,
      errorBuilder: (_, _, _) => SizedBox.square(dimension: size, child: Center(child: fallback)),
    );
  }
}

class DaryobCategoryIcon extends StatelessWidget {
  const DaryobCategoryIcon({super.key, required this.icon, this.size = 52});

  final CategoryIcon icon;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: categoryColors(context, icon).background,
        borderRadius: BorderRadius.circular(size * 0.32),
      ),
      alignment: Alignment.center,
      child: DaryobCategoryArt(icon: icon, size: size * 0.8),
    );
  }
}

/// Grid tile: icon above a two-line name.
class DaryobCategoryTile extends StatelessWidget {
  const DaryobCategoryTile({
    super.key,
    required this.category,
    required this.onTap,
    this.count,
  });

  final CategoryDefinition category;
  final VoidCallback onTap;
  final int? count;

  @override
  Widget build(BuildContext context) {
    final name = category.name.of(context);
    return Semantics(
      button: true,
      label: name,
      child: InkWell(
        onTap: onTap,
        borderRadius: DaryobRadius.cardAll,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            vertical: DaryobSpacing.sm,
            horizontal: 2,
          ),
          child: Column(
            children: [
              DaryobCategoryIcon(icon: category.icon, size: 60),
              const SizedBox(height: DaryobSpacing.sm),
              Flexible(child: _TileLabel(name)),
            ],
          ),
        ),
      ),
    );
  }
}

/// Two-line tile caption that never breaks a word in the middle: the font
/// shrinks (down to 10 px) until the longest word fits the tile width —
/// e.g. «Хизматрасонӣ» or «Недвижимость» in a 4-column grid.
class _TileLabel extends StatelessWidget {
  const _TileLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    final base = context.text.labelMedium!.copyWith(height: 1.25);
    final scaler = MediaQuery.textScalerOf(context);
    return LayoutBuilder(
      builder: (context, constraints) {
        var size = 12.5;
        final words = text.split(RegExp(r'\s+'));
        while (size > 10) {
          final style = base.copyWith(fontSize: size);
          final widest = words
              .map(
                (w) => (TextPainter(
                  text: TextSpan(text: w, style: style),
                  textDirection: TextDirection.ltr,
                  textScaler: scaler,
                  maxLines: 1,
                )..layout()).width,
              )
              .fold<double>(0, (a, b) => a > b ? a : b);
          if (widest <= constraints.maxWidth) break;
          size -= 0.5;
        }
        return Text(
          text,
          maxLines: 2,
          textAlign: TextAlign.center,
          overflow: TextOverflow.ellipsis,
          style: base.copyWith(fontSize: size),
        );
      },
    );
  }
}

/// Row version used in the full categories list.
class DaryobCategoryRow extends StatelessWidget {
  const DaryobCategoryRow({
    super.key,
    required this.category,
    required this.onTap,
    this.countLabel,
  });

  final CategoryDefinition category;
  final VoidCallback onTap;
  final String? countLabel;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      leading: DaryobCategoryIcon(icon: category.icon, size: 44),
      title: Text(category.name.of(context)),
      subtitle: Text(
        category.description.of(context),
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (countLabel != null)
            Text(countLabel!, style: context.text.labelSmall),
          const SizedBox(width: DaryobSpacing.xs),
          const Icon(Icons.chevron_right_rounded),
        ],
      ),
    );
  }
}
