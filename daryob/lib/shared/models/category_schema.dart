import 'package:flutter/foundation.dart';

import 'localized_text.dart';

/// Kinds of input a category schema can declare. The listing wizard,
/// filters and the detail screen all render from these, so adding a category
/// means adding a schema (catalog data), not new screens.
enum FieldType {
  text,
  multilineText,

  /// Decimal number (area, engine volume, screen size).
  number,
  integer,

  /// Amount in TJS other than the main price (deposit, salary).
  money,
  singleSelect,
  multiSelect,
  boolean,
  color,

  /// Free size value ("M", "42", "110 cm") next to a size-system select.
  size,

  /// List of short free-text tags (skills).
  tags,

  /// Directory-backed: manufacturer / brand.
  brand,

  /// Directory-backed: model of the selected brand.
  model,

  /// Directory-backed: verified variant of the selected model (storage,
  /// RAM, generation, CPU, breed). Never offered from a guessed list.
  variant,

  /// Directory-backed: product family / series.
  family,

  /// Occupation taxonomy (jobs).
  occupation,

  /// Species list (animals and plants).
  species,

  /// Sub-area of the chosen location (district).
  locationChild,

  /// Point on a map.
  geoPoint,

  /// Two numbers (from–to). Filters only.
  numberRange,
}

/// Field types whose values are numbers.
const numericFieldTypes = {FieldType.number, FieldType.integer, FieldType.money};

/// Field types whose values come from a catalog directory.
const directoryFieldTypes = {
  FieldType.brand,
  FieldType.model,
  FieldType.variant,
  FieldType.family,
  FieldType.occupation,
  FieldType.species,
};

@immutable
class FieldOption {
  const FieldOption(this.value, this.label);
  final String value;
  final LocalizedText label;
}

enum ConditionOperator { equals, inList, notInList, notEmpty }

/// Show a field only when another field matches (catalog `show_if`):
/// `equals`, `in`, `not_in`, `operator: not_empty`.
@immutable
class FieldCondition {
  const FieldCondition({
    required this.fieldKey,
    this.op = ConditionOperator.equals,
    this.values = const [],
  });

  final String fieldKey;
  final ConditionOperator op;
  final List<Object> values;

  bool isMet(Map<String, Object?> attributes) {
    final current = attributes[fieldKey];
    bool matches(Object expected) =>
        current is List ? current.contains(expected) : current == expected;
    switch (op) {
      case ConditionOperator.equals:
      case ConditionOperator.inList:
        return values.any(matches);
      case ConditionOperator.notInList:
        return !values.any(matches);
      case ConditionOperator.notEmpty:
        if (current == null) return false;
        if (current is String) return current.trim().isNotEmpty;
        if (current is List) return current.isNotEmpty;
        return true;
    }
  }
}

@immutable
class FieldSchema {
  const FieldSchema({
    required this.key,
    required this.type,
    required this.label,
    this.hint,
    this.required = false,
    this.options = const [],
    this.min,
    this.max,
    this.minExclusive,
    this.maxCurrentYearOffset,
    this.unit,
    this.visibleWhen,
    this.filterable = false,
    this.showInDetails = true,
    this.directory,
    this.dependsOn,
  });

  /// Stored under `listing.attributes[key]`. Never rename a shipped key.
  final String key;
  final FieldType type;
  final LocalizedText label;
  final LocalizedText? hint;
  final bool required;
  final List<FieldOption> options;
  final num? min;
  final num? max;

  /// Value must be strictly greater than this (e.g. area > 0).
  final num? minExclusive;

  /// Upper bound relative to the current year (`current_year+1` → 1).
  final int? maxCurrentYearOffset;

  /// Unit code: TJS, m2, km, l, GB, %, inch, sotka, cm, mm.
  final String? unit;
  final FieldCondition? visibleWhen;
  final bool filterable;
  final bool showInDetails;

  /// Catalog directory for brand/model/variant fields
  /// (e.g. `vehicles`, `smartphones`, `laptops`).
  final String? directory;

  /// Field this one depends on: model → brand, variant → model.
  final String? dependsOn;

  bool isVisible(Map<String, Object?> values) =>
      visibleWhen == null || visibleWhen!.isMet(values);

  bool get isNumeric => numericFieldTypes.contains(type);

  num? maxFor(DateTime now) =>
      maxCurrentYearOffset != null ? now.year + maxCurrentYearOffset! : max;

