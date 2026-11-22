import 'package:flutter/foundation.dart';

enum NotificationKind {
  newMessage,
  listingApproved,
  listingRejected,
  listingExpiring,
  promotionEnding,
  newMatchingListing,
  system,
}

/// Stored without final text: the screen builds the sentence in the current
/// language from [kind] and [params].
@immutable
class AppNotification {
  const AppNotification({
    required this.id,
    required this.ownerKey,
    required this.kind,
    required this.createdAt,
    this.params = const {},
    this.listingId,
    this.isRead = false,
  });

  final String id;
  final String ownerKey;
  final NotificationKind kind;

  /// e.g. {'title': 'Диван'} or {'code': 'welcome'} for system messages.
  final Map<String, String> params;
  final String? listingId;
  final DateTime createdAt;
  final bool isRead;

  AppNotification markRead() => AppNotification(
    id: id,
    ownerKey: ownerKey,
    kind: kind,
    createdAt: createdAt,
    params: params,
    listingId: listingId,
    isRead: true,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'ownerKey': ownerKey,
    'kind': kind.name,
    'params': params,
    'listingId': listingId,
    'createdAt': createdAt.toIso8601String(),
    'isRead': isRead,
  };

  factory AppNotification.fromJson(Map<String, dynamic> json) =>
      AppNotification(
        id: json['id'] as String,
        ownerKey: json['ownerKey'] as String,
        kind: NotificationKind.values.byName(json['kind'] as String),
        params: Map<String, String>.from(json['params'] as Map? ?? const {}),
        listingId: json['listingId'] as String?,
        createdAt: DateTime.parse(json['createdAt'] as String),
        isRead: json['isRead'] as bool? ?? false,
      );
}

/// Notification centre storage. Push delivery (FCM or similar) plugs in
/// through [PushNotificationService]; the centre works without it.
abstract interface class NotificationRepository {
  Future<List<AppNotification>> list(String ownerKey);
  Future<int> unreadCount(String ownerKey);
  Future<void> add(AppNotification notification);
  Future<void> markRead(String id);
  Future<void> markAllRead(String ownerKey);
  Future<void> delete(String id);
}

/// Push delivery. The default implementation reports that push is not
/// configured; a Firebase implementation is added once credentials exist.
abstract interface class PushNotificationService {
  bool get isConfigured;
  Future<void> initialize();
}

class UnconfiguredPushService implements PushNotificationService {
  const UnconfiguredPushService();

  @override
  bool get isConfigured => false;

  @override
  Future<void> initialize() async {}
}
