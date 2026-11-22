import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';

/// Large rounded search field. With [onTap] it is a button that opens the
/// search screen; with [controller] it is an editable field.
class DaryobSearchBar extends StatelessWidget {
  const DaryobSearchBar({
    super.key,
    this.onTap,
    this.controller,
    this.focusNode,
    this.onChanged,
    this.onSubmitted,
    this.onFilterTap,
    this.activeFilters = 0,
    this.autofocus = false,
  });

  final VoidCallback? onTap;
  final TextEditingController? controller;
  final FocusNode? focusNode;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final VoidCallback? onFilterTap;
  final int activeFilters;
  final bool autofocus;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final palette = context.palette;
    final editable = controller != null;

    final field = editable
        ? TextField(
            controller: controller,
            focusNode: focusNode,
            autofocus: autofocus,
            onChanged: onChanged,
            onSubmitted: onSubmitted,
            textInputAction: TextInputAction.search,
            style: context.text.bodyLarge,
            decoration: InputDecoration(
              hintText: l10n.searchHint,
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              filled: false,
              isDense: true,
              contentPadding: EdgeInsets.zero,
            ),
          )
        : Text(
            l10n.searchHint,
            style: context.text.bodyLarge?.copyWith(
              color: palette.textSecondary,
            ),
            overflow: TextOverflow.ellipsis,
          );

    return Semantics(
      button: !editable,
      label: editable ? null : l10n.searchHint,
      child: Material(
        color: context.colors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: DaryobRadius.inputAll,
          side: BorderSide(color: palette.border),
        ),
        child: InkWell(
          borderRadius: DaryobRadius.inputAll,
          onTap: editable ? null : onTap,
          child: SizedBox(
            height: DaryobSizes.inputHeight,
            child: Row(
              children: [
                const SizedBox(width: DaryobSpacing.lg),
                Icon(Icons.search_rounded, color: palette.textSecondary),
                const SizedBox(width: DaryobSpacing.md),
                Expanded(child: field),
                if (editable && (controller!.text.isNotEmpty))
                  IconButton(
                    tooltip: l10n.clear,
                    icon: const Icon(Icons.close_rounded),
                    onPressed: () {
                      controller!.clear();
                      onChanged?.call('');
                    },
                  ),
                if (onFilterTap != null)
                  _FilterButton(onTap: onFilterTap!, count: activeFilters),
                const SizedBox(width: DaryobSpacing.xs),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _FilterButton extends StatelessWidget {
  const _FilterButton({required this.onTap, required this.count});
  final VoidCallback onTap;
  final int count;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: context.l10n.filters,
      onPressed: onTap,
      icon: Badge(
        isLabelVisible: count > 0,
        label: Text('$count'),
        backgroundColor: DaryobColors.lime,
        textColor: DaryobColors.navy,
        child: const Icon(Icons.tune_rounded),
      ),
    );
  }
}