  LocalizedText? optionLabel(Object? value) {
    for (final option in options) {
      if (option.value == value) return option.label;
    }
    return null;
  }
}

/// Group of fields shown together as one wizard step.
@immutable
class FormStepSchema {
  const FormStepSchema({
    required this.id,
    required this.title,
    required this.fieldKeys,
  });

  final String id;
  final LocalizedText title;
  final List<String> fieldKeys;
}

/// Rule between two fields, e.g. floor ≤ total_floors.
@immutable
class CrossFieldRule {
  const CrossFieldRule.lessOrEqual(this.field, this.other);
  final String field;
  final String other;

  bool holds(Map<String, Object?> values) {
    final a = values[field];
    final b = values[other];
    if (a is! num || b is! num) return true;
    return a <= b;
  }
}

/// How the main price behaves for a (sub)category.
enum PriceMode {
  /// A price is required.
  required,

  /// A price may be left empty ("договорная").
  optional,

  /// Price is always zero — "Free items".
  free,

  /// No price field (jobs use salary attributes instead).
  none,
}

/// Unit a price refers to (real estate rent is per month or day).
enum PriceUnit { item, perMonth, perDay }

@immutable
class CategorySchema {
  const CategorySchema({
    required this.id,
    required this.version,
    this.fields = const [],
    this.extraSteps = const [],
    this.crossRules = const [],
    this.filterKeys,
    this.priceMode = PriceMode.required,
    this.photosMin = 0,
    this.photosMax = 10,
    this.contactMethods = const ['chat', 'phone'],
    this.categoryChildKey,
    this.presetAttributes = const {},
    this.lockedAttributes = const {},
    this.allowedOptions = const {},
    this.catalogVersion,
    this.priceUnit = PriceUnit.item,
  });

  final String id;

  /// Bump when fields change; stored on each listing for migrations.
  final int version;

  /// Category-specific fields (not title/description/price/photos/
  /// location/contact, which every listing has).
  final List<FieldSchema> fields;

  /// Optional extra wizard steps; fields not placed in one are shown in the
  /// "characteristics" step.
  final List<FormStepSchema> extraSteps;
  final List<CrossFieldRule> crossRules;

  /// Filter fields in display order. Null = every filterable field.
  final List<String>? filterKeys;
  final PriceMode priceMode;
  final int photosMin;
  final int photosMax;
  final List<String> contactMethods;

  /// Field that stores the subcategory slug (catalog `category_child`).
  final String? categoryChildKey;

  /// Values set automatically for this subcategory (e.g. listing_kind =
  /// vacancy in "Vacancies").
  final Map<String, Object> presetAttributes;

  /// Preset fields the user cannot change.
  final Set<String> lockedAttributes;

  /// Narrower option lists for this subcategory (e.g. rent-only deals).
  final Map<String, List<String>> allowedOptions;

  /// Version of the catalog the schema came from.
  final String? catalogVersion;

  /// What the price refers to when the listing doesn't say (room rent is
  /// per month).
  final PriceUnit priceUnit;

  FieldSchema? field(String key) {
    for (final f in fields) {
      if (f.key == key) return f;
    }
    return null;
  }

  /// Fields shown in the characteristics step.
  List<FieldSchema> get detailFields {
    final placed = {for (final s in extraSteps) ...s.fieldKeys};
    return fields
        .where(
          (f) =>
              !placed.contains(f.key) &&
              f.type != FieldType.locationChild &&
              f.type != FieldType.geoPoint,
        )
        .toList();
  }

  /// Kept for older call sites: same as [detailFields].
  List<FieldSchema> get basicStepFields => detailFields;

  /// Fields shown with the location (district, map point).
  List<FieldSchema> get locationFields => fields
      .where((f) => f.type == FieldType.locationChild || f.type == FieldType.geoPoint)
      .toList();

  List<FieldSchema> get filterFields {
    if (filterKeys == null) return fields.where((f) => f.filterable).toList();
    return [
      for (final key in filterKeys!)
        if (field(key) case final f? when f.filterable) f,
    ];
  }

  /// Options the user may pick for [field] in this schema.
  List<FieldOption> optionsFor(FieldSchema field) {
    final allowed = allowedOptions[field.key];
    if (allowed == null) return field.options;
    return field.options.where((o) => allowed.contains(o.value)).toList();
  }
}
