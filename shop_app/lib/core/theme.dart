import 'package:material_ui/material_ui.dart';

import 'models.dart';

const kStar = Color(0xFFFFB800);
const kDanger = Color(0xFFE5484D);
const kSuccess = Color(0xFF18A957);

/// Фирменный стиль каждого из четырёх приложений: свой цвет, общий дизайн.
class Brand {
  const Brand({
    required this.appName,
    required this.roleName,
    required this.image,
    required this.primary,
    required this.gradient,
    required this.softLight,
    required this.softDark,
    required this.textDark,
  });

  final String appName;
  final String roleName;

  /// Иллюстрация на экране входа.
  final String image;
  final Color primary;
  final List<Color> gradient;
  final Color softLight;
  final Color softDark;

  /// Цвет акцентного текста в тёмной теме (светлее основного).
  final Color textDark;

  static const buyer = Brand(
    appName: 'Витрина',
    roleName: 'Покупатель',
    image: 'bags',
    primary: Color(0xFF7B2FF7),
    gradient: [Color(0xFF7B2FF7), Color(0xFFC21FD6), Color(0xFFF107A3)],
    softLight: Color(0xFFF0E9FF),
    softDark: Color(0xFF2A2045),
    textDark: Color(0xFFB794FF),
  );

  static const seller = Brand(
    appName: 'Витрина Продавец',
    roleName: 'Продавец',
    image: 'store',
    primary: Color(0xFFF2542D),
    gradient: [Color(0xFFFF8A3D), Color(0xFFFF5A4E), Color(0xFFFF3D7F)],
    softLight: Color(0xFFFFEDE6),
    softDark: Color(0xFF3A2220),
    textDark: Color(0xFFFF9B7A),
  );

  static const courier = Brand(
    appName: 'Витрина Курьер',
    roleName: 'Курьер',
    image: 'scooter',
    primary: Color(0xFF0A8F9E),
    gradient: [Color(0xFF00B4A0), Color(0xFF0E9AC8), Color(0xFF2F80ED)],
    softLight: Color(0xFFE2F6F6),
    softDark: Color(0xFF15323A),
    textDark: Color(0xFF5FD3E0),
  );

  static const admin = Brand(
    appName: 'Витрина Админ',
    roleName: 'Администратор',
    image: 'check',
    primary: Color(0xFF4B3BFF),
    gradient: [Color(0xFF2B2E83), Color(0xFF4B3BFF), Color(0xFF8E2DE2)],
    softLight: Color(0xFFEAE8FF),
    softDark: Color(0xFF24224A),
    textDark: Color(0xFFA59CFF),
  );

  static Brand of(Role role) => switch (role) {
    Role.buyer => buyer,
    Role.seller => seller,
    Role.courier => courier,
    Role.admin => admin,
  };
}

/// Цвета дизайна «Сочный градиент», доступны через `AppColors.of(context)`.
class AppColors extends ThemeExtension<AppColors> {
  const AppColors({
    required this.dark,
    required this.bg,
    required this.surface,
    required this.text,
    required this.muted,
    required this.chip,
    required this.line,
    required this.accent,
    required this.accentSoft,
    required this.accentText,
    required this.gradientColors,
  });

  final bool dark;
  final Color bg;
  final Color surface;
  final Color text;
  final Color muted;
  final Color chip;
  final Color line;
  final Color accent;
  final Color accentSoft;
  final Color accentText;
  final List<Color> gradientColors;

  factory AppColors.build(Brand brand, Brightness b) {
    final dark = b == Brightness.dark;
    return AppColors(
      dark: dark,
      bg: dark ? const Color(0xFF0F0E17) : const Color(0xFFF4F3F9),
      surface: dark ? const Color(0xFF1B1928) : Colors.white,
      text: dark ? const Color(0xFFF2F1F8) : const Color(0xFF17142B),
      muted: dark ? const Color(0xFF9C99B3) : const Color(0xFF8A87A0),
      chip: dark ? const Color(0xFF272438) : const Color(0xFFEFEDF6),
      line: dark ? const Color(0xFF2E2B42) : const Color(0xFFE6E3F0),
      accent: brand.primary,
      accentSoft: dark ? brand.softDark : brand.softLight,
      accentText: dark ? brand.textDark : brand.primary,
      gradientColors: brand.gradient,
    );
  }

  static AppColors of(BuildContext context) => Theme.of(context).extension<AppColors>()!;

  /// Горизонтальный градиент для кнопок.
  LinearGradient get gradient => LinearGradient(colors: [gradientColors.first, gradientColors.last]);

  /// Диагональный градиент для шапок.
  LinearGradient get headerGradient =>
      LinearGradient(colors: gradientColors, begin: Alignment.topLeft, end: Alignment.bottomRight);

  List<BoxShadow> get cardShadow => dark
      ? const []
      : const [BoxShadow(color: Color(0x2E3C1E8C), blurRadius: 22, offset: Offset(0, 8), spreadRadius: -12)];

  @override
  AppColors copyWith() => this;

  @override
  AppColors lerp(ThemeExtension<AppColors>? other, double t) => t < .5 ? this : (other as AppColors? ?? this);
}

const kFontFamily = 'Onest';

ThemeData buildTheme(Brand brand, Brightness brightness) {
  final c = AppColors.build(brand, brightness);
  final scheme = ColorScheme.fromSeed(
    seedColor: brand.primary,
    brightness: brightness,
  ).copyWith(primary: brand.primary, secondary: brand.gradient.last, surface: c.surface, onSurface: c.text);
  final base = ThemeData(useMaterial3: true, brightness: brightness, colorScheme: scheme, fontFamily: kFontFamily);

  OutlineInputBorder border([Color? color, double width = 1.5]) => OutlineInputBorder(
    borderRadius: BorderRadius.circular(16),
    borderSide: color == null ? BorderSide.none : BorderSide(color: color, width: width),
  );

  return base.copyWith(
    extensions: [c],
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
      errorBorder: border(kDanger, 1),
      focusedErrorBorder: border(kDanger),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: c.dark ? const Color(0xFF2B2842) : const Color(0xFF17142B),
      contentTextStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500),
      actionTextColor: c.dark ? brand.textDark : Color.lerp(brand.gradient.last, Colors.white, .45),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: c.surface,
      surfaceTintColor: Colors.transparent,
      indicatorColor: c.accentSoft,
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
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Colors.white : null),
      trackColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? brand.primary : null),
    ),
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
    tabBarTheme: TabBarThemeData(
      labelColor: c.accentText,
      unselectedLabelColor: c.muted,
      indicatorColor: c.accentText,
      dividerColor: c.line,
      labelStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
      unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
      tabAlignment: TabAlignment.start,
    ),
  );
}
