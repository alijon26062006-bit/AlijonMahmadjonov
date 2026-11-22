import '../../../core/utils/validators.dart';
import '../../../shared/models/category_schema.dart';
import '../../../shared/models/localized_text.dart';

/// Ids of the schemas shipped in Phase 1.
abstract final class SchemaIds {
  /// No extra fields. Used by jobs, services, real estate until their own
  /// modules are written.
  static const basic = 'generic.basic';

  /// Adds "condition: new / used" for physical goods.
  static const goods = 'generic.goods';
}

/// Holds every category schema. Future category modules call [register]
/// with their own schema (e.g. `vehicles.v1`) and point their category's
/// schema ids at it — no screen needs to change.
class SchemaRegistry {
  SchemaRegistry([Iterable<CategorySchema> schemas = const []]) {
    for (final s in [...builtInSchemas, ...schemas]) {
      register(s);
    }
  }

  final Map<String, CategorySchema> _schemas = {};

  void register(CategorySchema schema) => _schemas[schema.id] = schema;

  /// Falls back to the basic schema so an unknown id never crashes a screen.
  CategorySchema schemaFor(String id) =>
      _schemas[id] ?? _schemas[SchemaIds.basic]!;

  bool contains(String id) => _schemas.containsKey(id);

  /// Validates attribute values against a schema.
  /// Returns field key → [ValidationCode].
  ///
  /// [onlyKeys] limits validation to some fields (one wizard step).
  Map<String, String> validate(
    String schemaId,
    Map<String, Object?> values, {
    Set<String>? onlyKeys,
  }) {
    final schema = schemaFor(schemaId);
    final errors = <String, String>{};
    for (final field in schema.fields) {
      if (onlyKeys != null && !onlyKeys.contains(field.key)) continue;
      if (!field.isVisible(values)) continue;
      final value = values[field.key];
      final empty =
          value == null ||
          (value is String && value.trim().isEmpty) ||
          (value is List && value.isEmpty);
      if (empty) {
        if (field.required) errors[field.key] = ValidationCode.required;
        continue;
      }
      switch (field.type) {
        case FieldType.number:
          final n = value is num ? value : num.tryParse('$value');
          if (n == null) {
            errors[field.key] = ValidationCode.invalidNumber;
          } else if ((field.min != null && n < field.min!) ||
              (field.max != null && n > field.max!)) {
            errors[field.key] = ValidationCode.outOfRange;
          }
        case FieldType.singleSelect:
          if (field.optionLabel(value) == null) {
            errors[field.key] = ValidationCode.required;
          }
        case FieldType.multiSelect:
          final list = value is List ? value : const [];
          if (list.any((v) => field.optionLabel(v) == null)) {
            errors[field.key] = ValidationCode.required;
          }
        case FieldType.text:
        case FieldType.multilineText:
        case FieldType.boolean:
        case FieldType.numberRange:
          break;
      }
    }
    return errors;
  }

  static const List<CategorySchema> builtInSchemas = [
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
