import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../models/listing.dart';

enum BadgeTone { neutral, success, warning, danger, lime, navy }

class DaryobStatusBadge extends StatelessWidget {
  const DaryobStatusBadge({
    super.key,
    required this.label,
    this.tone = BadgeTone.neutral,
    this.icon,
  });

  final String label;
  final BadgeTone tone;
  final IconData? icon;

  factory DaryobStatusBadge.forStatus(
    BuildContext context,
    ListingStatus status,
  ) {
    final tone = switch (status) {
      ListingStatus.active => BadgeTone.success,
      ListingStatus.pending => BadgeTone.warning,
      ListingStatus.rejected => BadgeTone.danger,
      ListingStatus.sold => BadgeTone.navy,
      ListingStatus.draft || ListingStatus.archived => BadgeTone.neutral,
    };
    return DaryobStatusBadge(
      label: statusLabel(context.l10n, status),
      tone: tone,
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = context.palette;
    final (bg, fg) = switch (tone) {
      BadgeTone.neutral => (palette.surfaceMuted, context.colors.onSurface),
      BadgeTone.success => (
        palette.success.withValues(alpha: 0.14),
        palette.success,
      ),
      BadgeTone.warning => (
        palette.warning.withValues(alpha: 0.16),
        const Color(0xFF8A5A00),
      ),
      BadgeTone.danger => (
        context.colors.error.withValues(alpha: 0.12),
        context.colors.error,
      ),
      BadgeTone.lime => (DaryobColors.lime, DaryobColors.navy),
      BadgeTone.navy => (DaryobColors.navy, Colors.white),
    };
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final fgColor = tone == BadgeTone.warning && isDark ? palette.warning : fg;

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: DaryobSpacing.sm,
        vertical: 3,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: fgColor),
            const SizedBox(width: 3),
          ],
          Text(
            label,
            style: context.text.labelSmall?.copyWith(
              color: fgColor,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }
}

/// Marks sample data in development builds.
class DemoBadge extends StatelessWidget {
  const DemoBadge({super.key});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: context.l10n.demoBadgeDescription,
      child: const DaryobStatusBadge(label: 'DEMO', tone: BadgeTone.warning),
    );
  }
}

class PromotionBadge extends StatelessWidget {
  const PromotionBadge({super.key, required this.type});
  final PromotionType type;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return switch (type) {
      PromotionType.vip || PromotionType.vipPlus => DaryobStatusBadge(
        label: promotionLabel(l10n, type),
        tone: BadgeTone.lime,
        icon: Icons.star_rounded,
      ),
      PromotionType.top => DaryobStatusBadge(
        label: l10n.promoTop,
        tone: BadgeTone.navy,
        icon: Icons.arrow_upward_rounded,
      ),
      _ => const SizedBox.shrink(),
    };
  }
}
