import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_ce_flutter/hive_ce_flutter.dart';

import '../core/security/session_storage.dart';
import '../core/storage/local_database.dart';
import '../shared/providers/core_providers.dart';
import 'app.dart';
import 'configuration/app_config.dart';

/// Opens storage, wires dependencies and starts the app. The native splash
/// (navy background, lime mark) stays on screen until the first frame.
Future<void> bootstrap() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromEnvironment();

  await Hive.initFlutter('daryob');
  final database = await HiveLocalDatabase.open();

  runApp(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(config),
        localDatabaseProvider.overrideWithValue(database),
        sessionStorageProvider.overrideWithValue(SecureSessionStorage()),
      ],
      // Screens offer explicit "Retry" buttons; automatic background retries
      // would hide real errors and waste mobile data.
      retry: (_, _) => null,
      child: const DaryobApp(),
    ),
  );
}
