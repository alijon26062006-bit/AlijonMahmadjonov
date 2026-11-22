import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/filter_sheet.dart';
import '../../../shared/widgets/listing_card.dart';
import '../../../shared/widgets/location_selector.dart';
import '../../../shared/widgets/skeleton.dart';
import '../../../shared/widgets/states.dart';
import '../../home/presentation/home_screen.dart';
import '../../listings/application/listing_providers.dart';
import '../../listings/domain/listing_query.dart';
import '../../settings/application/settings_controller.dart';

/// Generic listings screen for any category. Category modules can later
/// add their own header sections; filtering already uses the category's
/// filter schema through the shared filter sheet.
class CategoryListingsScreen extends ConsumerStatefulWidget {
  const CategoryListingsScreen({super.key, required this.slug});
  final String slug;

  @override
  ConsumerState<CategoryListingsScreen> createState() =>
      _CategoryListingsScreenState();
}

class _CategoryListingsScreenState
    extends ConsumerState<CategoryListingsScreen> {
  ListingQuery? _query;
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      final q = _query;
      if (q != null && _scroll.position.extentAfter < 600) {
        ref.read(pagedListingsProvider(q).notifier).loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final category = ref.watch(categoryRegistryProvider).bySlug(widget.slug);

    if (category == null) {
      return Scaffold(
        appBar: AppBar(),
        body: DaryobEmptyState(
          icon: Icons.search_off_rounded,
          title: l10n.categoryNotFound,
        ),
      );
    }

    final query = _query ??= ListingQuery(
      categoryId: category.id,
      regionId: ref.read(settingsControllerProvider).regionId,
    );
    final children = ref
        .watch(categoryRegistryProvider)
        .childrenOf(category.id);
    final page = ref.watch(pagedListingsProvider(query));

    return Scaffold(
      appBar: AppBar(
        title: Text(category.name.of(context)),
        actions: [
          IconButton(
            tooltip: l10n.search,
            icon: const Icon(Icons.search_rounded),
            onPressed: () =>
                context.push('${Routes.search}?category=${category.id}'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () =>
            ref.read(pagedListingsProvider(query).notifier).refresh(),
        child: CustomScrollView(
          controller: _scroll,
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(
                  DaryobSpacing.page,
                  0,
                  DaryobSpacing.page,
                  DaryobSpacing.md,
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: DaryobLocationChip(
                          regionId: query.regionId ?? 'tj',
                          onChanged: (id) => setState(
                            () => _query = query.copyWith(regionId: id),
                          ),
                        ),
                      ),
                    ),
                    Badge(
                      isLabelVisible: query.activeFilterCount > 1,
                      label: Text('${query.activeFilterCount - 1}'),
                      child: OutlinedButton.icon(
                        style: OutlinedButton.styleFrom(
                          minimumSize: const Size(0, 44),
                        ),
                        onPressed: () async {
                          final next = await showFilterSheet(
                            context,
                            query: query,
                            lockCategory: true,
                          );
                          if (next != null) setState(() => _query = next);
                        },
                        icon: const Icon(Icons.tune_rounded, size: 18),
                        label: Text(l10n.filters),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            if (children.isNotEmpty)
              SliverToBoxAdapter(
                child: SizedBox(
                  height: 48,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(
                      horizontal: DaryobSpacing.page,
                    ),
                    children: [
                      for (final c in children)
                        Padding(
                          padding: const EdgeInsets.only(
                            right: DaryobSpacing.sm,
                          ),
                          child: ActionChip(
                            label: Text(c.name.of(context)),
                            onPressed: () =>
                                context.push(Routes.category(c.slug)),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ...page.when(
              loading: () => const [SliverListingGridSkeleton(count: 6)],
              error: (e, _) => [
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: DaryobErrorState(
                    error: e,
                    onRetry: () => ref.invalidate(pagedListingsProvider(query)),
                  ),
                ),
              ],
              data: (data) => data.items.isEmpty
                  ? [
                      SliverFillRemaining(
                        hasScrollBody: false,
                        child: DaryobEmptyState(
                          icon: Icons.manage_search_rounded,
                          title: l10n.nothingFound,
                          message: l10n.nothingFoundBody,
                          actionLabel: query.activeFilterCount > 1
                              ? l10n.resetFilters
                              : null,
                          onAction: () => setState(
                            () => _query = ListingQuery(
                              categoryId: category.id,
                              regionId: query.regionId,
                            ),
                          ),
                        ),
                      ),
                    ]
                  : [
                      if (data.total != null)
                        SliverToBoxAdapter(
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(
                              DaryobSpacing.page,
                              0,
                              DaryobSpacing.page,
                              DaryobSpacing.md,
                            ),
                            child: Text(
                              l10n.listingsCount(data.total!),
                              style: context.text.bodySmall,
                            ),
                          ),
                        ),
                      SliverListingGrid(listings: data.items),
                      SliverToBoxAdapter(
                        child: PagedFooter(
                          page: data,
                          onLoadMore: () => ref
                              .read(pagedListingsProvider(query).notifier)
                              .loadMore(),
                        ),
                      ),
                    ],
            ),
          ],
        ),
      ),
    );
  }
}
