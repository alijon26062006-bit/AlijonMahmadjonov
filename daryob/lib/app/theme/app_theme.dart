import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'tokens.dart';

const String kFontFamily = 'Inter';

abstract final class DaryobTheme {
  static ThemeData light() => _build(
    brightness: Brightness.light,
    palette: DaryobPalette.light,
    scheme: const ColorScheme(
      brightness: Brightness.light,
      primary: DaryobColors.navy,
      onPrimary: Colors.white,
      secondary: DaryobColors.lime,
      onSecondary: DaryobColors.navy,
      error: DaryobColors.error,
      onError: Colors.white,
      surface: DaryobColors.surface,
      onSurface: DaryobColors.textPrimary,
      onSurfaceVariant: DaryobColors.textSecondary,
      surfaceContainerLowest: DaryobColors.surface,
      surfaceContainerLow: DaryobColors.background,
      surfaceContainer: DaryobColors.background,
      surfaceContainerHigh: DaryobColors.navySoft,
      surfaceContainerHighest: DaryobColors.navySoft,
      outline: DaryobColors.border,
      outlineVariant: DaryobColors.border,
    ),
    background: DaryobColors.background,
  );

  static ThemeData dark() => _build(
    brightness: Brightness.dark,
    palette: DaryobPalette.dark,
    scheme: const ColorScheme(
      brightness: Brightness.dark,
      primary: DaryobColors.lime,
      onPrimary: DaryobColors.navy,
      secondary: DaryobColors.lime,
      onSecondary: DaryobColors.navy,
      error: DaryobColors.darkError,
      onError: DaryobColors.navy,
      surface: DaryobColors.darkSurface,
      onSurface: DaryobColors.darkTextPrimary,
      onSurfaceVariant: DaryobColors.darkTextSecondary,
      surfaceContainerLowest: DaryobColors.darkBackground,
      surfaceContainerLow: DaryobColors.darkBackground,
      surfaceContainer: DaryobColors.darkSurface,
      surfaceContainerHigh: DaryobColors.darkSurfaceHigh,
      surfaceContainerHighest: DaryobColors.darkSurfaceHigh,
      outline: DaryobColors.darkBorder,
      outlineVariant: DaryobColors.darkBorder,
    ),
    background: DaryobColors.darkBackground,
  );

  static TextTheme _textTheme(Color primary, Color secondary) {
    TextStyle s(double size, FontWeight w, double height, [Color? c]) =>
        TextStyle(
          fontFamily: kFontFamily,
          fontSize: size,
          fontWeight: w,
          height: height,
          color: c ?? primary,
          letterSpacing: size >= 22 ? -0.4 : 0,
        );
    return TextTheme(
      displaySmall: s(30, FontWeight.w800, 1.15),
      headlineMedium: s(26, FontWeight.w800, 1.2),
      headlineSmall: s(22, FontWeight.w700, 1.25),
      titleLarge: s(18, FontWeight.w700, 1.3),
      titleMedium: s(16, FontWeight.w600, 1.35),
      titleSmall: s(14, FontWeight.w600, 1.35),
      bodyLarge: s(16, FontWeight.w400, 1.5),
      bodyMedium: s(14, FontWeight.w400, 1.45),
      bodySmall: s(12.5, FontWeight.w400, 1.4, secondary),
      labelLarge: s(15, FontWeight.w600, 1.2),
      labelMedium: s(13, FontWeight.w600, 1.2),
      labelSmall: s(11.5, FontWeight.w600, 1.2, secondary),
    );
  }

