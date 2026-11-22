import '../../../shared/models/category.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/models/category_schema.dart';
import '../../../shared/models/localized_text.dart';
import '../domain/catalog.dart';
import 'catalog_labels.dart';

/// Reads `DARYOB_CATALOG_MASTER_*.json` into categories, field schemas and
/// brand/model directories.
///
/// Rules taken from the file itself:
///  * a subcategory with an empty `fields` list inherits the category's
///    `form_fields`; a non-empty list replaces them;
///  * `price_tjs`, `location_id`, `photos`, `description`,
///    `contact_method` and `category_child` are core parts of every listing
///    and are not stored as attributes;
///  * option ids are stable; labels come from [catalogOptionLabels];
///  * model variants are never generated — only imported verified records
///    become selectable configurations.
class CatalogParser {
  const CatalogParser();

  /// Catalog category id → app category id (kept from Phase 1 so existing
  /// listings stay valid).
  static String appCategoryId(String catalogId) => catalogId.replaceAll('_', '-');

  static String subcategoryId(String parentAppId, String slug) => '$parentAppId.$slug';

  static const _coreKeys = {
    'price_tjs',
    'location_id',
    'photos',
    'description',
    'contact_method',
  };

  /// Which brand directory a brand/model field uses, by category or
  /// subcategory (`<catalog category id>/<subcategory slug>`).
  static const directoryRouting = {
    'vehicles': 'vehicles',
    'vehicles/tires': null,
    'electronics': 'smartphones',
    'electronics/smartphones': 'smartphones',
    'electronics/feature_phones': 'smartphones',
    'electronics/tablets': 'smartphones',
    'electronics/wearables': 'smartphones',
    'electronics/laptops': 'laptops',
    'electronics/desktops': 'laptops',
    'electronics/components': 'laptops',
    'electronics/tvs': 'tvs',
    'electronics/home_appliances': 'appliances',
    'electronics/game_consoles': null,
    'electronics/audio': null,
    'electronics/cameras': null,
    'electronics/network': null,
    'fashion': 'clothes',
    'home_furniture': 'furniture',
    'kids': 'kids',
    'sports_hobbies': 'sports',
    'construction': 'construction',
    'business': null,
  };

  static const directoryLabels = {
    'vehicles': LocalizedText(ru: 'Марки и модели авто', tg: 'Тамғаҳо ва моделҳои мошин'),
    'smartphones': LocalizedText(ru: 'Бренды и модели телефонов', tg: 'Брендҳо ва моделҳои телефон'),
    'laptops': LocalizedText(ru: 'Ноутбуки и компьютеры', tg: 'Ноутбукҳо ва компютерҳо'),
    'tvs': LocalizedText(ru: 'Телевизоры', tg: 'Телевизорҳо'),
    'appliances': LocalizedText(ru: 'Бытовая техника', tg: 'Техникаи маишӣ'),
    'clothes': LocalizedText(ru: 'Одежда и обувь', tg: 'Либос ва пойафзол'),
    'furniture': LocalizedText(ru: 'Мебель', tg: 'Мебел'),
    'kids': LocalizedText(ru: 'Детские товары', tg: 'Молҳои кӯдакона'),
    'sports': LocalizedText(ru: 'Спорт', tg: 'Варзиш'),
    'construction': LocalizedText(ru: 'Инструменты и стройматериалы', tg: 'Асбобҳо ва масолеҳи сохтмонӣ'),
  };

