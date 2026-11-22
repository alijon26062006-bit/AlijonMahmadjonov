import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/models/user.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/badges.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/language_selector.dart';
import '../../../shared/widgets/require_sign_in.dart';
import '../../../shared/widgets/seller_tile.dart';
import '../../authentication/application/session_controller.dart';
import '../../settings/application/settings_controller.dart';
import '../../settings/domain/app_settings.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final user = ref.watch(sessionControllerProvider);
    final config = ref.watch(appConfigProvider);
    final settings = ref.watch(settingsControllerProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.tabProfile)),
      body: ListView(
        children: [
          Padding(
            padding: const EdgeInsets.all(DaryobSpacing.page),
            child: user == null ? const _GuestCard() : _UserCard(user: user),
          ),
          if (user != null) ...[
            _Section(l10n.sectionListings),
            _Item(
              Icons.list_alt_rounded,
              l10n.myListings,
              () => context.push(Routes.myListings),
            ),
            _Item(
              Icons.edit_note_rounded,
              l10n.myDrafts,
              () => context.push(Routes.drafts),
            ),
            _Item(
              Icons.favorite_border_rounded,
              l10n.tabFavorites,
              () => context.go(Routes.favorites),
            ),
            _Section(l10n.sectionMoney),
            _Item(
              Icons.rocket_launch_outlined,
              l10n.myPromotions,
              () => context.push(Routes.myPromotions),
            ),
            _Item(
              Icons.account_balance_wallet_outlined,
              l10n.wallet,
              () => context.push(Routes.wallet),
            ),
            _Item(
              Icons.storefront_outlined,
              l10n.businessAccount,
              () => context.push(Routes.business),
            ),
          ] else ...[
            _Section(l10n.sectionListings),
            _Item(
              Icons.edit_note_rounded,
              l10n.myDrafts,
              () => context.push(Routes.drafts),
            ),
            _Item(
              Icons.favorite_border_rounded,
              l10n.tabFavorites,
              () => context.go(Routes.favorites),
            ),
          ],
          _Section(l10n.sectionApp),
          _Item(
            Icons.notifications_none_rounded,
            l10n.notifications,
            () => context.push(Routes.notifications),
          ),
          _Item(
            Icons.translate_rounded,
            l10n.language,
            () => _pickLanguage(context),
            trailing: languageNames[context.languageCode],
          ),
          _Item(
            Icons.dark_mode_outlined,
            l10n.theme,
            () => _pickTheme(context, ref),
            trailing: themeLabel(l10n, settings.theme),
          ),
          _Item(
            Icons.settings_outlined,
            l10n.settings,
            () => context.push(Routes.settings),
          ),
          _Section(l10n.sectionHelp),
          _Item(
            Icons.shield_outlined,
            l10n.safetyTitle,
            () => context.push(Routes.safety),
          ),
          _Item(
            Icons.support_agent_rounded,
            l10n.support,
            () => context.push(Routes.info('support')),
          ),
          _Item(
            Icons.description_outlined,
            l10n.terms,
            () => context.push(Routes.info('terms')),
          ),
          _Item(
            Icons.privacy_tip_outlined,
            l10n.privacyPolicy,
            () => context.push(Routes.info('privacy')),
          ),
          _Item(
            Icons.info_outline_rounded,
            l10n.aboutApp,
            () => context.push(Routes.info('about')),
          ),
          if (config.isDevelopment)
            _Item(
              Icons.science_outlined,
              l10n.devTools,
              () => context.push(Routes.devTools),
            ),
          if (user != null) ...[
            const SizedBox(height: DaryobSpacing.lg),
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: DaryobSpacing.page,
              ),
              child: DaryobSecondaryButton(
                label: l10n.signOut,
                icon: Icons.logout_rounded,
                onPressed: () async {
                  final ok = await DaryobConfirmationDialog.show(
                    context,
                    title: l10n.signOutTitle,
                    message: l10n.signOutBody,
                    confirmLabel: l10n.signOut,
                  );
                  if (ok) {
                    await ref
                        .read(sessionControllerProvider.notifier)
                        .signOut();
                  }
                },
              ),
            ),
            TextButton(
              onPressed: () => context.push(Routes.info('deletion')),
              style: TextButton.styleFrom(
                foregroundColor: context.colors.error,
              ),
              child: Text(l10n.deleteAccount),
            ),
          ],
          Padding(
            padding: const EdgeInsets.all(DaryobSpacing.lg),
            child: Text(
              'DARYOB ${config.versionLabel}${config.isDevelopment ? ' · DEV' : ''}',
              textAlign: TextAlign.center,
              style: context.text.bodySmall,
            ),
          ),
        ],
      ),
    );
  }

  void _pickLanguage(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      builder: (context) => Padding(
        padding: const EdgeInsets.fromLTRB(
          DaryobSpacing.page,
          0,
          DaryobSpacing.page,
          DaryobSpacing.xxl,
        ),
        child: DaryobLanguageSelector(
          onSelected: (_) => Navigator.of(context).pop(),
        ),
      ),
    );
  }

  void _pickTheme(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: RadioGroup<AppThemePreference>(
          groupValue: ref.read(settingsControllerProvider).theme,
          onChanged: (v) {
            if (v != null) {
              ref.read(settingsControllerProvider.notifier).setTheme(v);
            }
            Navigator.of(context).pop();
          },
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final t in AppThemePreference.values)
                RadioListTile<AppThemePreference>(
                  value: t,
                  title: Text(themeLabel(l10n, t)),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GuestCard extends ConsumerWidget {
  const _GuestCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    return Container(
      padding: const EdgeInsets.all(DaryobSpacing.xl),
      decoration: const BoxDecoration(
        color: DaryobColors.navy,
        borderRadius: DaryobRadius.heroAll,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l10n.guestTitle,
            style: context.text.titleLarge?.copyWith(color: Colors.white),
          ),
          const SizedBox(height: DaryobSpacing.xs),
          Text(
            l10n.guestBody,
            style: context.text.bodyMedium?.copyWith(color: Colors.white70),
          ),
          const SizedBox(height: DaryobSpacing.lg),
          DaryobPrimaryButton(
            label: l10n.signIn,
            tone: DaryobButtonTone.accent,
            onPressed: () => requireSignIn(context, ref),
          ),
        ],
      ),
    );
  }
}

