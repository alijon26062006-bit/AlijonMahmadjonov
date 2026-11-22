import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/router/routes.dart';
import '../../app/theme/tokens.dart';
import '../../core/utils/formatters.dart';
import '../../shared/models/category.dart';
import '../../shared/models/listing.dart';
import '../../shared/models/localized_text.dart';
import '../../shared/providers/core_providers.dart';
import '../../shared/widgets/dialogs.dart';
import '../../shared/widgets/listing_image.dart';
import '../../shared/widgets/states.dart';
import '../../shared/widgets/toast.dart';
import '../catalog/presentation/catalog_ui.dart';
import '../conversations/domain/conversation.dart';
import '../support/support.dart';
import 'admin_repository.dart';

// The admin panel is for the DARYOB team and is in Russian only.

String _dateTime(DateTime d) => '${Formatters.date(d)} ${Formatters.time(d)}';

Future<void> _run(BuildContext context, Future<void> Function() action, String done) async {
  try {
    await action();
    if (context.mounted) DaryobToast.show(context, done);
  } catch (e) {
    if (context.mounted) DaryobToast.show(context, failureMessage(context.l10n, e));
  }
}

Widget _chip(BuildContext context, String text, Color color) => Container(
  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
  decoration: BoxDecoration(color: color.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(6)),
  child: Text(text, style: context.text.labelSmall?.copyWith(color: color, fontWeight: FontWeight.w700)),
);

Color _statusColor(BuildContext context, ListingStatus s) => switch (s) {
  ListingStatus.active => context.palette.success,
  ListingStatus.pending => const Color(0xFFB7791F),
  ListingStatus.rejected => context.colors.error,
  _ => context.palette.textSecondary,
};

const _statusRu = {
  ListingStatus.active: 'Опубликовано',
  ListingStatus.pending: 'На проверке',
  ListingStatus.rejected: 'Отклонено',
  ListingStatus.archived: 'В архиве',
  ListingStatus.sold: 'Продано',
  ListingStatus.draft: 'Черновик',
};

/// Gate for every admin screen.
class _StaffOnly extends ConsumerWidget {
  const _StaffOnly({required this.builder});
  final Widget Function(String role) builder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final role = ref.watch(staffRoleProvider);
    return role.when(
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(appBar: AppBar(), body: DaryobErrorState(error: e)),
      data: (r) => r == null
          ? Scaffold(
              appBar: AppBar(),
              body: const DaryobEmptyState(
                icon: Icons.lock_outline_rounded,
                title: 'Нет доступа',
                message: 'Админ-панель доступна только сотрудникам DARYOB.',
              ),
            )
          : builder(r),
    );
  }
}

// ── Dashboard ───────────────────────────────────────────────────────────

final _statsProvider = FutureProvider.autoDispose<Map<String, dynamic>>(
  (ref) => ref.watch(adminRepositoryProvider)!.stats(),
);
final _settingsProvider = FutureProvider.autoDispose<Map<String, dynamic>>(
  (ref) => ref.watch(adminRepositoryProvider)!.settings(),
);

class AdminHomeScreen extends ConsumerWidget {
  const AdminHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _StaffOnly(builder: (role) {
      final stats = ref.watch(_statsProvider);
      final settings = ref.watch(_settingsProvider).value;
      final ai = settings?['ai_status'] as Map?;
      final aiMissing = ai == null || ai['ai_configured'] == false;
      int n(String key) => ((stats.value ?? const {})[key] as num?)?.toInt() ?? 0;
      void open(Widget screen) => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen)).then((_) {
        ref.invalidate(_statsProvider);
      });

      final tiles = <(String, int, IconData, Color, Widget)>[
        ('На проверке', n('listings_pending'), Icons.fact_check_outlined, const Color(0xFFB7791F), const AdminModerationScreen()),
        ('Жалобы', n('reports_open'), Icons.flag_outlined, context.colors.error, const AdminReportsScreen()),
        ('Обращения', n('tickets_open'), Icons.support_agent_rounded, const Color(0xFF2457C5), const AdminSupportScreen()),
        ('Подозрительные сообщения', n('flags_open'), Icons.shield_outlined, const Color(0xFFC2327A), const AdminFlagsScreen()),
        ('Активные объявления', n('listings_active'), Icons.storefront_outlined, context.palette.success, const AdminModerationScreen(initialTab: 2)),
        ('Пользователи', n('users'), Icons.people_outline_rounded, context.palette.textSecondary, const AdminUsersScreen()),
      ];

