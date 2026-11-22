import 'package:dio/dio.dart';

import '../../../core/errors/failure.dart';
import '../../../core/networking/api_client.dart';
import '../../../core/networking/page_result.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/models/listing.dart';
import '../domain/listing_draft.dart';
import '../domain/listing_query.dart';
import '../domain/listing_repository.dart';

/// REST implementation for production. The expected API contract is
/// documented in README.md ("API contract"). Authorization and ownership are
/// enforced by the server; the client only sends requests.
class ApiListingRepository implements ListingRepository {
  ApiListingRepository(this._api);

  final ApiClient _api;

  @override
  Future<PageResult<Listing>> search(ListingQuery query, {int page = 1}) async {
    final json = await _api.getJson(
      '/v1/listings',
      query: {
        if (query.text.isNotEmpty) 'q': query.text,
        if (query.categoryId != null) 'category': query.categoryId,
        if (query.regionId != null) 'region': query.regionId,
        if (query.minPrice != null) 'price_min': query.minPrice,
        if (query.maxPrice != null) 'price_max': query.maxPrice,
        if (query.onlyPromoted) 'promoted': true,
        if (query.ownerId != null) 'owner': query.ownerId,
        for (final f in query.attributeFilters.entries) ...f.value.toQuery(f.key),
        'status': query.statuses.map((s) => s.name).join(','),
        'sort': query.sort.name,
        'page': page,
        'page_size': query.pageSize,
      },
    );
    final items = (json['items'] as List? ?? const [])
        .map((e) => Listing.fromJson(Map<String, dynamic>.from(e as Map)))
        .where((l) => !query.excludeIds.contains(l.id))
        .toList();
    return PageResult(
      items: items,
      page: page,
      hasMore: json['has_more'] as bool? ?? false,
      total: (json['total'] as num?)?.toInt(),
    );
  }

  @override
  Future<Listing?> getById(String id) async {
    try {
      final json = await _api.getJson('/v1/listings/$id');
      return Listing.fromJson(
        Map<String, dynamic>.from(json['listing'] as Map),
      );
    } on NotFoundFailure {
      return null;
    }
  }

  @override
  Future<List<Listing>> byOwner(String ownerId) async {
    final json = await _api.getJson('/v1/me/listings');
    return (json['items'] as List? ?? const [])
        .map((e) => Listing.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  @override
  Future<Listing> publish(ListingDraft draft, {required String ownerId}) async {
    final body = await _body(draft);
    final json = await _api.postJson('/v1/listings', body: body);
    return Listing.fromJson(Map<String, dynamic>.from(json['listing'] as Map));
  }

  @override
  Future<Listing> update(
    String listingId,
    ListingDraft draft, {
    required String actingUserId,
  }) async {
    final body = await _body(draft);
    final json = await _api.patchJson('/v1/listings/$listingId', body: body);
    return Listing.fromJson(Map<String, dynamic>.from(json['listing'] as Map));
  }

  @override
  Future<Listing> changeStatus(
    String listingId,
    ListingStatus status, {
    required String actingUserId,
  }) async {
    final json = await _api.postJson(
      '/v1/listings/$listingId/status',
      body: {'status': status.name},
    );
    return Listing.fromJson(Map<String, dynamic>.from(json['listing'] as Map));
  }

  @override
  Future<void> delete(String listingId, {required String actingUserId}) =>
      _api.delete('/v1/listings/$listingId');

  @override
  Future<void> report(ListingReport report) async {
    await _api.postJson('/v1/reports', body: report.toJson());
  }

  @override
  Future<Listing> applyPromotion(
    String listingId,
    ListingPromotion promotion, {
    required String actingUserId,
  }) {
    // Paid promotions are activated by the server after a verified payment.
    throw const FeatureUnavailableFailure(UnavailableFeature.payments);
  }

  @override
  Future<Map<String, int>> countByCategory() async {
    final json = await _api.getJson('/v1/categories/counts');
    return (json['counts'] as Map? ?? const {}).map(
      (k, v) => MapEntry('$k', (v as num).toInt()),
    );
  }

  Future<Map<String, dynamic>> _body(ListingDraft draft) async {
    final photos = <String>[];
    for (final path in draft.photos) {
      photos.add(path.startsWith('http') ? path : await _upload(path));
    }
    return {
      'category_id': draft.categoryId,
      'title': draft.title.trim(),
      'description': draft.description.trim(),
      'price': Validators.parsePrice(draft.priceText),
      'currency': draft.currency.code,
      'is_negotiable': draft.isNegotiable,
      'attributes': draft.attributes,
      'photos': photos,
      'region_id': draft.regionId,
      'address_note': draft.addressNote.trim(),
      'contact': {
        'name': draft.contactName.trim(),
        'phone': Formatters.nationalDigits(draft.contactPhone),
        'phone_visibility': draft.phoneVisibility.name,
        'chat_enabled': draft.chatEnabled,
      },
    };
  }

  Future<String> _upload(String path) async {
    final form = FormData.fromMap({'file': await MultipartFile.fromFile(path)});
    final json = await _api.postJson('/v1/uploads', body: form);
    final url = json['url'] as String?;
    if (url == null) throw const ServerFailure();
    return url;
  }
}

/// Used in production when no API URL was configured: every call reports
/// that the backend is not connected instead of returning fake data.
class UnavailableListingRepository implements ListingRepository {
  const UnavailableListingRepository();

  static const _failure = FeatureUnavailableFailure(UnavailableFeature.backend);

  @override
  Future<PageResult<Listing>> search(ListingQuery query, {int page = 1}) =>
      Future.error(_failure);
  @override
  Future<Listing?> getById(String id) => Future.error(_failure);
  @override
  Future<List<Listing>> byOwner(String ownerId) => Future.error(_failure);
  @override
  Future<Listing> publish(ListingDraft draft, {required String ownerId}) =>
      Future.error(_failure);
  @override
  Future<Listing> update(
    String listingId,
    ListingDraft draft, {
    required String actingUserId,
  }) => Future.error(_failure);
  @override
  Future<Listing> changeStatus(
    String listingId,
    ListingStatus status, {
    required String actingUserId,
  }) => Future.error(_failure);
  @override
  Future<void> delete(String listingId, {required String actingUserId}) =>
      Future.error(_failure);
  @override
  Future<void> report(ListingReport report) => Future.error(_failure);
  @override
  Future<Listing> applyPromotion(
    String listingId,
    ListingPromotion promotion, {
    required String actingUserId,
  }) => Future.error(_failure);
  @override
  Future<Map<String, int>> countByCategory() async => const {};
}
