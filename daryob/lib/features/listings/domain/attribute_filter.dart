import 'package:flutter/foundation.dart';

/// One structured filter on a listing attribute. Built from the same
/// catalog field schema the form uses, so search matches what sellers
/// entered.
@immutable
sealed class AttributeFilter {
  const AttributeFilter();

  bool matches(Object? value);

  /// Query parameters for the API (`attr[key]=…`).
  Map<String, String> toQuery(String key);

  int get weight => 1;
}

/// Exact value (select, brand, model).
class EqualsFilter extends AttributeFilter {
  const EqualsFilter(this.value);
  final String value;

  @override
  bool matches(Object? v) => v is List ? v.map((e) => '$e').contains(value) : '$v' == value;

  @override
  Map<String, String> toQuery(String key) => {'attr[$key]': value};

  @override
  bool operator ==(Object other) => other is EqualsFilter && other.value == value;

  @override
  int get hashCode => value.hashCode;
}

/// Any of several values (multi-select chips).
class AnyOfFilter extends AttributeFilter {
  const AnyOfFilter(this.values);
  final Set<String> values;

  @override
  bool matches(Object? v) =>
      v is List ? v.any((e) => values.contains('$e')) : values.contains('$v');

  @override
  Map<String, String> toQuery(String key) => {'attr[$key][in]': (values.toList()..sort()).join(',')};

  @override
  bool operator ==(Object other) => other is AnyOfFilter && setEquals(other.values, values);

  @override
  int get hashCode => Object.hashAllUnordered(values);
}

/// Numeric range, either end optional (year, mileage, area, salary).
class RangeFilter extends AttributeFilter {
  const RangeFilter({this.min, this.max});
  final num? min;
  final num? max;

  @override
  bool matches(Object? v) {
    final n = v is num ? v : num.tryParse('$v');
    if (n == null) return false;
    if (min != null && n < min!) return false;
    if (max != null && n > max!) return false;
    return true;
  }

  @override
  Map<String, String> toQuery(String key) => {
    if (min != null) 'attr[$key][min]': '$min',
    if (max != null) 'attr[$key][max]': '$max',
  };

  @override
  bool operator ==(Object other) => other is RangeFilter && other.min == min && other.max == max;

  @override
  int get hashCode => Object.hash(min, max);
}

/// Yes/no fields: only listings where the value is true.
class IsTrueFilter extends AttributeFilter {
  const IsTrueFilter();

  @override
  bool matches(Object? v) => v == true;

  @override
  Map<String, String> toQuery(String key) => {'attr[$key]': 'true'};

  @override
  bool operator ==(Object other) => other is IsTrueFilter;

  @override
  int get hashCode => 1;
}

/// Text contains (employer, variety, grade).
class ContainsFilter extends AttributeFilter {
  const ContainsFilter(this.text);
  final String text;

  @override
  bool matches(Object? v) => v != null && '$v'.toLowerCase().contains(text.toLowerCase());

  @override
  Map<String, String> toQuery(String key) => {'attr[$key][contains]': text};

  @override
  bool operator ==(Object other) => other is ContainsFilter && other.text == text;

  @override
  int get hashCode => text.hashCode;
}
