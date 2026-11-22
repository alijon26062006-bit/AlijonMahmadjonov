import 'package:flutter_riverpod/flutter_riverpod.dart';

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
      .search(const ListingQuery(pageSize: 6));
  return result.items;
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
