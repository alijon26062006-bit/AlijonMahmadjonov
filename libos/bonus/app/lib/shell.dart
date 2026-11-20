import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:webview_flutter/webview_flutter.dart';

const _ink = Color(0xFF0B0B0B);

/// Starts one of the two apps. Each app is a page from assets/web shown full screen.
void runShell({required String title, required String page}) {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: _ink,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: _ink,
    systemNavigationBarIconBrightness: Brightness.light,
  ));
  runApp(MaterialApp(
    title: title,
    debugShowCheckedModeBanner: false,
    theme: ThemeData(scaffoldBackgroundColor: _ink),
    home: WebShell(page: page),
  ));
}

class WebShell extends StatefulWidget {
  const WebShell({super.key, required this.page});

  final String page;

  @override
  State<WebShell> createState() => _WebShellState();
}

class _WebShellState extends State<WebShell> {
  final _web = WebViewController();
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _web
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(_ink)
      ..addJavaScriptChannel('IstanbulNative', onMessageReceived: (m) {
        if (m.message == 'scan') _scan();
      })
      ..setNavigationDelegate(NavigationDelegate(
        onPageFinished: (_) {
          if (mounted) setState(() => _ready = true);
        },
        // The page never leaves itself; links to other sites are ignored.
        onNavigationRequest: (r) => r.url.startsWith('https://istanbul.local')
            ? NavigationDecision.navigate
            : NavigationDecision.prevent,
      ));
    _load();
  }

  Future<void> _load() async {
    final html = await rootBundle.loadString('assets/web/${widget.page}');
    // A fixed https origin keeps the saved login between launches.
    await _web.loadHtmlString(html, baseUrl: 'https://istanbul.local/');
  }

  Future<void> _scan() async {
    final code = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const ScanPage()),
    );
    await _web.runJavaScript('window.__onScan && window.__onScan(${jsonEncode(code)})');
  }

  Future<void> _back() async {
    final handled = await _web.runJavaScriptReturningResult('window.__back ? window.__back() : false');
    if (handled != true && handled.toString() != 'true') await SystemNavigator.pop();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _back();
      },
      child: Scaffold(
        body: SafeArea(
          child: Stack(children: [
            WebViewWidget(controller: _web),
            if (!_ready)
              const Center(child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3)),
          ]),
        ),
      ),
    );
  }
}

/// Full screen camera that reads the barcode on the customer's card.
class ScanPage extends StatefulWidget {
  const ScanPage({super.key});

  @override
  State<ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends State<ScanPage> {
  final _camera = MobileScannerController(
    formats: const [BarcodeFormat.ean13, BarcodeFormat.qrCode, BarcodeFormat.code128],
    detectionSpeed: DetectionSpeed.noDuplicates,
  );
  bool _done = false;

  @override
  void dispose() {
    _camera.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_done) return;
    for (final b in capture.barcodes) {
      final v = b.rawValue;
      if (v != null && v.isNotEmpty) {
        _done = true;
        HapticFeedback.mediumImpact();
        Navigator.of(context).pop(v);
        return;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(children: [
        MobileScanner(controller: _camera, onDetect: _onDetect),
        Center(
          child: Container(
            width: 290,
            height: 170,
            decoration: BoxDecoration(
              border: Border.all(color: Colors.white, width: 3),
              borderRadius: BorderRadius.circular(18),
            ),
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(children: [
              Row(children: [
                _RoundButton(icon: Icons.close, onTap: () => Navigator.of(context).pop()),
                const Spacer(),
                _RoundButton(icon: Icons.flashlight_on_outlined, onTap: () => _camera.toggleTorch()),
              ]),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                decoration: BoxDecoration(color: Colors.black.withValues(alpha: .65), borderRadius: BorderRadius.circular(16)),
                child: const Text(
                  'Штрихкод карты · Карта штрих-коды · Card barcode',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14),
                ),
              ),
              const SizedBox(height: 24),
            ]),
          ),
        ),
      ]),
    );
  }
}

class _RoundButton extends StatelessWidget {
  const _RoundButton({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.black.withValues(alpha: .55),
      shape: const CircleBorder(),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: Padding(padding: const EdgeInsets.all(12), child: Icon(icon, color: Colors.white, size: 26)),
      ),
    );
  }
}
