import 'dart:convert';

import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/backend/backend.dart';
import '../../../core/errors/failure.dart';
import '../../../core/security/session_storage.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/models/user.dart';
import '../domain/auth_repository.dart';

/// Accounts on the DARYOB server.
///
/// Phone verification is not connected yet, so an account is tied to this
/// device: a random id and secret kept in secure storage. The phone number
/// the user enters is stored as unverified contact data and never used to
/// find an account — otherwise anyone could open someone else's account by
/// typing their number. When verification by code is connected, verified
/// numbers will be able to restore an account on a new phone.
class ServerAuthRepository implements AuthRepository {
  ServerAuthRepository({
    required this._client,
    required this._storage,
    required this._clock,
  });

  final SupabaseClient _client;
  final SessionStorage _storage;
  final DateTime Function() _clock;

  static const _deviceIdKey = 'backend.device_id';
  static const _deviceSecretKey = 'backend.device_secret';
  static const _userCacheKey = 'backend.user';

  static String emailFor(String deviceId) => '$deviceId@device.daryob.tj';

  @override
  bool get verifiesPhone => false;

  @override
  Future<AppUser?> restoreSession() async {
    final authUser = _client.auth.currentUser;
    if (authUser == null) return null;
    try {
      return await _loadUser(authUser.id);
    } catch (_) {
      // Offline start: show the account as it was last seen.
      final cached = await _storage.read(_userCacheKey);
      if (cached == null) return null;
      final user = AppUser.fromJson(jsonDecode(cached) as Map<String, dynamic>);
      return user.id == authUser.id ? user : null;
    }
  }

  @override
  Future<OtpChallenge> requestCode(String phone) async {
    final error = Validators.tajikPhone(phone);
    if (error != null) throw ValidationFailure({'phone': error});
    return OtpChallenge(
      phone: Formatters.nationalDigits(phone),
      codeLength: 0,
      resendAvailableAt: _clock(),
      requiresCode: false,
    );
  }

  @override
  Future<AppUser> verifyCode(OtpChallenge challenge, String code) {
    return backendCall(() async {
      final userId = await _signInDevice();
      await _client
          .from('profile_private')
          .update({'phone': challenge.phone})
          .eq('id', userId);
      return _loadUser(userId);
    });
  }

  @override
  Future<AppUser> updateProfile(AppUser user) {
    return backendCall(() async {
      await _client
          .from('profiles')
          .update({
            'name': user.name?.trim(),
            'region_id': user.regionId,
            'account_type': user.accountType.name,
          })
          .eq('id', user.id);
      return _loadUser(user.id);
    });
  }

  @override
  Future<void> signOut() async {
    await _storage.delete(_userCacheKey);
    try {
      await _client.auth.signOut(scope: SignOutScope.local);
    } catch (_) {
      // The local session is cleared even when the server is unreachable.
    }
  }

  @override
  Future<void> requestAccountDeletion(AppUser user) {
    return backendCall(() async {
      await _client.functions.invoke('delete-account', body: const {});
      await _storage.delete(_userCacheKey);
      await _storage.delete(_deviceIdKey);
      await _storage.delete(_deviceSecretKey);
      try {
        await _client.auth.signOut(scope: SignOutScope.local);
      } catch (_) {}
    });
  }

  /// Signs in with this device's credentials, creating the account on first
  /// use. Returns the user id.
  Future<String> _signInDevice() async {
    final current = _client.auth.currentUser;
    if (current != null) return current.id;

    var deviceId = await _storage.read(_deviceIdKey);
    var secret = await _storage.read(_deviceSecretKey);
    if (deviceId != null && secret != null) {
      try {
        final res = await _client.auth.signInWithPassword(
          email: emailFor(deviceId),
          password: secret,
        );
        if (res.user != null) return res.user!.id;
      } on AuthException catch (e) {
        // Anything but "wrong credentials" (the account was deleted) is a
        // real error.
        if (int.tryParse(e.statusCode ?? '') != 400) rethrow;
      }
    }

    deviceId = uuidV4();
    secret = randomSecret();
    await _client.functions.invoke(
      'device-signup',
      body: {'device_id': deviceId, 'password': secret},
    );
    await _storage.write(_deviceIdKey, deviceId);
    await _storage.write(_deviceSecretKey, secret);
    final res = await _client.auth.signInWithPassword(
      email: emailFor(deviceId),
      password: secret,
    );
    final user = res.user;
    if (user == null) throw const UnauthorizedFailure();
    return user.id;
  }

  Future<AppUser> _loadUser(String id) async {
    final profile = await _client
        .from('profiles')
        .select()
        .eq('id', id)
        .single()
        .timeout(const Duration(seconds: 15));
    final private = await _client
        .from('profile_private')
        .select('phone')
        .eq('id', id)
        .maybeSingle()
        .timeout(const Duration(seconds: 15));
    final user = AppUser(
      id: id,
      phone: private?['phone'] as String? ?? '',
      name: profile['name'] as String?,
      regionId: profile['region_id'] as String?,
      isPhoneVerified: profile['is_phone_verified'] as bool? ?? false,
      accountType: AccountType.values.byName(
        profile['account_type'] as String? ?? AccountType.individual.name,
      ),
      createdAt:
          DateTime.tryParse(profile['created_at'] as String? ?? '') ?? _clock(),
    );
    await _storage.write(_userCacheKey, jsonEncode(user.toJson()));
    return user;
  }
}
