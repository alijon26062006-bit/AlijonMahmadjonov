import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/backend/backend.dart';
import '../domain/app_notification.dart';

/// Notifications the platform sends to a user (moderation results, system
/// messages) come from the server; notifications the app raises for itself
/// stay on the device.
class ServerNotificationRepository implements NotificationRepository {
  ServerNotificationRepository(this._local, this._client);

  final NotificationRepository _local;
  final SupabaseClient _client;

  bool _isMine(String ownerKey) => ownerKey == _client.auth.currentUser?.id;

  Future<List<AppNotification>> _remote(String ownerKey) async {
    if (!_isMine(ownerKey)) return const [];
    try {
      final rows = await _client
          .from('notifications')
          .select()
          .order('created_at', ascending: false)
          .limit(100)
          .timeout(const Duration(seconds: 15));
      return [for (final row in rows) _fromRow(row, ownerKey)];
    } catch (_) {
      return const [];
    }
  }

  @override
  Future<List<AppNotification>> list(String ownerKey) async {
    final items = [...await _local.list(ownerKey), ...await _remote(ownerKey)]
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return items;
  }

  @override
  Future<int> unreadCount(String ownerKey) async =>
      (await list(ownerKey)).where((n) => !n.isRead).length;

  @override
  Future<void> add(AppNotification notification) => _local.add(notification);

  @override
  Future<void> markRead(String id) async {
    if (!isServerId(id)) return _local.markRead(id);
    try {
      await _client
          .from('notifications')
          .update({'read_at': DateTime.now().toUtc().toIso8601String()})
          .eq('id', id);
    } catch (_) {}
  }

  @override
  Future<void> markAllRead(String ownerKey) async {
    await _local.markAllRead(ownerKey);
    if (!_isMine(ownerKey)) return;
    try {
      await _client
          .from('notifications')
          .update({'read_at': DateTime.now().toUtc().toIso8601String()})
          .isFilter('read_at', null);
    } catch (_) {}
  }

  @override
  Future<void> delete(String id) async {
    if (!isServerId(id)) return _local.delete(id);
    try {
      await _client.from('notifications').delete().eq('id', id);
    } catch (_) {}
  }

  AppNotification _fromRow(Map<String, dynamic> row, String ownerKey) {
    final data = Map<String, dynamic>.from(row['data'] as Map? ?? const {});
    final kind = NotificationKind.values.asNameMap()[row['kind']] ?? NotificationKind.system;
    return AppNotification(
      id: row['id'] as String,
      ownerKey: ownerKey,
      kind: kind,
      createdAt: DateTime.parse(row['created_at'] as String).toLocal(),
      params: {
        for (final e in data.entries)
          if (e.value != null && e.key != 'listingId') e.key: '${e.value}',
        // For listing events `data.title` is the listing's title; a system
        // message carries its own title and body.
        if (data['title'] == null) 'title': row['title'] as String? ?? '',
        'body': row['body'] as String? ?? '',
      },
      listingId: data['listingId'] as String?,
      isRead: row['read_at'] != null,
    );
  }
}