      return Scaffold(
        appBar: AppBar(
          title: Text(context.l10n.adminPanel),
          actions: [
            IconButton(
              tooltip: 'Обновить',
              icon: const Icon(Icons.refresh_rounded),
              onPressed: () {
                ref.invalidate(_statsProvider);
                ref.invalidate(_settingsProvider);
              },
            ),
          ],
        ),
        body: RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(_settingsProvider);
            ref.invalidate(_statsProvider);
            await ref.read(_statsProvider.future);
          },
          child: ListView(
            padding: const EdgeInsets.all(DaryobSpacing.page),
            children: [
              Text('Роль: ${_roleRu(role)}', style: context.text.bodySmall),
              const SizedBox(height: DaryobSpacing.md),
              if (aiMissing)
                const Padding(
                  padding: EdgeInsets.only(bottom: DaryobSpacing.md),
                  child: DaryobNotice(
                    tone: NoticeTone.warning,
                    message: 'AI-модерация не работает: ключ OpenAI не добавлен в секреты Supabase '
                        '(OPENAI_API_KEY). Новые объявления ждут ручной проверки.',
                  ),
                )
              else if (ai['last_error'] != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: DaryobSpacing.md),
                  child: DaryobNotice(tone: NoticeTone.warning, message: 'Последняя ошибка AI: ${ai['last_error']}'),
                ),
              if (stats.hasError) DaryobErrorState(error: stats.error!, compact: true),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: DaryobSpacing.sm,
                crossAxisSpacing: DaryobSpacing.sm,
                childAspectRatio: 1.7,
                children: [
                  for (final t in tiles)
                    Material(
                      color: context.colors.surface,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                        side: BorderSide(color: context.palette.border),
                      ),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(14),
                        onTap: () => open(t.$5),
                        child: Padding(
                          padding: const EdgeInsets.all(DaryobSpacing.md),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Icon(t.$3, color: t.$4),
                              Text(
                                stats.isLoading ? '…' : '${t.$2}',
                                style: context.text.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
                              ),
                              Text(t.$1, maxLines: 1, overflow: TextOverflow.ellipsis, style: context.text.bodySmall),
                            ],
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: DaryobSpacing.md),
              Text(
                'Сегодня: ${n('users_today')} новых пользователей, ${n('listings_today')} объявлений, '
                '${n('messages_today')} сообщений. Отклонено всего: ${n('listings_rejected')}, '
                'заблокировано пользователей: ${n('users_blocked')}.',
                style: context.text.bodySmall,
              ),
              const SizedBox(height: DaryobSpacing.lg),
              _menu(context, Icons.fact_check_outlined, 'Модерация объявлений', () => open(const AdminModerationScreen())),
              _menu(context, Icons.flag_outlined, 'Жалобы', () => open(const AdminReportsScreen())),
              _menu(context, Icons.people_outline_rounded, 'Пользователи', () => open(const AdminUsersScreen())),
              _menu(context, Icons.support_agent_rounded, 'Техподдержка', () => open(const AdminSupportScreen())),
              _menu(context, Icons.shield_outlined, 'Проверка чатов', () => open(const AdminFlagsScreen())),
              _menu(context, Icons.tune_rounded, 'Настройки модерации', () => open(AdminSettingsScreen(isAdmin: role == 'admin'))),
              _menu(context, Icons.history_rounded, 'Журнал действий', () => open(const AdminAuditScreen())),
            ],
          ),
        ),
      );
    });
  }

  Widget _menu(BuildContext context, IconData icon, String title, VoidCallback onTap) => ListTile(
    contentPadding: EdgeInsets.zero,
    leading: Icon(icon),
    title: Text(title),
    trailing: const Icon(Icons.chevron_right_rounded),
    onTap: onTap,
  );
}

String _roleRu(String? role) => switch (role) {
  'admin' => 'администратор',
  'moderator' => 'модератор',
  'support' => 'поддержка',
  _ => 'нет',
};

// ── Moderation ──────────────────────────────────────────────────────────

final _listingsProvider = FutureProvider.autoDispose.family<List<AdminListing>, String>((ref, status) {
  return ref.watch(adminRepositoryProvider)!.listings(statuses: [status]);
});

class AdminModerationScreen extends ConsumerWidget {
  const AdminModerationScreen({super.key, this.initialTab = 0});
  final int initialTab;

  static const _tabs = [('pending', 'На проверке'), ('rejected', 'Отклонённые'), ('active', 'Активные')];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: _tabs.length,
      initialIndex: initialTab,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Модерация'),
          bottom: TabBar(tabs: [for (final t in _tabs) Tab(text: t.$2)]),
        ),
        body: TabBarView(
          children: [
            for (final t in _tabs)
              Consumer(
                builder: (context, ref, _) {
                  final value = ref.watch(_listingsProvider(t.$1));
                  return RefreshIndicator(
                    onRefresh: () => ref.refresh(_listingsProvider(t.$1).future),
                    child: value.when(
                      loading: () => const Center(child: CircularProgressIndicator()),
                      error: (e, _) => DaryobErrorState(error: e, onRetry: () => ref.invalidate(_listingsProvider(t.$1))),
                      data: (items) => items.isEmpty
                          ? ListView(children: const [DaryobEmptyState(icon: Icons.done_all_rounded, title: 'Пусто')])
                          : ListView.separated(
                              itemCount: items.length,
                              separatorBuilder: (_, _) => const Divider(height: 1),
                              itemBuilder: (_, i) => _AdminListingTile(item: items[i], onChanged: () => ref.invalidate(_listingsProvider(t.$1))),
                            ),
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }
}

String _aiSummary(Map<String, Object?>? m) {
  if (m == null) return 'AI: ещё не проверено';
  if (m['note'] == 'no_ai_key') return 'AI: нет ключа OpenAI';
  if (m['note'] == 'ai_error') return 'AI: ошибка проверки';
  final decision = switch (m['decision']) {
    'approve' => 'одобрить',
    'reject' => 'отклонить',
    _ => 'на усмотрение модератора',
  };
  final conf = (m['confidence'] as num?)?.toDouble();
  return 'AI: $decision${conf == null ? '' : ' (${(conf * 100).round()}%)'}';
}

class _AdminListingTile extends ConsumerWidget {
  const _AdminListingTile({required this.item, required this.onChanged});
  final AdminListing item;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = item.listing;
    final category = ref.watch(categoryRegistryProvider).byId(l.categoryId);
    final problems = (l.moderation?['problems'] as List?)?.cast<Map>() ?? const [];
    return ListTile(
      leading: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: SizedBox.square(
          dimension: 56,
          child: DaryobListingImage(
            source: l.photos.isEmpty ? null : l.photos.first,
            icon: category?.icon ?? CategoryIcon.generic,
            cacheWidth: 160,
          ),
        ),
      ),
      title: Text(l.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text(
        [
          '${listingPriceText(context, ref, l)} · ${category?.name.of(context) ?? l.categoryId}',
          '${item.ownerName ?? 'Без имени'} · ${_dateTime(l.updatedAt)}',
          _aiSummary(l.moderation),
          if (problems.isNotEmpty) '• ${problems.first['ru']}',
        ].join('\n'),
        maxLines: 4,
        overflow: TextOverflow.ellipsis,
      ),
      isThreeLine: true,
      onTap: () async {
        await context.push(Routes.adminListing(l.id));
        onChanged();
      },
    );
  }
}

final _adminListingProvider = FutureProvider.autoDispose.family<AdminListing?, String>(
  (ref, id) => ref.watch(adminRepositoryProvider)!.listing(id),
);

const _rejectPresets = [
  ('Фотографии не соответствуют товару', 'Суратҳо ба мол мувофиқ нестанд'),
  ('Выбрана неверная категория', 'Категорияи нодуруст интихоб шудааст'),
  ('Товар запрещён к продаже', 'Фурӯши ин мол манъ аст'),
  ('Подозрение на мошенничество', 'Гумони қаллобӣ'),
  ('Недостаточно информации о товаре', 'Маълумот дар бораи мол кифоя нест'),
  ('Повторное объявление', 'Эълони такрорӣ'),
  ('Контакты или ссылки в тексте/на фото', 'Тамос ё пайвандҳо дар матн/сурат'),
];

Future<(String, String?)?> _askRejectReason(BuildContext context) {
  final ru = TextEditingController();
  final tg = TextEditingController();
  return showDialog<(String, String?)>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Причина отклонения'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final p in _rejectPresets)
                  ActionChip(
                    label: Text(p.$1),
                    onPressed: () {
                      ru.text = p.$1;
                      tg.text = p.$2;
                    },
                  ),
              ],
            ),
            const SizedBox(height: DaryobSpacing.md),
            TextField(controller: ru, minLines: 2, maxLines: 4, decoration: const InputDecoration(labelText: 'Причина (русский)')),
            const SizedBox(height: DaryobSpacing.sm),
            TextField(controller: tg, minLines: 2, maxLines: 4, decoration: const InputDecoration(labelText: 'Причина (тоҷикӣ, необязательно)')),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Отмена')),
        FilledButton(
          onPressed: () {
            if (ru.text.trim().isEmpty) return;
            Navigator.pop(context, (ru.text.trim(), tg.text.trim().isEmpty ? null : tg.text.trim()));
          },
          child: const Text('Отклонить'),
        ),
      ],
    ),
  );
}

