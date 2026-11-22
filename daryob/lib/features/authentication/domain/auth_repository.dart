import 'package:flutter/foundation.dart';

import '../../../shared/models/user.dart';

/// A sign-in attempt waiting for the one-time code.
@immutable
class OtpChallenge {
  const OtpChallenge({
    required this.phone,
    required this.codeLength,
    required this.resendAvailableAt,
    this.isDemo = false,
    this.demoCode,
  });

  /// National digits (9).
  final String phone;
  final int codeLength;
  final DateTime resendAvailableAt;

  /// Development flow: no SMS is sent and the code is shown on screen.
  final bool isDemo;
  final String? demoCode;
}

/// Phone + one-time code sign-in. Real SMS delivery happens on the server;
/// the app never holds SMS provider credentials.
abstract interface class AuthRepository {
  /// Restores the session saved on this device, if any.
  Future<AppUser?> restoreSession();

  Future<OtpChallenge> requestCode(String phone);

  /// Throws [ValidationFailure] with key `code` when the code is wrong.
  Future<AppUser> verifyCode(OtpChallenge challenge, String code);

  Future<AppUser> updateProfile(AppUser user);

  Future<void> signOut();

  /// Records an account deletion request. In development this deletes the
  /// local account and its listings.
  Future<void> requestAccountDeletion(AppUser user);
}
