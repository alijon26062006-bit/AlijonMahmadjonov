import 'package:image_picker/image_picker.dart' show XFile;
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/backend/backend.dart';
import '../../../core/errors/failure.dart';
import '../../../core/networking/page_result.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/models/category_schema.dart';
import '../../../shared/models/listing.dart';
import '../../categories/data/tajikistan_regions.dart';
import '../../categories/domain/category_registry.dart';
import '../../categories/domain/region_directory.dart';
import '../../categories/domain/schema_registry.dart';
import '../domain/draft_validator.dart';
import '../domain/listing_draft.dart';
import '../domain/listing_query.dart';
import '../domain/listing_repository.dart';

/// Listings on the DARYOB server.
///
/// The app validates a draft with the same catalog schema the form uses;
/// the database then enforces what the client cannot be trusted with:
/// ownership, paid promotion, the view counter and moderation status.
class ServerListingRepository implements ListingRepository {
  ServerListingRepository({
    required this._client,
    required this._categories,
    required this._schemas,
    required this._regions,
    required this._validator,
  });

  final SupabaseClient _client;
  final CategoryRegistry _categories;
  final SchemaRegistry _schemas;
  final RegionDirectory _regions;
  final DraftValidator _validator;

  static const photoBucket = 'listing-photos';

  String? get _me => _client.auth.currentUser?.id;

  @override
  Future<PageResult<Listing>> search(ListingQuery query, {int page = 1}) {
    return backendCall(() async {
      final regionId = query.regionId;
      final result = await _client.rpc<dynamic>(
        'search_listings',
        params: {
          'p_text': query.text.trim(),
          'p_category': query.categoryId,
          'p_regions': regionId == null || regionId == RegionIds.country
              ? null
              : _regions.subtreeIds(regionId).toList(),
          'p_min_price': query.minPrice,
          'p_max_price': query.maxPrice,
          'p_sort': query.sort.name,
          'p_filters': [
            for (final f in query.attributeFilters.entries) filterJson(f.key, f.value),
          ],
          'p_only_promoted': query.onlyPromoted,
          'p_statuses': query.statuses.map((s) => s.name).toList(),
          'p_exclude': query.excludeIds.where(isServerId).toList(),
          'p_owner': isServerId(query.ownerId) ? query.ownerId : null,
          'p_page': page,
          'p_page_size': query.pageSize,
        },
      );
      final map = Map<String, dynamic>.from(result as Map);
      final items = [
        for (final row in map['items'] as List? ?? const <Object?>[])
          fromRow(Map<String, dynamic>.from(row as Map)),
      ];
      final total = (map['total'] as num?)?.toInt() ?? items.length;
      return PageResult(
        items: items,
        page: page,
        hasMore: page * query.pageSize < total,
        total: total,
      );
    });
  }

  @override
  Future<Listing?> getById(String id) {
    if (!isServerId(id)) return Future.value();
    return backendCall(() async {
      final row = await _client.from('listings').select().eq('id', id).maybeSingle();
      if (row == null) return null;
      final listing = fromRow(row);
      if (listing.ownerId != _me) return listing;
      final private = await _client
          .from('listing_private')
          .select('phone')
          .eq('listing_id', id)
          .maybeSingle();
      return _withPrivatePhone(listing, private?['phone'] as String?);
    });
  }

  @override
  Future<List<Listing>> byOwner(String ownerId) {
    if (!isServerId(ownerId)) return Future.value(const []);
    return backendCall(() async {
      final rows = await _client
          .from('listings')
          .select()
          .eq('owner_id', ownerId)
          .order('updated_at', ascending: false)
          .limit(500);
      final phones = <String, String?>{};
      if (ownerId == _me) {
        final private = await _client
            .from('listing_private')
            .select('listing_id, phone')
            .eq('owner_id', ownerId);
        for (final p in private) {
          phones[p['listing_id'] as String] = p['phone'] as String?;
        }
      }
      return [
        for (final row in rows)
          _withPrivatePhone(fromRow(row), phones[row['id']]),
      ];
    });
  }

  @override
  Future<Listing> publish(ListingDraft draft, {required String ownerId}) {
    final errors = _validator.validateAll(draft);
    if (errors.isNotEmpty) throw ValidationFailure(errors);
    final me = _me;
    if (me == null) throw const UnauthorizedFailure();
    return backendCall(() async {
      final photos = await _uploadPhotos(draft.photos, me);
      final row = await _client
          .from('listings')
          .insert({..._draftColumns(draft, photos), 'owner_id': me})
          .select()
          .single();
      final listing = fromRow(row);
      await _savePrivatePhone(listing.id, draft);
      return _withPrivatePhone(listing, _hiddenPhone(draft));
    });
  }