  static ThemeData _build({
    required Brightness brightness,
    required DaryobPalette palette,
    required ColorScheme scheme,
    required Color background,
  }) {
    final text = _textTheme(scheme.onSurface, palette.textSecondary);
    final isDark = brightness == Brightness.dark;
    final inputBorder = OutlineInputBorder(
      borderRadius: DaryobRadius.inputAll,
      borderSide: BorderSide(color: palette.border),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      fontFamily: kFontFamily,
      textTheme: text,
      scaffoldBackgroundColor: background,
      canvasColor: background,
      extensions: [palette],
      splashFactory: InkSparkle.splashFactory,
      appBarTheme: AppBarTheme(
        backgroundColor: background,
        foregroundColor: scheme.onSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        centerTitle: false,
        titleTextStyle: text.titleLarge,
        systemOverlayStyle: isDark
            ? SystemUiOverlayStyle.light
            : SystemUiOverlayStyle.dark,
      ),
      cardTheme: CardThemeData(
        color: scheme.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: DaryobRadius.cardAll,
          side: BorderSide(color: palette.border),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: palette.border,
        thickness: 1,
        space: 1,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: DaryobSpacing.lg,
          vertical: DaryobSpacing.md + 2,
        ),
        hintStyle: text.bodyMedium?.copyWith(color: palette.textSecondary),
        labelStyle: text.bodyMedium?.copyWith(color: palette.textSecondary),
        floatingLabelStyle: text.bodyMedium?.copyWith(color: scheme.onSurface),
        border: inputBorder,
        enabledBorder: inputBorder,
        focusedBorder: inputBorder.copyWith(
          borderSide: BorderSide(
            color: isDark ? DaryobColors.lime : DaryobColors.navy,
            width: 1.6,
          ),
        ),
        errorBorder: inputBorder.copyWith(
          borderSide: BorderSide(color: scheme.error),
        ),
        focusedErrorBorder: inputBorder.copyWith(
          borderSide: BorderSide(color: scheme.error, width: 1.6),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(DaryobSizes.buttonHeight),
          shape: const RoundedRectangleBorder(
            borderRadius: DaryobRadius.buttonAll,
          ),
          textStyle: text.labelLarge,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(DaryobSizes.buttonHeight),
          shape: const RoundedRectangleBorder(
            borderRadius: DaryobRadius.buttonAll,
          ),
          side: BorderSide(color: palette.border, width: 1.4),
          foregroundColor: scheme.onSurface,
          textStyle: text.labelLarge,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: isDark ? DaryobColors.lime : DaryobColors.navy,
          textStyle: text.labelMedium,
          minimumSize: const Size(DaryobSizes.touch, DaryobSizes.touch),
        ),
      ),
      chipTheme: ChipThemeData(
        shape: const RoundedRectangleBorder(borderRadius: DaryobRadius.chipAll),
        side: BorderSide(color: palette.border),
        backgroundColor: scheme.surface,
        selectedColor: DaryobColors.lime,
        labelStyle: text.labelMedium,
        secondaryLabelStyle: text.labelMedium?.copyWith(
          color: DaryobColors.navy,
        ),
        checkmarkColor: DaryobColors.navy,
        padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.sm),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: scheme.surface,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        dragHandleColor: palette.border,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(DaryobRadius.sheet),
          ),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: scheme.surface,
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(borderRadius: DaryobRadius.cardAll),
        titleTextStyle: text.titleLarge,
        contentTextStyle: text.bodyMedium,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: isDark
            ? DaryobColors.darkSurfaceHigh
            : DaryobColors.navy,
        contentTextStyle: text.bodyMedium?.copyWith(color: Colors.white),
        shape: const RoundedRectangleBorder(
          borderRadius: DaryobRadius.buttonAll,
        ),
      ),
      listTileTheme: ListTileThemeData(
        iconColor: scheme.onSurface,
        titleTextStyle: text.titleSmall,
        subtitleTextStyle: text.bodySmall,
        minVerticalPadding: DaryobSpacing.md,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: DaryobSpacing.lg,
        ),
      ),
      // Off state uses visible greys so the switch never looks disabled.
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected)
              ? DaryobColors.navy
              : palette.textSecondary,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected)
              ? DaryobColors.lime
              : palette.surfaceMuted,
        ),
        trackOutlineColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected)
              ? DaryobColors.lime
              : palette.textSecondary.withValues(alpha: 0.5),
        ),
      ),
      tabBarTheme: TabBarThemeData(
        labelStyle: text.labelMedium,
        unselectedLabelStyle: text.labelMedium,
        labelColor: scheme.onSurface,
        unselectedLabelColor: palette.textSecondary,
        indicatorColor: isDark ? DaryobColors.lime : DaryobColors.navy,
        dividerColor: palette.border,
        tabAlignment: TabAlignment.start,
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: isDark ? DaryobColors.lime : DaryobColors.navy,
      ),
    );
  }
}
