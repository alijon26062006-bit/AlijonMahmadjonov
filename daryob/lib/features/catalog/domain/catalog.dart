import 'package:flutter/foundation.dart';

import '../../../shared/models/category.dart';
import '../../../shared/models/category_schema.dart';
import '../../../shared/models/localized_text.dart';

/// Where a catalog record came from. Required for every imported record
/// (catalog `future_catalog_ingestion_plan.required_record_metadata`).
@immutable
class RecordSource {
  const RecordSource({
    required this.sourceUrl,
    required this.sourceType,
    required this.verifiedAt,
    required this.importBatchId,
    required this.licenseOrTerms,
    required this.marketRegion,
    required this.confidence,
    required this.status,
  });

  final String sourceUrl;
  final String sourceType;
  final DateTime verifiedAt;
  final String importBatchId;
  final String licenseOrTerms;
  final String marketRegion;
  final double confidence;

  /// `verified`, `approved`, … — see [RecordSource.trustedStatuses].
  final String status;

  static const trustedStatuses = {'verified', 'approved'};

  bool get isTrusted => trustedStatuses.contains(status);

  Map<String, dynamic> toJson() => {
    'source_url': sourceUrl,
    'source_type': sourceType,
    'verified_at': verifiedAt.toIso8601String(),
    'import_batch_id': importBatchId,
    'license_or_terms': licenseOrTerms,
    'market_region': marketRegion,
    'confidence': confidence,
    'status': status,
  };

  factory RecordSource.fromJson(Map<String, dynamic> json) => RecordSource(
    sourceUrl: json['source_url'] as String,
    sourceType: json['source_type'] as String,
    verifiedAt: DateTime.parse(json['verified_at'] as String),
    importBatchId: json['import_batch_id'] as String,
    licenseOrTerms: json['license_or_terms'] as String,
    marketRegion: json['market_region'] as String,
    confidence: (json['confidence'] as num).toDouble(),
    status: json['status'] as String,
  );
}

/// A configuration of a model (storage, RAM, generation …) that came from a
/// verified source. Seed data contains none; they only arrive by import.
@immutable
class VerifiedVariant {
  const VerifiedVariant({
    required this.kind,
    required this.value,
    required this.source,
  });

  /// Matches the field key it fills, e.g. `storage_gb`, `ram_gb`.
  final String kind;
  final String value;
  final RecordSource source;
}

@immutable
class CatalogModel {
  const CatalogModel({
    required this.id,
    required this.name,
    required this.verification,
    this.variants = const [],
    this.source,
  });

  /// `<brandId>/<modelSlug>`.
  final String id;
  final String name;

  /// Status from the source, e.g. `needs_model_and_market_validation` for
  /// seed data or `verified` for imported records.
  final String verification;
  final List<VerifiedVariant> variants;
  final RecordSource? source;

  bool get isVerified => source?.isTrusted ?? false;

  List<VerifiedVariant> variantsOf(String kind) =>
      variants.where((v) => v.kind == kind).toList();
}

@immutable
class CatalogBrand {
  const CatalogBrand({
    required this.id,
    required this.name,
    this.models = const [],
    this.modelStatus = 'seed',
  });

  final String id;
  final String name;
  final List<CatalogModel> models;

  /// `not_collected` when the source lists the brand without models.
  final String modelStatus;

  CatalogModel? model(String id) {
    for (final m in models) {
      if (m.id == id) return m;
    }
    return null;
  }
}

/// Manufacturer/brand list for one kind of goods.
@immutable
class CatalogDirectory {
  const CatalogDirectory({
    required this.id,
    required this.label,
    required this.dataStatus,
    required this.brands,
  });

  final String id;
  final LocalizedText label;
  final String dataStatus;
  final List<CatalogBrand> brands;

  int get modelCount => brands.fold(0, (sum, b) => sum + b.models.length);

  CatalogBrand? brand(String id) {
    for (final b in brands) {
      if (b.id == id) return b;
    }
    return null;
  }

  CatalogModel? model(String modelId) {
    final brandId = modelId.split('/').first;
    return brand(brandId)?.model(modelId);
  }
}

/// Everything the app needs from one catalog version.
@immutable
class CatalogSnapshot {
  const CatalogSnapshot({
    required this.version,
    required this.createdOn,
    required this.currency,
    required this.languages,
    required this.limitations,
    required this.categories,
    required this.schemas,
    required this.directories,
    required this.warnings,
    this.appliedImportBatches = const [],
  });

  final String version;
  final String createdOn;
  final String currency;
  final List<String> languages;
  final List<String> limitations;

  /// Top-level categories followed by their subcategories.
  final List<CategoryDefinition> categories;
  final List<CategorySchema> schemas;
  final Map<String, CatalogDirectory> directories;

  /// Problems found while reading the source (e.g. a field with an invalid
  /// type that was skipped). Shown in the catalog status report.
  final List<String> warnings;
  final List<String> appliedImportBatches;

  int get topLevelCount => categories.where((c) => c.isTopLevel).length;
  int get subcategoryCount => categories.where((c) => !c.isTopLevel).length;

  CatalogDirectory? directory(String? id) => id == null ? null : directories[id];
}

/// Text helpers for ids built from names: "Mercedes-Benz" → "mercedes-benz".
String catalogSlug(String name) {
  const folding = {
    'ë': 'e', 'é': 'e', 'è': 'e', 'ö': 'o', 'ü': 'u', 'ä': 'a',
    'á': 'a', 'à': 'a', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ç': 'c', 'š': 's',
  };
  // "Galaxy S10+" must not collapse into "Galaxy S10".
  final lower = name.toLowerCase().split('').map((c) => folding[c] ?? c).join().replaceAll('+', ' plus ');
  return lower
      .replaceAll(RegExp(r'[^a-z0-9а-яёҷҳқғӣӯ]+'), '-')
      .replaceAll(RegExp(r'^-+|-+$'), '');
}
