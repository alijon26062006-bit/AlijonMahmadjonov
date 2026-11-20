import 'package:material_ui/material_ui.dart';

const kViolet = Color(0xFF7B2FF7);
const kMagenta = Color(0xFFC21FD6);
const kPink = Color(0xFFF107A3);
const kStar = Color(0xFFFFB800);

const kBrandGradient = LinearGradient(
  colors: [kViolet, kPink],
  begin: Alignment.centerLeft,
  end: Alignment.centerRight,
);

const kHeaderGradient = LinearGradient(
  colors: [kViolet, kMagenta, kPink],
  stops: [0, .6, 1],
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
);

/// Цвета дизайна «Сочный градиент» для светлой и тёмной темы.
class AppColors {
  const AppColors._({
    required this.dark,
    required this.bg,
    required this.surface,
    required this.text,
    required this.muted,
    required this.chip,
    required this.line,
    required this.accentSoft,
    required this.accentText,
  });

  final bool dark;
  final Color bg;
  final Color surface;
  final Color text;
  final Color muted;
  final Color chip;
  final Color line;
  final Color accentSoft;
  final Color accentText;

  static const light = AppColors._(
    dark: false,
    bg: Color(0xFFF4F3F9),
    surface: Colors.white,
    text: Color(0xFF17142B),
    muted: Color(0xFF8A87A0),
    chip: Color(0xFFEFEBFA),
    line: Color(0xFFE6E3F0),
    accentSoft: Color(0xFFF0E9FF),
    accentText: kViolet,
  );

  static const night = AppColors._(
    dark: true,
    bg: Color(0xFF0F0E17),
    surface: Color(0xFF1B1928),
    text: Color(0xFFF2F1F8),
    muted: Color(0xFF9C99B3),
    chip: Color(0xFF272438),
    line: Color(0xFF2E2B42),
    accentSoft: Color(0xFF2A2045),
    accentText: Color(0xFFB794FF),
  );

  static AppColors of(BuildContext context) => Theme.of(context).brightness == Brightness.dark ? night : light;

  List<BoxShadow> get cardShadow => dark
      ? const []
      : const [BoxShadow(color: Color(0x2E3C1E8C), blurRadius: 22, offset: Offset(0, 8), spreadRadius: -12)];
}

ThemeData buildTheme(Brightness brightness) {
  final c = brightness == Brightness.dark ? AppColors.night : AppColors.light;
  final scheme = ColorScheme.fromSeed(
    seedColor: kViolet,
    brightness: brightness,
  ).copyWith(primary: kViolet, secondary: kPink, surface: c.surface, onSurface: c.text);
  final base = ThemeData(useMaterial3: true, brightness: brightness, colorScheme: scheme);

  OutlineInputBorder border([Color? color, double width = 1.5]) => OutlineInputBorder(
    borderRadius: BorderRadius.circular(16),
    borderSide: color == null ? BorderSide.none : BorderSide(color: color, width: width),
  );

  return base.copyWith(
    scaffoldBackgroundColor: c.bg,
    textTheme: base.textTheme.apply(bodyColor: c.text, displayColor: c.text),
    appBarTheme: AppBarTheme(
      backgroundColor: c.bg,
      foregroundColor: c.text,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: c.text, letterSpacing: -0.3),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: c.surface,
      hintStyle: TextStyle(color: c.muted),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: border(),
      enabledBorder: border(),
      focusedBorder: border(c.accentText),
      errorBorder: border(const Color(0xFFE5484D), 1),
      focusedErrorBorder: border(const Color(0xFFE5484D)),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: c.dark ? const Color(0xFF2B2842) : const Color(0xFF17142B),
      contentTextStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500),
      actionTextColor: const Color(0xFFFF8AD8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: c.surface,
      surfaceTintColor: Colors.transparent,
      indicatorColor: c.dark ? const Color(0xFF33275A) : const Color(0xFFEFE6FF),
      elevation: 0,
      height: 68,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (s) => TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w600,
          color: s.contains(WidgetState.selected) ? c.accentText : c.muted,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (s) => IconThemeData(color: s.contains(WidgetState.selected) ? c.accentText : c.muted),
      ),
    ),
    dividerTheme: DividerThemeData(color: c.line, space: 1, thickness: 1),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: c.surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
    ),
    dialogTheme: DialogThemeData(backgroundColor: c.surface, surfaceTintColor: Colors.transparent),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        backgroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? c.accentSoft : Colors.transparent,
        ),
        foregroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? c.accentText : c.text,
        ),
        side: WidgetStatePropertyAll(BorderSide(color: c.line)),
      ),
    ),
  );
}
