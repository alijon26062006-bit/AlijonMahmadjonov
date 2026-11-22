import 'package:flutter/foundation.dart';
import 'package:flutter/painting.dart' show Color;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// System notifications shown by the app itself (new chat messages while
/// the app is open or in the background). Push notifications for a closed
/// app need a push service and are not part of this.
class LocalAlerts {
  LocalAlerts._();
  static final LocalAlerts instance = LocalAlerts._();

  final _plugin = FlutterLocalNotificationsPlugin();
  bool _ready = false;

  /// Called with the payload (a route) when the user taps a notification.
  void Function(String route)? onOpen;

  static const _channel = AndroidNotificationDetails(
    'messages',
    'Сообщения',
    channelDescription: 'Новые сообщения в чатах DARYOB',
    importance: Importance.high,
    priority: Priority.high,
    color: Color(0xFF101C32),
  );

  Future<void> initialize() async {
    if (_ready || kIsWeb) return;
    try {
      await _plugin.initialize(
        settings: const InitializationSettings(
          android: AndroidInitializationSettings('@mipmap/ic_launcher'),
          iOS: DarwinInitializationSettings(
            requestAlertPermission: false,
            requestBadgePermission: false,
            requestSoundPermission: false,
          ),
        ),
        onDidReceiveNotificationResponse: (response) {
          final route = response.payload;
          if (route != null && route.isNotEmpty) onOpen?.call(route);
        },
      );
      _ready = true;
      // Opened by tapping a notification while the app was not running.
      final launch = await _plugin.getNotificationAppLaunchDetails();
      final route = launch?.notificationResponse?.payload;
      if ((launch?.didNotificationLaunchApp ?? false) && route != null) {
        Future<void>.delayed(const Duration(seconds: 2), () => onOpen?.call(route));
      }
    } catch (_) {
      // Notifications are a convenience; the app works without them.
    }
  }

  /// Asks for permission (Android 13+, iOS). Safe to call repeatedly.
  Future<bool> requestPermission() async {
    if (!_ready) return false;
    try {
      final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin
      >();
      if (android != null) return await android.requestNotificationsPermission() ?? false;
      final ios = _plugin.resolvePlatformSpecificImplementation<
        IOSFlutterLocalNotificationsPlugin
      >();
      if (ios != null) {
        return await ios.requestPermissions(alert: true, badge: true, sound: true) ?? false;
      }
    } catch (_) {}
    return false;
  }

  Future<void> show({
    required int id,
    required String title,
    required String body,
    String? route,
  }) async {
    if (!_ready) return;
    try {
      await _plugin.show(
        id: id,
        title: title,
        body: body,
        notificationDetails: const NotificationDetails(
          android: _channel,
          iOS: DarwinNotificationDetails(),
        ),
        payload: route,
      );
    } catch (_) {}
  }
}
