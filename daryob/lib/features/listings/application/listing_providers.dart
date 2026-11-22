import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/failure.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/models/user.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../domain/listing_query.dart';

/// Paginated listings for any query. Used by home, categories and search.
final pagedListingsProvider = AsyncNotifierProvider.autoDispose
    .family<PagedListingsController, PagedListings, ListingQuery>(
      PagedListingsController.new,
    );

class PagedListings {
  const PagedListings({
    required this.items,
    required this.page,
    required this.hasMore,
    this.total,
    this.isLoadingMore = false,
    this.loadMoreError,
  });

  final List<Listing> items;
  final int page;
  final bool hasMore;
  final int? total;
  final bool isLoadingMore;
  final AppFailure? loadMoreError;

  PagedListings copyWith({
    List<Listing>? items,
    int? page,
    bool? hasMore,
    bool? isLoadingMore,
    AppFailure? loadMoreError,
    bool clearError = false,
  }) {
    return PagedListings(
      items: items ?? this.items,
      page: page ?? this.page,
      hasMore: hasMore ?? this.hasMore,
      total: total,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      loadMoreError: clearError ? null : (loadMoreError ?? this.loadMoreError),
    );
  }
}

class PagedListingsController extends AsyncNotifier<PagedListings> {
  PagedListingsController(this.query);

  final ListingQuery query;

  @override
  Future<PagedListings> build() async {
    final result = await ref.watch(listingRepositoryProvider).search(query);
    return PagedListings(
      items: result.items,
      page: result.page,
      hasMore: result.hasMore,
      total: result.total,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() async {
    final current = state.value;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncData(current.copyWith(isLoadingMore: true, clearError: true));
    try {
      final next = await ref
          .read(listingRepositoryProvider)
          .search(query, page: current.page + 1);
      final known = current.items.map((l) => l.id).toSet();
      state = AsyncData(
        current.copyWith(
          items: [
            ...current.items,
            ...next.items.where((l) => !known.contains(l.id)),
          ],
          page: next.page,
          hasMore: next.hasMore,
          isLoadingMore: false,
        ),
      );
    } catch (e) {
      state = AsyncData(
        current.copyWith(isLoadingMore: false, loadMoreError: asFailure(e)),
      );
    }
  }
}

final listingByIdProvider = FutureProvider.autoDispose.family<Listing?, String>(
  (ref, id) {
    return ref.watch(listingRepositoryProvider).getById(id);
  },
);

final sellerProvider = FutureProvider.autoDispose
    .family<SellerSummary?, String>((ref, userId) {
      return ref.watch(sellerRepositoryProvider).seller(userId);
    });

final categoryCountsProvider = FutureProvider.autoDispose<Map<String, int>>((
  ref,
) {
  return ref.watch(listingRepositoryProvider).countByCategory();
});

/// Other active listings of the same seller.
final sellerListingsProvider = FutureProvider.autoDispose
    .family<List<Listing>, String>((ref, sellerId) async {
      final result = await ref
          .watch(listingRepositoryProvider)
          .search(
            ListingQuery(
              ownerId: sellerId,
              sort: ListingSort.newest,
              pageSize: 20,
            ),
          );
      return result.items;
    });

/// Same category, excluding the listing itself.
final similarListingsProvider = FutureProvider.autoDispose
    .family<List<Listing>, ({String listingId, String categoryId})>((
      ref,
      key,
    ) async {
      final result = await ref
          .watch(listingRepositoryProvider)
          .search(
            ListingQuery(
              categoryId: key.categoryId,
              excludeIds: {key.listingId},
              pageSize: 6,
            ),
          );
      return result.items;
    });

/// Bumped whenever listings change; lists that aren't paginated watch it.
final listingsRevisionProvider = NotifierProvider<ListingsRevision, int>(
  ListingsRevision.new,
);

class ListingsRevision extends Notifier<int> {
  @override
  int build() => 0;

  void bump() => state++;
}

/// Call after anything changes listings so every list reloads.
void invalidateListings(Ref ref) {
  ref.read(listingsRevisionProvider.notifier).bump();
  ref.invalidate(pagedListingsProvider);
  ref.invalidate(listingByIdProvider);
  ref.invalidate(categoryCountsProvider);
  ref.invalidate(sellerListingsProvider);
  ref.invalidate(similarListingsProvider);
}

/// Same as [invalidateListings] for widget code.
void invalidateListingsFromWidget(WidgetRef ref) {
  ref.read(listingsRevisionProvider.notifier).bump();
  ref.invalidate(pagedListingsProvider);
  ref.invalidate(listingByIdProvider);
  ref.invalidate(categoryCountsProvider);
  ref.invalidate(sellerListingsProvider);
  ref.invalidate(similarListingsProvider);
}

/// The clock, read once per build — keeps "VIP"/"TOP" badges consistent.
final nowProvider = Provider.autoDispose<DateTime>(
  (ref) => ref.watch(clockProvider)(),
);
