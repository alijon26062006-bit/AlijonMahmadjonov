import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:workmanager/workmanager.dart';

import 'local_alerts.dart';

/// Turns server notifications into phone notifications.
///
/// * While the app runs, notifications arrive over a realtime channel and
///   are shown at once (see server_alerts.dart).
/// * When the app is closed, Android runs [backgroundDispatcher] about every
///   15 minutes; it asks the server for new notifications with this
///   install's device token (no login session needed) and shows them.
/// Instant notifications for a closed app need Firebase Cloud Messaging.
abstract final class Alerts {
  static const _storage = FlutterSecureStorage();
  static const _task = 'daryob.pull_notifications';

  static const kDeviceId = 'alerts.device_id';
  static const kToken = 'alerts.token';
  static const kSince = 'alerts.since';
  static const kShown = 'alerts.shown';
  static const kLang = 'alerts.lang';
  static const kUrl = 'alerts.url';
  static const kKey = 'alerts.key';

  /// Opened chat (no alert for it).
  static String? openConversationId;

  static Future<void> initializeBackground() async {
    if (kIsWeb || !Platform.isAndroid) return;
    try {
      await Workmanager().initialize(backgroundDispatcher);
    } catch (_) {}
  }

  static Future<void> schedule() async {
    if (kIsWeb || !Platform.isAndroid) return;
    try {
      await Workmanager().registerPeriodicTask(
        _task,
        _task,
        frequency: const Duration(minutes: 15),
        existingWorkPolicy: ExistingPeriodicWorkPolicy.keep,
        constraints: Constraints(networkType: NetworkType.connected),
      );
    } catch (_) {}
  }

  static Future<void> cancel() async {
    if (kIsWeb || !Platform.isAndroid) return;
    try {
      await Workmanager().cancelByUniqueName(_task);
    } catch (_) {}
  }

  static Future<String?> read(String key) async {
    try {
      return await _storage.read(key: key);
    } catch (_) {
      return null;
    }
  }

  static Future<void> write(String key, String? value) async {
    try {
      if (value == null) {
        await _storage.delete(key: key);
      } else {
        await _storage.write(key: key, value: value);
      }
    } catch (_) {}
  }

  /// Remembers that a notification was shown, so the background task does
  /// not show it again. Returns false when it was already shown.
  static Future<bool> markShown(String id, DateTime createdAt) async {
    final shown = (await read(kShown) ?? '').split(',').where((s) => s.isNotEmpty).toList();
    if (shown.contains(id)) return false;
    shown.add(id);
    await write(kShown, shown.skip(shown.length > 60 ? shown.length - 60 : 0).join(','));
    final since = DateTime.tryParse(await read(kSince) ?? '');
    if (since == null || createdAt.isAfter(since)) {
      await write(kSince, createdAt.toUtc().toIso8601String());
    }
    return true;
  }

  /// Shows one server notification as a phone notification.
  static Future<void> show(Map<String, dynamic> n, String languageCode) async {
    final id = '${n['id']}';
    final created = DateTime.tryParse('${n['created_at']}') ?? DateTime.now();
    final data = Map<String, dynamic>.from(n['data'] as Map? ?? const {});
    if (n['kind'] == 'newMessage' && data['conversationId'] == openConversationId) {
      await markShown(id, created);
      return;
    }
    if (!await markShown(id, created)) return;
    final (title, body) = texts(
      '${n['kind']}',
      '${n['title'] ?? ''}',
      '${n['body'] ?? ''}',
      data,
      languageCode,
    );
    await LocalAlerts.instance.show(
      id: id.hashCode & 0x7fffffff,
      title: title,
      body: body,
      route: route('${n['kind']}', data),
    );
  }

  static (String, String) texts(
    String kind,
    String title,
    String body,
    Map<String, dynamic> data,
    String lang,
  ) {
    final tg = lang == 'tg';
    final listing = '${data['title'] ?? ''}';
    switch (kind) {
      case 'newMessage':
        return (title, body);
      case 'listingApproved':
        return (tg ? 'Эълон нашр шуд' : 'Объявление опубликовано', listing);
      case 'listingRejected':
        final reason = tg && '${data['reason_tg'] ?? ''}'.isNotEmpty ? data['reason_tg'] : (data['reason'] ?? body);
        return (tg ? 'Эълон рад шуд' : 'Объявление отклонено', '«$listing»: $reason');
      default:
        if (data['code'] == 'support_reply') return (tg ? 'Ҷавоби дастгирӣ' : 'Ответ поддержки', body);
        return (title.isEmpty ? 'DARYOB' : title, body);
    }
  }

  static String route(String kind, Map<String, dynamic> data) {
    if (data['conversationId'] != null) return '/chat/${data['conversationId']}';
    if (data['ticketId'] != null) return '/support/${data['ticketId']}';
    if (data['listingId'] != null) return '/listing/${data['listingId']}';
    return '/notifications';
  }

  /// Background check (also used when the app comes back to the front).
  static Future<int> pull() async {
    final device = await read(kDeviceId);
    final token = await read(kToken);
    final url = await read(kUrl);
    final key = await read(kKey);
    if (device == null || token == null || url == null || key == null) return 0;
    final lang = await read(kLang) ?? 'tg';
    final since = await read(kSince);
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 20);
    try {
      final req = await client.postUrl(Uri.parse('$url/rest/v1/rpc/pull_notifications'));
      req.headers
        ..set('apikey', key)
        ..set('Content-Type', 'application/json');
      req.write(jsonEncode({'p_device': device, 'p_token': token, 'p_since': since}));
      final res = await req.close().timeout(const Duration(seconds: 30));
      final text = await res.transform(utf8.decoder).join();
      if (res.statusCode != 200) return 0;
      final list = jsonDecode(text);
      if (list is! List) return 0;
      await LocalAlerts.instance.initialize();
      for (final n in list) {
        await show(Map<String, dynamic>.from(n as Map), lang);
      }
      return list.length;
    } catch (_) {
      return 0;
    } finally {
      client.close(force: true);
    }
  }
}

@pragma('vm:entry-point')
void backgroundDispatcher() {
  Workmanager().executeTask((task, input) async {
    WidgetsFlutterBinding.ensureInitialized();
    await Alerts.pull();
    return true;
  });
}
