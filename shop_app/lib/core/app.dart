import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'store.dart';
import 'theme.dart';

/// Запуск любого из четырёх приложений.
Future<void> runMarketApp(Role role, Widget home) async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(statusBarColor: Colors.transparent, systemNavigationBarColor: Colors.transparent),
  );
  final store = MarketStore(role);
  await store.load();
  runApp(MarketApp(store: store, home: home));
}

class MarketApp extends StatelessWidget {
  const MarketApp({super.key, required this.store, required this.home});

  final MarketStore store;
  final Widget home;

  @override
  Widget build(BuildContext context) {
    final brand = Brand.of(store.role);
    return StoreScope(
      store: store,
      child: ListenableBuilder(
        listenable: store,
        builder: (context, _) => MaterialApp(
          title: brand.appName,
          debugShowCheckedModeBanner: false,
          theme: buildTheme(brand, Brightness.light),
          darkTheme: buildTheme(brand, Brightness.dark),
          themeMode: store.themeMode,
          // Не даём крупному системному шрифту ломать вёрстку.
          builder: (context, child) {
            final mq = MediaQuery.of(context);
            return MediaQuery(
              data: mq.copyWith(textScaler: mq.textScaler.clamp(minScaleFactor: .9, maxScaleFactor: 1.15)),
              child: child!,
            );
          },
          home: home,
        ),
      ),
    );
  }
}
