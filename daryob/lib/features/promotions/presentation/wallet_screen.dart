import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/errors/failure.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/states.dart';
import '../../authentication/application/session_controller.dart';
import '../domain/monetization.dart';

final _walletProvider =
    FutureProvider.autoDispose<(Wallet, List<WalletTransaction>)>((ref) async {
      final user = ref.watch(sessionControllerProvider);
      final repo = ref.watch(promotionRepositoryProvider);
      if (user == null) {
        return (const Wallet(balance: 0), const <WalletTransaction>[]);
      }
      return (await repo.wallet(user.id), await repo.transactions(user.id));
    });

/// Wallet overview and history. Shows only real data: until a payment
/// provider exists the balance is zero and the history is empty.
class WalletScreen extends ConsumerWidget {
  const WalletScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final value = ref.watch(_walletProvider);
    final gateway = ref.watch(paymentGatewayProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.wallet)),
      body: value.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => DaryobErrorState(error: e),
        data: (data) {
          final (wallet, transactions) = data;
          return ListView(
            padding: const EdgeInsets.all(DaryobSpacing.page),
            children: [
              Container(
                padding: const EdgeInsets.all(DaryobSpacing.xl),
                decoration: const BoxDecoration(
                  color: DaryobColors.navy,
                  borderRadius: DaryobRadius.heroAll,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.walletBalance,
                      style: context.text.bodyMedium?.copyWith(
                        color: Colors.white70,
                      ),
                    ),
                    const SizedBox(height: DaryobSpacing.xs),
                    Text(
                      Formatters.price(
                        wallet.balance,
                        wallet.currency,
                        context.languageCode,
                      ),
                      style: context.text.headlineMedium?.copyWith(
                        color: DaryobColors.lime,
                      ),
                    ),
                    const SizedBox(height: DaryobSpacing.lg),
                    DaryobPrimaryButton(
                      label: l10n.topUp,
                      tone: DaryobButtonTone.accent,
                      expand: false,
                      icon: Icons.add_rounded,
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
              if (!gateway.isConfigured) ...[
                const SizedBox(height: DaryobSpacing.lg),
                DaryobNotice(
                  message: l10n.unavailablePayments,
                  tone: NoticeTone.warning,
                ),
              ],
              const SizedBox(height: DaryobSpacing.xl),
              Text(l10n.transactionHistory, style: context.text.titleMedium),
              if (transactions.isEmpty)
                DaryobEmptyState(
                  icon: Icons.receipt_long_outlined,
                  title: l10n.noTransactions,
                  compact: true,
                )
              else
                for (final t in transactions)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(t.description ?? t.type.name),
                    subtitle: Text(Formatters.date(t.createdAt)),
                    trailing: Text(
                      Formatters.price(
                        t.amount,
                        wallet.currency,
                        context.languageCode,
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
