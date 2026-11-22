import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../../core/errors/failure.dart';
import 'buttons.dart';

class DaryobEmptyState extends StatelessWidget {
  const DaryobEmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.actionLabel,
    this.onAction,
    this.compact = false,
  });

  final IconData icon;
  final String title;
  final String? message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: DaryobSpacing.xxxl,
          vertical: compact ? DaryobSpacing.xxl : DaryobSpacing.huge,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: compact ? 64 : 88,
              height: compact ? 64 : 88,
              decoration: BoxDecoration(
                color: context.palette.limeSoft,
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                size: compact ? 30 : 40,
                color: Theme.of(context).brightness == Brightness.dark
                    ? DaryobColors.lime
                    : DaryobColors.navy,
              ),
            ),
            const SizedBox(height: DaryobSpacing.lg),
            Text(
              title,
              textAlign: TextAlign.center,
              style: context.text.titleMedium,
            ),
            if (message != null) ...[
              const SizedBox(height: DaryobSpacing.sm),
              Text(
                message!,
                textAlign: TextAlign.center,
                style: context.text.bodyMedium?.copyWith(
                  color: context.palette.textSecondary,
                ),
              ),
            ],
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: DaryobSpacing.xl),
              DaryobPrimaryButton(
                label: actionLabel!,
                onPressed: onAction,
                expand: false,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Error with a localised explanation and a retry button.
class DaryobErrorState extends StatelessWidget {
  const DaryobErrorState({
    super.key,
    required this.error,
    this.onRetry,
    this.compact = false,
  });

  final Object error;
  final VoidCallback? onRetry;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final failure = asFailure(error);
    final unavailable = failure is FeatureUnavailableFailure;
    final icon = switch (failure) {
      NetworkFailure() || TimeoutFailure() => Icons.wifi_off_rounded,
      FeatureUnavailableFailure() => Icons.cloud_off_outlined,
      NotFoundFailure() => Icons.search_off_rounded,
      _ => Icons.error_outline_rounded,
    };
    return DaryobEmptyState(
      icon: icon,
      compact: compact,
      title: unavailable ? l10n.unavailableTitle : l10n.errTitle,
      message: failureMessage(l10n, failure),
      actionLabel: onRetry == null || unavailable ? null : l10n.retry,
      onAction: onRetry,
    );
  }
}

/// A plain information panel used for "not configured" notices.
class DaryobNotice extends StatelessWidget {
  const DaryobNotice({
    super.key,
    required this.message,
    this.icon = Icons.info_outline_rounded,
    this.tone = NoticeTone.info,
  });

  final String message;
  final IconData icon;
  final NoticeTone tone;

  @override
  Widget build(BuildContext context) {
    final palette = context.palette;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final (bg, fg) = switch (tone) {
      NoticeTone.info => (palette.surfaceMuted, context.colors.onSurface),
      NoticeTone.warning => (
        palette.warning.withValues(alpha: 0.14),
        isDark ? palette.warning : const Color(0xFF7A4F00),
      ),
      NoticeTone.brand => (palette.limeSoft, context.colors.onSurface),
    };
    return Container(
      padding: const EdgeInsets.all(DaryobSpacing.md),
      decoration: BoxDecoration(color: bg, borderRadius: DaryobRadius.inputAll),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: fg),
          const SizedBox(width: DaryobSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: context.text.bodyMedium?.copyWith(color: fg),
            ),
          ),
        ],
      ),
    );
  }
}

enum NoticeTone { info, warning, brand }
