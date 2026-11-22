import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/errors/failure.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/promotion_card.dart';
import '../../../shared/widgets/states.dart';
import '../../../shared/widgets/toast.dart';
import '../../authentication/application/session_controller.dart';
import '../../listings/application/listing_providers.dart';
import '../domain/monetization.dart';

final promotionPlansProvider = FutureProvider.autoDispose<List<PromotionPlan>>(
  (ref) => ref.watch(promotionRepositoryProvider).plans(),
);

class PromoteListingScreen extends ConsumerStatefulWidget {
  const PromoteListingScreen({super.key, required this.listingId});
  final String listingId;

  @override
  ConsumerState<PromoteListingScreen> createState() =>
      _PromoteListingScreenState();
}

class _PromoteListingScreenState extends ConsumerState<PromoteListingScreen> {
  String? _selectedId;
  bool _busy = false;

  Future<void> _pay(PromotionPlan plan) async {
    final l10n = context.l10n;
    setState(() => _busy = true);
    try {
      // Activation happens only after the server confirms the payment.
      await ref
          .read(paymentGatewayProvider)
          .payForPromotion(listingId: widget.listingId, plan: plan);
    } catch (e) {
      if (!mounted) return;
      final failure = asFailure(e);
      await showInfoDialog(
        context,
        title: failure is FeatureUnavailableFailure
            ? l10n.paymentUnavailableTitle
            : l10n.errTitle,
        message: failureMessage(l10n, e),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Development builds only: lets testers see promoted listings without a
  /// payment provider. Clearly labelled and absent from production.
  Future<void> _activateForDevelopment(PromotionPlan plan) async {
    final l10n = context.l10n;
    final user = ref.read(sessionControllerProvider);
    if (user == null) return;
    final ok = await DaryobConfirmationDialog.show(
      context,
      title: l10n.devActivateTitle,
      message: l10n.devActivateBody,
      confirmLabel: l10n.devActivate,
    );
    if (!ok) return;
    final now = ref.read(clockProvider)();
    try {
      await ref
          .read(listingRepositoryProvider)
          .applyPromotion(
            widget.listingId,
            ListingPromotion(
              type: plan.type,
              startsAt: now,
              endsAt: now.add(Duration(days: plan.durationDays)),
              isDevelopmentOnly: true,
            ),
            actingUserId: user.id,
          );
      invalidateListingsFromWidget(ref);
      if (!mounted) return;
      DaryobToast.show(context, l10n.devActivated);
      context.pop();
    } catch (e) {
      if (mounted) {
        DaryobToast.show(context, failureMessage(l10n, e), isError: true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final plans = ref.watch(promotionPlansProvider);
    final listing = ref.watch(listingByIdProvider(widget.listingId)).value;
    final isDevelopment = ref.watch(appConfigProvider).isDevelopment;
    final gateway = ref.watch(paymentGatewayProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.promote)),
      body: plans.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => DaryobErrorState(error: e),
        data: (items) {
          final selected = items.where((p) => p.id == _selectedId).firstOrNull;
          return Column(
            children: [
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(DaryobSpacing.page),
                  children: [
                    if (listing != null) ...[
                      Text(listing.title, style: context.text.titleMedium),
                      const SizedBox(height: DaryobSpacing.md),
                    ],
                    if (!gateway.isConfigured) ...[
                      DaryobNotice(
                        message: l10n.unavailablePayments,
                        tone: NoticeTone.warning,
                      ),
                      const SizedBox(height: DaryobSpacing.lg),
                    ],
                    for (final plan in items)
                      Padding(
                        padding: const EdgeInsets.only(
                          bottom: DaryobSpacing.md,
                        ),
                        child: DaryobPromotionCard(
                          plan: plan,
                          selected: plan.id == _selectedId,
                          onTap: () => setState(() => _selectedId = plan.id),
                        ),
                      ),
                  ],
                ),
              ),
              SafeArea(
                top: false,
                child: Padding(
                  padding: const EdgeInsets.all(DaryobSpacing.md),
                  child: Column(
                    children: [
                      DaryobPrimaryButton(
                        label: l10n.payAndPromote,
                        tone: DaryobButtonTone.accent,
                        isLoading: _busy,
                        onPressed: selected == null
                            ? null
                            : () => _pay(selected),
                      ),
                      if (isDevelopment && selected != null)
                        TextButton(
                          onPressed: () => _activateForDevelopment(selected),
                          child: Text(l10n.devActivate),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