class AdminListingScreen extends ConsumerWidget {
  const AdminListingScreen({super.key, required this.listingId});
  final String listingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _StaffOnly(builder: (role) {
      final value = ref.watch(_adminListingProvider(listingId));
      final repo = ref.read(adminRepositoryProvider)!;
      void refresh() => ref.invalidate(_adminListingProvider(listingId));
      return Scaffold(
        appBar: AppBar(
          title: const Text('Объявление'),
          actions: [
            IconButton(
              tooltip: 'Открыть как покупатель',
              icon: const Icon(Icons.open_in_new_rounded),
              onPressed: () => context.push(Routes.listing(listingId)),
            ),
          ],
        ),
        body: value.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => DaryobErrorState(error: e, onRetry: refresh),
          data: (item) {
            if (item == null) return const DaryobEmptyState(icon: Icons.search_off_rounded, title: 'Объявление удалено');
            final l = item.listing;
            final categories = ref.watch(categoryRegistryProvider);
            final schema = ref.watch(schemaRegistryProvider).schemaFor(l.schemaId);
            final characteristics = attributeFormatter(context, ref).characteristics(schema, l.attributes);
            final m = l.moderation;
            final problems = (m?['problems'] as List?)?.cast<Map>() ?? const [];
            final regions = ref.watch(regionDirectoryProvider);
            return ListView(
              padding: const EdgeInsets.all(DaryobSpacing.page),
              children: [
                if (l.photos.isNotEmpty)
                  SizedBox(
                    height: 150,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: l.photos.length,
                      separatorBuilder: (_, _) => const SizedBox(width: 8),
                      itemBuilder: (_, i) => ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: SizedBox.square(dimension: 150, child: DaryobListingImage(source: l.photos[i], cacheWidth: 400)),
                      ),
                    ),
                  )
                else
                  const DaryobNotice(message: 'Фото нет'),
                const SizedBox(height: DaryobSpacing.md),
                Wrap(spacing: 6, children: [_chip(context, _statusRu[l.status] ?? l.status.name, _statusColor(context, l.status))]),
                const SizedBox(height: DaryobSpacing.sm),
                Text(listingPriceText(context, ref, l), style: context.text.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                Text(l.title, style: context.text.titleMedium),
                const SizedBox(height: DaryobSpacing.xs),
                Text(
                  categories.pathTo(l.categoryId).map((c) => c.name.of(context)).join(' › '),
                  style: context.text.bodySmall,
                ),
                Text(
                  [?l.placeName, regions.byId(l.regionId)?.name.of(context) ?? l.regionId].join(', '),
                  style: context.text.bodySmall,
                ),
                Text('Создано ${_dateTime(l.createdAt)} · изменено ${_dateTime(l.updatedAt)}', style: context.text.bodySmall),
                const SizedBox(height: DaryobSpacing.md),
                Text(l.description),
                if (characteristics.isNotEmpty) ...[
                  const SizedBox(height: DaryobSpacing.md),
                  for (final (k, v) in characteristics)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(child: Text(k, style: context.text.bodySmall)),
                          Expanded(child: Text(v)),
                        ],
                      ),
                    ),
                ],
                const Divider(height: DaryobSpacing.xxl),
                Text('Проверка AI', style: context.text.titleSmall),
                const SizedBox(height: DaryobSpacing.xs),
                Text(_aiSummary(m)),
                if (m != null && m['photos_match'] != null)
                  Text('Фото соответствуют: ${m['photos_match'] == true ? 'да' : 'нет'} · категория верна: ${m['category_ok'] == true ? 'да' : 'нет'}'),
                if ((m?['suggested_category'] as String?)?.isNotEmpty == true && m?['category_ok'] == false)
                  Text('Предлагаемая категория: ${m!['suggested_category']}'),
                for (final p in problems) Text('• ${p['ru']}'),
                if (m?['error'] != null) Text('Ошибка: ${m!['error']}', style: TextStyle(color: context.colors.error)),
                if ((l.rejectionReason ?? '').isNotEmpty) ...[
                  const SizedBox(height: DaryobSpacing.sm),
                  Text('Причина отказа: ${l.rejectionReason}', style: TextStyle(color: context.colors.error)),
                ],
                const Divider(height: DaryobSpacing.xxl),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.person_outline_rounded),
                  title: Text(item.ownerName ?? 'Без имени'),
                  subtitle: Text(item.ownerBlocked ? 'Заблокирован' : 'Продавец'),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => context.push(Routes.adminUser(l.ownerId)),
                ),
                const SizedBox(height: DaryobSpacing.md),
                Wrap(
                  spacing: DaryobSpacing.sm,
                  runSpacing: DaryobSpacing.sm,
                  children: [
                    if (l.status != ListingStatus.active)
                      FilledButton.icon(
                        icon: const Icon(Icons.check_rounded),
                        label: const Text('Одобрить'),
                        onPressed: () async {
                          await _run(context, () => repo.moderate(l.id, 'approve'), 'Опубликовано');
                          refresh();
                        },
                      ),
                    if (l.status != ListingStatus.rejected)
                      FilledButton.icon(
                        style: FilledButton.styleFrom(backgroundColor: context.colors.error),
                        icon: const Icon(Icons.block_rounded),
                        label: const Text('Отклонить'),
                        onPressed: () async {
                          final reason = await _askRejectReason(context);
                          if (reason == null || !context.mounted) return;
                          await _run(context, () => repo.moderate(l.id, 'reject', reason: reason.$1, reasonTg: reason.$2), 'Отклонено');
                          refresh();
                        },
                      ),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.auto_awesome_outlined),
                      label: const Text('Проверить AI'),
                      onPressed: () async {
                        await _run(context, () => repo.recheck(l.id), 'Отправлено на проверку AI — обновите через минуту');
                      },
                    ),
                    if (l.status != ListingStatus.archived)
                      OutlinedButton.icon(
                        icon: const Icon(Icons.archive_outlined),
                        label: const Text('В архив'),
                        onPressed: () async {
                          await _run(context, () => repo.moderate(l.id, 'archive'), 'Перенесено в архив');
                          refresh();
                        },
                      ),
                    OutlinedButton.icon(
                      icon: Icon(Icons.delete_outline_rounded, color: context.colors.error),
                      label: Text('Удалить', style: TextStyle(color: context.colors.error)),
                      onPressed: () async {
                        final ok = await DaryobConfirmationDialog.show(
                          context,
                          title: 'Удалить объявление?',
                          message: 'Объявление и его чаты будут удалены без возможности восстановления.',
                          confirmLabel: 'Удалить',
                          destructive: true,
                        );
                        if (!ok || !context.mounted) return;
                        await _run(context, () => repo.deleteListing(l.id), 'Удалено');
                        if (context.mounted) Navigator.of(context).maybePop();
                      },
                    ),
                  ],
                ),
              ],
            );
          },
        ),
      );
    });
  }
}

