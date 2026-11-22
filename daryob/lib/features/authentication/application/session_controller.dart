import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/models/user.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../favorites/application/favorites_controller.dart';
import '../../favorites/data/favorites_repository.dart';
import '../domain/auth_repository.dart';

/// The signed-in user, or null for guests.
final sessionControllerProvider = NotifierProvider<SessionController, AppUser?>(
  SessionController.new,
);

/// Key under which per-user local data (favourites, notifications) is kept.
final ownerKeyProvider = Provider<String>(
  (ref) => ref.watch(sessionControllerProvider)?.id ?? kGuestOwner,
);

class SessionController extends Notifier<AppUser?> {
  @override
  AppUser? build() => null;

  AuthRepository get _auth => ref.read(authRepositoryProvider);

  Future<void> restore() async {
    state = await _auth.restoreSession();
  }

  Future<OtpChallenge> requestCode(String phone) => _auth.requestCode(phone);

  Future<AppUser> verify(OtpChallenge challenge, String code) async {
    final user = await _auth.verifyCode(challenge, code);
    // Guest favourites move into the account; duplicates are dropped.
    await ref.read(favoritesRepositoryProvider).mergeGuestInto(user.id);
    state = user;
    ref.invalidate(favoritesControllerProvider);
    return user;
  }

  Future<void> updateProfile({String? name, String? regionId}) async {
    final current = state;
    if (current == null) return;
    state = await _auth.updateProfile(
      current.copyWith(name: name, regionId: regionId),
    );
  }

  Future<void> markBusiness() async {
    final current = state;
    if (current == null) return;
    state = await _auth.updateProfile(
      current.copyWith(accountType: AccountType.business),
    );
  }

  Future<void> signOut() async {
    await _auth.signOut();
    state = null;
  }

  Future<void> deleteAccount() async {
    final current = state;
    if (current == null) return;
    await _auth.requestAccountDeletion(current);
    state = null;
  }
}
