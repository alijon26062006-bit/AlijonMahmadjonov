import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/utils/debouncer.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/daryob_search_bar.dart';
import '../../../shared/widgets/filter_sheet.dart';
import '../../../shared/widgets/listing_card.dart';
import '../../../shared/widgets/skeleton.dart';
import '../../../shared/widgets/states.dart';
import '../../home/presentation/home_screen.dart';
import '../../listings/application/listing_providers.dart';
import '../../listings/domain/listing_query.dart';
import '../application/search_controller.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key, this.initialCategoryId});
  final String? initialCategoryId;

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  late final TextEditingController _text;
  final _debouncer = Debouncer(DaryobDurations.searchDebounce);
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    final state = ref.read(searchControllerProvider);
    _text = TextEditingController(text: state.query.text);
    if (widget.initialCategoryId != null &&
        widget.initialCategoryId != state.query.categoryId) {
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => ref
            .read(searchControllerProvider.notifier)
            .setCategory(widget.initialCategoryId),
      );
    }
    _scroll.addListener(() {
      if (_scroll.position.extentAfter < 600) {
        final q = ref.read(searchControllerProvider).query;
        ref.read(pagedListingsProvider(q).notifier).loadMore();
      }
    });
  }

  @override
  void dispose() {
    _debouncer.dispose();
    _text.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    setState(() {}); // Updates the clear button.
    _debouncer(() {
      if (value.trim().length >= 2) {
        ref.read(searchControllerProvider.notifier).submit(value);
      } else if (value.trim().isEmpty) {
        ref.read(searchControllerProvider.notifier).showHistory();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(searchControllerProvider);
    final controller = ref.read(searchControllerProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Padding(
          padding: const EdgeInsets.only(right: DaryobSpacing.page),
          child: DaryobSearchBar(
            controller: _text,
            autofocus: !state.submitted,
            onChanged: _onChanged,
            onSubmitted: (v) {
              _debouncer.cancel();
              controller.submit(v);
            },
            activeFilters: state.query.activeFilterCount,
            onFilterTap: () async {
              final next = await showFilterSheet(
                context,
                query: state.query.copyWith(text: _text.text.trim()),
              );
              if (next != null) controller.applyFilters(next);
            },
          ),
        ),
      ),
      body: state.submitted
          ? _Results(query: state.query, scroll: _scroll)
          : _History(
              history: state.history,
              onPick: (phrase) {
                _text.text = phrase;
                controller.submit(phrase);
              },
              onRemove: controller.removeHistory,
              onClear: controller.clearHistory,
              onCategory: controller.setCategory,
            ),
    );
  }
}

class _History extends ConsumerWidget {
  const _History({
    required this.history,
    required this.onPick,
    required this.onRemove,
    required this.onClear,
    required this.onCategory,
  });

  final List<String> history;
  final ValueChanged<String> onPick;
  final ValueChanged<String> onRemove;
  final VoidCallback onClear;
  final ValueChanged<String> onCategory;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final categories = ref.watch(categoryRegistryProvider).topLevel;
    return ListView(
      children: [
        if (history.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(
              DaryobSpacing.page,
              DaryobSpacing.md,
              DaryobSpacing.sm,
              0,
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    l10n.recentSearches,
                    style: context.text.titleMedium,
                  ),
                ),
                TextButton(onPressed: onClear, child: Text(l10n.clearHistory)),
              ],
            ),
          ),
          for (final phrase in history)
            ListTile(
              leading: const Icon(Icons.history_rounded),
              title: Text(phrase),
              onTap: () => onPick(phrase),
              trailing: IconButton(
                tooltip: l10n.delete,
                icon: const Icon(Icons.close_rounded),
                onPressed: () => onRemove(phrase),
              ),
            ),
        ],
        Padding(
          padding: const EdgeInsets.fromLTRB(
            DaryobSpacing.page,
            DaryobSpacing.xl,
            DaryobSpacing.page,
            DaryobSpacing.md,
          ),
          child: Text(l10n.searchByCategory, style: context.text.titleMedium),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
          child: Wrap(
            spacing: DaryobSpacing.sm,
            runSpacing: DaryobSpacing.sm,
            children: [
              for (final c in categories)
                ActionChip(
                  label: Text(c.name.of(context)),
                  onPressed: () => onCategory(c.id),
                ),
            ],
          ),
        ),
        const SizedBox(height: DaryobSpacing.xxl),
      ],
    );
  }
}

class _Results extends ConsumerWidget {
  const _Results({required this.query, required this.scroll});
  final ListingQuery query;
  final ScrollController scroll;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final page = ref.watch(pagedListingsProvider(query));
    final controller = ref.read(searchControllerProvider.notifier);
    final category = ref.watch(categoryRegistryProvider).byId(query.categoryId);

    return RefreshIndicator(
      onRefresh: () =>
          ref.read(pagedListingsProvider(query).notifier).refresh(),
      child: CustomScrollView(
        controller: scroll,
        slivers: [
          SliverToBoxAdapter(
            child: SizedBox(
              height: 52,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(
                  horizontal: DaryobSpacing.page,
                  vertical: DaryobSpacing.sm,
                ),
                children: [
                  PopupMenuButton<ListingSort>(
                    tooltip: l10n.sortBy,
                    onSelected: (s) =>
                        controller.applyFilters(query.copyWith(sort: s)),
                    itemBuilder: (_) => [
                      for (final s in ListingSort.values)
                        CheckedPopupMenuItem(
                          value: s,
                          checked: s == query.sort,
                          child: Text(sortLabel(l10n, s)),
                        ),
                    ],
                    child: Chip(
                      avatar: const Icon(Icons.swap_vert_rounded, size: 18),
                      label: Text(sortLabel(l10n, query.sort)),
                    ),
                  ),
                  if (category != null) ...[
                    const SizedBox(width: DaryobSpacing.sm),
                    InputChip(
                      label: Text(category.name.of(context)),
                      onDeleted: () => controller.setCategory(null),
                      deleteButtonTooltipMessage: l10n.delete,
                    ),
                  ],
                  if (query.minPrice != null || query.maxPrice != null) ...[
                    const SizedBox(width: DaryobSpacing.sm),
                    InputChip(
                      label: Text(
                        l10n.priceFilterChip(
                          query.minPrice?.toString() ?? '0',
                          query.maxPrice?.toString() ?? '∞',
                        ),
                      ),
                      onDeleted: () => controller.applyFilters(
                        query.copyWith(
                          clearMinPrice: true,
                          clearMaxPrice: true,
                        ),
                      ),
                      deleteButtonTooltipMessage: l10n.delete,
                    ),
                  ],
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
                        actionLabel: query.hasFilters
                            ? l10n.resetFilters
                            : null,
                        onAction: () =>
                            controller.applyFilters(query.withoutFilters()),
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
                            l10n.resultsCount(data.total!),
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
    );
  }
}

/// Lets other screens open search pre-filled (used by "see all").
void openSearchWith(BuildContext context, WidgetRef ref, ListingQuery query) {
  ref.read(searchControllerProvider.notifier).applyFilters(query);
  context.push('/search');
}
