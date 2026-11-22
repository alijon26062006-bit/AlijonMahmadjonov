import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';

/// Hosts the five tabs. Each tab keeps its own navigation stack and scroll
/// position (StatefulShellRoute.indexedStack).
class MainShell extends ConsumerWidget {
  const MainShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: DaryobBottomNavigation(
        currentIndex: navigationShell.currentIndex,
        onSelect: (index) => navigationShell.goBranch(
          index,
          // Tapping the active tab again returns it to its first screen.
          initialLocation: index == navigationShell.currentIndex,
        ),
      ),
    );
  }
}

class DaryobBottomNavigation extends StatelessWidget {
  const DaryobBottomNavigation({
    super.key,
    required this.currentIndex,
    required this.onSelect,
  });

  final int currentIndex;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final items = [
      (Icons.home_outlined, Icons.home_rounded, l10n.tabHome),
      (
        Icons.favorite_border_rounded,
        Icons.favorite_rounded,
        l10n.tabFavorites,
      ),
      (Icons.add_rounded, Icons.add_rounded, l10n.tabCreate),
      (
        Icons.chat_bubble_outline_rounded,
        Icons.chat_bubble_rounded,
        l10n.tabChats,
      ),
      (Icons.person_outline_rounded, Icons.person_rounded, l10n.tabProfile),
    ];

    return DecoratedBox(
      decoration: BoxDecoration(
        color: context.colors.surface,
        border: Border(top: BorderSide(color: context.palette.border)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: DaryobSizes.bottomBar,
          child: Row(
            children: [
              for (var i = 0; i < items.length; i++)
                Expanded(
                  child: i == 2
                      ? _CreateButton(
                          label: items[i].$3,
                          selected: currentIndex == i,
                          onTap: () => onSelect(i),
                        )
                      : _NavItem(
                          icon: currentIndex == i ? items[i].$2 : items[i].$1,
                          label: items[i].$3,
                          selected: currentIndex == i,
                          onTap: () => onSelect(i),
                        ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final active = isDark ? DaryobColors.lime : DaryobColors.navy;
    final color = selected ? active : context.palette.textSecondary;
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      excludeSemantics: true,
      child: InkResponse(
        onTap: onTap,
        radius: 36,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: DaryobDurations.fast,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 3),
              decoration: BoxDecoration(
                color: selected ? context.palette.limeSoft : Colors.transparent,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: context.text.labelSmall?.copyWith(
                color: color,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CreateButton extends StatelessWidget {
  const _CreateButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      excludeSemantics: true,
      child: InkResponse(
        onTap: onTap,
        radius: 36,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 46,
              height: 34,
              decoration: BoxDecoration(
                color: DaryobColors.lime,
                borderRadius: BorderRadius.circular(12),
                border: selected
                    ? Border.all(color: DaryobColors.navy, width: 2)
                    : null,
              ),
              child: const Icon(
                Icons.add_rounded,
                color: DaryobColors.navy,
                size: 26,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: context.text.labelSmall?.copyWith(
                color: context.colors.onSurface,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