  CatalogSnapshot parse(Map<String, dynamic> json) {
    final warnings = <String>[];
    final version = json['version'] as String;
    final schemaVersion = _numericVersion(version);
    final rules = (json['category_specific_rules'] as Map?)?.cast<String, dynamic>() ?? const {};

    final categories = <CategoryDefinition>[];
    final schemas = <CategorySchema>[];
    var order = 0;

    for (final raw in (json['categories'] as List).cast<Map<String, dynamic>>()) {
      final catalogId = raw['id'] as String;
      final appId = appCategoryId(catalogId);
      final name = _text(raw['name']);
      final categoryFields = (raw['form_fields'] as List).cast<Map<String, dynamic>>();
      final filterKeys = (raw['filters'] as List? ?? const []).cast<String>();

      final parentSchema = _schema(
        id: appId,
        version: schemaVersion,
        catalogVersion: version,
        rawFields: categoryFields,
        filterKeys: filterKeys,
        context: catalogId,
        directory: directoryRouting[catalogId],
        isFreeCategory: catalogId == 'free',
        subcategorySlug: null,
        rules: rules,
        warnings: warnings,
      );
      schemas.add(parentSchema);
      categories.add(CategoryDefinition(
        id: appId,
        slug: appId,
        order: ++order,
        icon: CategoryIcon.fromCatalog(raw['icon'] as String?),
        name: name,
        description: categoryDescriptions[appId] ?? const LocalizedText(ru: '', tg: ''),
        formSchemaId: parentSchema.id,
        filterSchemaId: parentSchema.id,
        attributeSchemaId: parentSchema.id,
        priceMode: parentSchema.priceMode,
        restrictionPolicyId: catalogId == 'animals_plants' ? 'wildlife' : null,
        catalogId: catalogId,
      ));

      var subOrder = 0;
      for (final sub in (raw['subcategories'] as List).cast<Map<String, dynamic>>()) {
        final slug = sub['slug'] as String;
        final id = subcategoryId(appId, slug);
        final own = (sub['fields'] as List? ?? const []).cast<Map<String, dynamic>>();
        final routeKey = '$catalogId/$slug';
        final schema = _schema(
          id: id,
          version: schemaVersion,
          catalogVersion: version,
          rawFields: own.isEmpty ? categoryFields : own,
          filterKeys: filterKeys,
          context: routeKey,
          directory: directoryRouting.containsKey(routeKey)
              ? directoryRouting[routeKey]
              : directoryRouting[catalogId],
          isFreeCategory: catalogId == 'free',
          subcategorySlug: slug,
          rules: rules,
          warnings: warnings,
        );
        schemas.add(schema);
        categories.add(CategoryDefinition(
          id: id,
          slug: id,
          parentId: appId,
          order: ++subOrder,
          icon: CategoryIcon.fromCatalog(raw['icon'] as String?),
          name: _text(sub['name']),
          description: const LocalizedText(ru: '', tg: ''),
          formSchemaId: schema.id,
          filterSchemaId: schema.id,
          attributeSchemaId: schema.id,
          priceMode: schema.priceMode,
          restrictionPolicyId: catalogId == 'animals_plants' ? 'wildlife' : null,
          catalogId: slug,
        ));
      }
    }

    return CatalogSnapshot(
      version: version,
      createdOn: json['created_on'] as String? ?? '',
      currency: json['currency'] as String? ?? 'TJS',
      languages: (json['languages'] as List? ?? const []).cast<String>(),
      limitations: (json['IMPORTANT_LIMITATIONS'] as List? ?? const []).cast<String>(),
      categories: categories,
      schemas: schemas,
      directories: _directories(json['catalogs'] as Map<String, dynamic>? ?? const {}),
      warnings: warnings,
    );
  }

