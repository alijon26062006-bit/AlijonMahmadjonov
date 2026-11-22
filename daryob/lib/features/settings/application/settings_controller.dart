import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/providers/repository_providers.dart';
import '../../notifications/domain/app_notification.dart';
import '../domain/app_settings.dart';

final settingsControllerProvider =
    NotifierProvider<SettingsController, AppSettings>(SettingsController.new);

/// Settings are read synchronously at startup (the database is already
/// open) so the first frame already has the right language and theme.
class SettingsController extends Notifier<AppSettings> {
  @override
  AppSettings build() => ref.read(settingsRepositoryProvider).load();

  Future<void> _update(AppSettings next) async {
    state = next;
    await ref.read(settingsRepositoryProvider).save(next);
  }

  Future<void> setLanguage(String code) =>
      _update(state.copyWith(languageCode: code));

  Future<void> setTheme(AppThemePreference theme) =>
      _update(state.copyWith(theme: theme));

  Future<void> setRegion(String regionId) =>
      _update(state.copyWith(regionId: regionId));

  Future<void> completeOnboarding() =>
      _update(state.copyWith(onboardingCompleted: true));

  /// Development tool: show onboarding again on next launch.
  Future<void> resetOnboarding() =>
      _update(state.copyWith(onboardingCompleted: false));

  Future<void> setNotificationEnabled(NotificationKind kind, bool enabled) {
    final next = {...state.disabledNotifications};
    enabled ? next.remove(kind) : next.add(kind);
    return _update(state.copyWith(disabledNotifications: next));
  }

  Future<void> setHidePhoneByDefault(bool hide) =>
      _update(state.copyWith(hidePhoneByDefault: hide));
}
