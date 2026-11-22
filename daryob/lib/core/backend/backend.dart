import 'dart:async';
import 'dart:io' show SocketException;
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../errors/failure.dart';
import '../security/session_storage.dart';

/// The DARYOB server (Supabase). Null in development builds, in tests and
/// when a production build has no server configured; repositories then fall
/// back to local demo data or explicit "unavailable" states.
final backendClientProvider = Provider<SupabaseClient?>((ref) => null);

/// Opens the connection. Returns null instead of throwing so the app still
/// starts (with "unavailable" states) when the server cannot be initialised.
Future<SupabaseClient?> connectBackend({
  required String url,
  required String publishableKey,
  required SessionStorage sessionStorage,
}) async {
  if (url.isEmpty || publishableKey.isEmpty) return null;
  try {
    final supabase = await Supabase.initialize(
      url: url,
      publishableKey: publishableKey,
      authOptions: FlutterAuthClientOptions(
        // The session token goes to the platform keystore, not to plain
        // preferences.
        localStorage: _SecureAuthStorage(sessionStorage),
      ),
    );
    return supabase.client;
  } catch (_) {
    return null;
  }
}

class _SecureAuthStorage extends LocalStorage {
  const _SecureAuthStorage(this._storage);
  final SessionStorage _storage;
  static const _key = 'backend.session';

  @override
  Future<void> initialize() async {}

  @override
  Future<String?> accessToken() => _storage.read(_key);

  @override
  Future<bool> hasAccessToken() async => (await _storage.read(_key)) != null;

  @override
  Future<void> persistSession(String persistSessionString) =>
      _storage.write(_key, persistSessionString);

  @override
  Future<void> removePersistedSession() => _storage.delete(_key);
}

/// Translates server and transport errors into the app's failures, so the
/// UI shows the same messages whatever the data source is.
AppFailure backendFailure(Object error) {
  if (error is AppFailure) return error;
  if (error is TimeoutException) return const TimeoutFailure();
  if (error is SocketException) return const NetworkFailure();
  if (error is PostgrestException) {
    final message = error.message;
    if (message.contains('daily_limit')) return const RateLimitedFailure();
    if (message.contains('listing_not_found') || message.contains('PGRST116')) {
      return const NotFoundFailure();
    }
    return switch (error.code) {
      '42501' => const ForbiddenFailure(),
      'PGRST116' || 'P0002' => const NotFoundFailure(),
      'PGRST301' || 'PGRST302' => const UnauthorizedFailure(sessionExpired: true),
      _ => ServerFailure(int.tryParse(error.code ?? '')),
    };
  }
  if (error is AuthException) {
    final status = int.tryParse(error.statusCode ?? '');
    if (status == 429) return const RateLimitedFailure();
    if (status == null) return const NetworkFailure();
    return const UnauthorizedFailure(sessionExpired: true);
  }
  if (error is StorageException) {
    final status = int.tryParse(error.statusCode ?? '');
    if (status == 403 || status == 400) return const ForbiddenFailure();
    return ServerFailure(status);
  }
  if (error is FunctionException) {
    if (error.status == 429) return const RateLimitedFailure();
    if (error.status == 401) return const UnauthorizedFailure(sessionExpired: true);
    return ServerFailure(error.status);
  }
  // http.ClientException and friends: no response at all.
  final text = error.toString();
  if (text.contains('ClientException') || text.contains('Failed host lookup') || text.contains('XMLHttpRequest')) {
    return const NetworkFailure();
  }
  return UnknownFailure(error);
}

/// Runs a server call with a timeout and failure translation.
Future<T> backendCall<T>(Future<T> Function() run) async {
  try {
    return await run().timeout(const Duration(seconds: 30));
  } catch (e) {
    throw backendFailure(e);
  }
}

final _secure = Random.secure();

/// RFC 4122 version 4 identifier.
String uuidV4() {
  final b = List<int>.generate(16, (_) => _secure.nextInt(256));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  String hex(int from, int to) =>
      b.sublist(from, to).map((x) => x.toRadixString(16).padLeft(2, '0')).join();
  return '${hex(0, 4)}-${hex(4, 6)}-${hex(6, 8)}-${hex(8, 10)}-${hex(10, 16)}';
}

String randomSecret([int bytes = 32]) => List<int>.generate(
  bytes,
  (_) => _secure.nextInt(256),
).map((x) => x.toRadixString(16).padLeft(2, '0')).join();

final _uuidPattern = RegExp(
  r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
);

/// Server ids are UUIDs; local demo ids (`l_…`, `demo-…`) are not.
bool isServerId(String? id) => id != null && _uuidPattern.hasMatch(id);