class _UserCard extends ConsumerWidget {
  const _UserCard({required this.user});
  final AppUser user;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final region = ref.watch(regionDirectoryProvider).byId(user.regionId);
    final initials = user.name == null
        ? ''
        : user.name!
              .trim()
              .split(RegExp(r'\s+'))
              .where((p) => p.isNotEmpty)
              .take(2)
              .map((p) => String.fromCharCode(p.runes.first).toUpperCase())
              .join();

    return Card(
      child: InkWell(
        borderRadius: DaryobRadius.cardAll,
        onTap: () => context.push(Routes.editProfile),
        child: Padding(
          padding: const EdgeInsets.all(DaryobSpacing.lg),
          child: Row(
            children: [
              DaryobAvatar(initials: initials, size: 60),
              const SizedBox(width: DaryobSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      user.name ?? l10n.noName,
                      style: context.text.titleMedium,
                    ),
                    const SizedBox(height: 2),
                    // The number is shown as "verified" only after real SMS.
                    Text(
                      user.isPhoneVerified
                          ? Formatters.phone(user.phone)
                          : '${Formatters.phone(user.phone)} · ${l10n.phoneNotVerified}',
                      style: context.text.bodySmall,
                    ),
                    if (region != null)
                      Text(
                        region.name.of(context),
                        style: context.text.bodySmall,
                      ),
                    Text(
                      l10n.memberSince(Formatters.date(user.createdAt)),
                      style: context.text.bodySmall,
                    ),
                    const SizedBox(height: DaryobSpacing.xs),
                    Wrap(
                      spacing: 4,
                      children: [
                        DaryobStatusBadge(
                          label: user.accountType == AccountType.business
                              ? l10n.sellerBusiness
                              : l10n.sellerPrivate,
                        ),
                        if (user.isDemo) const DemoBadge(),
                      ],
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.title);
  final String title;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(
      DaryobSpacing.page,
      DaryobSpacing.xl,
      DaryobSpacing.page,
      DaryobSpacing.xs,
    ),
    child: Text(
      title.toUpperCase(),
      style: context.text.labelSmall?.copyWith(letterSpacing: 0.8),
    ),
  );
}

class _Item extends StatelessWidget {
  const _Item(this.icon, this.title, this.onTap, {this.trailing});
  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final String? trailing;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon),
      title: Text(title),
      onTap: onTap,
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (trailing != null) Text(trailing!, style: context.text.bodySmall),
          const SizedBox(width: DaryobSpacing.xs),
          const Icon(Icons.chevron_right_rounded),
        ],
      ),
    );
  }
}
