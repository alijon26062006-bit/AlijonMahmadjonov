import '../../../core/networking/page_result.dart';
import '../../../shared/models/listing.dart';
import 'listing_draft.dart';
import 'listing_query.dart';

/// All listing operations go through this interface. UI code never touches
/// storage or HTTP directly.
///
/// Ownership checks here protect the local demo data only. In production the
/// server is the authority on who may edit what.
abstract interface class ListingRepository {
  Future<PageResult<Listing>> search(ListingQuery query, {int page = 1});

  Future<Listing?> getById(String id);

  Future<List<Listing>> byOwner(String ownerId);

  /// Publishes a draft. Returns the stored listing only after it is saved.
  Future<Listing> publish(ListingDraft draft, {required String ownerId});

  /// Applies an edited draft to an existing listing.
  Future<Listing> update(
    String listingId,
    ListingDraft draft, {
    required String actingUserId,
  });

  Future<Listing> changeStatus(
    String listingId,
    ListingStatus status, {
    required String actingUserId,
  });

  Future<void> delete(String listingId, {required String actingUserId});

  Future<void> report(ListingReport report);

  /// Development builds only: marks a listing as promoted without payment.
  Future<Listing> applyPromotion(
    String listingId,
    ListingPromotion promotion, {
    required String actingUserId,
  });

  /// Number of active listings per top-level category, when known.
  Future<Map<String, int>> countByCategory();
}
