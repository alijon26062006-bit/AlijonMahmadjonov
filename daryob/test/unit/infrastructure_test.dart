import 'dart:convert';
import 'dart:io';

import 'package:daryob/app/configuration/app_config.dart';
import 'package:daryob/core/errors/failure.dart';
import 'package:daryob/core/networking/api_client.dart';
import 'package:daryob/core/storage/local_database.dart';
import 'package:daryob/features/settings/application/settings_controller.dart';
import 'package:daryob/features/settings/domain/app_settings.dart';
import 'package:daryob/shared/providers/core_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('API error mapping', () {
    test('status codes', () {
      expect(mapStatusCode(401), isA<UnauthorizedFailure>());
      expect(
        mapStatusCode(401, {'code': 'session_expired'}),
        isA<UnauthorizedFailure>().having(
          (f) => f.sessionExpired,
          'expired',
          isTrue,
        ),
      );
      expect(mapStatusCode(403), isA<ForbiddenFailure>());
      expect(mapStatusCode(404), isA<NotFoundFailure>());
      expect(mapStatusCode(429), isA<RateLimitedFailure>());
      expect(mapStatusCode(500), isA<ServerFailure>());
      final validation = mapStatusCode(422, {
        'errors': {'title': 'too_short'},
      });
      expect((validation as ValidationFailure).fieldErrors, {
        'title': 'too_short',
      });
    });

    test('transport errors', () {
      DioException e(DioExceptionType t) =>
          DioException(requestOptions: RequestOptions(), type: t);
      expect(
        mapDioException(e(DioExceptionType.connectionError)),
        isA<NetworkFailure>(),
      );
      expect(
        mapDioException(e(DioExceptionType.receiveTimeout)),
        isA<TimeoutFailure>(),
      );
    });
  });

  group('settings persistence', () {
    test('language, theme and region survive a restart', () async {
      final db = MemoryLocalDatabase();
      ProviderContainer make() => ProviderContainer(
        overrides: [localDatabaseProvider.overrideWithValue(db)],
      );

      final first = make();
      final controller = first.read(settingsControllerProvider.notifier);
      await controller.setLanguage('tg');
      await controller.setTheme(AppThemePreference.dark);
      await controller.setRegion('khujand');
      await controller.completeOnboarding();
      first.dispose();

      final second = make();
      final settings = second.read(settingsControllerProvider);
      expect(settings.languageCode, 'tg');
      expect(settings.theme, AppThemePreference.dark);
      expect(settings.regionId, 'khujand');
      expect(settings.onboardingCompleted, isTrue);
      second.dispose();
    });

    test('unknown stored language is ignored', () {
      expect(AppSettings.fromJson({'languageCode': 'en'}).languageCode, isNull);
    });
  });

  test('app version constant matches pubspec.yaml', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    final match = RegExp(
      r'^version:\s*([\d.]+)\+(\d+)',
      multiLine: true,
    ).firstMatch(pubspec)!;
    expect(kAppVersion, match.group(1));
    expect(kAppBuildNumber, int.parse(match.group(2)!));
  });

  group('translations', () {
    Map<String, dynamic> arb(String lang) => jsonDecode(
      File('lib/app/localization/arb/app_$lang.arb').readAsStringSync(),
    ) as Map<String, dynamic>;

    test('Tajik and Russian have the same keys and no empty strings', () {
      final ru = arb('ru');
      final tg = arb('tg');
      Set<String> keys(Map<String, dynamic> m) =>
          m.keys.where((k) => !k.startsWith('@')).toSet();
      expect(keys(tg), keys(ru));
      for (final k in keys(tg)) {
        expect((tg[k] as String).trim(), isNotEmpty, reason: k);
      }
    });

    test('placeholders match between languages', () {
      final ru = arb('ru');
      final tg = arb('tg');
      final placeholder = RegExp(r'\{(\w+)[},]');
      for (final key in ru.keys.where((k) => !k.startsWith('@'))) {
        final expected = placeholder
            .allMatches(ru[key] as String)
            .map((m) => m[1])
            .toSet();
        final actual = placeholder
            .allMatches(tg[key] as String)
            .map((m) => m[1])
            .toSet();
        expect(actual, expected, reason: key);
      }
    });

    test('Tajik texts use Tajik letters', () {
      final tg = arb('tg');
      final all = tg.values.whereType<String>().join(' ');
      for (final letter in ['ҷ', 'ҳ', 'қ', 'ӯ', 'ғ', 'ӣ']) {
        expect(all.contains(letter), isTrue, reason: letter);
      }
    });
  });
}
