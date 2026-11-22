import 'dart:convert';

import 'package:crypto/crypto.dart';

import '../../../core/networking/api_client.dart';
import '../../../core/storage/local_database.dart';
import '../domain/catalog.dart';
import 'catalog_importer.dart';
import 'catalog_parser.dart';

/// Loads the raw bundled catalog (an asset in the app, a file in tests).
typedef CatalogSeedLoader = Future<String> Function();

/// Information about the installed catalog version.
class CatalogInstall {
  const CatalogInstall({
    required this.version,
    required this.source,
    required this.installedAt,
    required this.checksum,
  });

  final String version;

  /// `bundled` or `remote`.
  final String source;
  final DateTime installedAt;
  final String checksum;

  Map<String, dynamic> toJson() => {
    'version': version,
    'source': source,
    'installedAt': installedAt.toIso8601String(),
    'checksum': checksum,
  };

  factory CatalogInstall.fromJson(Map<String, dynamic> j) => CatalogInstall(
    version: j['version'] as String,
    source: j['source'] as String,
    installedAt: DateTime.parse(j['installedAt'] as String),
    checksum: j['checksum'] as String,
  );
}

/// Versioned, offline-cached catalog.
///
/// * The active version and the previous one are kept in the local
///   database, so the app works offline and a bad update can be rolled back.
/// * A newer bundled catalog (shipped with an app update) replaces an older
///   cached one; a newer remote catalog (production API) replaces both.
/// * Every candidate is parsed before it is installed — a file that fails
///   parsing never becomes active.
/// * Authorized import batches are stored separately and merged on load.
class CatalogRepository {
  CatalogRepository({
    required LocalDatabase database,
    required this.loadSeed,
    required this._clock,
    this.api,
    this.parser = const CatalogParser(),
    this.importer = const CatalogImporter(),
  }) : _store = database.collection(Collections.catalog);

  final JsonCollection _store;
  final CatalogSeedLoader loadSeed;
  final DateTime Function() _clock;
  final ApiClient? api;
  final CatalogParser parser;
  final CatalogImporter importer;

  static const _active = 'active';
  static const _previous = 'previous';
  static const _batchPrefix = 'import:';

  CatalogInstall? get installed {
    final json = _store.get(_active);
    return json == null ? null : CatalogInstall.fromJson(json['info'] as Map<String, dynamic>);
  }

  CatalogInstall? get previous {
    final json = _store.get(_previous);
    return json == null ? null : CatalogInstall.fromJson(json['info'] as Map<String, dynamic>);
  }

  /// Installs the bundled catalog if nothing newer is cached, then returns
  /// the active snapshot with import batches applied.
  Future<CatalogSnapshot> load() async {
    final seedRaw = await loadSeed();
    final seed = jsonDecode(seedRaw) as Map<String, dynamic>;
    final current = installed;
    if (current == null || compareVersions(seed['version'] as String, current.version) > 0) {
      await install(seed, source: 'bundled', rawText: seedRaw);
    }
    return activeSnapshot();
  }

  CatalogSnapshot activeSnapshot() {
    final json = _store.get(_active);
    if (json == null) throw StateError('No catalog installed');
    final base = parser.parse(json['data'] as Map<String, dynamic>);
    return importer.apply(base, importBatches());
  }

  /// Parses first (throws on a broken file), then makes [raw] active and
  /// keeps the previous version for rollback.
  Future<CatalogInstall> install(
    Map<String, dynamic> raw, {
    required String source,
    String? rawText,
  }) async {
    parser.parse(raw); // integrity check — throws on bad data
    final info = CatalogInstall(
      version: raw['version'] as String,
      source: source,
      installedAt: _clock(),
      checksum: sha256.convert(utf8.encode(rawText ?? jsonEncode(raw))).toString(),
    );
    final old = _store.get(_active);
    if (old != null) await _store.put(_previous, old);
    await _store.put(_active, {'info': info.toJson(), 'data': raw});
    return info;
  }

  /// Restores the previous version. Returns false when there is none.
  Future<bool> rollback() async {
    final old = _store.get(_previous);
    if (old == null) return false;
    await _store.put(_active, old);
    await _store.delete(_previous);
    return true;
  }

  /// Production: asks the API for a newer catalog and installs it. Any
  /// failure leaves the current catalog untouched.
  Future<CatalogSyncResult> syncRemote() async {
    final client = api;
    if (client == null) return CatalogSyncResult.notConfigured;
    try {
      final manifest = await client.getJson('/v1/catalog/manifest');
      final remoteVersion = manifest['version'] as String?;
      final current = installed;
      if (remoteVersion == null ||
          (current != null && compareVersions(remoteVersion, current.version) <= 0)) {
        return CatalogSyncResult.upToDate;
      }
      final raw = await client.getJson('/v1/catalog');
      await install(raw, source: 'remote');
      return CatalogSyncResult.updated;
    } catch (_) {
      return CatalogSyncResult.failed;
    }
  }

  // ── Authorized imports ────────────────────────────────────────────────

  List<Map<String, dynamic>> importBatches() => [
    for (final key in _store.keys.where((k) => k.startsWith(_batchPrefix)).toList()..sort())
      _store.get(key)!,
  ];

  /// Validates and stores a batch. Only accepted records are kept.
  Future<ImportReport> importBatch(Map<String, dynamic> batch) async {
    final base = parser.parse(_store.get(_active)!['data'] as Map<String, dynamic>);
    final report = importer.validate(batch, base);
    if (report.accepted.isNotEmpty) {
      await _store.put('$_batchPrefix${report.batchId}', {
        'import_batch_id': report.batchId,
        'records': report.accepted,
      });
    }
    return report;
  }

  Future<void> removeBatch(String batchId) => _store.delete('$_batchPrefix$batchId');
}

enum CatalogSyncResult { notConfigured, upToDate, updated, failed }

/// Compares "0.1.0-research-starter" style versions by their numbers.
int compareVersions(String a, String b) {
  List<int> parts(String v) =>
      RegExp(r'\d+').allMatches(v).map((m) => int.parse(m[0]!)).toList();
  final pa = parts(a);
  final pb = parts(b);
  for (var i = 0; i < 3; i++) {
    final x = i < pa.length ? pa[i] : 0;
    final y = i < pb.length ? pb[i] : 0;
    if (x != y) return x.compareTo(y);
  }
  return 0;
}
