import '../domain/catalog.dart';

/// One record of an authorized import batch, e.g.
///
/// ```json
/// {"directory": "smartphones", "brand": "Apple", "model": "iPhone 16",
///  "variant_kind": "storage_gb", "variant_value": "128",
///  "source_url": "https://…", "source_type": "manufacturer_spec_page",
///  "verified_at": "2026-11-22", "import_batch_id": "apple-2026-11",
///  "license_or_terms": "…", "market_region": "TJ", "confidence": 0.95,
///  "status": "verified"}
/// ```
///
/// A batch is `{"import_batch_id": "...", "records": [...]}`.
class CatalogImporter {
  const CatalogImporter();

  /// Metadata every record must carry (catalog
  /// `future_catalog_ingestion_plan.required_record_metadata`).
  static const requiredMetadata = [
    'source_url',
    'source_type',
    'verified_at',
    'import_batch_id',
    'license_or_terms',
    'market_region',
    'confidence',
    'status',
  ];

  /// Field keys a variant may fill. Anything else is rejected.
  static const variantKinds = {'storage_gb', 'ram_gb', 'generation_id', 'cpu', 'breed'};

  /// Checks a batch without applying it.
  ImportReport validate(Map<String, dynamic> batch, CatalogSnapshot base) {
    final accepted = <Map<String, dynamic>>[];
    final rejected = <RejectedRecord>[];
    final batchId = batch['import_batch_id'];
    final records = batch['records'];
    if (batchId is! String || batchId.trim().isEmpty || records is! List) {
      return ImportReport(
        batchId: '$batchId',
        accepted: const [],
        rejected: const [RejectedRecord(index: -1, reason: 'batch must have import_batch_id and records')],
      );
    }
    final seen = <String>{};
    for (var i = 0; i < records.length; i++) {
      final r = records[i];
      String? reason;
      if (r is! Map<String, dynamic>) {
        reason = 'record is not an object';
      } else {
        reason = _check(r, base, batchId);
        if (reason == null) {
          final key = [
            r['directory'],
            catalogSlug(r['brand'] as String),
            catalogSlug('${r['model'] ?? ''}'),
            r['variant_kind'] ?? '',
            '${r['variant_value'] ?? ''}'.trim().toLowerCase(),
          ].join('|');
          if (!seen.add(key)) reason = 'duplicate within batch';
        }
      }
      if (reason == null) {
        accepted.add(r as Map<String, dynamic>);
      } else {
        rejected.add(RejectedRecord(index: i, reason: reason));
      }
    }
    return ImportReport(batchId: batchId, accepted: accepted, rejected: rejected);
  }

  String? _check(Map<String, dynamic> r, CatalogSnapshot base, String batchId) {
    for (final key in requiredMetadata) {
      final v = r[key];
      if (v == null || (v is String && v.trim().isEmpty)) return 'missing $key';
    }
    if (r['import_batch_id'] != batchId) return 'import_batch_id differs from batch';
    final license = (r['license_or_terms'] as String).toLowerCase();
    if (license == 'unknown' || license == 'none') return 'no licence / terms of use';
    if (!RecordSource.trustedStatuses.contains(r['status'])) {
      return 'status "${r['status']}" is not verified/approved';
    }
    final confidence = r['confidence'];
    if (confidence is! num || confidence < 0 || confidence > 1) return 'confidence must be 0..1';
    if (DateTime.tryParse('${r['verified_at']}') == null) return 'verified_at is not a date';
    final url = Uri.tryParse('${r['source_url']}');
    if (url == null || !url.hasScheme || !url.scheme.startsWith('http')) return 'source_url is not a URL';
    final directory = r['directory'];
    if (directory is! String || base.directory(directory) == null) return 'unknown directory "$directory"';
    final brand = r['brand'];
    if (brand is! String || brand.trim().isEmpty) return 'missing brand';
    final hasVariant = r.containsKey('variant_kind') || r.containsKey('variant_value');
    if (hasVariant) {
      if (!variantKinds.contains(r['variant_kind'])) return 'unknown variant_kind "${r['variant_kind']}"';
      if ('${r['variant_value'] ?? ''}'.trim().isEmpty) return 'missing variant_value';
      if ('${r['model'] ?? ''}'.trim().isEmpty) return 'variant needs a model';
    }
    return null;
  }

