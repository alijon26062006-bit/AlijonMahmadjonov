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
        final art = broken
            ? null
            : (double size) => DaryobCategoryArt(icon: icon, size: size);
        // Thumbnails (chat rows, drafts) only fit the picture itself.
        if (!side.isFinite || side < 96) {
          final size = side.isFinite ? side * 0.7 : 28.0;
          return ColoredBox(
            color: colors.background,
            child: Center(
              child: art?.call(size) ?? Icon(glyph, size: size * 0.7, color: colors.foreground),
            ),
          );
        }
        final picture = (side * 0.56).clamp(64.0, 150.0);
        return ClipRect(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  colors.background,
                  Color.lerp(colors.background, colors.foreground, 0.22)!,
                ],
              ),
            ),
            child: Stack(
              fit: StackFit.expand,
              children: [
                // Soft light spot behind the picture so white objects stand out.
                Center(
                  child: Container(
                    width: picture * 1.35,
                    height: picture * 1.35,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: colors.foreground.withValues(alpha: 0.10),
                    ),
                  ),
                ),
                Center(
                  child: art?.call(picture) ?? Icon(glyph, size: picture * 0.6, color: colors.foreground),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
