import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'screens/shell.dart';
import 'state.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(statusBarColor: Colors.transparent, systemNavigationBarColor: Colors.transparent),
  );
  final state = ShopState();
  await state.load();
  runApp(VitrinaApp(state: state));
}

class VitrinaApp extends StatelessWidget {
  const VitrinaApp({super.key, required this.state});

  final ShopState state;

  @override
  Widget build(BuildContext context) {
    return ShopScope(
      state: state,
      child: ListenableBuilder(
        listenable: state,
        builder: (context, _) => MaterialApp(
          title: 'Витрина',
          debugShowCheckedModeBanner: false,
          theme: buildTheme(Brightness.light),
          darkTheme: buildTheme(Brightness.dark),
          themeMode: state.themeMode,
          // Не даём крупному системному шрифту ломать вёрстку карточек.
          builder: (context, child) {
            final mq = MediaQuery.of(context);
            return MediaQuery(
              data: mq.copyWith(textScaler: mq.textScaler.clamp(minScaleFactor: .9, maxScaleFactor: 1.15)),
              child: child!,
            );
          },
          home: const RootShell(),
        ),
      ),
    );
  }
}
