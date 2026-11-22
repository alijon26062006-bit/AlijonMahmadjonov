import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/daryob_logo.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/states.dart';
import '../../../shared/widgets/toast.dart';
import '../../authentication/application/session_controller.dart';

/// About, terms, privacy, support and account deletion.
///
/// Terms and privacy texts are placeholders that state so plainly — the
/// legal documents must be written and approved by the business before
/// release.
class InfoScreen extends ConsumerWidget {
  const InfoScreen({super.key, required this.page});
  final String page;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final config = ref.watch(appConfigProvider);

    final (String title, List<Widget> body) = switch (page) {
      InfoPages.about => (
        l10n.aboutApp,
        [
          const Center(child: DaryobBadgeLogo(size: 80)),
          const SizedBox(height: DaryobSpacing.lg),
          Center(child: Text('DARYOB', style: context.text.headlineSmall)),
          Center(child: Text(l10n.brandSlogan, style: context.text.bodyMedium)),
          const SizedBox(height: DaryobSpacing.xl),
          Text(l10n.aboutBody, style: context.text.bodyLarge),
          const SizedBox(height: DaryobSpacing.xl),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(l10n.appVersion),
            trailing: Text(config.versionLabel),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(l10n.environment),
            trailing: Text(
              config.isDevelopment ? l10n.envDevelopment : l10n.envProduction,
            ),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(l10n.licenses),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => showLicensePage(
              context: context,
              applicationName: 'DARYOB',
              applicationVersion: config.versionLabel,
            ),
          ),
        ],
      ),
      InfoPages.terms => (
        l10n.terms,
        [
          DaryobNotice(
            message: l10n.legalDraftNotice,
            tone: NoticeTone.warning,
          ),
          const SizedBox(height: DaryobSpacing.lg),
          Text(l10n.termsBody, style: context.text.bodyLarge),
        ],
      ),
      InfoPages.privacy => (
        l10n.privacyPolicy,
        [
          DaryobNotice(
            message: l10n.legalDraftNotice,
            tone: NoticeTone.warning,
          ),
          const SizedBox(height: DaryobSpacing.lg),
          Text(l10n.privacyBody, style: context.text.bodyLarge),
        ],
      ),
      InfoPages.support => (
        l10n.support,
        [
          Text(l10n.supportBody, style: context.text.bodyLarge),
          const SizedBox(height: DaryobSpacing.lg),
          DaryobNotice(message: l10n.supportNotConfigured),
          const SizedBox(height: DaryobSpacing.lg),
          DaryobSecondaryButton(
            label: l10n.safetyTitle,
            icon: Icons.shield_outlined,
            onPressed: () => context.push(Routes.safety),
          ),
        ],
      ),
      InfoPages.deletion => (l10n.deleteAccount, [const _DeletionBody()]),
      _ => (l10n.errNotFound, const <Widget>[]),
    };

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(
        padding: const EdgeInsets.all(DaryobSpacing.page),
        children: body,
      ),
    );
  }
}

class _DeletionBody extends ConsumerStatefulWidget {
  const _DeletionBody();

  @override
  ConsumerState<_DeletionBody> createState() => _DeletionBodyState();
}

class _DeletionBodyState extends ConsumerState<_DeletionBody> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final user = ref.watch(sessionControllerProvider);
    final isDevelopment = ref.watch(appConfigProvider).isDevelopment;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l10n.deletionBody, style: context.text.bodyLarge),
        const SizedBox(height: DaryobSpacing.lg),
        if (isDevelopment)
          DaryobNotice(
            message: l10n.deletionDevNotice,
            tone: NoticeTone.warning,
          ),
        const SizedBox(height: DaryobSpacing.xl),
        if (user == null)
          Text(l10n.signInRequired, style: context.text.bodyMedium)
        else
          DaryobPrimaryButton(
            label: l10n.deleteAccount,
            isLoading: _busy,
            onPressed: () async {
              final ok = await DaryobConfirmationDialog.show(
                context,
                title: l10n.deleteAccountConfirmTitle,
                message: l10n.deleteAccountConfirmBody,
                confirmLabel: l10n.delete,
                destructive: true,
              );
              if (!ok || !context.mounted) return;
              setState(() => _busy = true);
              try {
                await ref
                    .read(sessionControllerProvider.notifier)
                    .deleteAccount();
                if (!context.mounted) return;
                DaryobToast.show(context, l10n.accountDeleted);
                context.go(Routes.home);
              } catch (e) {
                if (context.mounted) {
                  setState(() => _busy = false);
                  DaryobToast.show(
                    context,
                    failureMessage(l10n, e),
                    isError: true,
                  );
                }
              }
            },
          ),
      ],
    );
  }
}