  /// Returns [base] with every batch merged in. Records are re-validated;
  /// invalid ones are ignored, so a bad batch can never break the catalog.
  CatalogSnapshot apply(CatalogSnapshot base, List<Map<String, dynamic>> batches) {
    if (batches.isEmpty) return base;
    final directories = {
      for (final e in base.directories.entries) e.key: _Mutable.from(e.value),
    };
    final applied = <String>[];
    for (final batch in batches) {
      final report = validate(batch, base);
      if (report.accepted.isEmpty) continue;
      applied.add(report.batchId);
      for (final r in report.accepted) {
        directories[r['directory']]!.add(r);
      }
    }
    return CatalogSnapshot(
      version: base.version,
      createdOn: base.createdOn,
      currency: base.currency,
      languages: base.languages,
      limitations: base.limitations,
      categories: base.categories,
      schemas: base.schemas,
      directories: {for (final e in directories.entries) e.key: e.value.build()},
      warnings: base.warnings,
      appliedImportBatches: [...base.appliedImportBatches, ...applied],
    );
  }
}

class ImportReport {
  const ImportReport({required this.batchId, required this.accepted, required this.rejected});
  final String batchId;
  final List<Map<String, dynamic>> accepted;
  final List<RejectedRecord> rejected;

  bool get isClean => rejected.isEmpty && accepted.isNotEmpty;
}

class RejectedRecord {
  const RejectedRecord({required this.index, required this.reason});
  final int index;
  final String reason;

  @override
  String toString() => '#$index: $reason';
}

/// Mutable copy of a directory used while merging records.
class _Mutable {
  _Mutable(this.base, this.brands);

  factory _Mutable.from(CatalogDirectory d) => _Mutable(d, {
    for (final b in d.brands)
      b.id: _MutableBrand(b, {
        for (final m in b.models) m.id: _MutableModel(m, [...m.variants], m.source),
      }),
  });

  final CatalogDirectory base;
  final Map<String, _MutableBrand> brands;

  void add(Map<String, dynamic> r) {
    final source = RecordSource.fromJson(r);
    final brandName = (r['brand'] as String).trim();
    final brandId = catalogSlug(brandName);
    final brand = brands.putIfAbsent(
      brandId,
      () => _MutableBrand(CatalogBrand(id: brandId, name: brandName, modelStatus: 'imported'), {}),
    );
    final modelName = '${r['model'] ?? ''}'.trim();
    if (modelName.isEmpty) return;
    final modelId = '$brandId/${catalogSlug(modelName)}';
    final model = brand.models.putIfAbsent(
      modelId,
      () => _MutableModel(
        CatalogModel(id: modelId, name: modelName, verification: source.status),
        [],
        source,
      ),
    );
    // A verified record upgrades a seed model's status.
    model.source ??= source;
    if (r['variant_kind'] != null) {
      final value = '${r['variant_value']}'.trim();
      final exists = model.variants.any((v) => v.kind == r['variant_kind'] && v.value == value);
      if (!exists) {
        model.variants.add(VerifiedVariant(kind: r['variant_kind'] as String, value: value, source: source));
      }
    }
  }

  CatalogDirectory build() {
    final list = brands.values.map((b) => b.build()).toList()
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    return CatalogDirectory(id: base.id, label: base.label, dataStatus: base.dataStatus, brands: list);
  }
}

class _MutableBrand {
  _MutableBrand(this.base, this.models);
  final CatalogBrand base;
  final Map<String, _MutableModel> models;

  CatalogBrand build() => CatalogBrand(
    id: base.id,
    name: base.name,
    modelStatus: base.modelStatus,
    models: models.values.map((m) => m.build()).toList(),
  );
}

class _MutableModel {
  _MutableModel(this.base, this.variants, this.source);
  final CatalogModel base;
  final List<VerifiedVariant> variants;
  RecordSource? source;

  CatalogModel build() => CatalogModel(
    id: base.id,
    name: base.name,
    verification: source?.status ?? base.verification,
    variants: variants,
    source: source,
  );
}
