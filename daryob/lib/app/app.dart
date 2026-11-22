import 'package:cupertino_ui/cupertino_ui.dart'
    show GlobalCupertinoLocalizations;
import 'package:flutter_localizations/flutter_localizations.dart'
    show GlobalWidgetsLocalizations;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../core/notifications/local_alerts.dart';
import '../features/conversations/application/chat_alerts.dart';
import '../features/settings/application/settings_controller.dart';
import '../features/settings/domain/app_settings.dart';
import '../shared/providers/core_providers.dart';
import 'localization/l10n.dart';
import 'localization/tajik_fallback.dart';
import 'router/app_router.dart';
import 'theme/app_theme.dart';

class DaryobApp extends ConsumerWidget {
  const DaryobApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(settingsControllerProvider);
    final config = ref.watch(appConfigProvider);
    final router = ref.watch(routerProvider);
    // System notifications for new chat messages; tapping one opens the chat.
    ref.watch(chatAlertsProvider);
    LocalAlerts.instance.onOpen = router.push;

    return MaterialApp.router(
      onGenerateTitle: (context) => context.l10n.appName,
      debugShowCheckedModeBanner: false,
      routerConfig: router,
      theme: DaryobTheme.light(),
      darkTheme: DaryobTheme.dark(),
      themeMode: switch (settings.theme) {
        AppThemePreference.system => ThemeMode.system,
        AppThemePreference.light => ThemeMode.light,
        AppThemePreference.dark => ThemeMode.dark,
      },
      locale: settings.locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        ...tajikFallbackDelegates,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ],
      // Before the user picks a language: use the device language when it
      // is Tajik or Russian, otherwise the configured default.
      localeResolutionCallback: (device, supported) {
        if (settings.locale != null) return settings.locale;
        final code = device?.languageCode;
        if (code == 'tg' || code == 'ru') return Locale(code!);
        return Locale(config.defaultLanguageCode);
      },
      builder: (context, child) {
        // Respect the user's font size but cap it so layouts stay usable.
        final media = MediaQuery.of(context);
        return MediaQuery(
          data: media.copyWith(
            textScaler: media.textScaler.clamp(maxScaleFactor: 1.3),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