// ── Reports ─────────────────────────────────────────────────────────────

const _reasonRu = {
  'fraud': 'Мошенничество',
  'prohibited': 'Запрещённый товар',
  'wrongCategory': 'Неверная категория',
  'duplicate': 'Дубликат',
  'sold': 'Уже продано',
  'offensive': 'Оскорбительное содержание',
  'other': 'Другое',
};

final _reportsProvider = FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>(
  (ref, status) => ref.watch(adminRepositoryProvider)!.reports(status: status),
);

class AdminReportsScreen extends ConsumerWidget {
  const AdminReportsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.read(adminRepositoryProvider)!;
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Жалобы'),
          bottom: const TabBar(tabs: [Tab(text: 'Новые'), Tab(text: 'Решённые'), Tab(text: 'Отклонённые')]),
        ),
        body: TabBarView(
          children: [
            for (final status in ['open', 'resolved', 'dismissed'])
              Consumer(builder: (context, ref, _) {
                final value = ref.watch(_reportsProvider(status));
                void refresh() => ref.invalidate(_reportsProvider(status));
                return value.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (e, _) => DaryobErrorState(error: e, onRetry: refresh),
                  data: (items) => items.isEmpty
                      ? const DaryobEmptyState(icon: Icons.done_all_rounded, title: 'Жалоб нет')
                      : ListView.separated(
                          itemCount: items.length,
                          separatorBuilder: (_, _) => const Divider(height: 1),
                          itemBuilder: (_, i) {
                            final r = items[i];
                            final listing = r['listing'] as Map?;
                            final reason = _reasonRu[r['reason']] ?? '${r['reason']}';
                            return Padding(
                              padding: const EdgeInsets.all(DaryobSpacing.md),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(children: [
                                    _chip(context, reason, context.colors.error),
                                    const Spacer(),
                                    Text(_dateTime(DateTime.parse(r['created_at'] as String).toLocal()), style: context.text.bodySmall),
                                  ]),
                                  const SizedBox(height: 6),
                                  InkWell(
                                    onTap: listing == null ? null : () => context.push(Routes.adminListing(listing['id'] as String)),
                                    child: Text(listing?['title'] as String? ?? 'Объявление удалено', style: context.text.titleSmall),
                                  ),
                                  if ((r['comment'] as String? ?? '').isNotEmpty) Text('«${r['comment']}»'),
                                  if ((r['resolution'] as String? ?? '').isNotEmpty) Text('Решение: ${r['resolution']}', style: context.text.bodySmall),
                                  if (status == 'open')
                                    Wrap(spacing: 8, children: [
                                      if (listing != null)
                                        TextButton(
                                          onPressed: () async {
                                            await _run(context, () async {
                                              await repo.moderate(listing['id'] as String, 'reject', reason: 'Снято по жалобе: $reason');
                                              await repo.resolveReport(r['id'] as String, 'resolved', resolution: 'Объявление снято');
                                            }, 'Объявление снято');
                                            refresh();
                                          },
                                          child: Text('Снять объявление', style: TextStyle(color: context.colors.error)),
                                        ),
                                      TextButton(
                                        onPressed: () async {
                                          await _run(context, () => repo.resolveReport(r['id'] as String, 'dismissed', resolution: 'Нарушений нет'), 'Жалоба отклонена');
                                          refresh();
                                        },
                                        child: const Text('Нарушений нет'),
                                      ),
                                    ]),
                                ],
                              ),
                            );
                          },
                        ),
                );
              }),
          ],
        ),
      ),
    );
  }
}

