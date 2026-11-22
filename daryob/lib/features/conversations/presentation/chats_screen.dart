import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/badges.dart';
import '../../../shared/widgets/listing_image.dart';
import '../../../shared/widgets/require_sign_in.dart';
import '../../../shared/widgets/states.dart';
import '../../authentication/application/session_controller.dart';
import '../domain/conversation.dart';

final conversationsProvider = FutureProvider.autoDispose<List<Conversation>>((
  ref,
) async {
  final user = ref.watch(sessionControllerProvider);
  if (user == null) return const [];
  // Reload when the server reports a new message or a read receipt.
  ref.watch(chatChangesProvider(null));
  return ref.watch(conversationRepositoryProvider).list(user.id);
});

/// Counts change signals for the user's chats (or for one conversation).
/// Watching it keeps a single realtime channel open; data providers that
/// watch it reload on every tick without reopening the channel. A slow
/// timer covers anything missed while the connection was down.
final chatChangesProvider = StreamProvider.autoDispose.family<int, String?>((
  ref,
  conversationId,
) {
  final user = ref.watch(sessionControllerProvider);
  final repo = ref.watch(conversationRepositoryProvider);
  if (user == null || !repo.deliversMessages) return const Stream.empty();
  final controller = StreamController<int>();
  var ticks = 0;
  final changes = repo
      .watch(user.id, conversationId: conversationId)
      .listen((_) => controller.add(++ticks));
  final timer = Timer.periodic(
    const Duration(seconds: 30),
    (_) => controller.add(++ticks),
  );
  ref.onDispose(() {
    timer.cancel();
    changes.cancel();
    controller.close();
  });
  return controller.stream;
});

class ChatsScreen extends ConsumerWidget {
  const ChatsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final user = ref.watch(sessionControllerProvider);
    final delivers = ref.watch(conversationRepositoryProvider).deliversMessages;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.tabChats)),
      body: user == null
          ? DaryobEmptyState(
              icon: Icons.chat_bubble_outline_rounded,
              title: l10n.chatsSignInTitle,
              message: l10n.chatsSignInBody,
              actionLabel: l10n.signIn,
              onAction: () => requireSignIn(context, ref),
            )
          : ref
                .watch(conversationsProvider)
                .when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (e, _) => DaryobErrorState(
                    error: e,
                    onRetry: () => ref.invalidate(conversationsProvider),
                  ),
                  data: (items) => Column(
                    children: [
                      if (!delivers)
                        Padding(
                          padding: const EdgeInsets.fromLTRB(
                            DaryobSpacing.page,
                            0,
                            DaryobSpacing.page,
                            DaryobSpacing.sm,
                          ),
                          child: DaryobNotice(
                            message: l10n.chatLocalNotice,
                            tone: NoticeTone.warning,
                          ),
                        ),
                      Expanded(
                        child: items.isEmpty
                            ? DaryobEmptyState(
                                icon: Icons.forum_outlined,
                                title: l10n.chatsEmpty,
                                message: l10n.chatsEmptyBody,
                              )
                            : RefreshIndicator(
                                onRefresh: () async =>
                                    ref.invalidate(conversationsProvider),
                                child: ListView.separated(
                                  itemCount: items.length,
                                  separatorBuilder: (_, _) =>
                                      const Divider(indent: 84),
                                  itemBuilder: (_, i) =>
                                      _ConversationTile(conversation: items[i]),
                                ),
                              ),
                      ),
                    ],
                  ),
                ),
    );
  }
}

class _ConversationTile extends StatelessWidget {
  const _ConversationTile({required this.conversation});
  final Conversation conversation;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final c = conversation;
    final today = DateUtils.isSameDay(c.updatedAt, DateTime.now());
    return ListTile(
      onTap: () => context.push(Routes.conversation(c.id)),
      leading: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(
          width: 52,
          height: 52,
          child: DaryobListingImage(source: c.listingPhoto, cacheWidth: 156),
        ),
      ),
      title: Row(
        children: [
          Flexible(
            child: Text(c.otherPartyName, overflow: TextOverflow.ellipsis),
          ),
          if (c.isDemo) ...[const SizedBox(width: 6), const DemoBadge()],
          if (c.isBlocked) ...[
            const SizedBox(width: 6),
            DaryobStatusBadge(label: l10n.blocked, tone: BadgeTone.danger),
          ],
        ],
      ),
      subtitle: Text(
        '${c.listingTitle}\n${c.lastMessage ?? l10n.noMessagesYet}',
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      isThreeLine: true,
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(
            today ? Formatters.time(c.updatedAt) : Formatters.date(c.updatedAt),
            style: context.text.bodySmall,
          ),
          if (c.unreadCount > 0) ...[
            const SizedBox(height: 4),
            Badge(
              label: Text('${c.unreadCount}'),
              backgroundColor: DaryobColors.lime,
              textColor: DaryobColors.navy,
            ),
          ],
        ],
      ),
    );
  }
}
