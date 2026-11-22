import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/backend/backend.dart';
import '../../../core/notifications/alerts.dart';
import '../../../core/notifications/local_alerts.dart';
import '../../../shared/providers/core_providers.dart';
import '../../authentication/application/session_controller.dart';
import '../../settings/application/settings_controller.dart';
import '../domain/app_notification.dart';
import 'notification_providers.dart';

/// Registers this phone for the signed-in user's notifications and shows
/// new ones as phone notifications while the app runs.
final serverAlertsProvider = Provider<void>((ref) {
  final client = ref.watch(backendClientProvider);
  final user = ref.watch(sessionControllerProvider);
  if (client == null) return;
  if (user == null) {
    unawaited(Alerts.cancel());
    return;
  }
  final config = ref.read(appConfigProvider);
  final lang = ref.watch(settingsControllerProvider.select((s) => s.languageCode)) ?? 'tg';

  Future<void> register() async {
    var device = await Alerts.read(Alerts.kDeviceId);
    var token = await Alerts.read(Alerts.kToken);
    if (device == null || token == null) {
      device = uuidV4();
      token = randomSecret();
      await Alerts.write(Alerts.kDeviceId, device);
      await Alerts.write(Alerts.kToken, token);
    }
    await Alerts.write(Alerts.kUrl, config.serverUrl);
    await Alerts.write(Alerts.kKey, config.serverKey);
    await Alerts.write(Alerts.kLang, lang);
    if (await Alerts.read(Alerts.kSince) == null) {
      await Alerts.write(Alerts.kSince, DateTime.now().toUtc().toIso8601String());
    }
    try {
      await client.rpc<void>('register_device', params: {
        'p_device': device,
        'p_token': token,
        'p_platform': 'android',
      });
      await Alerts.schedule();
    } catch (_) {
      // Retried on the next start.
    }
    await LocalAlerts.instance.requestPermission();
  }

  unawaited(register());

  final channel = client.channel('alerts-${user.id}-${uuidV4()}');
  channel.onPostgresChanges(
    event: PostgresChangeEvent.insert,
    schema: 'public',
    table: 'notifications',
    filter: PostgresChangeFilter(
      type: PostgresChangeFilterType.eq,
      column: 'user_id',
      value: user.id,
    ),
    callback: (payload) {
      final settings = ref.read(settingsControllerProvider);
      final kind = NotificationKind.values.asNameMap()[payload.newRecord['kind']] ?? NotificationKind.system;
      if (settings.isNotificationEnabled(kind)) {
        unawaited(Alerts.show(payload.newRecord, settings.languageCode ?? 'tg'));
      }
      ref.invalidate(notificationsProvider);
    },
  );
  channel.subscribe();

  // Anything that arrived while the app was closed.
  unawaited(Alerts.pull().then((_) => ref.invalidate(notificationsProvider)));

  ref.onDispose(() => client.removeChannel(channel));
});
