import '../../../core/errors/failure.dart';
import '../../../core/networking/page_result.dart';
import '../../../core/storage/local_database.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/utils/ids.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/models/category.dart';
import '../../../shared/models/listing.dart';
import '../../categories/domain/category_registry.dart';
import '../../categories/domain/region_directory.dart';
import '../../categories/domain/schema_registry.dart';
import '../domain/draft_validator.dart';
import '../domain/listing_draft.dart';
import '../domain/listing_query.dart';
import '../domain/listing_repository.dart';

/// Listings stored on the device. Used in development mode; every record it
/// creates is flagged `isLocalOnly`.
class LocalListingRepository implements ListingRepository {
  LocalListingRepository({
    required LocalDatabase database,
    required CategoryRegistry categories,
    required SchemaRegistry schemas,
    required this._regions,
    required this._clock,
  }) : _listings = database.collection(Collections.listings),
       _reports = database.collection(Collections.reports),
       _categories = categories,
       _schemas = schemas,
       _validator = DraftValidator(categories, schemas);

  final JsonCollection _listings;
  final JsonCollection _reports;
  final CategoryRegistry _categories;
  final SchemaRegistry _schemas;
  final RegionDirectory _regions;
  final DateTime Function() _clock;
  final DraftValidator _validator;

  Iterable<Listing> get _all => _listings.values().map(Listing.fromJson);

  @override
  Future<PageResult<Listing>> search(ListingQuery query, {int page = 1}) async {
    final now = _clock();
    final text = query.text.trim().toLowerCase();
    final categoryIds = query.categoryId == null
        ? null
        : _categories.subtreeIds(query.categoryId!);

    final matches = _all.where((l) {
      if (!query.statuses.contains(l.status)) return false;
      if (query.ownerId != null && l.ownerId != query.ownerId) return false;
      if (query.excludeIds.contains(l.id)) return false;
      if (categoryIds != null && !categoryIds.contains(l.categoryId)) {
        return false;
      }
      if (query.regionId != null &&
          !_regions.contains(query.regionId!, l.regionId)) {
        return false;
      }
      if (query.minPrice != null &&
          (l.price == null || l.price! < query.minPrice!)) {
        return false;
      }
      if (query.maxPrice != null &&
          (l.price == null || l.price! > query.maxPrice!)) {
        return false;
      }
      for (final f in query.attributeFilters.entries) {
        if (!f.value.matches(l.attributes[f.key])) return false;
      }
      if (query.onlyPromoted && !l.isPromotedAt(now)) return false;
      if (text.isNotEmpty &&
          !l.title.toLowerCase().contains(text) &&
          !l.description.toLowerCase().contains(text)) {
        return false;
      }
      return true;
    }).toList();

    int promotionRank(Listing l) {
      if (!l.isPromotedAt(now)) return 0;
      return switch (l.promotion!.type) {
        PromotionType.vipPlus => 4,
        PromotionType.vip => 3,
        PromotionType.top => 2,
        PromotionType.boost => 1,
        _ => 0,
      };
    }

    int byNewest(Listing a, Listing b) => b.sortDate.compareTo(a.sortDate);

    switch (query.sort) {
      case ListingSort.relevance:
        matches.sort((a, b) {
          if (text.isNotEmpty) {
            final at = a.title.toLowerCase().contains(text) ? 1 : 0;
            final bt = b.title.toLowerCase().contains(text) ? 1 : 0;
            if (at != bt) return bt - at;
          }
          final p = promotionRank(b) - promotionRank(a);
          return p != 0 ? p : byNewest(a, b);
        });
      case ListingSort.newest:
        matches.sort(byNewest);
      case ListingSort.priceAsc:
        matches.sort((a, b) {
          if (a.price == null) return b.price == null ? byNewest(a, b) : 1;
          if (b.price == null) return -1;
          return a.price!.compareTo(b.price!);
        });
      case ListingSort.priceDesc:
        matches.sort((a, b) {
          if (a.price == null) return b.price == null ? byNewest(a, b) : 1;
          if (b.price == null) return -1;
          return b.price!.compareTo(a.price!);
        });
    }

    final start = (page - 1) * query.pageSize;
    final items = start >= matches.length
        ? <Listing>[]
        : matches.sublist(
            start,
            (start + query.pageSize).clamp(0, matches.length),
          );
    return PageResult(
      items: items,
      page: page,
      hasMore: start + query.pageSize < matches.length,
      total: matches.length,
    );
  }

  @override
  Future<Listing?> getById(String id) async {
    final json = _listings.get(id);
    return json == null ? null : Listing.fromJson(json);
  }

  @override
  Future<List<Listing>> byOwner(String ownerId) async {
    return _all.where((l) => l.ownerId == ownerId).toList()
      ..sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
  }

