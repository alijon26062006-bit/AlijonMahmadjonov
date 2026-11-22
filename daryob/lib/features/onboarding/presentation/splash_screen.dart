import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/storage/local_database.dart';
import '../../../core/utils/ids.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/daryob_logo.dart';
import '../../authentication/application/session_controller.dart';
import '../../notifications/domain/app_notification.dart';
import '../../settings/application/settings_controller.dart';

/// Owner key for notifications meant for whoever uses this device.
const String kDeviceOwner = 'device';

/// Branded start screen. Same navy/lime as the native splash, so there is no
/// white flash. Restores the session and prepares local data, then routes to
/// onboarding or home.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _start());
  }

  Future<void> _start() async {
    final started = DateTime.now();
    final config = ref.read(appConfigProvider);
    try {
      await ref.read(sessionControllerProvider.notifier).restore();
      if (config.isDevelopment) {
        await ref.read(demoSeederProvider).seedIfNeeded();
      }
      await _welcomeOnce();
      await ref.read(pushServiceProvider).initialize();
    } catch (_) {
      // Startup must never get stuck on the splash; screens show their own
      // errors if a repository is unavailable.
    }

    // Keep the brand on screen briefly so the transition isn't a flicker.
    final elapsed = DateTime.now().difference(started);
    const minimum = Duration(milliseconds: 700);
    if (elapsed < minimum) await Future<void>.delayed(minimum - elapsed);

    if (!mounted) return;
    final done = ref.read(settingsControllerProvider).onboardingCompleted;
    context.go(done ? Routes.home : Routes.onboarding);
  }

  Future<void> _welcomeOnce() async {
    final meta = ref.read(localDatabaseProvider).collection(Collections.meta);
    if (meta.get('welcome_sent') != null) return;
    await ref
        .read(notificationRepositoryProvider)
        .add(
          AppNotification(
            id: newId('n_'),
            ownerKey: kDeviceOwner,
            kind: NotificationKind.system,
            params: const {'code': 'welcome'},
            createdAt: ref.read(clockProvider)(),
          ),
        );
    await meta.put('welcome_sent', {'at': DateTime.now().toIso8601String()});
  }

  @override
  Widget build(BuildContext context) {
    return const AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: DaryobColors.navy,
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DaryobMark(size: 96),
              SizedBox(height: DaryobSpacing.xl),
              Text(
                'DARYOB',
                style: TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 34,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.5,
                  color: Colors.white,
                ),
              ),
              SizedBox(height: DaryobSpacing.sm),
              Text(
                'Ҷустуҷӯ кун. Дарёб!',
                style: TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: DaryobColors.lime,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
