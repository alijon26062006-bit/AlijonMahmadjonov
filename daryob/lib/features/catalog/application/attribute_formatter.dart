import '../../../core/utils/formatters.dart';
import '../../../shared/models/category_schema.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/models/money.dart';
import '../../categories/domain/region_directory.dart';
import '../data/catalog_labels.dart';
import '../domain/catalog.dart';

/// Turns stored attribute values into text for people, using the same
/// schema and directories the form used — so the wizard preview, the
/// listing page and cards always agree.
class AttributeFormatter {
  AttributeFormatter({
    required this.catalog,
    required this.languageCode,
    this.regions,
    required this.yes,
    required this.no,
  });

  final CatalogSnapshot catalog;
  final String languageCode;
  final RegionDirectory? regions;
  final String yes;
  final String no;

  String _t(LocalizedText text) => text.byCode(languageCode);

  String unit(String? code) {
    if (code == null) return '';
    final label = catalogUnitLabels[code];
    return label == null ? code : _t(label);
  }

  String number(num value) {
    if (value == value.roundToDouble()) return Formatters.groupDigits(value.toInt());
    return value.toString().replaceAll('.', ',');
  }

  /// Name of a brand/model/variant value: the directory name when the id is
  /// known, otherwise the seller's own text.
  String directoryValue(FieldSchema field, Object value) {
    final text = '$value';
    final directory = catalog.directory(field.directory);
    if (directory == null) return text;
    switch (field.type) {
      case FieldType.brand:
        return directory.brand(text)?.name ?? text;
      case FieldType.model:
        final model = directory.model(text);
        if (model == null) return text;
        return model.name;
      default:
        return text;
    }
  }

  /// Display text for one attribute, or null when there is nothing to show.
  String? format(CategorySchema schema, FieldSchema field, Object? value) {
    if (value == null) return null;
    if (value is String && value.trim().isEmpty) return null;
    if (value is List && value.isEmpty) return null;

    String withUnit(String s) {
      final u = field.unit == null || field.unit == 'TJS' ? '' : unit(field.unit);
      if (u.isEmpty) return s;
      return u == '%' || u == '″' ? '$s$u' : '$s $u';
    }

    switch (field.type) {
      case FieldType.singleSelect:
      case FieldType.color:
        final label = field.optionLabel(value);
        return label == null ? '$value' : _t(label);
      case FieldType.multiSelect:
        final list = value is List ? value : [value];
        return list.map((v) => field.optionLabel(v) == null ? '$v' : _t(field.optionLabel(v)!)).join(', ');
      case FieldType.boolean:
        return value == true ? yes : no;
      case FieldType.integer:
      case FieldType.number:
        final n = value is num ? value : num.tryParse('$value');
        return n == null ? '$value' : withUnit(number(n));
      case FieldType.money:
        final n = value is num ? value : num.tryParse('$value');
        return n == null ? '$value' : Formatters.price(n.round(), Currency.tjs, languageCode);
      case FieldType.tags:
        return (value is List ? value : [value]).join(', ');
      case FieldType.brand:
      case FieldType.model:
      case FieldType.variant:
      case FieldType.family:
      case FieldType.occupation:
      case FieldType.species:
        return withUnit(directoryValue(field, value));
      case FieldType.locationChild:
        final region = regions?.byId('$value');
        return region == null ? '$value' : region.name.byCode(languageCode);
      case FieldType.size:
      case FieldType.text:
      case FieldType.multilineText:
        return '$value';
      case FieldType.geoPoint:
      case FieldType.numberRange:
        return null;
    }
  }

  /// (label, value) pairs for the characteristics table, in schema order.
  List<(String, String)> characteristics(CategorySchema schema, Map<String, Object?> attributes) {
    return [
      for (final field in schema.fields)
        if (field.showInDetails && field.isVisible(attributes))
          if (format(schema, field, attributes[field.key]) case final text?)
            (_t(field.label), text),
    ];
  }

  /// "Toyota Camry, 2015" — offered as a title once brand/model are chosen.
  String? suggestTitle(CategorySchema schema, Map<String, Object?> attributes) {
    final parts = <String>[];
    for (final field in schema.fields) {
      if (field.type != FieldType.brand && field.type != FieldType.model) continue;
      final v = attributes[field.key];
      if (v == null || '$v'.trim().isEmpty) continue;
      parts.add(directoryValue(field, v));
    }
    if (parts.isEmpty) return null;
    final year = attributes['year'];
    final storage = attributes['storage_gb'];
    var title = parts.join(' ');
    if (storage != null) title += ' ${number(storage is num ? storage : num.tryParse('$storage') ?? 0)} ${unit('GB')}';
    if (year != null) title += ', $year';
    return title;
  }

  /// Rent is priced per month or per day (catalog real-estate rules).
  PriceUnit priceUnit(Map<String, Object?> attributes, {CategorySchema? schema}) {
    final deal = attributes['transaction_type'];
    if (deal == null) return schema?.priceUnit ?? PriceUnit.item;
    if (deal != 'rent_long' && deal != 'rent_short') return PriceUnit.item;
    return attributes['rent_period'] == 'day' || (deal == 'rent_short' && attributes['rent_period'] == null)
        ? PriceUnit.perDay
        : PriceUnit.perMonth;
  }

  /// Salary text for jobs ("3 000 – 5 000 сомони в месяц").
  String? salary(Map<String, Object?> attributes) {
    final min = attributes['salary_min_tjs'];
    final max = attributes['salary_max_tjs'];
    if (min is! num && max is! num) return null;
    String fmt(Object v) => Formatters.groupDigits((v as num).round());
    final currency = unit('TJS');
    final range = switch ((min, max)) {
      (num a, num b) => '${fmt(a)} – ${fmt(b)} $currency',
      (num a, _) => '${languageCode == 'tg' ? 'аз' : 'от'} ${fmt(a)} $currency',
      (_, num b) => '${languageCode == 'tg' ? 'то' : 'до'} ${fmt(b)} $currency',
      _ => '',
    };
    final period = attributes['salary_period'];
    final periodLabel = period == null ? null : catalogOptionLabels['salary_period']?[period];
    return periodLabel == null ? range : '$range · ${_t(periodLabel).toLowerCase()}';
  }
}