  @override
  Future<Listing> publish(ListingDraft draft, {required String ownerId}) async {
    final errors = _validator.validateAll(draft);
    if (errors.isNotEmpty) throw ValidationFailure(errors);

    final now = _clock();
    final category = _categories.byId(draft.categoryId)!;
    final schema = _schemas.schemaFor(category.formSchemaId);
    final listing = Listing(
      id: newId('l_'),
      ownerId: ownerId,
      categoryId: category.id,
      title: draft.title.trim(),
      description: draft.description.trim(),
      price: _price(draft, category),
      currency: draft.currency,
      isNegotiable: draft.isNegotiable,
      attributes: _visibleAttributes(draft, category),
      photos: List.of(draft.photos),
      regionId: draft.regionId!,
      addressNote: draft.addressNote.trim().isEmpty
          ? null
          : draft.addressNote.trim(),
      contact: _contact(draft),
      status: ListingStatus.active,
      createdAt: now,
      updatedAt: now,
      publishedAt: now,
      schemaId: schema.id,
      schemaVersion: schema.version,
      isLocalOnly: true,
    );
    await _listings.put(listing.id, listing.toJson());
    return listing;
  }

  @override
  Future<Listing> update(
    String listingId,
    ListingDraft draft, {
    required String actingUserId,
  }) async {
    final existing = await _owned(listingId, actingUserId);
    final errors = _validator.validateAll(draft);
    if (errors.isNotEmpty) throw ValidationFailure(errors);

    final category = _categories.byId(draft.categoryId)!;
    final schema = _schemas.schemaFor(category.formSchemaId);
    final price = _price(draft, category);
    final updated = existing.copyWith(
      categoryId: category.id,
      title: draft.title.trim(),
      description: draft.description.trim(),
      price: price,
      clearPrice: price == null,
      currency: draft.currency,
      isNegotiable: draft.isNegotiable,
      attributes: _visibleAttributes(draft, category),
      photos: List.of(draft.photos),
      regionId: draft.regionId,
      addressNote: draft.addressNote.trim(),
      contact: _contact(draft),
      updatedAt: _clock(),
      schemaId: schema.id,
      schemaVersion: schema.version,
    );
    await _listings.put(updated.id, updated.toJson());
    return updated;
  }

  @override
  Future<Listing> changeStatus(
    String listingId,
    ListingStatus status, {
    required String actingUserId,
  }) async {
    final existing = await _owned(listingId, actingUserId);
    final now = _clock();
    final updated = existing.copyWith(
      status: status,
      updatedAt: now,
      publishedAt: status == ListingStatus.active ? now : null,
    );
    await _listings.put(updated.id, updated.toJson());
    return updated;
  }

  @override
  Future<void> delete(String listingId, {required String actingUserId}) async {
    await _owned(listingId, actingUserId);
    await _listings.delete(listingId);
  }

  @override
  Future<void> report(ListingReport report) async {
    await _reports.put(report.id, report.toJson());
  }

  @override
  Future<Listing> applyPromotion(
    String listingId,
    ListingPromotion promotion, {
    required String actingUserId,
  }) async {
    final existing = await _owned(listingId, actingUserId);
    final updated = existing.copyWith(
      promotion: promotion,
      updatedAt: _clock(),
    );
    await _listings.put(updated.id, updated.toJson());
    return updated;
  }

  @override
  Future<Map<String, int>> countByCategory() async {
    final counts = <String, int>{};
    for (final l in _all.where((l) => l.status == ListingStatus.active)) {
      final top = _categories.pathTo(l.categoryId).firstOrNull;
      if (top != null) counts[top.id] = (counts[top.id] ?? 0) + 1;
    }
    return counts;
  }

  /// Stores a listing as-is. Used for seeding demo data.
  Future<void> putRaw(Listing listing) =>
      _listings.put(listing.id, listing.toJson());

  Future<Listing> _owned(String id, String actingUserId) async {
    final existing = await getById(id);
    if (existing == null) throw const NotFoundFailure();
    if (existing.ownerId != actingUserId) throw const ForbiddenFailure();
    return existing;
  }

  int? _price(ListingDraft draft, CategoryDefinition category) {
    final mode = _schemas.schemaFor(category.formSchemaId).priceMode;
    if (mode == PriceMode.free) return 0;
    if (mode == PriceMode.none) return null;
    return Validators.parsePrice(draft.priceText);
  }

  Map<String, Object?> _visibleAttributes(
    ListingDraft draft,
    CategoryDefinition category,
  ) => _validator.cleanAttributes(draft);

  ListingContact _contact(ListingDraft draft) => ListingContact(
    name: draft.contactName.trim(),
    phone: Formatters.nationalDigits(draft.contactPhone),
    phoneVisibility: draft.phoneVisibility,
    chatEnabled: draft.chatEnabled,
  );
}
