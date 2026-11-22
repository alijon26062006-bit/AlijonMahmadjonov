import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../core/backend/backend.dart';
import '../../shared/models/listing.dart';
import '../authentication/application/session_controller.dart';
import '../conversations/domain/conversation.dart';
import '../listings/data/server_listing_repository.dart';

/// A listing with its owner, as moderators see it.
class AdminListing {
  const AdminListing(this.listing, {this.ownerName, this.ownerBlocked = false});
  final Listing listing;
  final String? ownerName;
  final bool ownerBlocked;
}

class AdminUser {
  const AdminUser(this.row);
  final Map<String, dynamic> row;

  String get id => row['id'] as String;
  String get name => (row['name'] as String?)?.trim().isNotEmpty == true ? row['name'] as String : 'Без имени';
  String? get phone => row['phone'] as String?;
  bool get verified => row['is_phone_verified'] == true;
  bool get blocked => row['is_blocked'] == true;
  String? get staffRole => row['staff_role'] as String?;
  int count(String key) => (row[key] as num?)?.toInt() ?? 0;
  DateTime get createdAt => DateTime.parse(row['created_at'] as String).toLocal();
}

/// Everything the admin panel reads and changes. Every write goes through a
/// server function that checks the staff role and records the action.
class AdminRepository {
  AdminRepository(this._client);
  final SupabaseClient _client;

  static const _listingColumns = '*, owner:profiles!listings_owner_id_fkey(name, is_blocked)';

  AdminListing _adminListing(Map<String, dynamic> row) {
    final owner = row['owner'] as Map?;
    return AdminListing(
      ServerListingRepository.fromRow(row),
      ownerName: owner?['name'] as String?,
      ownerBlocked: owner?['is_blocked'] == true,
    );
  }

  Future<String?> myRole() async {
    if (_client.auth.currentUser == null) return null;
    try {
      return await _client.rpc<dynamic>('my_staff_role') as String?;
    } catch (_) {
      return null;
    }
  }

  Future<bool> claimAdmin(String code) => backendCall(
    () async => await _client.rpc<dynamic>('claim_admin', params: {'p_code': code}) == true,
  );

  Future<Map<String, dynamic>> stats() => backendCall(
    () async => Map<String, dynamic>.from(await _client.rpc<dynamic>('admin_stats') as Map),
  );

  Future<List<AdminListing>> listings({List<String>? statuses, String? ownerId, int limit = 100}) =>
      backendCall(() async {
        var q = _client.from('listings').select(_listingColumns);
        if (statuses != null) q = q.inFilter('status', statuses);
        if (ownerId != null) q = q.eq('owner_id', ownerId);
        final rows = await q.order('updated_at', ascending: statuses?.contains('pending') == true).limit(limit);
        return [for (final r in rows) _adminListing(r)];
      });

  Future<AdminListing?> listing(String id) => backendCall(() async {
    final row = await _client.from('listings').select(_listingColumns).eq('id', id).maybeSingle();
    return row == null ? null : _adminListing(row);
  });

  Future<void> moderate(String id, String decision, {String? reason, String? reasonTg}) => backendCall(
    () => _client.rpc<void>('admin_moderate_listing', params: {
      'p_listing': id,
      'p_decision': decision,
      'p_reason': reason,
      'p_reason_tg': reasonTg,
    }),
  );

  Future<void> deleteListing(String id) =>
      backendCall(() => _client.rpc<void>('admin_delete_listing', params: {'p_listing': id}));

  Future<void> recheck(String id) =>
      backendCall(() => _client.rpc<void>('admin_recheck_listing', params: {'p_listing': id}));

  Future<List<Map<String, dynamic>>> reports({String status = 'open'}) => backendCall(() async {
    final rows = await _client
        .from('reports')
        .select('*, listing:listings(id, title, status, photos, owner_id)')
        .eq('status', status)
        .order('created_at', ascending: status != 'open')
        .limit(200);
    return List<Map<String, dynamic>>.from(rows);
  });

  Future<void> resolveReport(String id, String status, {String? resolution}) => backendCall(
    () => _client.rpc<void>('admin_resolve_report', params: {
      'p_report': id,
      'p_status': status,
      'p_resolution': resolution,
    }),
  );

