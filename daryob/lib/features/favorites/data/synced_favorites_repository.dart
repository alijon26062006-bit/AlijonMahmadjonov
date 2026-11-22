import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/backend/backend.dart';
import 'favorites_repository.dart';

/// Favourites stay on the device (so the heart reacts instantly and works
/// offline) and are mirrored to the user's account on the server.
class SyncedFavoritesRepository implements FavoritesRepository {
  SyncedFavoritesRepository(this._local, this._client);

  final FavoritesRepository _local;
  final SupabaseClient _client;

  bool _syncs(String ownerKey, String listingId) =>
      ownerKey == _client.auth.currentUser?.id && isServerId(listingId);

  @override
  List<String> load(String ownerKey) => _local.load(ownerKey);

  @override
  Future<List<String>> add(String ownerKey, String listingId) async {
    final ids = await _local.add(ownerKey, listingId);
    if (_syncs(ownerKey, listingId)) {
      try {
        await _client.from('favorites').upsert({'listing_id': listingId});
      } catch (_) {
        // Kept locally; pushed again on the next sign-in merge.
      }
    }
    return ids;
  }

  @override
  Future<List<String>> remove(String ownerKey, String listingId) async {
    final ids = await _local.remove(ownerKey, listingId);
    if (_syncs(ownerKey, listingId)) {
      try {
        await _client.from('favorites').delete().eq('listing_id', listingId);
      } catch (_) {}
    }
    return ids;
  }

  @override
  Future<List<String>> mergeGuestInto(String userId) async {
    var merged = await _local.mergeGuestInto(userId);
    if (userId != _client.auth.currentUser?.id) return merged;
    try {
      final rows = await _client
          .from('favorites')
          .select('listing_id')
          .order('created_at', ascending: false)
          .timeout(const Duration(seconds: 15));
      final remote = [for (final r in rows) r['listing_id'] as String];
      final missingRemotely = merged.where(isServerId).where((id) => !remote.contains(id));
      if (missingRemotely.isNotEmpty) {
        await _client.from('favorites').upsert([
          for (final id in missingRemotely) {'listing_id': id},
        ]);
      }
      for (final id in remote.reversed) {
        if (!merged.contains(id)) merged = await _local.add(userId, id);
      }
    } catch (_) {
      // Offline: the local list is still correct for this device.
    }
    return merged;
  }
}
