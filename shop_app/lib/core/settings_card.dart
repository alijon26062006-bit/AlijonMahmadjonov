import 'package:material_ui/material_ui.dart';

import 'store.dart';
import 'theme.dart';
import 'widgets.dart';

/// Пункт настроек.
class SettingsTile extends StatelessWidget {
  const SettingsTile({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.onTap,
    this.danger = false,
    this.trailing,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;
  final bool danger;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final color = danger ? kDanger : c.text;
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: danger ? kDanger : c.accentText),
      title: Text(
        title,
        style: TextStyle(fontWeight: FontWeight.w600, color: color),
      ),
      subtitle: subtitle == null ? null : Text(subtitle!, style: TextStyle(color: c.muted, fontSize: 12.5)),
      trailing: trailing ?? (onTap == null ? null : Icon(Icons.chevron_right_rounded, color: c.muted)),
    );
  }
}

/// Общие настройки для всех приложений: тема, тестовый режим, выход.
class CommonSettings extends StatelessWidget {
  const CommonSettings({super.key, this.extra = const [], this.showLogout = true});

  final List<Widget> extra;
  final bool showLogout;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), boxShadow: c.cardShadow),
      child: Material(
        color: c.surface,
        borderRadius: BorderRadius.circular(20),
        clipBehavior: Clip.antiAlias,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Тема оформления',
                    style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    width: double.infinity,
                    child: SegmentedButton<ThemeMode>(
                      showSelectedIcon: false,
                      segments: const [
                        ButtonSegment(value: ThemeMode.light, label: Text('Светлая')),
                        ButtonSegment(value: ThemeMode.dark, label: Text('Тёмная')),
                        ButtonSegment(value: ThemeMode.system, label: Text('Авто')),
                      ],
                      selected: {s.themeMode},
                      onSelectionChanged: (v) => s.setThemeMode(v.first),
                    ),
                  ),
                ],
              ),
            ),
            for (final w in extra) ...[const Divider(indent: 16, endIndent: 16), w],
            const Divider(indent: 16, endIndent: 16),
            SwitchListTile(
              value: s.demoLive,
              onChanged: s.setDemoLive,
              secondary: Icon(Icons.science_outlined, color: c.accentText),
              title: Text(
                'Тестовый режим',
                style: TextStyle(fontWeight: FontWeight.w600, color: c.text),
              ),
              subtitle: Text(
                'Пока нет сервера, новые заказы и смена статусов происходят сами',
                style: TextStyle(color: c.muted, fontSize: 12.5),
              ),
            ),
            const Divider(indent: 16, endIndent: 16),
            SettingsTile(
              icon: Icons.restart_alt_rounded,
              title: 'Сбросить тестовые данные',
              onTap: () async {
                if (await confirm(
                  context,
                  title: 'Сбросить тестовые данные?',
                  text: 'Магазины, товары и заказы вернутся к начальным.',
                  ok: 'Сбросить',
                )) {
                  s.resetDemo();
                  if (context.mounted) showSnack(context, 'Тестовые данные сброшены');
                }
              },
            ),
            if (showLogout && s.user != null) ...[
              const Divider(indent: 16, endIndent: 16),
              SettingsTile(
                icon: Icons.logout_rounded,
                title: 'Выйти',
                danger: true,
                onTap: () async {
                  if (await confirm(context, title: 'Выйти из аккаунта?', ok: 'Выйти', danger: true)) s.logout();
                },
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Шапка профиля с градиентом.
class ProfileHeader extends StatelessWidget {
  const ProfileHeader({
    super.key,
    required this.title,
    required this.subtitle,
    required this.avatar,
    this.stats = const [],
    this.action,
  });

  final String title;
  final String subtitle;
  final String avatar;
  final List<(String, String)> stats;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 0),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: c.headerGradient,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: c.accent.withValues(alpha: .33),
            blurRadius: 30,
            offset: const Offset(0, 14),
            spreadRadius: -12,
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 62,
                height: 62,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: const Color(0x33FFFFFF),
                  shape: BoxShape.circle,
                  border: Border.all(color: const Color(0x66FFFFFF), width: 2),
                ),
                child: avatar.isEmpty
                    ? const Icon(Icons.person_rounded, color: Colors.white, size: 32)
                    : Text(
                        avatar,
                        style: const TextStyle(fontSize: 26, color: Colors.white, fontWeight: FontWeight.w800),
                      ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white, fontSize: 21, fontWeight: FontWeight.w800),
                    ),
                    Text(subtitle, style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 14)),
                  ],
                ),
              ),
              ?action,
            ],
          ),
          if (stats.isNotEmpty) ...[
            const SizedBox(height: 18),
            Row(
              children: [
                for (var i = 0; i < stats.length; i++) ...[
                  if (i > 0) const SizedBox(width: 10),
                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
                      decoration: BoxDecoration(
                        color: const Color(0x29FFFFFF),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Column(
                        children: [
                          FittedBox(
                            child: Text(
                              stats[i].$1,
                              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800),
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            stats[i].$2,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(color: Color(0xCCFFFFFF), fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }
}
