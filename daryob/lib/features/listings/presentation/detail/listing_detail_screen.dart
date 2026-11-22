import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show ProviderListenable;
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:share_plus/share_plus.dart';

import '../../../../app/localization/l10n.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/utils/ids.dart';
import '../../../../shared/models/category.dart';
import '../../../../shared/models/category_schema.dart';
import '../../../../shared/models/listing.dart';
import '../../../../shared/models/localized_text.dart';
import '../../../../shared/models/user.dart';
import '../../../../shared/providers/core_providers.dart';
import '../../../../shared/widgets/badges.dart';
import '../../../../shared/widgets/buttons.dart';
import '../../../../shared/widgets/listing_card.dart';
import '../../../../shared/widgets/location_selector.dart';
import '../../../../shared/widgets/photo_gallery.dart';
import '../../../../shared/widgets/section_header.dart';
import '../../../../shared/widgets/seller_tile.dart';
import '../../../../shared/widgets/states.dart';
import '../../../../shared/widgets/toast.dart';
import '../../../authentication/application/session_controller.dart';
import '../../../favorites/application/favorites_controller.dart';
import '../../application/listing_actions.dart';
import '../../application/listing_providers.dart';
import 'report_sheet.dart';

class ListingDetailScreen extends ConsumerWidget {
  const ListingDetailScreen({super.key, required this.listingId});
  final String listingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(listingByIdProvider(listingId));
    final l10n = context.l10n;
    return value.when(
      loading: () => Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Scaffold(
        appBar: AppBar(),
        body: DaryobErrorState(
          error: e,
          onRetry: () => ref.invalidate(listingByIdProvider(listingId)),
        ),
      ),
      data: (listing) => listing == null
          ? Scaffold(
              appBar: AppBar(),
              body: DaryobEmptyState(
                icon: Icons.search_off_rounded,
                title: l10n.listingNotFound,
                message: l10n.listingNotFoundBody,
              ),
            )
          : _DetailView(listing: listing),
    );
  }
}

class _DetailView extends ConsumerWidget {
  const _DetailView({required this.listing});
  final Listing listing;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final now = ref.watch(nowProvider);
    final categories = ref.watch(categoryRegistryProvider);
    final category = categories.byId(listing.categoryId);
    final schema = ref
        .watch(schemaRegistryProvider)
        .schemaFor(listing.schemaId);
    final regions = ref.watch(regionDirectoryProvider);
    final user = ref.watch(sessionControllerProvider);
    final isOwner = user?.id == listing.ownerId;
    final isFavorite = ref.watch(
      favoritesControllerProvider.select((ids) => ids.contains(listing.id)),
    );
    final seller = ref.watch(sellerProvider(listing.ownerId)).value;
    final actions = ListingActions(context, ref);
    final isFree = category?.priceMode == PriceMode.free;
    final galleryHeight = (MediaQuery.sizeOf(context).width * 0.8).clamp(
      240.0,
      420.0,
    );

