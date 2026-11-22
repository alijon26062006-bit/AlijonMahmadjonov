import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/states.dart';
import '../../authentication/application/session_controller.dart';
import '../../onboarding/presentation/splash_screen.dart';
import '../application/notification_providers.dart';
import '../domain/app_notification.dart';

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  IconData _icon(NotificationKind kind) => switch (kind) {
    NotificationKind.newMessage => Icons.chat_bubble_outline_rounded,
    NotificationKind.listingApproved => Icons.check_circle_outline_rounded,
    NotificationKind.listingRejected => Icons.block_rounded,
    NotificationKind.listingExpiring => Icons.hourglass_bottom_rounded,
    NotificationKind.promotionEnding => Icons.rocket_launch_outlined,
    NotificationKind.newMatchingListing => Icons.manage_search_rounded,
    NotificationKind.system => Icons.campaign_outlined,
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final value = ref.watch(notificationsProvider);
    final push = ref.watch(pushServiceProvider);
    final now = ref.watch(clockProvider)();

    Future<void> markAll() async {
      final repo = ref.read(notificationRepositoryProvider);
      await repo.markAllRead(ref.read(ownerKeyProvider));
      await repo.markAllRead(kDeviceOwner);
      ref.invalidate(notificationsProvider);
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.notifications),
        actions: [
          TextButton(onPressed: markAll, child: Text(l10n.markAllRead)),
        ],
      ),
      body: value.when(
        skipLoadingOnReload: true,
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => DaryobErrorState(error: e),
        data: (items) => ListView(
          children: [
            if (!push.isConfigured)
              Padding(
                padding: const EdgeInsets.all(DaryobSpacing.page),
                child: DaryobNotice(message: l10n.pushNotConfigured),
              ),
            if (items.isEmpty)
              DaryobEmptyState(
                icon: Icons.notifications_none_rounded,
                title: l10n.notificationsEmpty,
              ),
            for (final n in items)
              Dismissible(
                key: ValueKey(n.id),
                direction: DismissDirection.endToStart,
                background: Container(
                  color: context.colors.error,
                  alignment: Alignment.centerRight,
                  padding: const EdgeInsets.only(right: DaryobSpacing.xl),
                  child: const Icon(
                    Icons.delete_outline_rounded,
                    color: Colors.white,
                  ),
                ),
                onDismissed: (_) async {
                  await ref.read(notificationRepositoryProvider).delete(n.id);
                  ref.invalidate(notificationsProvider);
                },
                child: Builder(
                  builder: (context) {
                    final (title, body) = notificationText(l10n, n);
                    return ListTile(
                      tileColor: n.isRead
                          ? null
                          : context.palette.limeSoft.withValues(alpha: 0.5),
                      leading: CircleAvatar(
                        backgroundColor: context.palette.surfaceMuted,
                        foregroundColor: context.colors.onSurface,
                        child: Icon(_icon(n.kind)),
                      ),
                      title: Text(
                        title,
                        style: n.isRead
                            ? null
                            : context.text.titleSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                      ),
                      subtitle: Text(
                        '$body\n${ageLabel(l10n, n.createdAt, now)}',
                      ),
                      isThreeLine: true,
                      onTap: () async {
                        await ref
                            .read(notificationRepositoryProvider)
                            .markRead(n.id);
                        ref.invalidate(notificationsProvider);
                        if (!context.mounted) return;
                        final chat = n.params['conversationId'];
                        final ticket = n.params['ticketId'];
                        if (chat != null) {
                          context.push(Routes.conversation(chat));
                        } else if (ticket != null) {
                          context.push(Routes.supportTicket(ticket));
                        } else if (n.listingId != null) {
                          context.push(Routes.listing(n.listingId!));
                        }
                      },
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}
