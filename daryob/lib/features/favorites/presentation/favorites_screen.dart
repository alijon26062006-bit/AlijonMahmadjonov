import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/listing_card.dart';
import '../../../shared/widgets/skeleton.dart';
import '../../../shared/widgets/states.dart';
import '../../authentication/application/session_controller.dart';
import '../../listings/application/listing_providers.dart';
import '../application/favorites_controller.dart';

/// Saved listings in the order they were saved. Listings deleted by their
/// owner are dropped from the list.
final favoriteListingsProvider = FutureProvider.autoDispose<List<Listing>>((
  ref,
) async {
  ref.watch(listingsRevisionProvider);
  final ids = ref.watch(favoritesControllerProvider);
  final repo = ref.watch(listingRepositoryProvider);
  final result = <Listing>[];
  for (final id in ids) {
    final listing = await repo.getById(id);
    if (listing != null) result.add(listing);
  }
  return result;
});

class FavoritesScreen extends ConsumerStatefulWidget {
  const FavoritesScreen({super.key});

  @override
  ConsumerState<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends ConsumerState<FavoritesScreen> {
  String? _categoryFilter;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final value = ref.watch(favoriteListingsProvider);
    final categories = ref.watch(categoryRegistryProvider);
    final isGuest = ref.watch(sessionControllerProvider) == null;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.tabFavorites)),
      body: value.when(
        // Removing a heart reloads the list; keep showing the old one meanwhile.
        skipLoadingOnReload: true,
        loading: () =>
            const CustomScrollView(slivers: [SliverListingGridSkeleton()]),
        error: (e, _) => DaryobErrorState(
          error: e,
          onRetry: () => ref.invalidate(favoriteListingsProvider),
        ),
        data: (all) {
          if (all.isEmpty) {
            return DaryobEmptyState(
              icon: Icons.favorite_border_rounded,
              title: l10n.favoritesEmpty,
              message: l10n.favoritesEmptyBody,
              actionLabel: l10n.browseListings,
              onAction: () => context.go(Routes.home),
            );
          }
          final present = {for (final l in all) l.categoryId};
          final filtered = _categoryFilter == null
              ? all
              : all.where((l) => l.categoryId == _categoryFilter).toList();
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(favoriteListingsProvider),
            child: CustomScrollView(
              slivers: [
                if (isGuest)
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                        DaryobSpacing.page,
                        0,
                        DaryobSpacing.page,
                        DaryobSpacing.md,
                      ),
                      child: DaryobNotice(message: l10n.favoritesGuestNotice),
                    ),
                  ),
                if (present.length > 1)
                  SliverToBoxAdapter(
                    child: SizedBox(
                      height: 48,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(
                          horizontal: DaryobSpacing.page,
                        ),
                        children: [
                          ChoiceChip(
                            label: Text(l10n.all),
                            selected: _categoryFilter == null,
                            onSelected: (_) =>
                                setState(() => _categoryFilter = null),
                          ),
                          for (final id in present)
                            if (categories.byId(id) != null)
                              Padding(
                                padding: const EdgeInsets.only(
                                  left: DaryobSpacing.sm,
                                ),
                                child: ChoiceChip(
                                  label: Text(
                                    categories.byId(id)!.name.of(context),
                                  ),
                                  selected: _categoryFilter == id,
                                  onSelected: (_) =>
                                      setState(() => _categoryFilter = id),
                                ),
                              ),
                        ],
                      ),
                    ),
                  ),
                const SliverToBoxAdapter(
                  child: SizedBox(height: DaryobSpacing.sm),
                ),
                SliverListingGrid(listings: filtered),
                const SliverToBoxAdapter(
                  child: SizedBox(height: DaryobSpacing.xxl),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