  CategorySchema _schema({
    required String id,
    required int version,
    required String catalogVersion,
    required List<Map<String, dynamic>> rawFields,
    required List<String> filterKeys,
    required String context,
    required String? directory,
    required bool isFreeCategory,
    required String? subcategorySlug,
    required Map<String, dynamic> rules,
    required List<String> warnings,
  }) {
    final fields = <FieldSchema>[];
    String? categoryChildKey;
    var priceMode = isFreeCategory ? PriceMode.free : PriceMode.none;
    var photosMin = 0;
    var photosMax = 16;
    var contactMethods = const ['chat', 'phone'];

    for (final raw in rawFields) {
      final key = raw['key'] as String;
      final type = raw['type'];
      final required = raw['required'] as bool? ?? false;
      final validation = (raw['validation'] as Map?)?.cast<String, dynamic>() ?? const {};

      if (type is! String) {
        warnings.add('$context.$key: invalid type "$type" in source — field skipped');
        continue;
      }
      switch (type) {
        case 'money' when key == 'price_tjs':
          priceMode = required ? PriceMode.required : PriceMode.optional;
          continue;
        case 'media':
          photosMin = required ? (validation['min_count'] as num?)?.toInt() ?? 1 : 0;
          photosMax = (validation['max_count'] as num?)?.toInt() ?? 16;
          continue;
        case 'category_child':
          categoryChildKey = key;
          continue;
        case 'location':
          continue;
      }
      if (_coreKeys.contains(key)) {
        if (key == 'contact_method') {
          contactMethods = (raw['options'] as List? ?? const ['chat', 'phone']).cast<String>();
        }
        continue;
      }

      final fieldType = _fieldType(type);
      if (fieldType == null) {
        warnings.add('$context.$key: unknown type "$type" — field skipped');
        continue;
      }
      final showIf = raw['show_if'] as Map<String, dynamic>?;
      fields.add(FieldSchema(
        key: key,
        type: fieldType,
        label: _text(raw['label']),
        required: required,
        filterable: raw['filterable'] as bool? ?? false,
        options: switch (fieldType) {
          FieldType.color => catalogColorOptions,
          _ => _options(key, raw['options'] as List?, context),
        },
        min: validation['min'] as num?,
        max: validation['max'] as num?,
        minExclusive: validation['min_exclusive'] as num?,
        maxCurrentYearOffset: _dynamicMax(validation['max_dynamic'] as String?),
        unit: raw['unit'] as String?,
        visibleWhen: showIf == null ? null : _condition(showIf),
        directory: directoryFieldTypes.contains(fieldType) &&
                fieldType != FieldType.occupation &&
                fieldType != FieldType.species
            ? directory
            : null,
        dependsOn: switch (fieldType) {
          FieldType.model => showIf?['field'] as String? ?? _brandKey(rawFields),
          FieldType.variant => _modelKey(rawFields),
          _ => null,
        },
      ));
    }

    final keys = {for (final f in fields) f.key};
    var priceUnit = PriceUnit.item;
    final presets = <String, Object>{};
    final locked = <String>{};
    final allowed = <String, List<String>>{};

    if (subcategorySlug != null) {
      // A subcategory that names an option of a select field implies it
      // (e.g. "Vacancies" → listing_kind = vacancy, "Remote" → schedule =
      // remote). Taken from the data, nothing guessed.
      for (final f in fields) {
        if (f.optionLabel(subcategorySlug) == null) continue;
        if (f.type == FieldType.singleSelect) {
          presets[f.key] = subcategorySlug;
          locked.add(f.key);
        } else if (f.type == FieldType.multiSelect) {
          presets[f.key] = [subcategorySlug];
        }
      }
      // Real estate: rent subcategories are priced per month (catalog
      // `category_specific_rules.real_estate.transaction_forms`).
      final forms = (rules['real_estate'] as Map?)?['transaction_forms'] as Map?;
      final form = forms?[subcategorySlug] as Map?;
      final perMonth = (form?['price_unit'] as String? ?? '').contains('per_month');
      if (perMonth) priceUnit = PriceUnit.perMonth;
      if (form != null && keys.contains('transaction_type')) {
        if (perMonth) {
          allowed['transaction_type'] = const ['rent_long', 'rent_short'];
        } else {
          presets['transaction_type'] = 'sale';
          locked.add('transaction_type');
        }
      }
    }

    return CategorySchema(
      id: id,
      version: version,
      catalogVersion: catalogVersion,
      fields: fields,
      filterKeys: [for (final k in filterKeys) if (keys.contains(k)) k],
      crossRules: [
        if (keys.contains('floor') && keys.contains('total_floors'))
          const CrossFieldRule.lessOrEqual('floor', 'total_floors'),
      ],
      priceMode: priceMode,
      photosMin: photosMin,
      photosMax: photosMax.clamp(1, ListingLimits.photosMax),
      contactMethods: contactMethods,
      categoryChildKey: categoryChildKey,
      presetAttributes: presets,
      lockedAttributes: locked,
      allowedOptions: allowed,
      priceUnit: priceUnit,
    );
  }

  static String? _brandKey(List<Map<String, dynamic>> raw) {
    for (final f in raw) {
      if (f['type'] == 'catalog_brand') return f['key'] as String;
    }
    return null;
  }

  static String? _modelKey(List<Map<String, dynamic>> raw) {
    for (final f in raw) {
      if (f['type'] == 'catalog_model') return f['key'] as String;
    }
    return null;
  }

  static FieldType? _fieldType(String type) => switch (type) {
    'text' => FieldType.text,
    'multiline' => FieldType.multilineText,
    'integer' => FieldType.integer,
    'decimal' => FieldType.number,
    'money' => FieldType.money,
    'select' => FieldType.singleSelect,
    'multi_select' => FieldType.multiSelect,
    'boolean' => FieldType.boolean,
    'color' => FieldType.color,
    'size' => FieldType.size,
    'tags' => FieldType.tags,
    'catalog_brand' => FieldType.brand,
    'catalog_model' => FieldType.model,
    'catalog_variant' => FieldType.variant,
    'catalog_family' => FieldType.family,
    'catalog_occupation' => FieldType.occupation,
    'catalog_species' => FieldType.species,
    'location_child' => FieldType.locationChild,
    'geopoint' => FieldType.geoPoint,
    _ => null,
  };