    final characteristics = <(String, String)>[
      if (category != null) (l10n.category, category.name.of(context)),
      for (final field in schema.fields)
        if (field.showInDetails && listing.attributes[field.key] != null)
          (
            field.label.of(context),
            _attributeText(context, field, listing.attributes[field.key]),
          ),
    ];

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            pinned: true,
            expandedHeight: galleryHeight,
            leading: Padding(
              padding: const EdgeInsets.all(6),
              child: DaryobCircleButton(
                icon: Icons.arrow_back_rounded,
                tooltip: l10n.back,
                onPressed: () => context.pop(),
              ),
            ),
            actions: [
              DaryobCircleButton(
                icon: Icons.share_outlined,
                tooltip: l10n.share,
                onPressed: () => SharePlus.instance.share(
                  ShareParams(
                    subject: listing.title,
                    text: _shareText(context, listing, isFree),
                  ),
                ),
              ),
              const SizedBox(width: DaryobSpacing.sm),
              DaryobCircleButton(
                icon: isFavorite
                    ? Icons.favorite_rounded
                    : Icons.favorite_border_rounded,
                color: isFavorite ? DaryobColors.error : null,
                tooltip: isFavorite ? l10n.favoriteRemove : l10n.favoriteAdd,
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
              const SizedBox(width: DaryobSpacing.sm),
            ],
            flexibleSpace: FlexibleSpaceBar(
              background: DaryobPhotoGallery(
                photos: listing.photos,
                icon: category?.icon ?? CategoryIcon.generic,
                height: galleryHeight + MediaQuery.paddingOf(context).top,
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.all(DaryobSpacing.page),
            sliver: SliverList.list(
              children: [
                if (listing.isDemo) ...[
                  DaryobNotice(
                    message: l10n.demoListingNotice,
                    tone: NoticeTone.warning,
                  ),
                  const SizedBox(height: DaryobSpacing.md),
                ] else if (listing.isLocalOnly) ...[
                  DaryobNotice(message: l10n.localListingNotice),
                  const SizedBox(height: DaryobSpacing.md),
                ],
                if (listing.status != ListingStatus.active) ...[
                  Align(
                    alignment: Alignment.centerLeft,
                    child: DaryobStatusBadge.forStatus(context, listing.status),
                  ),
                  const SizedBox(height: DaryobSpacing.sm),
                ],
                Wrap(
                  spacing: 6,
                  children: [
                    if (listing.isPromotedAt(now))
                      PromotionBadge(type: listing.promotion!.type),
                    if (listing.isNegotiable && !isFree)
                      DaryobStatusBadge(
                        label: l10n.negotiable,
                        tone: BadgeTone.success,
                      ),
                  ],
                ),
                const SizedBox(height: DaryobSpacing.xs),
                Text(
                  priceLabel(
                    l10n,
                    context.languageCode,
                    price: listing.price,
                    currency: listing.currency,
                    isFreeCategory: isFree,
                  ),
                  style: context.text.headlineMedium,
                ),
                const SizedBox(height: DaryobSpacing.sm),
                Text(listing.title, style: context.text.titleLarge),
                const SizedBox(height: DaryobSpacing.md),
                _InfoLine(
                  icon: Icons.place_outlined,
                  text: [
                    regionPathLabel(context, regions, listing.regionId),
                    if ((listing.addressNote ?? '').isNotEmpty)
                      listing.addressNote!,
                  ].join(' · '),
                ),
                _InfoLine(
                  icon: Icons.schedule_rounded,
                  text: l10n.publishedOn(Formatters.date(listing.sortDate)),
                ),
                _InfoLine(
                  icon: Icons.tag_rounded,
                  text: l10n.listingNumber(listingNumber(listing.id)),
                ),
                if (listing.viewCount != null)
                  _InfoLine(
                    icon: Icons.visibility_outlined,
                    text: l10n.views(listing.viewCount!),
                  ),
                if (isOwner) ...[
                  const SizedBox(height: DaryobSpacing.lg),
                  _OwnerPanel(listing: listing),
                ],
                const SizedBox(height: DaryobSpacing.xl),
                Text(l10n.description, style: context.text.titleMedium),
                const SizedBox(height: DaryobSpacing.sm),
                SelectableText(
                  listing.description,
                  style: context.text.bodyLarge,
                ),
                if (characteristics.isNotEmpty) ...[
                  const SizedBox(height: DaryobSpacing.xl),
                  Text(l10n.characteristics, style: context.text.titleMedium),
                  const SizedBox(height: DaryobSpacing.sm),
                  for (final (label, value) in characteristics)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                              label,
                              style: context.text.bodyMedium?.copyWith(
                                color: context.palette.textSecondary,
                              ),
                            ),
                          ),
                          const SizedBox(width: DaryobSpacing.md),
                          Expanded(
                            child: Text(value, style: context.text.titleSmall),
                          ),
                        ],
                      ),
                    ),
                ],
                const SizedBox(height: DaryobSpacing.xl),
                Text(l10n.seller, style: context.text.titleMedium),
                const SizedBox(height: DaryobSpacing.sm),
                Card(
                  child: seller == null
                      ? ListTile(title: Text(listing.contact.name))
                      : DaryobSellerTile(
                          seller: seller,
                          onTap: () => context.push(Routes.seller(seller.id)),
                        ),
                ),
                const SizedBox(height: DaryobSpacing.md),
                InkWell(
                  borderRadius: DaryobRadius.inputAll,
                  onTap: () => context.push(Routes.safety),
                  child: DaryobNotice(
                    message: l10n.safetyTipShort,
                    icon: Icons.shield_outlined,
                    tone: NoticeTone.brand,
                  ),
                ),
                if (!isOwner)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: () => showReportSheet(context, listing),
                      icon: Icon(
                        Icons.flag_outlined,
                        color: context.colors.error,
                      ),
                      label: Text(
                        l10n.reportListing,
                        style: TextStyle(color: context.colors.error),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          _HorizontalListings(
            title: l10n.moreFromSeller,
            provider: sellerListingsProvider(listing.ownerId),
            excludeId: listing.id,
          ),
          _HorizontalListings(
            title: l10n.similarListings,
            provider: similarListingsProvider((
              listingId: listing.id,
              categoryId: listing.categoryId,
            )),
            excludeId: listing.id,
          ),
          const SliverToBoxAdapter(child: SizedBox(height: DaryobSpacing.xxxl)),
        ],
      ),
      bottomNavigationBar: isOwner
          ? null
          : _ContactBar(
              listing: listing,
              seller: seller,
              onCall: () => actions.call(listing),
              onChat: () => actions.openChat(
                listing,
                seller?.name ?? listing.contact.name,
              ),
            ),
    );
  }

  String _attributeText(
    BuildContext context,
    FieldSchema field,
    Object? value,
  ) {
    final l10n = context.l10n;
    switch (field.type) {
      case FieldType.singleSelect:
        return field.optionLabel(value)?.of(context) ?? '$value';
      case FieldType.multiSelect:
        final list = value is List ? value : const [];
        return list
            .map((v) => field.optionLabel(v)?.of(context) ?? '$v')
            .join(', ');
      case FieldType.boolean:
        return value == true ? l10n.yes : l10n.no;
      case FieldType.number:
        final unit = field.unit?.of(context);
        return unit == null ? '$value' : '$value $unit';
      case FieldType.text:
      case FieldType.multilineText:
      case FieldType.numberRange:
        return '$value';
    }
  }

  String _shareText(BuildContext context, Listing listing, bool isFree) {
    final l10n = context.l10n;
    final price = priceLabel(
      l10n,
      context.languageCode,
      price: listing.price,
      currency: listing.currency,
      isFreeCategory: isFree,
    );
    // No link: public listing URLs exist only once a web domain is set up.
    return '${listing.title}\n$price\n${l10n.sharedFromDaryob}';
  }
}