// ── Users ───────────────────────────────────────────────────────────────

class AdminUsersScreen extends ConsumerStatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  ConsumerState<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends ConsumerState<AdminUsersScreen> {
  Timer? _debounce;
  String _query = '';
  Future<List<AdminUser>>? _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  void _load() => setState(() => _future = ref.read(adminRepositoryProvider)!.users(_query));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Пользователи')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(DaryobSpacing.md),
            child: TextField(
              decoration: const InputDecoration(prefixIcon: Icon(Icons.search_rounded), hintText: 'Имя или номер телефона'),
              onChanged: (v) {
                _debounce?.cancel();
                _debounce = Timer(const Duration(milliseconds: 400), () {
                  _query = v.trim();
                  _load();
                });
              },
            ),
          ),
          Expanded(
            child: FutureBuilder<List<AdminUser>>(
              future: _future,
              builder: (context, snap) {
                if (snap.hasError) return DaryobErrorState(error: snap.error!, onRetry: _load);
                if (!snap.hasData) return const Center(child: CircularProgressIndicator());
                final users = snap.data!;
                if (users.isEmpty) return const DaryobEmptyState(icon: Icons.person_search_outlined, title: 'Никого не найдено');
                return ListView.separated(
                  itemCount: users.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final u = users[i];
                    return ListTile(
                      leading: CircleAvatar(child: Text(u.name.characters.first.toUpperCase())),
                      title: Text(u.name),
                      subtitle: Text(
                        '${u.phone == null ? 'номер не указан' : '+992 ${Formatters.phone(u.phone!)}'}'
                        ' · объявлений ${u.count('listings')} · жалоб ${u.count('reports')}',
                      ),
                      trailing: Wrap(spacing: 4, children: [
                        if (u.staffRole != null) _chip(context, _roleRu(u.staffRole), const Color(0xFF2457C5)),
                        if (u.blocked) _chip(context, 'блок', context.colors.error),
                        if (u.verified) Icon(Icons.verified_rounded, size: 18, color: context.palette.success),
                      ]),
                      onTap: () async {
                        await context.push(Routes.adminUser(u.id));
                        _load();
                      },
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

final _adminUserProvider = FutureProvider.autoDispose.family<AdminUser?, String>(
  (ref, id) => ref.watch(adminRepositoryProvider)!.user(id),
);
final _userListingsProvider = FutureProvider.autoDispose.family<List<AdminListing>, String>(
  (ref, id) => ref.watch(adminRepositoryProvider)!.listings(ownerId: id, limit: 200),
);

class AdminUserScreen extends ConsumerWidget {
  const AdminUserScreen({super.key, required this.userId});
  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _StaffOnly(builder: (role) {
      final repo = ref.read(adminRepositoryProvider)!;
      final user = ref.watch(_adminUserProvider(userId));
      final listings = ref.watch(_userListingsProvider(userId));
      void refresh() {
        ref.invalidate(_adminUserProvider(userId));
        ref.invalidate(_userListingsProvider(userId));
      }

      return Scaffold(
        appBar: AppBar(title: const Text('Пользователь')),
        body: user.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => DaryobErrorState(error: e, onRetry: refresh),
          data: (u) {
            if (u == null) return const DaryobEmptyState(icon: Icons.person_off_outlined, title: 'Пользователь не найден');
            return ListView(
              padding: const EdgeInsets.all(DaryobSpacing.page),
              children: [
                Text(u.name, style: context.text.headlineSmall),
                const SizedBox(height: DaryobSpacing.xs),
                Text(u.phone == null ? 'Номер не указан' : '+992 ${Formatters.phone(u.phone!)}'
                    '${u.verified ? ' · подтверждён' : ' · не подтверждён'}'),
                Text('На DARYOB с ${Formatters.date(u.createdAt)}'),
                Text('Объявлений: ${u.count('listings')} (активных ${u.count('active_listings')}) · '
                    'жалоб на объявления: ${u.count('reports')} · подозрительных сообщений: ${u.count('flags')}'),
                if (u.staffRole != null) Text('Роль: ${_roleRu(u.staffRole)}'),
                const SizedBox(height: DaryobSpacing.md),
                Wrap(spacing: DaryobSpacing.sm, runSpacing: DaryobSpacing.sm, children: [
                  if (!u.blocked)
                    FilledButton.icon(
                      style: FilledButton.styleFrom(backgroundColor: context.colors.error),
                      icon: const Icon(Icons.block_rounded),
                      label: const Text('Заблокировать'),
                      onPressed: () async {
                        final reason = await _askText(context, 'Причина блокировки', 'Например: мошенничество');
                        if (reason == null || !context.mounted) return;
                        await _run(context, () => repo.setBlocked(u.id, true, reason: reason), 'Заблокирован, объявления сняты');
                        refresh();
                      },
                    )
                  else
                    FilledButton.icon(
                      icon: const Icon(Icons.lock_open_rounded),
                      label: const Text('Разблокировать'),
                      onPressed: () async {
                        await _run(context, () => repo.setBlocked(u.id, false), 'Разблокирован');
                        refresh();
                      },
                    ),
                  if (role == 'admin')
                    PopupMenuButton<String>(
                      onSelected: (r) async {
                        await _run(context, () => repo.setStaff(u.id, r == 'none' ? null : r), 'Роль изменена');
                        refresh();
                      },
                      itemBuilder: (_) => const [
                        PopupMenuItem(value: 'none', child: Text('Обычный пользователь')),
                        PopupMenuItem(value: 'support', child: Text('Поддержка')),
                        PopupMenuItem(value: 'moderator', child: Text('Модератор')),
                        PopupMenuItem(value: 'admin', child: Text('Администратор')),
                      ],
                      child: const Chip(avatar: Icon(Icons.badge_outlined, size: 18), label: Text('Роль')),
                    ),
                ]),
                const Divider(height: DaryobSpacing.xxl),
                Text('Объявления', style: context.text.titleSmall),
                listings.when(
                  loading: () => const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator())),
                  error: (e, _) => DaryobErrorState(error: e, compact: true),
                  data: (items) => Column(
                    children: [
                      if (items.isEmpty) const Padding(padding: EdgeInsets.all(16), child: Text('Нет объявлений')),
                      for (final it in items)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(it.listing.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                          subtitle: Text(_dateTime(it.listing.updatedAt)),
                          trailing: _chip(context, _statusRu[it.listing.status] ?? '', _statusColor(context, it.listing.status)),
                          onTap: () => context.push(Routes.adminListing(it.listing.id)),
                        ),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      );
    });
  }
}

Future<String?> _askText(BuildContext context, String title, String hint) {
  final c = TextEditingController();
  return showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: TextField(controller: c, autofocus: true, minLines: 2, maxLines: 4, decoration: InputDecoration(hintText: hint)),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Отмена')),
        FilledButton(
          onPressed: () => c.text.trim().isEmpty ? null : Navigator.pop(context, c.text.trim()),
          child: const Text('Готово'),
        ),
      ],
    ),
  );
}

// ── Support ─────────────────────────────────────────────────────────────

final _ticketsProvider = FutureProvider.autoDispose.family<List<SupportTicket>, String>(
  (ref, status) => ref.watch(supportRepositoryProvider)!.allTickets(status: status),
);

class AdminSupportScreen extends ConsumerWidget {
  const AdminSupportScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Техподдержка'),
          bottom: const TabBar(tabs: [Tab(text: 'Ждут ответа'), Tab(text: 'С ответом'), Tab(text: 'Закрытые')]),
        ),
        body: TabBarView(
          children: [
            for (final status in ['open', 'answered', 'closed'])
              Consumer(builder: (context, ref, _) {
                final value = ref.watch(_ticketsProvider(status));
                return RefreshIndicator(
                  onRefresh: () => ref.refresh(_ticketsProvider(status).future),
                  child: value.when(
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (e, _) => DaryobErrorState(error: e, onRetry: () => ref.invalidate(_ticketsProvider(status))),
                    data: (items) => items.isEmpty
                        ? ListView(children: const [DaryobEmptyState(icon: Icons.done_all_rounded, title: 'Обращений нет')])
                        : ListView.separated(
                            itemCount: items.length,
                            separatorBuilder: (_, _) => const Divider(height: 1),
                            itemBuilder: (_, i) {
                              final t = items[i];
                              return ListTile(
                                leading: const Icon(Icons.forum_outlined),
                                title: Text(t.subject, maxLines: 1, overflow: TextOverflow.ellipsis),
                                subtitle: Text(
                                  '${t.userName ?? 'Без имени'} · ${_dateTime(t.updatedAt)} · ${ticketStatusLabel(l10n, t.status)}\n${t.lastMessage ?? ''}',
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                isThreeLine: true,
                                trailing: t.staffUnread > 0 ? Badge(label: Text('${t.staffUnread}')) : null,
                                onTap: () async {
                                  await context.push(Routes.adminTicket(t.id));
                                  ref.invalidate(_ticketsProvider(status));
                                },
                              );
                            },
                          ),
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }
}

// ── Chat safety ─────────────────────────────────────────────────────────

const _flagCategoryRu = {
  'prepayment': 'Предоплата',
  'card_or_code': 'Данные карты / код',
  'phishing_link': 'Подозрительная ссылка',
  'fake_delivery': 'Фальшивая доставка',
  'insult': 'Оскорбление',
  'threat': 'Угроза',
  'sexual': 'Домогательство',
  'spam': 'Спам',
  'prohibited': 'Запрещённый товар',
  'other': 'Другое',
};

final _flagsProvider = FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>(
  (ref, status) => ref.watch(adminRepositoryProvider)!.flags(status: status),
);

class AdminFlagsScreen extends ConsumerWidget {
  const AdminFlagsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.read(adminRepositoryProvider)!;
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Проверка чатов'),
          bottom: const TabBar(tabs: [Tab(text: 'Новые'), Tab(text: 'Проверенные')]),
        ),
        body: TabBarView(
          children: [
            for (final status in ['open', 'reviewed'])
              Consumer(builder: (context, ref, _) {
                final value = ref.watch(_flagsProvider(status));
                void refresh() => ref.invalidate(_flagsProvider(status));
                return value.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (e, _) => DaryobErrorState(error: e, onRetry: refresh),
                  data: (items) => items.isEmpty
                      ? const DaryobEmptyState(
                          icon: Icons.verified_user_outlined,
                          title: 'Подозрительных сообщений нет',
                          message: 'AI проверяет каждое сообщение в чатах. Если найдёт мошенничество или оскорбления, они появятся здесь.',
                        )
                      : ListView.separated(
                          itemCount: items.length,
                          separatorBuilder: (_, _) => const Divider(height: 1),
                          itemBuilder: (_, i) {
                            final f = items[i];
                            final message = f['message'] as Map?;
                            final block = f['risk'] == 'block';
                            final hidden = message?['hidden'] == true;
                            return Padding(
                              padding: const EdgeInsets.all(DaryobSpacing.md),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(children: [
                                    _chip(context, block ? 'Скрыто' : 'Предупреждение', block ? context.colors.error : const Color(0xFFB7791F)),
                                    const SizedBox(width: 6),
                                    _chip(context, _flagCategoryRu[f['category']] ?? '${f['category']}', context.palette.textSecondary),
                                    const Spacer(),
                                    Text(_dateTime(DateTime.parse(f['created_at'] as String).toLocal()), style: context.text.bodySmall),
                                  ]),
                                  const SizedBox(height: 6),
                                  Text('${(f['sender'] as Map?)?['name'] ?? 'Без имени'}: «${message?['text'] ?? ''}»'),
                                  if ((f['reason'] as String? ?? '').isNotEmpty)
                                    Text('AI: ${f['reason']}', style: context.text.bodySmall),
                                  Wrap(spacing: 4, children: [
                                    TextButton(
                                      onPressed: () => context.push(Routes.adminConversation(f['conversation_id'] as String)),
                                      child: const Text('Открыть чат'),
                                    ),
                                    if (status == 'open') ...[
                                      TextButton(
                                        onPressed: () async {
                                          await _run(context, () => repo.reviewFlag((f['id'] as num).toInt()), 'Отмечено');
                                          refresh();
                                        },
                                        child: const Text('Проверено'),
                                      ),
                                      if (hidden)
                                        TextButton(
                                          onPressed: () async {
                                            await _run(context, () => repo.reviewFlag((f['id'] as num).toInt(), unhide: true), 'Сообщение показано');
                                            refresh();
                                          },
                                          child: const Text('Ошибка AI — показать'),
                                        ),
                                      if (f['sender_id'] != null)
                                        TextButton(
                                          onPressed: () async {
                                            final reason = await _askText(context, 'Причина блокировки', 'Например: мошенничество в чате');
                                            if (reason == null || !context.mounted) return;
                                            await _run(context, () async {
                                              await repo.setBlocked(f['sender_id'] as String, true, reason: reason);
                                              await repo.reviewFlag((f['id'] as num).toInt());
                                            }, 'Отправитель заблокирован');
                                            refresh();
                                          },
                                          child: Text('Заблокировать', style: TextStyle(color: context.colors.error)),
                                        ),
                                    ],
                                  ]),
                                ],
                              ),
                            );
                          },
                        ),
                );
              }),
          ],
        ),
      ),
    );
  }
}

class AdminConversationScreen extends ConsumerWidget {
  const AdminConversationScreen({super.key, required this.conversationId});
  final String conversationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _StaffOnly(builder: (_) {
      final repo = ref.read(adminRepositoryProvider)!;
      return Scaffold(
        appBar: AppBar(title: const Text('Чат (просмотр)')),
        body: FutureBuilder(
          future: Future.wait([repo.conversation(conversationId), repo.conversationMessages(conversationId)]),
          builder: (context, snap) {
            if (snap.hasError) return DaryobErrorState(error: snap.error!);
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final c = snap.data![0] as Map<String, dynamic>?;
            final messages = snap.data![1] as List<ChatMessage>;
            if (c == null) return const DaryobEmptyState(icon: Icons.forum_outlined, title: 'Чат не найден');
            final buyer = (c['buyer'] as Map?)?['name'] ?? 'Покупатель';
            final seller = (c['seller'] as Map?)?['name'] ?? 'Продавец';
            return Column(
              children: [
                ListTile(
                  title: Text('${c['listing_title']}'),
                  subtitle: Text('Покупатель: $buyer · Продавец: $seller'),
                  trailing: c['listing_id'] == null ? null : const Icon(Icons.chevron_right_rounded),
                  onTap: c['listing_id'] == null ? null : () => context.push(Routes.adminListing(c['listing_id'] as String)),
                ),
                const Divider(height: 1),
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.all(DaryobSpacing.md),
                    itemCount: messages.length,
                    itemBuilder: (_, i) {
                      final m = messages[i];
                      if (m.isSystem) {
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Text('DARYOB: ${m.text}', textAlign: TextAlign.center, style: context.text.bodySmall),
                        );
                      }
                      final isSeller = m.senderId == c['seller_id'];
                      final hidden = m.state == DeliveryState.failed;
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Column(
                          crossAxisAlignment: isSeller ? CrossAxisAlignment.end : CrossAxisAlignment.start,
                          children: [
                            Text('${isSeller ? seller : buyer} · ${_dateTime(m.sentAt)}${hidden ? ' · СКРЫТО' : ''}',
                                style: context.text.labelSmall?.copyWith(color: hidden ? context.colors.error : null)),
                            Container(
                              margin: const EdgeInsets.only(top: 2),
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: hidden ? context.colors.error.withValues(alpha: 0.1) : context.colors.surface,
                                border: Border.all(color: context.palette.border),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(m.text),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
              ],
            );
          },
        ),
      );
    });
  }
}

// ── Settings ────────────────────────────────────────────────────────────

class AdminSettingsScreen extends ConsumerStatefulWidget {
  const AdminSettingsScreen({super.key, required this.isAdmin});
  final bool isAdmin;

  @override
  ConsumerState<AdminSettingsScreen> createState() => _AdminSettingsScreenState();
}

class _AdminSettingsScreenState extends ConsumerState<AdminSettingsScreen> {
  String? _mode;
  bool? _chatAi;

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(_settingsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Настройки модерации')),
      body: settings.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => DaryobErrorState(error: e),
        data: (s) {
          final moderation = Map<String, dynamic>.from(s['moderation'] as Map? ?? const {});
          final ai = s['ai_status'] as Map?;
          final mode = _mode ?? moderation['mode'] as String? ?? 'ai';
          final chatAi = _chatAi ?? (moderation['chat_ai'] as bool? ?? true);
          Widget option(String value, String title, String body) => RadioListTile<String>(
            value: value,
            enabled: widget.isAdmin,
            title: Text(title),
            subtitle: Text(body),
          );
          return ListView(
            padding: const EdgeInsets.symmetric(vertical: DaryobSpacing.md),
            children: [
              if (!widget.isAdmin)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
                  child: DaryobNotice(message: 'Менять настройки может только администратор.'),
                ),
              RadioGroup<String>(
                groupValue: mode,
                onChanged: (v) {
                  if (widget.isAdmin) setState(() => _mode = v);
                },
                child: Column(
                  children: [
                    option('ai', 'AI-модерация', 'AI проверяет фото, категорию и текст. Явные нарушения отклоняются с причиной, '
                        'честные объявления публикуются сразу, спорные ждут модератора.'),
                    option('manual', 'Только вручную', 'Каждое новое объявление ждёт решения модератора.'),
                    option('off', 'Без модерации', 'Объявления публикуются сразу. Только для тестов.'),
                  ],
                ),
              ),
              SwitchListTile(
                value: chatAi,
                onChanged: widget.isAdmin ? (v) => setState(() => _chatAi = v) : null,
                title: const Text('AI-проверка сообщений в чатах'),
                subtitle: const Text('Мошенничество и оскорбления: предупреждение получателю, опасные сообщения скрываются.'),
              ),
              const Divider(),
              ListTile(
                leading: Icon(ai?['ai_configured'] == true ? Icons.check_circle_outline : Icons.error_outline,
                    color: ai?['ai_configured'] == true ? context.palette.success : context.colors.error),
                title: Text(ai == null
                    ? 'AI ещё не запускался'
                    : ai['ai_configured'] == true
                    ? 'Ключ OpenAI подключён'
                    : 'Ключ OpenAI не добавлен'),
                subtitle: Text(ai?['last_error'] != null ? 'Последняя ошибка: ${ai!['last_error']}' :
                    'Ключ добавляется в Supabase → Edge Functions → Secrets, имя OPENAI_API_KEY.'),
              ),
              if (widget.isAdmin)
                Padding(
                  padding: const EdgeInsets.all(DaryobSpacing.page),
                  child: FilledButton(
                    onPressed: () async {
                      await _run(context, () => ref.read(adminRepositoryProvider)!.setSetting('moderation', {'mode': mode, 'chat_ai': chatAi}), 'Сохранено');
                      ref.invalidate(_settingsProvider);
                    },
                    child: const Text('Сохранить'),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

// ── Audit log ───────────────────────────────────────────────────────────

final _auditProvider = FutureProvider.autoDispose<List<Map<String, dynamic>>>(
  (ref) => ref.watch(adminRepositoryProvider)!.audit(),
);

const _actionRu = {
  'listing.approve': 'Одобрил объявление',
  'listing.reject': 'Отклонил объявление',
  'listing.archive': 'Убрал в архив',
  'listing.delete': 'Удалил объявление',
  'listing.ai_recheck': 'Отправил на AI-проверку',
  'user.block': 'Заблокировал пользователя',
  'user.unblock': 'Разблокировал пользователя',
  'staff.set': 'Изменил роль',
  'report.resolved': 'Решил жалобу',
  'report.dismissed': 'Отклонил жалобу',
  'flag.review': 'Проверил сообщение',
  'ticket.close': 'Закрыл обращение',
  'setting.set': 'Изменил настройки',
};

class AdminAuditScreen extends ConsumerWidget {
  const AdminAuditScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final value = ref.watch(_auditProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Журнал действий')),
      body: value.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => DaryobErrorState(error: e, onRetry: () => ref.invalidate(_auditProvider)),
        data: (items) => items.isEmpty
            ? const DaryobEmptyState(icon: Icons.history_rounded, title: 'Пока пусто')
            : ListView.separated(
                itemCount: items.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (_, i) {
                  final a = items[i];
                  final details = Map<String, dynamic>.from(a['details'] as Map? ?? const {});
                  final note = details['title'] ?? details['reason'] ?? details['role'] ?? '';
                  return ListTile(
                    dense: true,
                    title: Text(_actionRu[a['action']] ?? '${a['action']}'),
                    subtitle: Text('${(a['staff'] as Map?)?['name'] ?? '—'} · ${_dateTime(DateTime.parse(a['created_at'] as String).toLocal())}'
                        '${'$note'.isEmpty ? '' : '\n$note'}'),
                    onTap: switch (a['target_type']) {
                      'listing' => () => context.push(Routes.adminListing(a['target_id'] as String)),
                      'user' => () => context.push(Routes.adminUser(a['target_id'] as String)),
                      _ => null,
                    },
                  );
                },
              ),
      ),
    );
  }
}

/// Route wrapper so a support ticket opens from the support side.
class AdminTicketScreen extends StatelessWidget {
  const AdminTicketScreen({super.key, required this.ticketId});
  final String ticketId;

  @override
  Widget build(BuildContext context) => _StaffOnly(builder: (_) => SupportTicketScreen(ticketId: ticketId, asStaff: true));
}
