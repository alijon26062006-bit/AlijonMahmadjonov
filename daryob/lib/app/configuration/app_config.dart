/// Build-time configuration for DARYOB.
///
/// Values are passed with `--dart-define`:
///
/// ```
/// flutter run --dart-define=DARYOB_ENV=production \
///             --dart-define=DARYOB_API_URL=https://api.example.tj
/// ```
///
/// Nothing secret belongs here: everything compiled into the app can be
/// extracted from the APK. SMS, payment and push credentials must live on the
/// server, never in the mobile client.
library;

enum AppEnvironment {
  /// Works without any backend. Uses local persistent storage and clearly
  /// labelled demo data so every main flow can be tried on a phone.
  development,

  /// Uses real services only. Features whose service is not configured show
  /// an explicit "unavailable" state instead of pretending to work.
  production,
}

/// Version shown in Settings → About. Keep in sync with `version:` in
/// pubspec.yaml (a test checks this).
const String kAppVersion = '0.1.0';
const int kAppBuildNumber = 1;

class AppConfig {
  const AppConfig({
    required this.environment,
    required this.apiBaseUrl,
    this.defaultLanguageCode = 'tg',
  });

  factory AppConfig.fromEnvironment() {
    const env = String.fromEnvironment(
      'DARYOB_ENV',
      defaultValue: 'development',
    );
    const url = String.fromEnvironment('DARYOB_API_URL');
    const lang = String.fromEnvironment(
      'DARYOB_DEFAULT_LANG',
      defaultValue: 'tg',
    );
    return AppConfig(
      environment: env == 'production'
          ? AppEnvironment.production
          : AppEnvironment.development,
      apiBaseUrl: url.trim(),
      defaultLanguageCode: lang == 'ru' ? 'ru' : 'tg',
    );
  }

  final AppEnvironment environment;

  /// Base URL of the DARYOB REST API. Empty when no backend is connected.
  final String apiBaseUrl;

  /// Language used before the user picks one, when the phone's language is
  /// neither Tajik nor Russian.
  final String defaultLanguageCode;

  bool get isDevelopment => environment == AppEnvironment.development;
  bool get isProduction => environment == AppEnvironment.production;
  bool get hasBackend => apiBaseUrl.isNotEmpty;

  String get versionLabel => '$kAppVersion ($kAppBuildNumber)';
}
