import 'package:flutter/foundation.dart';

import 'localized_text.dart';

/// Kinds of input a category schema can declare. The listing wizard,
/// filters and the detail screen all render from these, so adding a category
/// module means adding a schema, not new screens.
enum FieldType {
  text,
  multilineText,
  number,
  singleSelect,
  multiSelect,
  boolean,

  /// Two numbers (from–to). Used in filters, e.g. year or area.
  numberRange,
}

@immutable
class FieldOption {
  const FieldOption(this.value, this.label);
  final String value;
  final LocalizedText label;
}

/// Show a field only when another field has a given value
/// (e.g. "mileage" only when condition = used).
@immutable
class FieldCondition {
  const FieldCondition({required this.fieldKey, required this.equals});
  final String fieldKey;
  final Object equals;

  bool isMet(Map<String, Object?> values) {
    final current = values[fieldKey];
    if (current is List) return current.contains(equals);
    return current == equals;
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
    this.unit,
    this.visibleWhen,
    this.filterable = false,
    this.showInDetails = true,
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
  final LocalizedText? unit;
  final FieldCondition? visibleWhen;
  final bool filterable;
  final bool showInDetails;

  bool isVisible(Map<String, Object?> values) =>
      visibleWhen == null || visibleWhen!.isMet(values);

  LocalizedText? optionLabel(Object? value) {
    for (final option in options) {
      if (option.value == value) return option.label;
    }
    return null;
  }
}

/// A group of fields shown together as one wizard step.
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

@immutable
class CategorySchema {
  const CategorySchema({
    required this.id,
    required this.version,
    this.fields = const [],
    this.extraSteps = const [],
  });

  final String id;

  /// Bump when fields change; stored on each listing for migrations.
  final int version;
  final List<FieldSchema> fields;

  /// Category-specific wizard steps inserted after "Basic information".
  /// Fields not placed in any extra step are shown in the basic step.
  final List<FormStepSchema> extraSteps;

  FieldSchema? field(String key) {
    for (final f in fields) {
      if (f.key == key) return f;
    }
    return null;
  }

  List<FieldSchema> get basicStepFields {
    final placed = {for (final s in extraSteps) ...s.fieldKeys};
    return fields.where((f) => !placed.contains(f.key)).toList();
  }

  List<FieldSchema> get filterFields =>
      fields.where((f) => f.filterable).toList();
}
