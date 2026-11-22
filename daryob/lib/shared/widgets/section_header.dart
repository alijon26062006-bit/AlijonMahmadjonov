import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';

class DaryobSectionHeader extends StatelessWidget {
  const DaryobSectionHeader({
    super.key,
    required this.title,
    this.onSeeAll,
    this.padding = const EdgeInsets.fromLTRB(
      DaryobSpacing.page,
      DaryobSpacing.xxl,
      DaryobSpacing.sm,
      DaryobSpacing.md,
    ),
    this.leading,
  });

  final String title;
  final VoidCallback? onSeeAll;
  final EdgeInsets padding;
  final Widget? leading;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Row(
        children: [
          if (leading != null) ...[
            leading!,
            const SizedBox(width: DaryobSpacing.sm),
          ],
          Expanded(
            child: Semantics(
              header: true,
              child: Text(title, style: context.text.titleLarge),
            ),
          ),
          if (onSeeAll != null)
            TextButton(onPressed: onSeeAll, child: Text(context.l10n.seeAll)),
        ],
      ),
    );
  }
}
