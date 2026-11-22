import '../../../core/storage/local_database.dart';
import '../domain/app_notification.dart';

class LocalNotificationRepository implements NotificationRepository {
  LocalNotificationRepository(LocalDatabase database)
    : _store = database.collection(Collections.notifications);

  final JsonCollection _store;

  Iterable<AppNotification> _forOwner(String ownerKey) => _store
      .values()
      .map(AppNotification.fromJson)
      .where((n) => n.ownerKey == ownerKey);

  @override
  Future<List<AppNotification>> list(String ownerKey) async =>
      _forOwner(ownerKey).toList()
        ..sort((a, b) => b.createdAt.compareTo(a.createdAt));

  @override
  Future<int> unreadCount(String ownerKey) async =>
      _forOwner(ownerKey).where((n) => !n.isRead).length;

  @override
  Future<void> add(AppNotification notification) =>
      _store.put(notification.id, notification.toJson());

  @override
  Future<void> markRead(String id) async {
    final json = _store.get(id);
    if (json == null) return;
    await _store.put(id, AppNotification.fromJson(json).markRead().toJson());
  }

  @override
  Future<void> markAllRead(String ownerKey) async {
    for (final n in _forOwner(ownerKey).where((n) => !n.isRead).toList()) {
      await _store.put(n.id, n.markRead().toJson());
    }
  }

  @override
  Future<void> delete(String id) => _store.delete(id);
}
