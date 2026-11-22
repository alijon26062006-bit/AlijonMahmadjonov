import '../../../core/storage/local_database.dart';

/// Owner key used for favourites saved before signing in.
const String kGuestOwner = 'guest';

/// Saved listings per owner. Guests keep favourites on the device; when they
/// sign in, the guest list is merged into the account (see [mergeGuestInto]).
///
/// A future backend implementation syncs the signed-in owner's list; the
/// interface stays the same.
abstract interface class FavoritesRepository {
  /// Most recently saved first.
  List<String> load(String ownerKey);
  Future<List<String>> add(String ownerKey, String listingId);
  Future<List<String>> remove(String ownerKey, String listingId);

  /// Moves guest favourites into [userId] without duplicates and clears the
  /// guest list. Returns the merged list.
  Future<List<String>> mergeGuestInto(String userId);
}

class LocalFavoritesRepository implements FavoritesRepository {
  LocalFavoritesRepository(LocalDatabase database)
    : _store = database.collection(Collections.favorites);

  final JsonCollection _store;

  @override
  List<String> load(String ownerKey) =>
      List<String>.from(_store.get(ownerKey)?['ids'] as List? ?? const []);

  Future<List<String>> _save(String ownerKey, List<String> ids) async {
    await _store.put(ownerKey, {'ids': ids});
    return ids;
  }

  @override
  Future<List<String>> add(String ownerKey, String listingId) {
    final ids = load(ownerKey)..remove(listingId);
    return _save(ownerKey, [listingId, ...ids]);
  }

  @override
  Future<List<String>> remove(String ownerKey, String listingId) {
    final ids = load(ownerKey)..remove(listingId);
    return _save(ownerKey, ids);
  }

  @override
  Future<List<String>> mergeGuestInto(String userId) async {
    final guest = load(kGuestOwner);
    final user = load(userId);
    final merged = <String>[
      ...guest,
      ...user.where((id) => !guest.contains(id)),
    ];
    await _store.delete(kGuestOwner);
    return _save(userId, merged);
  }
}
