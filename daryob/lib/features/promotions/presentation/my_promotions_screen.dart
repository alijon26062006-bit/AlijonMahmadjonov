import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/widgets/badges.dart';
import '../../../shared/widgets/states.dart';
import '../../listings/application/listing_providers.dart';
import '../../listings/presentation/my_listings_screen.dart';

/// Promotions currently applied to the user's listings.
class MyPromotionsScreen extends ConsumerWidget {
  const MyPromotionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final now = ref.watch(nowProvider);
    final value = ref.watch(myListingsProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.myPromotions)),
      body: value.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => DaryobErrorState(error: e),
        data: (listings) {
          final promoted = listings.where((l) => l.promotion != null).toList();
          if (promoted.isEmpty) {
            return DaryobEmptyState(
              icon: Icons.rocket_launch_outlined,
              title: l10n.noPromotions,
              message: l10n.noPromotionsBody,
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(DaryobSpacing.page),
            itemCount: promoted.length,
            separatorBuilder: (_, _) =>
                const SizedBox(height: DaryobSpacing.sm),
            itemBuilder: (context, i) {
              final l = promoted[i];
              final p = l.promotion!;
              final active = p.isActiveAt(now);
              return Card(
                child: ListTile(
                  onTap: () => context.push(Routes.listing(l.id)),
                  title: Text(
                    l.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    '${promotionLabel(l10n, p.type)} · ${l10n.until(Formatters.date(p.endsAt))}'
                    '${p.isDevelopmentOnly ? ' · DEV' : ''}',
                  ),
                  trailing: DaryobStatusBadge(
                    label: active ? l10n.promotionActive : l10n.promotionEnded,
                    tone: active ? BadgeTone.success : BadgeTone.neutral,
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
