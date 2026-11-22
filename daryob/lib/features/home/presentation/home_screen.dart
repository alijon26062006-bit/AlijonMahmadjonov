import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show ProviderListenable;
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/category_visuals.dart';
import '../../../shared/widgets/daryob_logo.dart';
import '../../../shared/widgets/daryob_search_bar.dart';
import '../../../shared/widgets/listing_card.dart';
import '../../../shared/widgets/location_selector.dart';
import '../../../shared/widgets/section_header.dart';
import '../../../shared/widgets/skeleton.dart';
import '../../../shared/widgets/states.dart';
import '../../categories/data/tajikistan_regions.dart';
import '../../listings/application/listing_providers.dart';
import '../../notifications/application/notification_providers.dart';
import '../../settings/application/settings_controller.dart';
import '../application/home_providers.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_maybeLoadMore);
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _maybeLoadMore() {
    if (_scroll.position.extentAfter < 600) {
      ref.read(pagedListingsProvider(homeRecentQuery).notifier).loadMore();
    }
  }

  Future<void> _refresh() async {
    ref.invalidate(homeVipProvider);
    ref.invalidate(homeRecommendedProvider);
    ref.invalidate(homeNearbyProvider);
    ref.invalidate(categoryCountsProvider);
    await ref.read(pagedListingsProvider(homeRecentQuery).notifier).refresh();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final regionId = ref.watch(
      settingsControllerProvider.select((s) => s.regionId),
    );
    final region = ref.watch(regionDirectoryProvider).byId(regionId);
    final recent = ref.watch(pagedListingsProvider(homeRecentQuery));

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: CustomScrollView(
            controller: _scroll,
            slivers: [
              const SliverToBoxAdapter(child: _Header()),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(
                    DaryobSpacing.page,
                    DaryobSpacing.sm,
                    DaryobSpacing.page,
                    0,
                  ),
                  child: DaryobSearchBar(
                    onTap: () => context.push(Routes.search),
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: _Hero()),
              DaryobSectionHeader(
                title: l10n.categories,
                onSeeAll: () => context.push(Routes.categories),
              ).sliver,
              const _CategoryGrid(),
              _ListingSection(
                provider: homeVipProvider,
                title: l10n.vipListings,
                leading: const Icon(
                  Icons.star_rounded,
                  color: DaryobColors.warning,
                ),
                horizontal: true,
              ),
              _ListingSection(
                provider: homeRecommendedProvider,
                title: l10n.recommended,
              ),
              if (regionId != RegionIds.country && region != null)
                _ListingSection(
                  provider: homeNearbyProvider,
                  title: l10n.nearbyIn(region.name.of(context)),
                  onSeeAll: () => context.push(Routes.search),
                ),
              DaryobSectionHeader(title: l10n.newListings).sliver,
              ...recent.when(
                loading: () => const [SliverListingGridSkeleton()],
                error: (e, _) => [
                  SliverToBoxAdapter(
                    child: DaryobErrorState(
                      error: e,
                      compact: true,
                      onRetry: () => ref.invalidate(
                        pagedListingsProvider(homeRecentQuery),
                      ),
                    ),
                  ),
                ],
                data: (page) => page.items.isEmpty
                    ? [
                        SliverToBoxAdapter(
                          child: DaryobEmptyState(
                            icon: Icons.inventory_2_outlined,
                            compact: true,
                            title: l10n.noListingsYet,
                            message: l10n.noListingsYetBody,
                            actionLabel: l10n.createListing,
                            onAction: () => context.go(Routes.create),
                          ),
                        ),
                      ]
                    : [
                        SliverListingGrid(listings: page.items),
                        SliverToBoxAdapter(
                          child: _LoadMoreFooter(
                            isLoading: page.isLoadingMore,
                            hasMore: page.hasMore,
                            error: page.loadMoreError,
                            onRetry: () => ref
                                .read(
                                  pagedListingsProvider(homeRecentQuery)
                                      .notifier,
                                )
                                .loadMore(),
                          ),
                        ),
                      ],
              ),
              const SliverToBoxAdapter(
                child: SizedBox(height: DaryobSpacing.xxxl),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

extension on Widget {
  Widget get sliver => SliverToBoxAdapter(child: this);
}

class _Header extends ConsumerWidget {
  const _Header();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final regionId = ref.watch(
      settingsControllerProvider.select((s) => s.regionId),
    );
    final unread = ref.watch(unreadNotificationsProvider).value ?? 0;
    final lang = context.languageCode;

    return Padding(
      padding: const EdgeInsets.fromLTRB(
        DaryobSpacing.page,
        DaryobSpacing.sm,
        DaryobSpacing.xs,
        0,
      ),
      child: Row(
        children: [
          const DaryobWordmark(height: 30),
          const SizedBox(width: DaryobSpacing.sm),
          Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: DaryobLocationChip(
                regionId: regionId,
                dense: true,
                onChanged: (id) =>
                    ref.read(settingsControllerProvider.notifier).setRegion(id),
              ),
            ),
          ),
          TextButton(
            onPressed: () => ref
                .read(settingsControllerProvider.notifier)
                .setLanguage(lang == 'tg' ? 'ru' : 'tg'),
            style: TextButton.styleFrom(minimumSize: const Size(44, 44)),
            child: Text(
              lang == 'tg' ? 'RU' : 'TJ',
              semanticsLabel: l10n.switchLanguage,
            ),
          ),
          IconButton(
            tooltip: l10n.notifications,
            onPressed: () => context.push(Routes.notifications),
            icon: Badge(
              isLabelVisible: unread > 0,
              label: Text(unread > 9 ? '9+' : '$unread'),
              child: const Icon(Icons.notifications_none_rounded),
            ),
          ),
        ],
      ),
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero();

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final compact = MediaQuery.sizeOf(context).height < 680;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        DaryobSpacing.page,
        DaryobSpacing.lg,
        DaryobSpacing.page,
        0,
      ),
      child: Container(
        decoration: const BoxDecoration(
          color: DaryobColors.navy,
          borderRadius: DaryobRadius.heroAll,
        ),
        clipBehavior: Clip.antiAlias,
        child: Stack(
          children: [
            Positioned(
              right: -24,
              bottom: -30,
              child: Opacity(
                opacity: 0.18,
                child: DaryobMark(size: compact ? 130 : 160),
              ),
            ),
            Padding(
              padding: EdgeInsets.all(
                compact ? DaryobSpacing.lg : DaryobSpacing.xl,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.heroTitle,
                    style: context.text.titleLarge?.copyWith(
                      color: Colors.white,
                      fontSize: compact ? 19 : 22,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: DaryobSpacing.xs),
                  Text(
                    l10n.heroSubtitle,
                    style: context.text.bodyMedium?.copyWith(
                      color: Colors.white70,
                    ),
                  ),
                  const SizedBox(height: DaryobSpacing.lg),
                  DaryobPrimaryButton(
                    label: l10n.createListing,
                    icon: Icons.add_rounded,
                    tone: DaryobButtonTone.accent,
                    expand: false,
                    onPressed: () => context.go(Routes.create),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CategoryGrid extends ConsumerWidget {
  const _CategoryGrid();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categories = ref
        .watch(categoryRegistryProvider)
        .topLevel
        .take(8)
        .toList();
    return SliverPadding(
      padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.xs),
      sliver: SliverGrid(
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: MediaQuery.sizeOf(context).width < 340 ? 3 : 4,
          mainAxisExtent: 76 + 36 * MediaQuery.textScalerOf(context).scale(1),
        ),
        delegate: SliverChildBuilderDelegate(
          (context, i) => DaryobCategoryTile(
            category: categories[i],
            onTap: () => context.push(Routes.category(categories[i].slug)),
          ),
          childCount: categories.length,
        ),
      ),
    );
  }
}

/// A titled section backed by a list provider. Hidden when empty.
class _ListingSection extends ConsumerWidget {
  const _ListingSection({
    required this.provider,
    required this.title,
    this.leading,
    this.horizontal = false,
    this.onSeeAll,
  });

  final ProviderListenable<AsyncValue<List<Listing>>> provider;
  final String title;
  final Widget? leading;
  final bool horizontal;
  final VoidCallback? onSeeAll;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(provider);
    final header = DaryobSectionHeader(
      title: title,
      leading: leading,
      onSeeAll: onSeeAll,
    );

    return value.when(
      loading: () => SliverMainAxisGroup(
        slivers: [
          SliverToBoxAdapter(child: header),
          horizontal
              ? const SliverToBoxAdapter(child: _CarouselSkeleton())
              : const SliverListingGridSkeleton(count: 2),
        ],
      ),
      // Errors are reported once, by the "new listings" section below.
      error: (_, _) => const SliverToBoxAdapter(child: SizedBox.shrink()),
      data: (items) {
        if (items.isEmpty) {
          return const SliverToBoxAdapter(child: SizedBox.shrink());
        }
        return SliverMainAxisGroup(
          slivers: [
            SliverToBoxAdapter(child: header),
            if (horizontal)
              SliverToBoxAdapter(child: _Carousel(items: items))
            else
              SliverListingGrid(listings: items),
          ],
        );
      },
    );
  }
}

class _Carousel extends StatelessWidget {
  const _Carousel({required this.items});
  final List<Listing> items;

  @override
  Widget build(BuildContext context) {
    const width = 210.0;
    final height = SliverListingGrid.extentFor(context, width);
    return SizedBox(
      height: height,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
        itemCount: items.length,
        separatorBuilder: (_, _) => const SizedBox(width: DaryobSpacing.md),
        itemBuilder: (_, i) =>
            DaryobListingCard(listing: items[i], width: width),
      ),
    );
  }
}

class _CarouselSkeleton extends StatelessWidget {
  const _CarouselSkeleton();

  @override
  Widget build(BuildContext context) {
    const width = 210.0;
    return SizedBox(
      height: SliverListingGrid.extentFor(context, width),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        physics: const NeverScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
        itemCount: 3,
        separatorBuilder: (_, _) => const SizedBox(width: DaryobSpacing.md),
        itemBuilder: (_, _) =>
            const SizedBox(width: width, child: ListingCardSkeleton()),
      ),
    );
  }
}

class _LoadMoreFooter extends StatelessWidget {
  const _LoadMoreFooter({
    required this.isLoading,
    required this.hasMore,
    required this.error,
    required this.onRetry,
  });

  final bool isLoading;
  final bool hasMore;
  final Object? error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    Widget child;
    if (isLoading) {
      child = const SizedBox.square(
        dimension: 28,
        child: CircularProgressIndicator(strokeWidth: 2.4),
      );
    } else if (error != null) {
      child = TextButton.icon(
        onPressed: onRetry,
        icon: const Icon(Icons.refresh_rounded),
        label: Text(l10n.loadMoreFailed),
      );
    } else if (hasMore) {
      child = TextButton(onPressed: onRetry, child: Text(l10n.loadMore));
    } else {
      child = Text(l10n.endOfList, style: context.text.bodySmall);
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: DaryobSpacing.xl),
      child: Center(child: child),
    );
  }
}

/// Exposed for other paginated screens.
class PagedFooter extends StatelessWidget {
  const PagedFooter({super.key, required this.page, required this.onLoadMore});
  final PagedListings page;
  final VoidCallback onLoadMore;

  @override
  Widget build(BuildContext context) => _LoadMoreFooter(
    isLoading: page.isLoadingMore,
    hasMore: page.hasMore,
    error: page.loadMoreError,
    onRetry: onLoadMore,
  );
}
