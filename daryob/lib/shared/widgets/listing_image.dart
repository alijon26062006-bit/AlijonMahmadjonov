import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/theme/tokens.dart';
import '../models/category.dart';
import 'category_visuals.dart';

/// Shows a listing photo from a URL (cached) or a local file. Without a
/// photo, shows the category icon on a soft background — never a stock
/// picture that could look like the real item.
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

class _Placeholder extends StatelessWidget {
  const _Placeholder({required this.icon, this.broken = false});
  final CategoryIcon icon;
  final bool broken;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: context.palette.surfaceMuted,
      child: Center(
        child: Icon(
          broken ? Icons.broken_image_outlined : categoryIconData(icon),
          size: 40,
          color: context.palette.textSecondary.withValues(alpha: 0.7),
        ),
      ),
    );
  }
}
