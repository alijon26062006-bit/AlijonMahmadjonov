import 'dart:convert';
import 'dart:io';

import 'package:daryob/app/app.dart';
import 'package:daryob/app/configuration/app_config.dart';
import 'package:daryob/core/security/session_storage.dart';
import 'package:daryob/core/storage/local_database.dart';
import 'package:daryob/features/catalog/application/catalog_providers.dart';
import 'package:daryob/features/catalog/data/catalog_parser.dart';
import 'package:daryob/features/catalog/domain/catalog.dart';
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

/// The bundled master catalog, parsed once per test file.
final CatalogSnapshot testCatalog = const CatalogParser().parse(
  jsonDecode(File('assets/catalog/daryob_catalog_master_2026.json').readAsStringSync())
      as Map<String, dynamic>,
);

CategoryRegistry testCategories() => CategoryRegistry(testCatalog.categories);

SchemaRegistry testSchemas() => SchemaRegistry(testCatalog.schemas);

LocalListingRepository listingRepo(
  LocalDatabase db, {
  DateTime Function()? clock,
}) {
  return LocalListingRepository(
    database: db,
    categories: testCategories(),
    schemas: testSchemas(),
    regions: RegionDirectory(tajikistanRegions),
    clock: clock ?? () => fixedNow,
  );
}

/// A draft that passes every validation step.
ListingDraft validDraft({
  String id = 'd1',
  String categoryId = 'electronics.smartphones',
  String title = 'Смартфон в отличном состоянии',
  String price = '2500',
  String regionId = 'khujand',
  Map<String, Object?> attributes = const {
    'brand_id': 'apple',
    'model_id': 'apple/iphone-13',
    'storage_gb': 128,
    'condition': 'used',
  },
}) {
  return ListingDraft(
    id: id,
    updatedAt: fixedNow,
    categoryId: categoryId,
    title: title,
    description: 'Полный комплект, коробка и зарядка, без царапин.',
    priceText: price,
    attributes: attributes,
    photos: const ['test/photo-1.jpg'],
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
      initialCatalogProvider.overrideWithValue(testCatalog),
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
