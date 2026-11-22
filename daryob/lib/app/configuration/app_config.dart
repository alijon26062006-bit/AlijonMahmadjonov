/// Build-time configuration for DARYOB.
///
/// Values are passed with `--dart-define`:
///
/// ```
/// flutter run --dart-define=DARYOB_ENV=production
/// flutter run --dart-define=DARYOB_ENV=development   # local demo data
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
const String kAppVersion = '0.2.0';
const int kAppBuildNumber = 2;

class AppConfig {
  const AppConfig({
    required this.environment,
    required this.apiBaseUrl,
    this.defaultLanguageCode = 'tg',
    this.serverUrl = '',
    this.serverKey = '',
  });

  factory AppConfig.fromEnvironment() {
    // Release builds talk to the real server unless told otherwise; debug
    // builds and tests use local demo data.
    const env = String.fromEnvironment(
      'DARYOB_ENV',
      defaultValue: bool.fromEnvironment('dart.vm.product') ? 'production' : 'development',
    );
    const serverUrl = String.fromEnvironment(
      'DARYOB_SERVER_URL',
      defaultValue: 'https://thmptlegknxlbxmmkyrl.supabase.co',
    );
    // A publishable key: it only identifies the project. What each user may
    // read or change is decided by the database's row level security.
    const serverKey = String.fromEnvironment(
      'DARYOB_SERVER_KEY',
      defaultValue: 'sb_publishable_tZDxituO7EfLL4NYag1nVw_ndkPeLdO',
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
      serverUrl: serverUrl.trim(),
      serverKey: serverKey.trim(),
    );
  }

  final AppEnvironment environment;

  /// Base URL of the DARYOB REST API. Empty when no backend is connected.
  final String apiBaseUrl;

  /// DARYOB server (Supabase) address and publishable key. Empty when no
  /// server is connected.
  final String serverUrl;
  final String serverKey;

  /// Language used before the user picks one, when the phone's language is
  /// neither Tajik nor Russian.
  final String defaultLanguageCode;

  bool get isDevelopment => environment == AppEnvironment.development;
  bool get isProduction => environment == AppEnvironment.production;
  bool get hasServer => serverUrl.isNotEmpty && serverKey.isNotEmpty;
  bool get hasBackend => apiBaseUrl.isNotEmpty || hasServer;

  String get versionLabel => '$kAppVersion ($kAppBuildNumber)';
}
