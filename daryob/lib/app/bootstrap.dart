import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_ce_flutter/hive_ce_flutter.dart';

import '../core/backend/backend.dart';
import '../core/security/session_storage.dart';
import '../features/catalog/application/catalog_providers.dart';
import '../features/catalog/data/catalog_parser.dart';
import '../features/catalog/data/catalog_repository.dart';
import '../features/catalog/domain/catalog.dart';
import '../core/storage/local_database.dart';
import '../shared/providers/core_providers.dart';
import 'app.dart';
import 'configuration/app_config.dart';

/// Opens storage, wires dependencies and starts the app. The native splash
/// (navy background, lime mark) stays on screen until the first frame.
Future<void> bootstrap() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromEnvironment();

  await Hive.initFlutter('daryob');
  final database = await HiveLocalDatabase.open();
  final catalog = await _loadCatalog(database);
  final sessionStorage = SecureSessionStorage();
  final backend = config.isProduction && config.hasServer
      ? await connectBackend(
          url: config.serverUrl,
          publishableKey: config.serverKey,
          sessionStorage: sessionStorage,
        )
      : null;

  runApp(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(config),
        localDatabaseProvider.overrideWithValue(database),
        sessionStorageProvider.overrideWithValue(sessionStorage),
        backendClientProvider.overrideWithValue(backend),
        initialCatalogProvider.overrideWithValue(catalog),
      ],
      // Screens offer explicit "Retry" buttons; automatic background retries
      // would hide real errors and waste mobile data.
      retry: (_, _) => null,
      child: const DaryobApp(),
    ),
  );
}

/// Loads the cached catalog (installing the bundled one when newer). If the
/// cache is unreadable, falls back to the bundled file so the app always
/// starts.
Future<CatalogSnapshot> _loadCatalog(HiveLocalDatabase database) async {
  final repository = CatalogRepository(
    database: database,
    loadSeed: () => rootBundle.loadString(kCatalogAsset),
    clock: DateTime.now,
  );
  try {
    return await repository.load();
  } catch (_) {
    final raw = await rootBundle.loadString(kCatalogAsset);
    return const CatalogParser().parse(jsonDecode(raw) as Map<String, dynamic>);
  }
}
