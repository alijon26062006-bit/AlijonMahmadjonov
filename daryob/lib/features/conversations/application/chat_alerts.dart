import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/router/routes.dart';
import '../../../core/notifications/local_alerts.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../authentication/application/session_controller.dart';
import '../../notifications/application/notification_providers.dart';
import '../../notifications/domain/app_notification.dart';
import '../../settings/application/settings_controller.dart';

/// The chat the user is looking at; no alert is shown for it.
String? openConversationId;

/// Watches the signed-in user's chats and shows a system notification (and
/// an entry in Notifications) when a new message arrives. Works while the
/// app is open or in the background.
final chatAlertsProvider = Provider<void>((ref) {
  final user = ref.watch(sessionControllerProvider);
  final repo = ref.watch(conversationRepositoryProvider);
  if (user == null || !repo.deliversMessages) return;

  final unread = <String, int>{};
  var primed = false;
  var checking = false;

  Future<void> check() async {
    if (checking) return;
    checking = true;
    try {
      final conversations = await repo.list(user.id);
      for (final c in conversations) {
        final before = unread[c.id] ?? 0;
        unread[c.id] = c.unreadCount;
        if (!primed || c.unreadCount <= before || c.id == openConversationId) continue;
        final settings = ref.read(settingsControllerProvider);
        if (!settings.isNotificationEnabled(NotificationKind.newMessage)) continue;
        await LocalAlerts.instance.show(
          id: c.id.hashCode & 0x7fffffff,
          title: c.otherPartyName,
          body: c.lastMessage ?? c.listingTitle,
          route: Routes.conversation(c.id),
        );
        await ref
            .read(notificationServiceProvider)
            .notify(NotificationKind.newMessage, params: {'title': c.listingTitle});
      }
      primed = true;
    } catch (_) {
      // Offline: try again on the next signal.
    } finally {
      checking = false;
    }
  }

  unawaited(LocalAlerts.instance.requestPermission());
  unawaited(check());
  final changes = repo.watch(user.id).listen((_) => check());
  final timer = Timer.periodic(const Duration(seconds: 45), (_) => check());
  ref.onDispose(() {
    timer.cancel();
    changes.cancel();
  });
});
