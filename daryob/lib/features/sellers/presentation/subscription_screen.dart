import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/errors/failure.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/states.dart';

/// Business subscription plans. Billing arrives in a later phase; the
/// screen states that instead of simulating a purchase.
class SubscriptionScreen extends StatelessWidget {
  const SubscriptionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final plans = [
      (l10n.planStart, [l10n.planStartPerk1, l10n.planStartPerk2]),
      (l10n.planPro, [l10n.planProPerk1, l10n.planProPerk2, l10n.planProPerk3]),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(l10n.subscription)),
      body: ListView(
        padding: const EdgeInsets.all(DaryobSpacing.page),
        children: [
          DaryobNotice(
            message: l10n.unavailablePayments,
            tone: NoticeTone.warning,
          ),
          const SizedBox(height: DaryobSpacing.lg),
          for (final (name, perks) in plans)
            Padding(
              padding: const EdgeInsets.only(bottom: DaryobSpacing.md),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(DaryobSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: context.text.titleLarge),
                      Text(l10n.priceNotSet, style: context.text.bodySmall),
                      const SizedBox(height: DaryobSpacing.sm),
                      for (final perk in perks)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                Icons.check_rounded,
                                size: 18,
                                color: context.palette.success,
                              ),
                              const SizedBox(width: 6),
                              Expanded(child: Text(perk)),
                            ],
                          ),
                        ),
                      const SizedBox(height: DaryobSpacing.md),
                      DaryobSecondaryButton(
                        label: l10n.choosePlan,
                        onPressed: () => showInfoDialog(
                          context,
                          title: l10n.paymentUnavailableTitle,
                          message: unavailableMessage(
                            l10n,
                            UnavailableFeature.payments,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