  Future<List<AdminUser>> users(String query) => backendCall(() async {
    final rows = await _client.rpc<dynamic>('admin_search_users', params: {'p_query': query, 'p_limit': 100});
    return [for (final r in rows as List) AdminUser(Map<String, dynamic>.from(r as Map))];
  });

  Future<AdminUser?> user(String id) async {
    final list = await users(id);
    return list.where((u) => u.id == id).firstOrNull;
  }

  Future<void> setBlocked(String userId, bool blocked, {String? reason}) => backendCall(
    () => _client.rpc<void>('admin_set_user_blocked', params: {
      'p_user': userId,
      'p_blocked': blocked,
      'p_reason': reason,
    }),
  );

  Future<void> setStaff(String userId, String? role) => backendCall(
    () => _client.rpc<void>('admin_set_staff', params: {'p_user': userId, 'p_role': role}),
  );

  Future<List<Map<String, dynamic>>> flags({String status = 'open'}) => backendCall(() async {
    final rows = await _client
        .from('message_flags')
        .select('*, message:messages(text, hidden, created_at), sender:profiles!message_flags_sender_id_fkey(name)')
        .eq('status', status)
        .order('created_at', ascending: false)
        .limit(200);
    return List<Map<String, dynamic>>.from(rows);
  });

  Future<void> reviewFlag(int id, {bool unhide = false}) => backendCall(
    () => _client.rpc<void>('admin_review_flag', params: {'p_flag': id, 'p_unhide': unhide}),
  );

  Future<Map<String, dynamic>?> conversation(String id) => backendCall(
    () async => await _client
        .from('conversations')
        .select('*, buyer:profiles!conversations_buyer_id_fkey(name), seller:profiles!conversations_seller_id_fkey(name)')
        .eq('id', id)
        .maybeSingle(),
  );

  Future<List<ChatMessage>> conversationMessages(String id) => backendCall(() async {
    final rows = await _client.from('messages').select().eq('conversation_id', id).order('created_at').limit(500);
    final notices = await _client.from('chat_notices').select().eq('conversation_id', id).order('created_at');
    return [
      for (final r in rows)
        ChatMessage(
          id: r['id'] as String,
          conversationId: id,
          senderId: r['sender_id'] as String? ?? '',
          text: r['text'] as String? ?? '',
          sentAt: DateTime.parse(r['created_at'] as String).toLocal(),
          state: r['hidden'] == true ? DeliveryState.failed : DeliveryState.sent,
        ),
      for (final n in notices)
        ChatMessage(
          id: n['id'] as String,
          conversationId: id,
          senderId: '',
          text: n['text_ru'] as String? ?? '',
          sentAt: DateTime.parse(n['created_at'] as String).toLocal(),
          state: DeliveryState.delivered,
          isSystem: true,
        ),
    ]..sort((a, b) => a.sentAt.compareTo(b.sentAt));
  });

  Future<Map<String, dynamic>> settings() => backendCall(() async {
    final rows = await _client.from('app_settings').select();
    return {for (final r in rows) r['key'] as String: r['value']};
  });

  Future<void> setSetting(String key, Map<String, dynamic> value) => backendCall(
    () => _client.rpc<void>('admin_set_setting', params: {'p_key': key, 'p_value': value}),
  );

  Future<List<Map<String, dynamic>>> audit() => backendCall(() async {
    final rows = await _client
        .from('admin_actions')
        .select('*, staff:profiles!admin_actions_staff_id_fkey(name)')
        .order('created_at', ascending: false)
        .limit(300);
    return List<Map<String, dynamic>>.from(rows);
  });
}

final adminRepositoryProvider = Provider<AdminRepository?>((ref) {
  final client = ref.watch(backendClientProvider);
  return client == null ? null : AdminRepository(client);
});

/// The signed-in user's staff role (admin, moderator, support) or null.
final staffRoleProvider = FutureProvider<String?>((ref) async {
  final user = ref.watch(sessionControllerProvider);
  final repo = ref.watch(adminRepositoryProvider);
  if (user == null || repo == null) return null;
  return repo.myRole();
});
