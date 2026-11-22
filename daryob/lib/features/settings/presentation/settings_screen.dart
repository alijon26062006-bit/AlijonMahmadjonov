import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/language_selector.dart';
import '../../../shared/widgets/location_selector.dart';
import '../../notifications/domain/app_notification.dart';
import '../application/settings_controller.dart';
import '../domain/app_settings.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final settings = ref.watch(settingsControllerProvider);
    final controller = ref.read(settingsControllerProvider.notifier);
    final config = ref.watch(appConfigProvider);
    final directory = ref.watch(regionDirectoryProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.settings)),
      body: ListView(
        children: [
          _Header(l10n.language),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
            child: const DaryobLanguageSelector(),
          ),
          _Header(l10n.theme),
          RadioGroup<AppThemePreference>(
            groupValue: settings.theme,
            onChanged: (v) {
              if (v != null) controller.setTheme(v);
            },
            child: Column(
              children: [
                for (final t in AppThemePreference.values)
                  RadioListTile<AppThemePreference>(
                    value: t,
                    title: Text(themeLabel(l10n, t)),
                  ),
              ],
            ),
          ),
          _Header(l10n.location),
          ListTile(
            leading: const Icon(Icons.place_outlined),
            title: Text(regionPathLabel(context, directory, settings.regionId)),
            subtitle: Text(l10n.defaultRegionHint),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () async {
              final picked = await showLocationPicker(
                context,
                selectedId: settings.regionId,
              );
              if (picked != null) await controller.setRegion(picked);
            },
          ),
          _Header(l10n.notifications),
          for (final kind in NotificationKind.values)
            SwitchListTile(
              title: Text(notificationKindLabel(l10n, kind)),
              value: settings.isNotificationEnabled(kind),
              onChanged: (v) => controller.setNotificationEnabled(kind, v),
            ),
          _Header(l10n.privacy),
          SwitchListTile(
            title: Text(l10n.hidePhoneByDefault),
            subtitle: Text(l10n.hidePhoneByDefaultHint),
            value: settings.hidePhoneByDefault,
            onChanged: controller.setHidePhoneByDefault,
          ),
          ListTile(
            leading: const Icon(Icons.privacy_tip_outlined),
            title: Text(l10n.privacyPolicy),
            onTap: () => context.push(Routes.info('privacy')),
          ),
          ListTile(
            leading: const Icon(Icons.delete_forever_outlined),
            title: Text(l10n.dataDeletion),
            onTap: () => context.push(Routes.info('deletion')),
          ),
          _Header(l10n.aboutApp),
          ListTile(
            leading: const Icon(Icons.info_outline_rounded),
            title: Text(l10n.appVersion),
            trailing: Text(config.versionLabel),
            onTap: () => context.push(Routes.info('about')),
          ),
          ListTile(
            leading: const Icon(Icons.support_agent_rounded),
            title: Text(l10n.support),
            onTap: () => context.push(Routes.info('support')),
          ),
          ListTile(
            leading: const Icon(Icons.description_outlined),
            title: Text(l10n.terms),
            onTap: () => context.push(Routes.info('terms')),
          ),
          if (config.isDevelopment)
            ListTile(
              leading: const Icon(Icons.science_outlined),
              title: Text(l10n.devTools),
              onTap: () => context.push(Routes.devTools),
            ),
          const SizedBox(height: DaryobSpacing.xxl),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header(this.title);
  final String title;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(
      DaryobSpacing.page,
      DaryobSpacing.xl,
      DaryobSpacing.page,
      DaryobSpacing.sm,
    ),
    child: Text(title, style: context.text.titleMedium),
  );
}
