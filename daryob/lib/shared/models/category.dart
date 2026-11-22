import 'package:flutter/foundation.dart';

import 'category_schema.dart';
import 'localized_text.dart';

export 'category_schema.dart' show PriceMode;

/// Icon identifiers. Mapped to actual glyphs in the UI layer so the data
/// model stays free of Flutter widgets and can come from the server.
enum CategoryIcon {
  house,
  car,
  smartphone,
  briefcase,
  shirt,
  sofa,
  wrench,
  hardHat,
  baby,
  building,
  dumbbell,
  sprout,
  pawPrint,
  gift,
  generic;

  /// Icon names used in the catalog file (Lucide-style names).
  static CategoryIcon fromCatalog(String? name) => switch (name) {
    'car-front' || 'car' => car,
    'house' => house,
    'smartphone' => smartphone,
    'briefcase' => briefcase,
    'shirt' => shirt,
    'sofa' => sofa,
    'wrench' => wrench,
    'hard-hat' => hardHat,
    'baby' => baby,
    'building' => building,
    'dumbbell' => dumbbell,
    'sprout' => sprout,
    'paw-print' => pawPrint,
    'gift' => gift,
    _ => generic,
  };

  static CategoryIcon fromName(String? name) => CategoryIcon.values.firstWhere(
    (i) => i.name == name,
    orElse: () => generic,
  );
}

@immutable
class CategoryDefinition {
  const CategoryDefinition({
    required this.id,
    required this.slug,
    required this.name,
    required this.description,
    required this.icon,
    required this.order,
    this.parentId,
    this.imageAsset,
    this.isActive = true,
    this.listingCount,
    this.attributeSchemaId = 'generic.basic',
    this.filterSchemaId = 'generic.basic',
    this.formSchemaId = 'generic.basic',
    this.priceMode = PriceMode.required,
    this.restrictionPolicyId,
    this.catalogId,
  });

  final String id;

  /// Stable identifier used in URLs and API calls. Never changes once shipped.
  final String slug;
  final String? parentId;
  final LocalizedText name;
  final LocalizedText description;
  final CategoryIcon icon;
  final String? imageAsset;
  final int order;
  final bool isActive;

  /// Known number of listings, or null when the source can't count them.
  final int? listingCount;

  /// References into the schema registry. Future category modules register a
  /// schema under a new id and point these at it.
  final String attributeSchemaId;
  final String filterSchemaId;
  final String formSchemaId;

  final PriceMode priceMode;

  /// Optional policy applied before publication (e.g. wildlife trade rules).
  final String? restrictionPolicyId;

  /// Id in the catalog file (`real_estate`, or the subcategory slug such as
  /// `apartment_rent`).
  final String? catalogId;

  bool get isTopLevel => parentId == null;

  CategoryDefinition copyWith({int? listingCount, bool? isActive}) {
    return CategoryDefinition(
      id: id,
      slug: slug,
      parentId: parentId,
      name: name,
      description: description,
      icon: icon,
      imageAsset: imageAsset,
      order: order,
      isActive: isActive ?? this.isActive,
      listingCount: listingCount ?? this.listingCount,
      attributeSchemaId: attributeSchemaId,
      filterSchemaId: filterSchemaId,
      formSchemaId: formSchemaId,
      priceMode: priceMode,
      restrictionPolicyId: restrictionPolicyId,
      catalogId: catalogId,
    );
  }
}