  @override
  Future<Listing> update(
    String listingId,
    ListingDraft draft, {
    required String actingUserId,
  }) {
    final errors = _validator.validateAll(draft);
    if (errors.isNotEmpty) throw ValidationFailure(errors);
    final me = _me;
    if (me == null) throw const UnauthorizedFailure();
    return backendCall(() async {
      final before = await _client
          .from('listings')
          .select('photos')
          .eq('id', listingId)
          .eq('owner_id', me)
          .maybeSingle();
      if (before == null) throw const ForbiddenFailure();
      final photos = await _uploadPhotos(draft.photos, me);
      final rows = await _client
          .from('listings')
          .update(_draftColumns(draft, photos))
          .eq('id', listingId)
          .select();
      if (rows.isEmpty) throw const ForbiddenFailure();
      final row = rows.first;
      await _savePrivatePhone(listingId, draft);
      // Photos the seller removed are deleted from storage.
      final removed = List<String>.from(before['photos'] as List? ?? const <String>[])
          .where((url) => !photos.contains(url));
      await _removePhotos(removed);
      return _withPrivatePhone(fromRow(row), _hiddenPhone(draft));
    });
  }

  @override
  Future<Listing> changeStatus(
    String listingId,
    ListingStatus status, {
    required String actingUserId,
  }) {
    return backendCall(() async {
      // Row level security makes another user's listing "not there" for
      // an update, so nothing comes back.
      final rows = await _client
          .from('listings')
          .update({'status': status.name})
          .eq('id', listingId)
          .select();
      if (rows.isEmpty) throw const ForbiddenFailure();
      return fromRow(rows.first);
    });
  }

  @override
  Future<void> delete(String listingId, {required String actingUserId}) {
    return backendCall(() async {
      final rows = await _client
          .from('listings')
          .delete()
          .eq('id', listingId)
          .select('photos');
      if (rows.isEmpty) throw const ForbiddenFailure();
      await _removePhotos(
        List<String>.from(rows.first['photos'] as List? ?? const <String>[]),
      );
    });
  }

  @override
  Future<void> report(ListingReport report) {
    if (!isServerId(report.listingId)) return Future.value();
    return backendCall(() async {
      await _client.from('reports').insert({
        'listing_id': report.listingId,
        'reporter_id': _me,
        'reason': report.reason.name,
        'comment': report.comment,
      });
    });
  }

  @override
  Future<Listing> applyPromotion(
    String listingId,
    ListingPromotion promotion, {
    required String actingUserId,
  }) {
    // Paid placement is activated by the server after a confirmed payment.
    throw const FeatureUnavailableFailure(UnavailableFeature.payments);
  }

  @override
  Future<Map<String, int>> countByCategory() {
    return backendCall(() async {
      final result = await _client.rpc<dynamic>('category_counts');
      return {
        for (final e in Map<String, dynamic>.from(result as Map).entries)
          e.key: (e.value as num).toInt(),
      };
    });
  }

  /// Counts a view of someone else's listing. Never fails the caller.
  Future<void> recordView(String listingId) async {
    if (!isServerId(listingId)) return;
    try {
      await _client.rpc<void>('listing_viewed', params: {'p_listing': listingId});
    } catch (_) {}
  }

  // ── Mapping ───────────────────────────────────────────────────────────

  static Map<String, Object?> filterJson(String key, AttributeFilter filter) =>
      switch (filter) {
        EqualsFilter(:final value) => {'key': key, 'op': 'eq', 'value': value},
        AnyOfFilter(:final values) => {
          'key': key,
          'op': 'in',
          'values': values.toList()..sort(),
        },
        RangeFilter(:final min, :final max) => {
          'key': key,
          'op': 'range',
          'min': ?min,
          'max': ?max,
        },
        IsTrueFilter() => {'key': key, 'op': 'true'},
        ContainsFilter(:final text) => {'key': key, 'op': 'contains', 'value': text},
      };

