import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/models/category.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/badges.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/listing_image.dart';
import '../../../shared/widgets/require_sign_in.dart';
import '../../../shared/widgets/states.dart';
import '../../authentication/application/session_controller.dart';
import '../../catalog/presentation/catalog_ui.dart';
import '../application/listing_actions.dart';
import '../application/listing_providers.dart';
import 'drafts_screen.dart';

/// All listings of the signed-in user, re-read whenever listings change.
final myListingsProvider = FutureProvider.autoDispose<List<Listing>>((
  ref,
) async {
  ref.watch(listingsRevisionProvider);
  final user = ref.watch(sessionControllerProvider);
  if (user == null) return const [];
  return ref.watch(listingRepositoryProvider).byOwner(user.id);
});

class MyListingsScreen extends ConsumerWidget {
  const MyListingsScreen({super.key});

  static const _tabs = [
    ListingStatus.active,
    ListingStatus.pending,
    ListingStatus.draft,
    ListingStatus.sold,
    ListingStatus.archived,
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final user = ref.watch(sessionControllerProvider);

    if (user == null) {
      return Scaffold(
        appBar: AppBar(title: Text(l10n.myListings)),
        body: DaryobEmptyState(
          icon: Icons.lock_outline_rounded,
          title: l10n.signInRequired,
          message: l10n.signInToManage,
          actionLabel: l10n.signIn,
          onAction: () => requireSignIn(context, ref),
        ),
      );
    }

    final value = ref.watch(myListingsProvider);
    final drafts = ref.watch(draftsProvider);

    return DefaultTabController(
      length: _tabs.length,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l10n.myListings),
          bottom: TabBar(
            isScrollable: true,
            tabs: [
              for (final status in _tabs)
                Tab(
                  text: status == ListingStatus.draft
                      ? '${statusLabel(l10n, status)} (${drafts.length})'
                      : '${statusLabel(l10n, status)} (${value.value?.where((l) => _matches(l, status)).length ?? 0})',
                ),
            ],
          ),
        ),
        body: value.when(
          skipLoadingOnReload: true,
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => DaryobErrorState(
            error: e,
            onRetry: () => ref.invalidate(myListingsProvider),
          ),
          data: (all) => TabBarView(
            children: [
              for (final status in _tabs)
                status == ListingStatus.draft
                    ? const DraftsList()
                    : _StatusList(
                        listings: all
                            .where((l) => _matches(l, status))
                            .toList(),
                        status: status,
                      ),
            ],
          ),
        ),
      ),
    );
  }

  /// "Under review" also shows rejected listings so the user sees why.
  static bool _matches(Listing l, ListingStatus tab) =>
      tab == ListingStatus.pending
      ? l.status == ListingStatus.pending || l.status == ListingStatus.rejected
      : l.status == tab;
}

class _StatusList extends ConsumerWidget {
  const _StatusList({required this.listings, required this.status});
  final List<Listing> listings;
  final ListingStatus status;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    if (listings.isEmpty) {
      return DaryobEmptyState(
        icon: Icons.inventory_2_outlined,
        title: l10n.noListingsInStatus,
        actionLabel: status == ListingStatus.active ? l10n.createListing : null,
        onAction: () => context.go(Routes.create),
      );
    }
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(myListingsProvider),
      child: ListView.separated(
        padding: const EdgeInsets.all(DaryobSpacing.page),
        itemCount: listings.length,
        separatorBuilder: (_, _) => const SizedBox(height: DaryobSpacing.md),
        itemBuilder: (_, i) => _MyListingTile(listing: listings[i]),
      ),
    );
  }
}

class _MyListingTile extends ConsumerWidget {
  const _MyListingTile({required this.listing});
  final Listing listing;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final category = ref
        .watch(categoryRegistryProvider)
        .byId(listing.categoryId);
    final now = ref.watch(nowProvider);
    final actions = ListingActions(context, ref);