class _InfoLine extends StatelessWidget {
  const _InfoLine({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: DaryobSpacing.xs + 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: context.palette.textSecondary),
          const SizedBox(width: DaryobSpacing.sm),
          Expanded(child: Text(text, style: context.text.bodyMedium)),
        ],
      ),
    );
  }
}

class _OwnerPanel extends ConsumerWidget {
  const _OwnerPanel({required this.listing});
  final Listing listing;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final actions = ListingActions(context, ref);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(DaryobSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.yourListing, style: context.text.titleSmall),
            const SizedBox(height: DaryobSpacing.sm),
            Wrap(
              spacing: DaryobSpacing.sm,
              runSpacing: DaryobSpacing.sm,
              children: [
                ActionChip(
                  avatar: const Icon(Icons.edit_outlined, size: 18),
                  label: Text(l10n.edit),
                  onPressed: () => context.push(Routes.editListing(listing.id)),
                ),
                if (listing.status == ListingStatus.active) ...[
                  ActionChip(
                    avatar: const Icon(Icons.rocket_launch_outlined, size: 18),
                    label: Text(l10n.promote),
                    onPressed: () => context.push(Routes.promote(listing.id)),
                  ),
                  ActionChip(
                    avatar: const Icon(Icons.sell_outlined, size: 18),
                    label: Text(l10n.markSold),
                    onPressed: () =>
                        actions.setStatus(listing, ListingStatus.sold),
                  ),
                ],
                if (listing.status != ListingStatus.archived)
                  ActionChip(
                    avatar: const Icon(Icons.archive_outlined, size: 18),
                    label: Text(l10n.archive),
                    onPressed: () =>
                        actions.setStatus(listing, ListingStatus.archived),
                  )
                else
                  ActionChip(
                    avatar: const Icon(Icons.unarchive_outlined, size: 18),
                    label: Text(l10n.republish),
                    onPressed: () =>
                        actions.setStatus(listing, ListingStatus.active),
                  ),
                ActionChip(
                  avatar: Icon(
                    Icons.delete_outline_rounded,
                    size: 18,
                    color: context.colors.error,
                  ),
                  label: Text(l10n.delete),
                  onPressed: () async {
                    if (await actions.delete(listing) && context.mounted) {
                      context.pop();
                    }
                  },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ContactBar extends StatefulWidget {
  const _ContactBar({
    required this.listing,
    required this.seller,
    required this.onCall,
    required this.onChat,
  });

  final Listing listing;
  final SellerSummary? seller;
  final VoidCallback onCall;
  final VoidCallback onChat;

  @override
  State<_ContactBar> createState() => _ContactBarState();
}

class _ContactBarState extends State<_ContactBar> {
  bool _revealed = false;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final contact = widget.listing.contact;
    final phoneVisible = contact.phoneVisibility == PhoneVisibility.visible;
    final available = widget.listing.status == ListingStatus.active;

    // Hidden numbers can't be revealed; visible ones are shown on the first
    // tap and dialled on the second, so nobody calls by accident.
    final callLabel = !phoneVisible
        ? l10n.phoneHidden
        : _revealed
        ? Formatters.phone(contact.phone)
        : l10n.showPhone;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: context.colors.surface,
        border: Border(top: BorderSide(color: context.palette.border)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(DaryobSpacing.md),
          child: !available
              ? Text(
                  l10n.listingNotAvailable,
                  textAlign: TextAlign.center,
                  style: context.text.titleSmall,
                )
              : Row(
                  children: [
                    if (contact.chatEnabled)
                      Expanded(
                        child: DaryobSecondaryButton(
                          label: l10n.writeMessage,
                          icon: Icons.chat_bubble_outline_rounded,
                          onPressed: widget.onChat,
                        ),
                      ),
                    if (contact.chatEnabled)
                      const SizedBox(width: DaryobSpacing.md),
                    Expanded(
                      child: DaryobPrimaryButton(
                        label: callLabel,
                        icon: Icons.call_rounded,
                        tone: DaryobButtonTone.accent,
                        onPressed: !phoneVisible
                            ? null
                            : () {
                                if (!_revealed) {
                                  setState(() => _revealed = true);
                                } else {
                                  widget.onCall();
                                }
                              },
                      ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

class _HorizontalListings extends ConsumerWidget {
  const _HorizontalListings({
    required this.title,
    required this.provider,
    required this.excludeId,
  });

  final String title;
  final ProviderListenable<AsyncValue<List<Listing>>> provider;
  final String excludeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final items = (ref.watch(provider).value ?? const <Listing>[])
        .where((l) => l.id != excludeId)
        .toList();
    if (items.isEmpty) {
      return const SliverToBoxAdapter(child: SizedBox.shrink());
    }
    const width = 190.0;
    return SliverMainAxisGroup(
      slivers: [
        SliverToBoxAdapter(child: DaryobSectionHeader(title: title)),
        SliverToBoxAdapter(
          child: SizedBox(
            height: SliverListingGrid.extentFor(context, width),
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(
                horizontal: DaryobSpacing.page,
              ),
              itemCount: items.length,
              separatorBuilder: (_, _) =>
                  const SizedBox(width: DaryobSpacing.md),
              itemBuilder: (_, i) =>
                  DaryobListingCard(listing: items[i], width: width),
            ),
          ),
        ),
      ],
    );
  }
}
