import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/theme/tokens.dart';
import '../models/category.dart';
import 'category_visuals.dart';

/// Shows a listing photo from a URL (cached) or a local file. Without a
/// photo, shows the category icon on the category's own colour — never a
/// stock picture that could look like the real item.
class DaryobListingImage extends StatelessWidget {
  const DaryobListingImage({
    super.key,
    required this.source,
    this.icon = CategoryIcon.generic,
    this.fit = BoxFit.cover,
    this.cacheWidth,
  });

  final String? source;
  final CategoryIcon icon;
  final BoxFit fit;

  /// Decode width in physical pixels; keeps memory low in grids.
  final int? cacheWidth;

  @override
  Widget build(BuildContext context) {
    final src = source;
    if (src == null || src.isEmpty) return _Placeholder(icon: icon);

    if (src.startsWith('http://') || src.startsWith('https://')) {
      return CachedNetworkImage(
        imageUrl: src,
        fit: fit,
        memCacheWidth: cacheWidth,
        fadeInDuration: DaryobDurations.fast,
        placeholder: (_, _) => ColoredBox(color: context.palette.skeleton),
        errorWidget: (_, _, _) => _Placeholder(icon: icon, broken: true),
      );
    }

    return Image.file(
      File(src),
      fit: fit,
      cacheWidth: cacheWidth,
      errorBuilder: (_, _, _) => _Placeholder(icon: icon, broken: true),
    );
  }
}

/// No photo: the category's own hue with its icon, so a feed of listings
/// without pictures still reads as different kinds of things.
class _Placeholder extends StatelessWidget {
  const _Placeholder({required this.icon, this.broken = false});
  final CategoryIcon icon;
  final bool broken;

  @override
  Widget build(BuildContext context) {
    final colors = categoryColors(context, icon);
    final glyph = broken ? Icons.broken_image_outlined : categoryIconData(icon);
    return LayoutBuilder(
      builder: (context, constraints) {
        final side = constraints.biggest.shortestSide;
        // Thumbnails (chat rows, drafts) only fit the icon itself.
        if (!side.isFinite || side < 96) {
          return ColoredBox(
            color: colors.background,
            child: Center(
              child: Icon(glyph, size: side.isFinite ? side * 0.45 : 24, color: colors.foreground),
            ),
          );
        }
        final badge = (side * 0.4).clamp(48.0, 84.0);
        return ClipRect(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  colors.background,
                  Color.lerp(colors.background, colors.foreground, 0.16)!,
                ],
              ),
            ),
            child: Stack(
              fit: StackFit.expand,
              children: [
                // Oversized echo of the icon, bleeding off the corner.
                Positioned(
                  right: -side * 0.18,
                  bottom: -side * 0.22,
                  child: Icon(
                    glyph,
                    size: side * 0.95,
                    color: colors.foreground.withValues(alpha: 0.08),
                  ),
                ),
                Center(
                  child: Container(
                    width: badge,
                    height: badge,
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.82),
                      shape: BoxShape.circle,
                    ),
                    alignment: Alignment.center,
                    child: Icon(glyph, size: badge * 0.5, color: colors.foreground),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
