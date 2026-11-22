import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/providers/repository_providers.dart';
import '../../authentication/application/session_controller.dart';

/// Ids of saved listings for the current owner (guest or user), newest first.
final favoritesControllerProvider =
    NotifierProvider<FavoritesController, List<String>>(
      FavoritesController.new,
    );

class FavoritesController extends Notifier<List<String>> {
  @override
  List<String> build() {
    final owner = ref.watch(ownerKeyProvider);
    return ref.read(favoritesRepositoryProvider).load(owner);
  }

  bool isFavorite(String listingId) => state.contains(listingId);

  /// Updates the UI immediately, then persists.
  Future<bool> toggle(String listingId) async {
    final owner = ref.read(ownerKeyProvider);
    final repo = ref.read(favoritesRepositoryProvider);
    final adding = !state.contains(listingId);
    state = adding
        ? [listingId, ...state]
        : (List.of(state)..remove(listingId));
    state = adding
        ? await repo.add(owner, listingId)
        : await repo.remove(owner, listingId);
    return adding;
  }

  Future<void> remove(String listingId) async {
    if (!state.contains(listingId)) return;
    await toggle(listingId);
  }
}
