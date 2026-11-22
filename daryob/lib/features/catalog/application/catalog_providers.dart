import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/providers/core_providers.dart';
import '../data/catalog_repository.dart';
import '../domain/catalog.dart';

const kCatalogAsset = 'assets/catalog/daryob_catalog_master_2026.json';

/// Snapshot loaded before the first frame (see `bootstrap`). Overridden in
/// the app and in tests.
final initialCatalogProvider = Provider<CatalogSnapshot>(
  (ref) => throw UnimplementedError('initialCatalogProvider must be overridden'),
);

final catalogRepositoryProvider = Provider<CatalogRepository>((ref) {
  return CatalogRepository(
    database: ref.watch(localDatabaseProvider),
    loadSeed: () => rootBundle.loadString(kCatalogAsset),
    clock: ref.watch(clockProvider),
    api: ref.watch(apiClientProvider),
  );
});

/// The catalog every screen uses. Reloads after a sync, import or rollback.
final catalogProvider = NotifierProvider<CatalogController, CatalogSnapshot>(
  CatalogController.new,
);

class CatalogController extends Notifier<CatalogSnapshot> {
  @override
  CatalogSnapshot build() => ref.read(initialCatalogProvider);

  void reload() => state = ref.read(catalogRepositoryProvider).activeSnapshot();

  /// Production only: fetch a newer catalog from the API.
  Future<CatalogSyncResult> sync() async {
    final result = await ref.read(catalogRepositoryProvider).syncRemote();
    if (result == CatalogSyncResult.updated) reload();
    return result;
  }
}
