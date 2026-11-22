import 'package:material_ui/material_ui.dart';

/// Brand colours. The only place raw colour values are allowed.
abstract final class DaryobColors {
  static const navy = Color(0xFF101C32);
  static const lime = Color(0xFFC9F24B);
  static const background = Color(0xFFF5F7FB);
  static const surface = Color(0xFFFFFFFF);
  static const textPrimary = Color(0xFF101C32);
  static const textSecondary = Color(0xFF667085);
  static const border = Color(0xFFE5EAF0);
  static const success = Color(0xFF159B68);
  static const warning = Color(0xFFF59E0B);
  static const error = Color(0xFFE5484D);

  // Dark mode keeps the navy/lime identity on deeper navy surfaces.
  static const darkBackground = Color(0xFF0A1322);
  static const darkSurface = Color(0xFF131F36);
  static const darkSurfaceHigh = Color(0xFF1B2944);
  static const darkTextPrimary = Color(0xFFF2F5FA);
  static const darkTextSecondary = Color(0xFFA3ADBF);
  static const darkBorder = Color(0xFF26344F);
  static const darkError = Color(0xFFFF6B6F);

  /// Soft tints used behind category icons and status badges.
  static const limeSoft = Color(0xFFF1FBD2);
  static const navySoft = Color(0xFFE8ECF4);
}

/// A soft background and a strong foreground of one hue.
@immutable
class DaryobTint {
  const DaryobTint(this.soft, this.strong);
  final Color soft;
  final Color strong;
}

/// Category accents: each category keeps one hue on its icon tile and on the
/// placeholder shown when a listing has no photo. Navy and lime stay the
/// brand colours for navigation and actions.
abstract final class DaryobTints {
  static const blue = DaryobTint(Color(0xFFE3EEFF), Color(0xFF2457C5));
  static const violet = DaryobTint(Color(0xFFEBE7FF), Color(0xFF5B45C9));
  static const cyan = DaryobTint(Color(0xFFDDF4F8), Color(0xFF0E7C91));
  static const amber = DaryobTint(Color(0xFFFFF0D1), Color(0xFFA86400));
  static const pink = DaryobTint(Color(0xFFFFE4EE), Color(0xFFC2327A));
  static const orange = DaryobTint(Color(0xFFFFE8DA), Color(0xFFC2541B));
  static const slate = DaryobTint(Color(0xFFE6EBF2), Color(0xFF41506B));
  static const yellow = DaryobTint(Color(0xFFFFF4C2), Color(0xFF8A6A00));
  static const coral = DaryobTint(Color(0xFFFFE6E0), Color(0xFFC0483A));
  static const teal = DaryobTint(Color(0xFFD9F4EC), Color(0xFF0F7A5E));
  static const red = DaryobTint(Color(0xFFFFE3E3), Color(0xFFC23A3A));
  static const green = DaryobTint(Color(0xFFE1F5D8), Color(0xFF3B7D1E));
  static const brown = DaryobTint(Color(0xFFF3E7DA), Color(0xFF8A5A2B));
  static const lime = DaryobTint(DaryobColors.limeSoft, Color(0xFF4F6B00));
  static const neutral = DaryobTint(DaryobColors.navySoft, DaryobColors.textSecondary);
}

abstract final class DaryobSpacing {
  static const double xxs = 2;
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double xxxl = 32;
  static const double huge = 48;

  /// Horizontal page gutter.
  static const double page = 16;
}

abstract final class DaryobRadius {
  static const double chip = 10;
  static const double input = 14;
  static const double button = 14;
  static const double card = 18;
  static const double hero = 20;
  static const double sheet = 24;

  static const BorderRadius chipAll = BorderRadius.all(Radius.circular(chip));
  static const BorderRadius inputAll = BorderRadius.all(Radius.circular(input));
  static const BorderRadius buttonAll = BorderRadius.all(
    Radius.circular(button),
  );
  static const BorderRadius cardAll = BorderRadius.all(Radius.circular(card));
  static const BorderRadius heroAll = BorderRadius.all(Radius.circular(hero));
}

abstract final class DaryobSizes {
  /// Minimum comfortable touch target.
  static const double touch = 48;
  static const double buttonHeight = 52;
  static const double inputHeight = 52;
  static const double bottomBar = 68;
  static const double iconSm = 18;
  static const double iconMd = 22;
  static const double iconLg = 28;
}

