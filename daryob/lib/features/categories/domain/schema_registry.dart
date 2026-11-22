import '../../../core/utils/validators.dart';
import '../../../shared/models/category_schema.dart';
import '../../../shared/models/localized_text.dart';

/// Ids of the generic schemas kept for listings created before the catalog
/// existed (Phase 1). New listings use catalog schemas.
abstract final class SchemaIds {
  static const basic = 'generic.basic';
  static const goods = 'generic.goods';
}

/// Holds every field schema: the catalog's (one per category and
/// subcategory) plus the two legacy generic ones.
class SchemaRegistry {
  SchemaRegistry([Iterable<CategorySchema> schemas = const []]) {
    for (final s in [...legacySchemas, ...schemas]) {
      register(s);
    }
  }

  final Map<String, CategorySchema> _schemas = {};

  void register(CategorySchema schema) => _schemas[schema.id] = schema;

  /// Falls back to the basic schema so an unknown id never crashes a screen.
  CategorySchema schemaFor(String id) => _schemas[id] ?? _schemas[SchemaIds.basic]!;

  bool contains(String id) => _schemas.containsKey(id);

  Iterable<CategorySchema> get all => _schemas.values;

  /// Validates attribute values against a schema.
  /// Returns field key → [ValidationCode].
  ///
  /// [onlyKeys] limits validation to some fields (one wizard step).
  Map<String, String> validate(
    String schemaId,
    Map<String, Object?> values, {
    Set<String>? onlyKeys,
    DateTime? now,
  }) {
    final schema = schemaFor(schemaId);
    final today = now ?? DateTime.now();
    final errors = <String, String>{};
    for (final field in schema.fields) {
      if (onlyKeys != null && !onlyKeys.contains(field.key)) continue;
      if (!field.isVisible(values)) continue;
      final value = values[field.key];
      if (_isEmpty(value)) {
        if (field.required) errors[field.key] = ValidationCode.required;
        continue;
      }
      final code = _check(schema, field, value!, today);
      if (code != null) errors[field.key] = code;
    }
    for (final rule in schema.crossRules) {
      if (onlyKeys != null && !onlyKeys.contains(rule.field)) continue;
      if (errors.containsKey(rule.field)) continue;
      if (!rule.holds(values)) errors[rule.field] = ValidationCode.notAboveOther;
    }
    return errors;
  }

  static bool _isEmpty(Object? value) =>
      value == null ||
      (value is String && value.trim().isEmpty) ||
      (value is List && value.isEmpty);

  static String? _check(CategorySchema schema, FieldSchema field, Object value, DateTime now) {
    switch (field.type) {
      case FieldType.integer:
      case FieldType.number:
      case FieldType.money:
        final n = value is num ? value : num.tryParse('$value');
        if (n == null) return ValidationCode.invalidNumber;
        if (field.type == FieldType.integer && n != n.roundToDouble()) {
          return ValidationCode.invalidNumber;
        }
        final max = field.maxFor(now);
        if ((field.min != null && n < field.min!) ||
            (field.minExclusive != null && n <= field.minExclusive!) ||
            (max != null && n > max)) {
          return ValidationCode.outOfRange;
        }
        return null;
      case FieldType.singleSelect:
      case FieldType.color:
        final allowed = schema.optionsFor(field).map((o) => o.value);
        return allowed.contains(value) ? null : ValidationCode.required;
      case FieldType.multiSelect:
        final allowed = schema.optionsFor(field).map((o) => o.value).toSet();
        final list = value is List ? value : const <Object?>[];
        return list.every(allowed.contains) ? null : ValidationCode.required;
      case FieldType.boolean:
        return value is bool ? null : ValidationCode.required;
      case FieldType.tags:
        return value is List ? null : ValidationCode.required;
      case FieldType.text:
      case FieldType.multilineText:
      case FieldType.size:
      case FieldType.brand:
      case FieldType.model:
      case FieldType.variant:
      case FieldType.family:
      case FieldType.occupation:
      case FieldType.species:
      case FieldType.locationChild:
        final text = '$value'.trim();
        return text.length > 2000 ? ValidationCode.tooLong : null;
      case FieldType.geoPoint:
      case FieldType.numberRange:
        return null;
    }
  }

  /// Schemas for listings created before the catalog. Kept so old listings
  /// still display and edit.
  static const List<CategorySchema> legacySchemas = [
    CategorySchema(id: SchemaIds.basic, version: 1),
    CategorySchema(
      id: SchemaIds.goods,
      version: 1,
      fields: [
        FieldSchema(
          key: 'condition',
          type: FieldType.singleSelect,
          label: LocalizedText(ru: 'Состояние', tg: 'Ҳолат'),
          required: true,
          filterable: true,
          options: [
            FieldOption('new', LocalizedText(ru: 'Новое', tg: 'Нав')),
            FieldOption('used', LocalizedText(ru: 'Б/у', tg: 'Истифодашуда')),
          ],
        ),
      ],
    ),
  ];
}
