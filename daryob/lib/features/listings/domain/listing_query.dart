import 'package:flutter/foundation.dart';

import '../../../shared/models/listing.dart';
import 'attribute_filter.dart';

export 'attribute_filter.dart';

enum ListingSort { relevance, newest, priceAsc, priceDesc }

/// Everything a listing search can filter by. Immutable and comparable so it
/// can key providers and survive navigation.
@immutable
class ListingQuery {
  const ListingQuery({
    this.text = '',
    this.categoryId,
    this.regionId,
    this.minPrice,
    this.maxPrice,
    this.sort = ListingSort.relevance,
    this.attributeFilters = const {},
    this.onlyPromoted = false,
    this.statuses = const {ListingStatus.active},
    this.excludeIds = const {},
    this.ownerId,
    this.pageSize = 20,
  });

  final String text;

  /// Includes subcategories.
  final String? categoryId;

  /// Includes everything inside the region. Null or the country = anywhere.
  final String? regionId;
  final int? minPrice;
  final int? maxPrice;
  final ListingSort sort;

  /// Schema field key → filter (e.g. {'condition': EqualsFilter('new'),
  /// 'year': RangeFilter(min: 2015)}).
  final Map<String, AttributeFilter> attributeFilters;
  final bool onlyPromoted;
  final Set<ListingStatus> statuses;
  final Set<String> excludeIds;
  final String? ownerId;
  final int pageSize;

  bool get hasFilters =>
      categoryId != null ||
      minPrice != null ||
      maxPrice != null ||
      attributeFilters.isNotEmpty ||
      sort != ListingSort.relevance;

  int get activeFilterCount =>
      (categoryId != null ? 1 : 0) +
      (minPrice != null || maxPrice != null ? 1 : 0) +
      attributeFilters.length +
      (sort != ListingSort.relevance ? 1 : 0);

  ListingQuery copyWith({
    String? text,
    String? categoryId,
    bool clearCategory = false,
    String? regionId,
    bool clearRegion = false,
    int? minPrice,
    bool clearMinPrice = false,
    int? maxPrice,
    bool clearMaxPrice = false,
    ListingSort? sort,
    Map<String, AttributeFilter>? attributeFilters,
    bool? onlyPromoted,
    Set<String>? excludeIds,
    int? pageSize,
  }) {
    return ListingQuery(
      text: text ?? this.text,
      categoryId: clearCategory ? null : (categoryId ?? this.categoryId),
      regionId: clearRegion ? null : (regionId ?? this.regionId),
      minPrice: clearMinPrice ? null : (minPrice ?? this.minPrice),
      maxPrice: clearMaxPrice ? null : (maxPrice ?? this.maxPrice),
      sort: sort ?? this.sort,
      attributeFilters: attributeFilters ?? this.attributeFilters,
      onlyPromoted: onlyPromoted ?? this.onlyPromoted,
      statuses: statuses,
      excludeIds: excludeIds ?? this.excludeIds,
      ownerId: ownerId,
      pageSize: pageSize ?? this.pageSize,
    );
  }

  /// Resets filters but keeps the search text and region.
  ListingQuery withoutFilters() => ListingQuery(text: text, regionId: regionId);

  @override
  bool operator ==(Object other) =>
      other is ListingQuery &&
      other.text == text &&
      other.categoryId == categoryId &&
      other.regionId == regionId &&
      other.minPrice == minPrice &&
      other.maxPrice == maxPrice &&
      other.sort == sort &&
      mapEquals(other.attributeFilters, attributeFilters) &&
      other.onlyPromoted == onlyPromoted &&
      setEquals(other.statuses, statuses) &&
      setEquals(other.excludeIds, excludeIds) &&
      other.ownerId == ownerId &&
      other.pageSize == pageSize;

  @override
  int get hashCode => Object.hash(
    text,
    categoryId,
    regionId,
    minPrice,
    maxPrice,
    sort,
    Object.hashAllUnordered(
      attributeFilters.entries.map((e) => Object.hash(e.key, e.value)),
    ),
    onlyPromoted,
    Object.hashAllUnordered(statuses),
    Object.hashAllUnordered(excludeIds),
    ownerId,
    pageSize,
  );
}
