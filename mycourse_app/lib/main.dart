import 'dart:async';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

import 'links.dart';

/// Цвета сайта mycourse.tj.
const kBg = Color(0xFF16181C);
const kGreen = Color(0xFF16A34A);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: kBg,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: kBg,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );
  runApp(const MyCourseApp());
}

class MyCourseApp extends StatelessWidget {
  const MyCourseApp({super.key, this.home});

  /// Для тестов: вместо сайта показать другой экран.
  final Widget? home;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MyCourse Beta',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: kGreen, brightness: Brightness.dark),
        scaffoldBackgroundColor: kBg,
      ),
      home: home ?? const WebShell(),
    );
  }
}

/// Сайт курса в WebView: вход, уроки и геймификация работают как на сайте.
class WebShell extends StatefulWidget {
  const WebShell({super.key});

  @override
  State<WebShell> createState() => _WebShellState();
}

class _WebShellState extends State<WebShell> {
  final WebViewController _web = WebViewController();
  int _progress = 0;
  bool _offline = false;
  bool _fullscreen = false;

  @override
  void initState() {
    super.initState();
    _setup();
  }

  Future<void> _setup() async {
    await _web.setJavaScriptMode(JavaScriptMode.unrestricted);
    await _web.setBackgroundColor(kBg);
    // сайт может узнать, что открыт из приложения
    final ua = await _web.getUserAgent();
    await _web.setUserAgent('${ua ?? ''} MyCourseApp/beta');
    await _web.setNavigationDelegate(
      NavigationDelegate(
        onProgress: (p) {
          if (mounted) setState(() => _progress = p);
        },
        onPageStarted: (_) {
          if (mounted && _offline) setState(() => _offline = false);
        },
        onWebResourceError: (e) {
          if ((e.isForMainFrame ?? true) && mounted) setState(() => _offline = true);
        },
        onNavigationRequest: _route,
      ),
    );
    final android = _web.platform;
    if (android is AndroidWebViewController) {
      // <input type="file"> на сайте (например, фото профиля)
      await android.setOnShowFileSelector(_pickFiles);
      // видео во весь экран
      await android.setCustomWidgetCallbacks(
        onShowCustomWidget: _showFullscreen,
        onHideCustomWidget: _hideFullscreen,
      );
    }
    await _web.loadRequest(Uri.parse(kStartUrl));
  }

  FutureOr<NavigationDecision> _route(NavigationRequest request) {
    final uri = Uri.tryParse(request.url);
    if (uri == null) return NavigationDecision.prevent;
    if (decide(uri, isMainFrame: request.isMainFrame) == LinkAction.inside) {
      return NavigationDecision.navigate;
    }
    launchUrl(uri, mode: LaunchMode.externalApplication).catchError((_) => false);
    return NavigationDecision.prevent;
  }

  Future<List<String>> _pickFiles(FileSelectorParams params) async {
    final types = params.acceptTypes.map((t) => t.trim()).where((t) => t.isNotEmpty).toList();
    final groups = types.isEmpty
        ? const <XTypeGroup>[]
        : [
            XTypeGroup(
              label: 'files',
              mimeTypes: types.where((t) => t.contains('/')).toList(),
              extensions: types.where((t) => t.startsWith('.')).map((t) => t.substring(1)).toList(),
            ),
          ];
    try {
      final files = params.mode == FileSelectorMode.openMultiple
          ? await openFiles(acceptedTypeGroups: groups)
          : [?await openFile(acceptedTypeGroups: groups)];
      return files.map((f) => Uri.file(f.path).toString()).toList();
    } catch (_) {
      return const [];
    }
  }

  void _showFullscreen(Widget video, void Function() onHidden) {
    _fullscreen = true;
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PopScope(
          // «Назад» на телефоне — выйти из полноэкранного видео
          onPopInvokedWithResult: (didPop, _) {
            if (didPop && _fullscreen) {
              _fullscreen = false;
              SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
              onHidden();
            }
          },
          child: Scaffold(backgroundColor: Colors.black, body: Center(child: video)),
        ),
      ),
    );
  }

  void _hideFullscreen() {
    if (!_fullscreen) return;
    _fullscreen = false;
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    Navigator.of(context).pop();
  }

  Future<void> _retry() async {
    setState(() => _offline = false);
    final current = await _web.currentUrl();
    if (current == null || !current.startsWith('http')) {
      await _web.loadRequest(Uri.parse(kStartUrl));
    } else {
      await _web.reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      // «Назад» на телефоне — назад по сайту; на первой странице — выход
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await _web.canGoBack()) {
          await _web.goBack();
        } else {
          await SystemNavigator.pop();
        }
      },
      child: Scaffold(
        body: SafeArea(
          child: Stack(
            children: [
              WebViewWidget(controller: _web),
              if (_progress < 100 && !_offline)
                LinearProgressIndicator(
                  value: _progress / 100,
                  minHeight: 3,
                  color: kGreen,
                  backgroundColor: Colors.transparent,
                ),
              if (_offline) OfflineView(onRetry: _retry),
            ],
          ),
        ),
      ),
    );
  }
}

/// Экран «нет интернета» с кнопкой повтора.
class OfflineView extends StatelessWidget {
  const OfflineView({super.key, required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: kBg,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.wifi_off_rounded, size: 64, color: Colors.white54),
              const SizedBox(height: 20),
              const Text(
                'Интернет нест',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: Colors.white),
              ),
              const SizedBox(height: 8),
              const Text(
                'Пайвастро санҷед ва аз нав кӯшиш кунед.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 15, color: Colors.white70),
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: onRetry,
                style: FilledButton.styleFrom(
                  backgroundColor: kGreen,
                  minimumSize: const Size(220, 52),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: const Text('Аз нав кӯшиш кунед', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
