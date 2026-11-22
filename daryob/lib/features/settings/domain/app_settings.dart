import 'package:flutter/widgets.dart';

import '../../notifications/domain/app_notification.dart';

enum AppThemePreference { system, light, dark }

@immutable
class AppSettings {
  const AppSettings({
    this.languageCode,
    this.theme = AppThemePreference.system,
    this.onboardingCompleted = false,
    this.regionId = 'tj',
    this.disabledNotifications = const {},
    this.hidePhoneByDefault = false,
  });

  /// 'tg' or 'ru'. Null until the user picks a language.
  final String? languageCode;
  final AppThemePreference theme;
  final bool onboardingCompleted;

  /// Region used for "nearby" and as the default search region.
  final String regionId;
  final Set<NotificationKind> disabledNotifications;
  final bool hidePhoneByDefault;

  static const supportedLanguages = ['tg', 'ru'];

  Locale? get locale => languageCode == null ? null : Locale(languageCode!);

  bool isNotificationEnabled(NotificationKind kind) =>
      !disabledNotifications.contains(kind);

  AppSettings copyWith({
    String? languageCode,
    AppThemePreference? theme,
    bool? onboardingCompleted,
    String? regionId,
    Set<NotificationKind>? disabledNotifications,
    bool? hidePhoneByDefault,
  }) {
    return AppSettings(
      languageCode: languageCode ?? this.languageCode,
      theme: theme ?? this.theme,
      onboardingCompleted: onboardingCompleted ?? this.onboardingCompleted,
      regionId: regionId ?? this.regionId,
      disabledNotifications:
          disabledNotifications ?? this.disabledNotifications,
      hidePhoneByDefault: hidePhoneByDefault ?? this.hidePhoneByDefault,
    );
  }

  Map<String, dynamic> toJson() => {
    'languageCode': languageCode,
    'theme': theme.name,
    'onboardingCompleted': onboardingCompleted,
    'regionId': regionId,
    'disabledNotifications': disabledNotifications.map((k) => k.name).toList(),
    'hidePhoneByDefault': hidePhoneByDefault,
  };

  factory AppSettings.fromJson(Map<String, dynamic> json) {
    final lang = json['languageCode'] as String?;
    return AppSettings(
      languageCode: supportedLanguages.contains(lang) ? lang : null,
      theme:
          AppThemePreference.values.asNameMap()[json['theme']] ??
          AppThemePreference.system,
      onboardingCompleted: json['onboardingCompleted'] as bool? ?? false,
      regionId: json['regionId'] as String? ?? 'tj',
      disabledNotifications: {
        for (final name in (json['disabledNotifications'] as List? ?? const []))
          if (NotificationKind.values.asNameMap()[name] != null)
            NotificationKind.values.asNameMap()[name]!,
      },
      hidePhoneByDefault: json['hidePhoneByDefault'] as bool? ?? false,
    );
  }
}
