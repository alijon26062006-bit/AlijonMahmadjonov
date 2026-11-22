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

    // Compact card: three fit across a phone screen.
    final card = Material(
      color: context.colors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
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
              aspectRatio: 1,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  DaryobListingImage(
                    source: listing.photos.isEmpty
                        ? null
                        : listing.photos.first,
                    icon: category?.icon ?? CategoryIcon.generic,
                    cacheWidth: ((width ?? 140) * dpr).round(),
                  ),
                  if (listing.isPromotedAt(now) || listing.isDemo)
                    Positioned(
                      left: 4,
                      top: 4,
                      right: 30,
                      child: Align(
                        alignment: Alignment.topLeft,
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.topLeft,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (listing.isPromotedAt(now))
                                PromotionBadge(type: listing.promotion!.type),
                              if (listing.isPromotedAt(now) && listing.isDemo)
                                const SizedBox(width: 3),
                              if (listing.isDemo) const DemoBadge(),
                            ],
                          ),
                        ),
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
                      right: 4,
                      bottom: 4,
                      child: _PhotoCount(count: listing.photos.length),
                    ),
                ],
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(7, 6, 7, 6),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      price,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: context.text.titleSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                        fontSize: 13,
                        height: 1.25,
                      ),
                    ),
                    const SizedBox(height: 1),
                    Expanded(
                      child: Text(
                        listing.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: context.text.bodySmall?.copyWith(
                          fontSize: 12,
                          height: 1.25,
                          color: context.colors.onSurface,
                        ),
                      ),
                    ),
                    Text(
                      [
                        if (region != null) region.name.of(context),
                        ageLabel(l10n, listing.sortDate, now),
                      ].join(' · '),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: context.text.bodySmall?.copyWith(fontSize: 10.5, height: 1.2),
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
          dimension: 40,
          child: Center(
            child: Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.92),
                shape: BoxShape.circle,
              ),
              child: Icon(
                isFavorite
                    ? Icons.favorite_rounded
                    : Icons.favorite_border_rounded,
                size: 16,
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
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.photo_camera_outlined,
            size: 10,
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

/// Responsive grid of compact listing cards: 3 columns on phones (2 on very
/// narrow screens), more on tablets.
class SliverListingGrid extends StatelessWidget {
  const SliverListingGrid({super.key, required this.listings});
  final List<Listing> listings;

  static const double gap = DaryobSpacing.sm;

  static int columnsFor(double width) {
    if (width < 300) return 2;
    if (width < 560) return 3;
    if (width < 800) return 4;
    if (width < 1040) return 5;
    return 6;
  }

  static double extentFor(BuildContext context, double cellWidth) {
    final textScale = MediaQuery.textScalerOf(context).scale(1);
    // Square image + price, two title lines, location, paddings.
    return cellWidth + 80 * textScale;
  }

  /// Width of a carousel card so that exactly three fit across [screenWidth].
  static double carouselCardWidth(double screenWidth) {
    final width = screenWidth - DaryobSpacing.page * 2;
    final columns = columnsFor(width);
    return (width - gap * (columns - 1)) / columns;
  }

  @override
  Widget build(BuildContext context) {
    return SliverLayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.crossAxisExtent - DaryobSpacing.page * 2;
        final columns = columnsFor(width);
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
              (context, index) =>
                  DaryobListingCard(listing: listings[index], width: cell),
              childCount: listings.length,
            ),
          ),
        );
      },
    );
  }
}

/// Horizontal, swipeable row of compact cards — three visible at a time.
class ListingCarousel extends StatelessWidget {
  const ListingCarousel({super.key, required this.listings});
  final List<Listing> listings;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final cardWidth = SliverListingGrid.carouselCardWidth(constraints.maxWidth);
        return SizedBox(
          height: SliverListingGrid.extentFor(context, cardWidth),
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
            itemCount: listings.length,
            separatorBuilder: (_, _) => const SizedBox(width: SliverListingGrid.gap),
            itemBuilder: (_, i) =>
                DaryobListingCard(listing: listings[i], width: cardWidth),
          ),
        );
      },
    );
  }
}