  static Listing fromRow(Map<String, dynamic> row) => Listing.fromJson({
    'id': row['id'],
    'ownerId': row['owner_id'],
    'categoryId': row['category_id'],
    'title': row['title'],
    'description': row['description'],
    'price': (row['price'] as num?)?.toInt(),
    'currency': row['currency'],
    'isNegotiable': row['is_negotiable'],
    'attributes': row['attributes'],
    'photos': row['photos'],
    'regionId': row['region_id'],
    'addressNote': row['address_note'],
    'contact': row['contact'],
    'status': row['status'],
    'createdAt': row['created_at'],
    'updatedAt': row['updated_at'],
    'publishedAt': row['published_at'],
    'viewCount': row['view_count'],
    'promotion': row['promotion'],
    'rejectionReason': row['rejection_reason'],
    'rejectionReasonTg': row['rejection_reason_tg'],
    'placeId': row['place_id'],
    'placeName': row['place_name'],
    'moderation': row['moderation'],
    'schemaId': row['schema_id'],
    'schemaVersion': row['schema_version'],
    'isDemo': false,
    'isLocalOnly': false,
  });

  Map<String, Object?> _draftColumns(ListingDraft draft, List<String> photos) {
    final category = _categories.byId(draft.categoryId)!;
    final schema = _schemas.schemaFor(category.formSchemaId);
    final note = draft.addressNote.trim();
    final hidden = draft.phoneVisibility == PhoneVisibility.hidden;
    return {
      'category_id': category.id,
      'title': draft.title.trim(),
      'description': draft.description.trim(),
      'price': switch (schema.priceMode) {
        PriceMode.free => 0,
        PriceMode.none => null,
        _ => Validators.parsePrice(draft.priceText),
      },
      'currency': draft.currency.code,
      'is_negotiable': draft.isNegotiable,
      'attributes': _validator.cleanAttributes(draft),
      'photos': photos,
      'region_id': draft.regionId,
      'address_note': note.isEmpty ? null : note,
      'place_id': draft.placeId,
      'place_name': draft.placeName,
      // A hidden number is not stored in the public row at all.
      'contact': {
        'name': draft.contactName.trim(),
        'phone': hidden ? '' : Formatters.nationalDigits(draft.contactPhone),
        'phoneVisibility': draft.phoneVisibility.name,
        'chatEnabled': draft.chatEnabled,
      },
      'schema_id': schema.id,
      'schema_version': schema.version,
    };
  }

  String? _hiddenPhone(ListingDraft draft) =>
      draft.phoneVisibility == PhoneVisibility.hidden
      ? Formatters.nationalDigits(draft.contactPhone)
      : null;

  Future<void> _savePrivatePhone(String listingId, ListingDraft draft) async {
    final phone = _hiddenPhone(draft);
    if (phone == null) {
      await _client.from('listing_private').delete().eq('listing_id', listingId);
    } else {
      await _client.from('listing_private').upsert({
        'listing_id': listingId,
        'owner_id': _me,
        'phone': phone,
      });
    }
  }

  /// The owner sees their own hidden number (to edit the listing).
  Listing _withPrivatePhone(Listing listing, String? phone) {
    if (phone == null || phone.isEmpty) return listing;
    return listing.copyWith(
      contact: ListingContact(
        name: listing.contact.name,
        phone: phone,
        phoneVisibility: listing.contact.phoneVisibility,
        chatEnabled: listing.contact.chatEnabled,
      ),
    );
  }

  // ── Photos ────────────────────────────────────────────────────────────

  /// Uploads photos that are still local files; keeps the ones already on
  /// the server. Order is preserved (the first photo is the cover).
  Future<List<String>> _uploadPhotos(List<String> photos, String userId) async {
    final bucket = _client.storage.from(photoBucket);
    final result = <String>[];
    for (final source in photos) {
      if (source.startsWith('http://') || source.startsWith('https://')) {
        result.add(source);
        continue;
      }
      final bytes = await XFile(source).readAsBytes();
      final lower = source.toLowerCase();
      final (ext, type) = lower.endsWith('.png')
          ? ('png', 'image/png')
          : lower.endsWith('.webp')
          ? ('webp', 'image/webp')
          : ('jpg', 'image/jpeg');
      final path = '$userId/${uuidV4()}.$ext';
      await bucket.uploadBinary(
        path,
        bytes,
        fileOptions: FileOptions(contentType: type, cacheControl: '31536000'),
      );
      result.add(bucket.getPublicUrl(path));
    }
    return result;
  }

  Future<void> _removePhotos(Iterable<String> urls) async {
    const marker = '/object/public/$photoBucket/';
    final paths = [
      for (final url in urls)
        if (url.contains(marker)) url.substring(url.indexOf(marker) + marker.length),
    ];
    if (paths.isEmpty) return;
    try {
      await _client.storage.from(photoBucket).remove(paths);
    } catch (_) {
      // Leftover files do not affect the listing; cleaned up server-side.
    }
  }
}
