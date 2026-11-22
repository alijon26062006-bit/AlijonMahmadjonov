import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/router/routes.dart';
import '../../app/theme/tokens.dart';
import '../../features/favorites/application/favorites_controller.dart';
import '../../features/catalog/presentation/catalog_ui.dart';
import '../../features/listings/application/listing_providers.dart';
import '../../shared/models/category.dart';
import '../../shared/models/listing.dart';
import '../../shared/models/localized_text.dart';
import '../providers/core_providers.dart';
import 'badges.dart';
import 'listing_image.dart';
import 'toast.dart';

/// Reusable listing card for grids and carousels.
class DaryobListingCard extends ConsumerWidget {
  const DaryobListingCard({super.key, required this.listing, this.width});

  final Listing listing;

  /// Fixed width for horizontal carousels; null fills the grid cell.
  final double? width;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final now = ref.watch(nowProvider);
    final category = ref
        .watch(categoryRegistryProvider)
        .byId(listing.categoryId);
    final region = ref.watch(regionDirectoryProvider).byId(listing.regionId);
    final isFavorite = ref.watch(
      favoritesControllerProvider.select((ids) => ids.contains(listing.id)),
    );
    final isVip = listing.isVipAt(now);
    final palette = context.palette;
    final dpr = MediaQuery.devicePixelRatioOf(context);

    final price = listingPriceText(context, ref, listing);

    final card = Material(
      color: context.colors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: DaryobRadius.cardAll,
        side: BorderSide(
          color: isVip ? DaryobColors.lime : palette.border,
          width: isVip ? 1.6 : 1,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push(Routes.listing(listing.id)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            AspectRatio(
              aspectRatio: 4 / 3,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  DaryobListingImage(
                    source: listing.photos.isEmpty
                        ? null
                        : listing.photos.first,
                    icon: category?.icon ?? CategoryIcon.generic,
                    cacheWidth: ((width ?? 200) * dpr).round(),
                  ),
                  Positioned(
                    left: DaryobSpacing.sm,
                    top: DaryobSpacing.sm,
                    right: 48,
                    child: Wrap(
                      spacing: 4,
                      runSpacing: 4,
                      children: [
                        if (listing.isPromotedAt(now))
                          PromotionBadge(type: listing.promotion!.type),
                        if (listing.isDemo) const DemoBadge(),
                      ],
                    ),
                  ),
                  Positioned(
                    right: 0,
                    top: 0,
                    child: _FavoriteButton(
                      isFavorite: isFavorite,
                      onPressed: () async {
                        final added = await ref
                            .read(favoritesControllerProvider.notifier)
                            .toggle(listing.id);
                        if (context.mounted) {
                          DaryobToast.show(
                            context,
                            added ? l10n.favoriteAdded : l10n.favoriteRemoved,
                          );
                        }
                      },
                    ),
                  ),
                  if (listing.photos.length > 1)
                    Positioned(
                      right: DaryobSpacing.sm,
                      bottom: DaryobSpacing.sm,
                      child: _PhotoCount(count: listing.photos.length),
                    ),
                ],
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(
                  DaryobSpacing.md,
                  DaryobSpacing.sm + 2,
                  DaryobSpacing.md,
                  DaryobSpacing.sm,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      price,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: context.text.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    if (listing.isNegotiable &&
                        listing.price != null &&
                        listing.price! > 0)
                      Text(
                        l10n.negotiable,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: context.text.labelSmall,
                      ),
                    const SizedBox(height: 2),
                    Flexible(
                      child: Text(
                        listing.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: context.text.bodyMedium?.copyWith(height: 1.3),
                      ),
                    ),
                    const SizedBox(height: DaryobSpacing.xs),
                    Text(
                      [
                        if (region != null) region.name.of(context),
                        ageLabel(l10n, listing.sortDate, now),
                      ].join(' · '),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: context.text.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );

    return width == null ? card : SizedBox(width: width, child: card);
  }
}

class _FavoriteButton extends StatelessWidget {
  const _FavoriteButton({required this.isFavorite, required this.onPressed});
  final bool isFavorite;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    // A separate 48×48 tap area so tapping the heart never opens the listing.
    return Semantics(
      button: true,
      toggled: isFavorite,
      label: isFavorite ? l10n.favoriteRemove : l10n.favoriteAdd,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onPressed,
        child: SizedBox.square(
          dimension: DaryobSizes.touch,
          child: Center(
            child: Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.92),
                shape: BoxShape.circle,
              ),
              child: Icon(
                isFavorite
                    ? Icons.favorite_rounded
                    : Icons.favorite_border_rounded,
                size: 19,
                color: isFavorite ? DaryobColors.error : DaryobColors.navy,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _PhotoCount extends StatelessWidget {
  const _PhotoCount({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.photo_camera_outlined,
            size: 12,
            color: Colors.white,
          ),
          const SizedBox(width: 3),
          Text(
            '$count',
            style: context.text.labelSmall?.copyWith(color: Colors.white),
          ),
        ],
      ),
    );
  }
}

/// Responsive grid of listing cards: 2 columns on phones, 1 on very narrow
/// screens, 3+ on tablets.
class SliverListingGrid extends StatelessWidget {
  const SliverListingGrid({super.key, required this.listings});
  final List<Listing> listings;

  static int columnsFor(double width) {
    if (width < 330) return 1;
    if (width < 640) return 2;
    if (width < 960) return 3;
    return 4;
  }

  static double extentFor(BuildContext context, double cellWidth) {
    final textScale = MediaQuery.textScalerOf(context).scale(1);
    // Image (4:3) + price, "negotiable", two title lines, location, paddings.
    return cellWidth * 0.75 + 128 * textScale;
  }

  @override
  Widget build(BuildContext context) {
    return SliverLayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.crossAxisExtent - DaryobSpacing.page * 2;
        final columns = columnsFor(width);
        const gap = DaryobSpacing.md;
        final cell = (width - gap * (columns - 1)) / columns;
        return SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
          sliver: SliverGrid(
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: columns,
              mainAxisSpacing: gap,
              crossAxisSpacing: gap,
              mainAxisExtent: extentFor(context, cell),
            ),
            delegate: SliverChildBuilderDelegate(
              (context, index) => DaryobListingCard(listing: listings[index]),
              childCount: listings.length,
            ),
          ),
        );
      },
    );
  }
}
