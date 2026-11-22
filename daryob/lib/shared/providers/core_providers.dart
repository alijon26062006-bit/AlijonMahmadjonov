import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/configuration/app_config.dart';
import '../../core/networking/api_client.dart';
import '../../core/security/session_storage.dart';
import '../../core/storage/local_database.dart';
import '../../features/catalog/application/catalog_providers.dart';
import '../../features/categories/data/tajikistan_regions.dart';
import '../../features/categories/domain/category_registry.dart';
import '../../features/categories/domain/region_directory.dart';
import '../../features/categories/domain/schema_registry.dart';
import '../../features/listings/domain/draft_validator.dart';

/// Overridden in `bootstrap()` and in tests.
final appConfigProvider = Provider<AppConfig>(
  (ref) => throw UnimplementedError('appConfigProvider must be overridden'),
);

final localDatabaseProvider = Provider<LocalDatabase>(
  (ref) => throw UnimplementedError('localDatabaseProvider must be overridden'),
);

final sessionStorageProvider = Provider<SessionStorage>(
  (ref) =>
      throw UnimplementedError('sessionStorageProvider must be overridden'),
);

/// Injectable clock so tests control time.
final clockProvider = Provider<DateTime Function()>((ref) => DateTime.now);

/// Null when no API URL is configured.
final apiClientProvider = Provider<ApiClient?>((ref) {
  final config = ref.watch(appConfigProvider);
  if (!config.hasBackend) return null;
  return ApiClient(
    baseUrl: config.apiBaseUrl,
    sessionStorage: ref.watch(sessionStorageProvider),
  );
});

/// Categories and field schemas come from the versioned catalog.
final categoryRegistryProvider = Provider<CategoryRegistry>(
  (ref) => CategoryRegistry(ref.watch(catalogProvider).categories),
);

final schemaRegistryProvider = Provider<SchemaRegistry>(
  (ref) => SchemaRegistry(ref.watch(catalogProvider).schemas),
);

final regionDirectoryProvider = Provider<RegionDirectory>(
  (ref) => RegionDirectory(tajikistanRegions),
);

final draftValidatorProvider = Provider<DraftValidator>(
  (ref) => DraftValidator(
    ref.watch(categoryRegistryProvider),
    ref.watch(schemaRegistryProvider),
    clock: ref.watch(clockProvider),
  ),
);
