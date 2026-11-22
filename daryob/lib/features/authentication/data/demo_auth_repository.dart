import '../../../core/errors/failure.dart';
import '../../../core/security/session_storage.dart';
import '../../../core/storage/local_database.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/models/user.dart';
import '../domain/auth_repository.dart';

/// Development-only sign-in. No SMS is sent: the screen shows the demo code,
/// and the resulting account is marked `isDemo` with an unverified phone.
class DemoAuthRepository implements AuthRepository {
  DemoAuthRepository({
    required LocalDatabase database,
    required this._session,
    required this._clock,
  }) : _users = database.collection(Collections.users),
       _listings = database.collection(Collections.listings);

  static const demoCode = '123456';

  final JsonCollection _users;
  final JsonCollection _listings;
  final SessionStorage _session;
  final DateTime Function() _clock;

  static String userIdFor(String phone) => 'demo-user-$phone';

  @override
  bool get verifiesPhone => true;

  @override
  Future<AppUser?> restoreSession() async {
    final id = await _session.read(SessionKeys.userId);
    if (id == null) return null;
    final json = _users.get(id);
    if (json == null) {
      await _session.delete(SessionKeys.userId);
      return null;
    }
    return AppUser.fromJson(json);
  }

  @override
  Future<OtpChallenge> requestCode(String phone) async {
    final error = Validators.tajikPhone(phone);
    if (error != null) throw ValidationFailure({'phone': error});
    return OtpChallenge(
      phone: Formatters.nationalDigits(phone),
      codeLength: demoCode.length,
      resendAvailableAt: _clock().add(const Duration(seconds: 60)),
      isDemo: true,
      demoCode: demoCode,
    );
  }

  @override
  Future<AppUser> verifyCode(OtpChallenge challenge, String code) async {
    if (code.trim() != demoCode) {
      throw const ValidationFailure({'code': ValidationCode.invalidCode});
    }
    final id = userIdFor(challenge.phone);
    final existing = _users.get(id);
    final user = existing != null
        ? AppUser.fromJson(existing)
        : AppUser(
            id: id,
            phone: challenge.phone,
            createdAt: _clock(),
            // No SMS was delivered, so the number is not verified.
            isPhoneVerified: false,
            isDemo: true,
          );
    await _users.put(user.id, user.toJson());
    await _session.write(SessionKeys.userId, user.id);
    return user;
  }

  @override
  Future<AppUser> updateProfile(AppUser user) async {
    await _users.put(user.id, user.toJson());
    return user;
  }

  @override
  Future<void> signOut() => _session.delete(SessionKeys.userId);

  @override
  Future<void> requestAccountDeletion(AppUser user) async {
    for (final json in _listings.values().toList()) {
      if (json['ownerId'] == user.id) {
        await _listings.delete(json['id'] as String);
      }
    }
    await _users.delete(user.id);
    await signOut();
  }
}

/// Production sign-in without a configured backend/SMS provider. Reports the
/// missing integration instead of creating a fake session.
class UnconfiguredAuthRepository implements AuthRepository {
  const UnconfiguredAuthRepository();

  static const _failure = FeatureUnavailableFailure(UnavailableFeature.sms);

  @override
  bool get verifiesPhone => true;

  @override
  Future<AppUser?> restoreSession() async => null;
  @override
  Future<OtpChallenge> requestCode(String phone) => Future.error(_failure);
  @override
  Future<AppUser> verifyCode(OtpChallenge challenge, String code) =>
      Future.error(_failure);
  @override
  Future<AppUser> updateProfile(AppUser user) => Future.error(_failure);
  @override
  Future<void> signOut() async {}
  @override
  Future<void> requestAccountDeletion(AppUser user) => Future.error(_failure);
}
