import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/utils/ids.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../authentication/application/session_controller.dart';
import '../../onboarding/presentation/splash_screen.dart';
import '../../settings/application/settings_controller.dart';
import '../domain/app_notification.dart';

/// Notifications for the current user plus device-wide ones.
final notificationsProvider = FutureProvider.autoDispose<List<AppNotification>>(
  (ref) async {
    final repo = ref.watch(notificationRepositoryProvider);
    final owner = ref.watch(ownerKeyProvider);
    final items = [...await repo.list(owner), ...await repo.list(kDeviceOwner)]
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return items;
  },
);

final unreadNotificationsProvider = FutureProvider.autoDispose<int>((
  ref,
) async {
  final items = await ref.watch(notificationsProvider.future);
  return items.where((n) => !n.isRead).length;
});

final notificationServiceProvider = Provider<NotificationService>(
  NotificationService.new,
);

/// Creates in-app notifications from things that happen in the app,
/// respecting the user's per-kind settings.
class NotificationService {
  NotificationService(this._ref);
  final Ref _ref;

  Future<void> notify(
    NotificationKind kind, {
    Map<String, String> params = const {},
    String? listingId,
  }) async {
    final settings = _ref.read(settingsControllerProvider);
    if (!settings.isNotificationEnabled(kind)) return;
    await _ref
        .read(notificationRepositoryProvider)
        .add(
          AppNotification(
            id: newId('n_'),
            ownerKey: _ref.read(ownerKeyProvider),
            kind: kind,
            params: params,
            listingId: listingId,
            createdAt: _ref.read(clockProvider)(),
          ),
        );
    _ref.invalidate(notificationsProvider);
  }
}