abstract final class DaryobDurations {
  static const fast = Duration(milliseconds: 150);
  static const normal = Duration(milliseconds: 250);
  static const searchDebounce = Duration(milliseconds: 350);
}

/// Colours that Material's [ColorScheme] has no slot for.
@immutable
class DaryobPalette extends ThemeExtension<DaryobPalette> {
  const DaryobPalette({
    required this.lime,
    required this.onLime,
    required this.navy,
    required this.onNavy,
    required this.textSecondary,
    required this.border,
    required this.success,
    required this.warning,
    required this.surfaceMuted,
    required this.limeSoft,
    required this.skeleton,
    required this.shadow,
  });

  final Color lime;
  final Color onLime;
  final Color navy;
  final Color onNavy;
  final Color textSecondary;
  final Color border;
  final Color success;
  final Color warning;
  final Color surfaceMuted;
  final Color limeSoft;
  final Color skeleton;
  final Color shadow;

  static const light = DaryobPalette(
    lime: DaryobColors.lime,
    onLime: DaryobColors.navy,
    navy: DaryobColors.navy,
    onNavy: Colors.white,
    textSecondary: DaryobColors.textSecondary,
    border: DaryobColors.border,
    success: DaryobColors.success,
    warning: DaryobColors.warning,
    surfaceMuted: DaryobColors.navySoft,
    limeSoft: DaryobColors.limeSoft,
    skeleton: Color(0xFFE9EDF3),
    shadow: Color(0x14101C32),
  );

  static const dark = DaryobPalette(
    lime: DaryobColors.lime,
    onLime: DaryobColors.navy,
    navy: DaryobColors.darkSurfaceHigh,
    onNavy: DaryobColors.darkTextPrimary,
    textSecondary: DaryobColors.darkTextSecondary,
    border: DaryobColors.darkBorder,
    success: Color(0xFF3CC48E),
    warning: Color(0xFFFFB547),
    surfaceMuted: DaryobColors.darkSurfaceHigh,
    limeSoft: Color(0xFF2A3A1E),
    skeleton: Color(0xFF1E2B45),
    shadow: Color(0x40000000),
  );

  @override
  DaryobPalette copyWith({
    Color? lime,
    Color? onLime,
    Color? navy,
    Color? onNavy,
    Color? textSecondary,
    Color? border,
    Color? success,
    Color? warning,
    Color? surfaceMuted,
    Color? limeSoft,
    Color? skeleton,
    Color? shadow,
  }) {
    return DaryobPalette(
      lime: lime ?? this.lime,
      onLime: onLime ?? this.onLime,
      navy: navy ?? this.navy,
      onNavy: onNavy ?? this.onNavy,
      textSecondary: textSecondary ?? this.textSecondary,
      border: border ?? this.border,
      success: success ?? this.success,
      warning: warning ?? this.warning,
      surfaceMuted: surfaceMuted ?? this.surfaceMuted,
      limeSoft: limeSoft ?? this.limeSoft,
      skeleton: skeleton ?? this.skeleton,
      shadow: shadow ?? this.shadow,
    );
  }

  @override
  DaryobPalette lerp(DaryobPalette? other, double t) {
    if (other == null) return this;
    return DaryobPalette(
      lime: Color.lerp(lime, other.lime, t)!,
      onLime: Color.lerp(onLime, other.onLime, t)!,
      navy: Color.lerp(navy, other.navy, t)!,
      onNavy: Color.lerp(onNavy, other.onNavy, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      border: Color.lerp(border, other.border, t)!,
      success: Color.lerp(success, other.success, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      surfaceMuted: Color.lerp(surfaceMuted, other.surfaceMuted, t)!,
      limeSoft: Color.lerp(limeSoft, other.limeSoft, t)!,
      skeleton: Color.lerp(skeleton, other.skeleton, t)!,
      shadow: Color.lerp(shadow, other.shadow, t)!,
    );
  }
}

extension DaryobThemeX on BuildContext {
  ThemeData get theme => Theme.of(this);
  TextTheme get text => Theme.of(this).textTheme;
  ColorScheme get colors => Theme.of(this).colorScheme;
  DaryobPalette get palette =>
      Theme.of(this).extension<DaryobPalette>() ?? DaryobPalette.light;
}