    Future<void> run(Future<bool> Function() action) async {
      if (await action()) ref.invalidate(myListingsProvider);
    }

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push(Routes.listing(listing.id)),
        child: Padding(
          padding: const EdgeInsets.all(DaryobSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: SizedBox(
                      width: 88,
                      height: 72,
                      child: DaryobListingImage(
                        source: listing.photos.isEmpty
                            ? null
                            : listing.photos.first,
                        icon: category?.icon ?? CategoryIcon.generic,
                        cacheWidth: 264,
                      ),
                    ),
                  ),
                  const SizedBox(width: DaryobSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          listing.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: context.text.titleSmall,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          listingPriceText(context, ref, listing),
                          style: context.text.titleMedium,
                        ),
                        const SizedBox(height: DaryobSpacing.xs),
                        Wrap(
                          spacing: 4,
                          runSpacing: 4,
                          children: [
                            DaryobStatusBadge.forStatus(
                              context,
                              listing.status,
                            ),
                            if (listing.isPromotedAt(now))
                              PromotionBadge(type: listing.promotion!.type),
                            if (listing.isLocalOnly)
                              DaryobStatusBadge(label: l10n.localOnlyBadge),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: DaryobSpacing.sm),
              Text(
                [
                  l10n.publishedOn(Formatters.date(listing.sortDate)),
                  // Views are shown only when actually tracked.
                  if (listing.viewCount != null) l10n.views(listing.viewCount!),
                ].join(' · '),
                style: context.text.bodySmall,
              ),
              if (listing.status == ListingStatus.rejected &&
                  listing.rejectionReason != null) ...[
                const SizedBox(height: DaryobSpacing.sm),
                DaryobNotice(
                  message: l10n.rejectedReason(listing.rejectionReason!),
                  tone: NoticeTone.warning,
                ),
              ],
              const Divider(height: DaryobSpacing.xl),
              Wrap(
                spacing: DaryobSpacing.xs,
                children: [
                  TextButton.icon(
                    onPressed: () =>
                        context.push(Routes.editListing(listing.id)),
                    icon: const Icon(Icons.edit_outlined, size: 18),
                    label: Text(l10n.edit),
                  ),
                  if (listing.status == ListingStatus.active) ...[
                    TextButton.icon(
                      onPressed: () => context.push(Routes.promote(listing.id)),
                      icon: const Icon(Icons.rocket_launch_outlined, size: 18),
                      label: Text(l10n.promote),
                    ),
                    TextButton.icon(
                      onPressed: () => run(
                        () => actions.setStatus(listing, ListingStatus.sold),
                      ),
                      icon: const Icon(Icons.sell_outlined, size: 18),
                      label: Text(l10n.markSold),
                    ),
                  ],
                  if (listing.status == ListingStatus.archived ||
                      listing.status == ListingStatus.sold)
                    TextButton.icon(
                      onPressed: () => run(
                        () => actions.setStatus(listing, ListingStatus.active),
                      ),
                      icon: const Icon(Icons.unarchive_outlined, size: 18),
                      label: Text(l10n.republish),
                    ),
                  if (listing.status != ListingStatus.archived)
                    TextButton.icon(
                      onPressed: () => run(
                        () =>
                            actions.setStatus(listing, ListingStatus.archived),
                      ),
                      icon: const Icon(Icons.archive_outlined, size: 18),
                      label: Text(l10n.archive),
                    ),
                  TextButton.icon(
                    onPressed: () => run(() => actions.delete(listing)),
                    style: TextButton.styleFrom(
                      foregroundColor: context.colors.error,
                    ),
                    icon: const Icon(Icons.delete_outline_rounded, size: 18),
                    label: Text(l10n.delete),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Shortcut used on the profile screen.
class MyListingsButton extends StatelessWidget {
  const MyListingsButton({super.key});

  @override
  Widget build(BuildContext context) => DaryobSecondaryButton(
    label: context.l10n.myListings,
    icon: Icons.list_alt_rounded,
    onPressed: () => context.push(Routes.myListings),
  );
}
