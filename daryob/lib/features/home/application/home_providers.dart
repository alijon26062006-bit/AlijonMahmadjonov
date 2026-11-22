import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/models/category.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../categories/data/tajikistan_regions.dart';
import '../../listings/domain/listing_query.dart';
import '../../settings/application/settings_controller.dart';

/// Active VIP / VIP+ listings for the carousel.
final homeVipProvider = FutureProvider.autoDispose<List<Listing>>((ref) async {
  final now = ref.watch(clockProvider)();
  final result = await ref
      .watch(listingRepositoryProvider)
      .search(const ListingQuery(onlyPromoted: true, pageSize: 12));
  return result.items.where((l) => l.isVipAt(now)).toList();
});

/// "For you": promoted first, then newest. A recommendation engine will
/// replace this ranking later; the section keeps the same interface.
final homeRecommendedProvider = FutureProvider.autoDispose<List<Listing>>((
  ref,
) async {
  final result = await ref
      .watch(listingRepositoryProvider)
      .search(const ListingQuery(pageSize: 12));
  return result.items;
});

/// One swipeable row per top-level category that has listings, in catalog
/// order: the newest listings of that category (promoted first).
final homeCategoryRowsProvider = FutureProvider.autoDispose<
  List<(CategoryDefinition, List<Listing>)>
>((ref) async {
  final repo = ref.watch(listingRepositoryProvider);
  final categories = ref.watch(categoryRegistryProvider).topLevel;
  final counts = await repo.countByCategory();
  final withListings = categories.where((c) => (counts[c.id] ?? 0) > 0).toList();
  final rows = await Future.wait([
    for (final c in withListings)
      repo
          .search(ListingQuery(categoryId: c.id, pageSize: 12))
          .then((r) => (c, r.items)),
  ]);
  return [for (final r in rows) if (r.$2.isNotEmpty) r];
});

/// Listings in the user's chosen region (region matching, not GPS).
final homeNearbyProvider = FutureProvider.autoDispose<List<Listing>>((
  ref,
) async {
  final regionId = ref.watch(
    settingsControllerProvider.select((s) => s.regionId),
  );
  if (regionId == RegionIds.country) return const [];
  final result = await ref
      .watch(listingRepositoryProvider)
      .search(
        ListingQuery(regionId: regionId, sort: ListingSort.newest, pageSize: 4),
      );
  return result.items;
});

const homeRecentQuery = ListingQuery(sort: ListingSort.newest, pageSize: 10);
