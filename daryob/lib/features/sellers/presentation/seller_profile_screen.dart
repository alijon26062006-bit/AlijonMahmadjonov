import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/listing_card.dart';
import '../../../shared/widgets/seller_tile.dart';
import '../../../shared/widgets/skeleton.dart';
import '../../../shared/widgets/states.dart';
import '../../listings/application/listing_providers.dart';

/// Public seller page with their active listings.
class SellerProfileScreen extends ConsumerWidget {
  const SellerProfileScreen({super.key, required this.sellerId});
  final String sellerId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final seller = ref.watch(sellerProvider(sellerId));
    final listings = ref.watch(sellerListingsProvider(sellerId));

    return Scaffold(
      appBar: AppBar(title: Text(l10n.sellerProfile)),
      body: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(DaryobSpacing.page),
              child: seller.when(
                loading: () =>
                    const DaryobLoadingSkeleton(height: 90, radius: 18),
                error: (e, _) => DaryobErrorState(error: e, compact: true),
                data: (s) => s == null
                    ? DaryobEmptyState(
                        icon: Icons.person_off_outlined,
                        title: l10n.sellerNotFound,
                        compact: true,
                      )
                    : Card(child: DaryobSellerTile(seller: s)),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                DaryobSpacing.page,
                0,
                DaryobSpacing.page,
                DaryobSpacing.md,
              ),
              child: Text(l10n.sellerListings, style: context.text.titleLarge),
            ),
          ),
          ...listings.when(
            loading: () => const [SliverListingGridSkeleton()],
            error: (e, _) => [
              SliverToBoxAdapter(
                child: DaryobErrorState(error: e, compact: true),
              ),
            ],
            data: (items) => items.isEmpty
                ? [
                    SliverToBoxAdapter(
                      child: DaryobEmptyState(
                        icon: Icons.inventory_2_outlined,
                        title: l10n.noActiveListings,
                        compact: true,
                      ),
                    ),
                  ]
                : [SliverListingGrid(listings: items)],
          ),
          const SliverToBoxAdapter(child: SizedBox(height: DaryobSpacing.xxl)),
        ],
      ),
    );
  }
}