  static FieldCondition _condition(Map<String, dynamic> raw) {
    final field = raw['field'] as String;
    if (raw['operator'] == 'not_empty') {
      return FieldCondition(fieldKey: field, op: ConditionOperator.notEmpty);
    }
    if (raw.containsKey('equals')) {
      return FieldCondition(fieldKey: field, values: [raw['equals'] as Object]);
    }
    if (raw.containsKey('in')) {
      return FieldCondition(
        fieldKey: field,
        op: ConditionOperator.inList,
        values: (raw['in'] as List).cast<Object>(),
      );
    }
    if (raw.containsKey('not_in')) {
      return FieldCondition(
        fieldKey: field,
        op: ConditionOperator.notInList,
        values: (raw['not_in'] as List).cast<Object>(),
      );
    }
    throw FormatException('Unsupported show_if: $raw');
  }

  static int? _dynamicMax(String? expr) {
    if (expr == null) return null;
    final match = RegExp(r'^current_year([+-]\d+)?$').firstMatch(expr.replaceAll(' ', ''));
    if (match == null) throw FormatException('Unsupported max_dynamic: $expr');
    return int.parse(match.group(1) ?? '0');
  }

  List<FieldOption> _options(String key, List? raw, String context) {
    if (raw == null) return const [];
    final labels = catalogOptionLabels[key];
    return [
      for (final value in raw.cast<String>())
        FieldOption(
          value,
          labels?[value] ??
              (throw StateError(
                'No ru/tg label for option "$value" of field "$key" ($context). '
                'Add it to catalog_labels.dart.',
              )),
        ),
    ];
  }

  Map<String, CatalogDirectory> _directories(Map<String, dynamic> catalogs) {
    final result = <String, CatalogDirectory>{};

    CatalogDirectory build(String id, String status, List raw) {
      final brands = <CatalogBrand>[];
      final seen = <String>{};
      for (final b in raw.cast<Map<String, dynamic>>()) {
        final name = (b['name'] as String).trim();
        final brandId = catalogSlug(name);
        if (!seen.add(brandId)) continue; // duplicate normalisation
        final modelSeen = <String>{};
        brands.add(CatalogBrand(
          id: brandId,
          name: name,
          modelStatus: b['model_status'] as String? ?? 'seed',
          models: [
            for (final m in (b['models'] as List? ?? const []).cast<Map<String, dynamic>>())
              if (modelSeen.add(catalogSlug(m['name'] as String)))
                CatalogModel(
                  id: '$brandId/${catalogSlug(m['name'] as String)}',
                  name: (m['name'] as String).trim(),
                  verification: m['verification'] as String? ?? 'unverified',
                ),
          ],
        ));
      }
      brands.sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
      return CatalogDirectory(
        id: id,
        label: directoryLabels[id] ?? LocalizedText(ru: id, tg: id),
        dataStatus: status,
        brands: brands,
      );
    }

    final vehicles = catalogs['vehicle_makes_models'] as Map<String, dynamic>?;
    if (vehicles != null) {
      result['vehicles'] = build(
        'vehicles',
        vehicles['data_status'] as String? ?? '',
        vehicles['manufacturers'] as List,
      );
    }
    final phones = catalogs['smartphone_brands_models'] as Map<String, dynamic>?;
    if (phones != null) {
      result['smartphones'] = build(
        'smartphones',
        phones['data_status'] as String? ?? '',
        phones['manufacturers'] as List,
      );
    }
    final other = catalogs['other_brand_directories'] as Map<String, dynamic>?;
    if (other != null) {
      final status = other['data_status'] as String? ?? '';
      (other['directories'] as Map<String, dynamic>).forEach((id, list) {
        result[id] = build(id, status, list as List);
      });
    }
    return result;
  }

  static LocalizedText _text(Object? raw) {
    final map = (raw as Map).cast<String, dynamic>();
    return LocalizedText(ru: map['ru'] as String, tg: map['tg'] as String? ?? map['ru'] as String);
  }

  /// "0.1.0-research-starter" → 100 (major·10000 + minor·100 + patch).
  static int _numericVersion(String version) {
    final parts = RegExp(r'\d+').allMatches(version).take(3).map((m) => int.parse(m[0]!)).toList();
    while (parts.length < 3) {
      parts.add(0);
    }
    return parts[0] * 10000 + parts[1] * 100 + parts[2];
  }
}
