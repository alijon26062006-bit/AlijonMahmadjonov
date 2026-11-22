import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/theme/tokens.dart';
import '../../features/settings/application/settings_controller.dart';

/// Language names are always written in their own language.
const languageNames = {'tg': 'Тоҷикӣ', 'ru': 'Русский'};

class DaryobLanguageSelector extends ConsumerWidget {
  const DaryobLanguageSelector({super.key, this.onSelected});

  final ValueChanged<String>? onSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = Localizations.localeOf(context).languageCode;
    return Column(
      children: [
        for (final entry in languageNames.entries)
          Padding(
            padding: const EdgeInsets.only(bottom: DaryobSpacing.md),
            child: _LanguageOption(
              code: entry.key,
              name: entry.value,
              selected: current == entry.key,
              onTap: () {
                ref
                    .read(settingsControllerProvider.notifier)
                    .setLanguage(entry.key);
                onSelected?.call(entry.key);
              },
            ),
          ),
      ],
    );
  }
}

class _LanguageOption extends StatelessWidget {
  const _LanguageOption({
    required this.code,
    required this.name,
    required this.selected,
    required this.onTap,
  });

  final String code;
  final String name;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Semantics(
      selected: selected,
      button: true,
      child: Material(
        color: selected ? context.palette.limeSoft : context.colors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: DaryobRadius.cardAll,
          side: BorderSide(
            color: selected
                ? (isDark ? DaryobColors.lime : DaryobColors.navy)
                : context.palette.border,
            width: selected ? 2 : 1,
          ),
        ),
        child: InkWell(
          borderRadius: DaryobRadius.cardAll,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: DaryobSpacing.lg,
              vertical: DaryobSpacing.lg,
            ),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: DaryobColors.navy,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    code.toUpperCase(),
                    style: const TextStyle(
                      color: DaryobColors.lime,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(width: DaryobSpacing.lg),
                Expanded(child: Text(name, style: context.text.titleMedium)),
                Icon(
                  selected
                      ? Icons.radio_button_checked_rounded
                      : Icons.radio_button_off_rounded,
                  color: selected
                      ? (isDark ? DaryobColors.lime : DaryobColors.navy)
                      : context.palette.textSecondary,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
