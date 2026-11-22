import 'package:daryob/app/app.dart';
import 'package:daryob/app/configuration/app_config.dart';
import 'package:daryob/core/security/session_storage.dart';
import 'package:daryob/core/storage/local_database.dart';
import 'package:daryob/features/categories/data/initial_categories.dart';
import 'package:daryob/features/categories/data/tajikistan_regions.dart';
import 'package:daryob/features/categories/domain/category_registry.dart';
import 'package:daryob/features/categories/domain/region_directory.dart';
import 'package:daryob/features/categories/domain/schema_registry.dart';
import 'package:daryob/features/listings/data/local_listing_repository.dart';
import 'package:daryob/features/listings/domain/listing_draft.dart';
import 'package:daryob/features/settings/domain/app_settings.dart';
import 'package:daryob/shared/providers/core_providers.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const devConfig = AppConfig(
  environment: AppEnvironment.development,
  apiBaseUrl: '',
  defaultLanguageCode: 'ru',
);

const prodConfig = AppConfig(
  environment: AppEnvironment.production,
  apiBaseUrl: '',
);

final fixedNow = DateTime(2026, 11, 20, 12);

LocalListingRepository listingRepo(
  LocalDatabase db, {
  DateTime Function()? clock,
}) {
  return LocalListingRepository(
    database: db,
    categories: CategoryRegistry(initialCategories),
    schemas: SchemaRegistry(),
    regions: RegionDirectory(tajikistanRegions),
    clock: clock ?? () => fixedNow,
  );
}

/// A draft that passes every validation step.
ListingDraft validDraft({
  String id = 'd1',
  String categoryId = 'electronics',
  String title = 'Смартфон в отличном состоянии',
  String price = '2500',
  String regionId = 'khujand',
}) {
  return ListingDraft(
    id: id,
    updatedAt: fixedNow,
    categoryId: categoryId,
    title: title,
    description: 'Полный комплект, коробка и зарядка, без царапин.',
    priceText: price,
    attributes: const {'condition': 'used'},
    regionId: regionId,
    contactName: 'Фарид',
    contactPhone: '93 123 45 67',
  );
}

/// Seeds settings so the app starts past onboarding in [language].
Future<void> seedSettings(
  LocalDatabase db, {
  String language = 'ru',
  bool onboardingDone = true,
}) async {
  await db
      .collection(Collections.settings)
      .put(
        'app',
        AppSettings(
          languageCode: language,
          onboardingCompleted: onboardingDone,
        ).toJson(),
      );
}

Widget testApp(
  LocalDatabase db, {
  AppConfig config = devConfig,
  SessionStorage? session,
}) {
  return ProviderScope(
    overrides: [
      appConfigProvider.overrideWithValue(config),
      localDatabaseProvider.overrideWithValue(db),
      sessionStorageProvider.overrideWithValue(
        session ?? MemorySessionStorage(),
      ),
    ],
    retry: (_, _) => null,
    child: const DaryobApp(),
  );
}

/// Pumps frames for [duration]. The app has looping animations (skeletons),
/// so pumpAndSettle would never return.
Future<void> pumpFor(WidgetTester tester, Duration duration) async {
  const step = Duration(milliseconds: 50);
  var elapsed = Duration.zero;
  while (elapsed < duration) {
    await tester.pump(step);
    elapsed += step;
  }
}

/// Starts the app and waits past the splash screen.
Future<void> startApp(
  WidgetTester tester,
  LocalDatabase db, {
  AppConfig config = devConfig,
}) async {
  tester.view.physicalSize = const Size(1080, 2340);
  tester.view.devicePixelRatio = 3;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(testApp(db, config: config));
  await pumpFor(tester, const Duration(milliseconds: 1200));
}
