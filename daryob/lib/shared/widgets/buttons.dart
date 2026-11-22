import 'package:material_ui/material_ui.dart';

import '../../app/theme/tokens.dart';

enum DaryobButtonTone {
  /// Navy in light theme, lime in dark theme.
  primary,

  /// Lime with navy text — the brand call to action.
  accent,
}

class DaryobPrimaryButton extends StatelessWidget {
  const DaryobPrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
    this.tone = DaryobButtonTone.primary,
    this.expand = true,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isLoading;
  final DaryobButtonTone tone;
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final accent = tone == DaryobButtonTone.accent;
    final style = accent
        ? FilledButton.styleFrom(
            backgroundColor: DaryobColors.lime,
            foregroundColor: DaryobColors.navy,
            disabledBackgroundColor: DaryobColors.lime.withValues(alpha: 0.45),
            disabledForegroundColor: DaryobColors.navy.withValues(alpha: 0.6),
          )
        : null;
    final fg = accent ? DaryobColors.navy : context.colors.onPrimary;

    final child = isLoading
        ? SizedBox.square(
            dimension: 22,
            child: CircularProgressIndicator(strokeWidth: 2.4, color: fg),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: DaryobSizes.iconMd),
                const SizedBox(width: DaryobSpacing.sm),
              ],
              Flexible(child: Text(label, overflow: TextOverflow.ellipsis)),
            ],
          );

    final button = FilledButton(
      onPressed: isLoading ? null : onPressed,
      style: style,
      child: child,
    );
    return expand ? SizedBox(width: double.infinity, child: button) : button;
  }
}

class DaryobSecondaryButton extends StatelessWidget {
  const DaryobSecondaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.expand = true,
    this.destructive = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool expand;
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    final color = destructive ? context.colors.error : null;
    final button = OutlinedButton(
      onPressed: onPressed,
      style: destructive
          ? OutlinedButton.styleFrom(
              foregroundColor: color,
              side: BorderSide(
                color: context.colors.error.withValues(alpha: 0.5),
              ),
            )
          : null,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: DaryobSizes.iconMd),
            const SizedBox(width: DaryobSpacing.sm),
          ],
          Flexible(child: Text(label, overflow: TextOverflow.ellipsis)),
        ],
      ),
    );
    return expand ? SizedBox(width: double.infinity, child: button) : button;
  }
}

/// Round icon button with a visible surface, used over photos.
class DaryobCircleButton extends StatelessWidget {
  const DaryobCircleButton({
    super.key,
    required this.icon,
    required this.onPressed,
    required this.tooltip,
    this.color,
    this.background,
    this.size = 40,
  });

  final IconData icon;
  final VoidCallback? onPressed;
  final String tooltip;
  final Color? color;
  final Color? background;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Material(
        color: background ?? context.colors.surface.withValues(alpha: 0.92),
        shape: const CircleBorder(),
        elevation: 0,
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: onPressed,
          child: SizedBox.square(
            // Keep a 48px touch area even when the circle is smaller.
            dimension: size < DaryobSizes.touch ? size : size,
            child: Icon(
              icon,
              size: size * 0.5,
              color: color ?? context.colors.onSurface,
            ),
          ),
        ),
      ),
    );
  }
}
