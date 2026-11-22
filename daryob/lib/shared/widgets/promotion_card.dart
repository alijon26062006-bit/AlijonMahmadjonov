import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../../core/utils/formatters.dart';
import '../../features/promotions/domain/monetization.dart';
import '../models/localized_text.dart';
import 'badges.dart';

class DaryobPromotionCard extends StatelessWidget {
  const DaryobPromotionCard({
    super.key,
    required this.plan,
    required this.selected,
    required this.onTap,
  });

  final PromotionPlan plan;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final price = plan.price == null
        ? l10n.priceNotSet
        : Formatters.price(plan.price!, plan.currency, context.languageCode);

    return Semantics(
      selected: selected,
      button: true,
      child: Material(
        color: selected ? context.palette.limeSoft : context.colors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: DaryobRadius.cardAll,
          side: BorderSide(
            color: selected
                ? (isDark ? DaryobColors.lime : DaryobColors.navy)
                : context.palette.border,
            width: selected ? 2 : 1,
          ),
        ),
        child: InkWell(
          borderRadius: DaryobRadius.cardAll,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(DaryobSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    PromotionBadge(type: plan.type),
                    if (plan.type.name == 'boost')
                      DaryobStatusBadge(label: l10n.promoBoost),
                    const Spacer(),
                    Text(price, style: context.text.titleMedium),
                  ],
                ),
                const SizedBox(height: DaryobSpacing.sm),
                Text(plan.title.of(context), style: context.text.titleSmall),
                Text(
                  l10n.durationDays(plan.durationDays),
                  style: context.text.bodySmall,
                ),
                const SizedBox(height: DaryobSpacing.sm),
                for (final perk in plan.perks)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          Icons.check_rounded,
                          size: 18,
                          color: context.palette.success,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            perk.of(context),
                            style: context.text.bodyMedium,
                          ),
                        ),
                      ],
                    ),
                  ),
                if (plan.isSamplePrice) ...[
                  const SizedBox(height: DaryobSpacing.sm),
                  Text(l10n.samplePriceNote, style: context.text.labelSmall),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
