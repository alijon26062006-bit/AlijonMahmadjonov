import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/utils/ids.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/listing_image.dart';
import '../../../shared/widgets/states.dart';
import '../../../shared/widgets/toast.dart';
import '../../authentication/application/session_controller.dart';
import '../domain/conversation.dart';
import 'chats_screen.dart';

final _conversationProvider = FutureProvider.autoDispose
    .family<Conversation?, String>((ref, id) {
      return ref.watch(conversationRepositoryProvider).get(id);
    });

final _messagesProvider = FutureProvider.autoDispose
    .family<List<ChatMessage>, String>((ref, id) {
      return ref.watch(conversationRepositoryProvider).messages(id);
    });

class ConversationScreen extends ConsumerStatefulWidget {
  const ConversationScreen({super.key, required this.conversationId});
  final String conversationId;

  @override
  ConsumerState<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends ConsumerState<ConversationScreen> {
  final _input = TextEditingController();
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await ref
          .read(conversationRepositoryProvider)
          .markRead(widget.conversationId);
      ref.invalidate(conversationsProvider);
    });
  }

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    final user = ref.read(sessionControllerProvider);
    if (text.isEmpty || user == null || _sending) return;
    setState(() => _sending = true);
    try {
      await ref
          .read(conversationRepositoryProvider)
          .send(widget.conversationId, user.id, text);
      _input.clear();
      ref.invalidate(_messagesProvider(widget.conversationId));
      ref.invalidate(conversationsProvider);
    } catch (e) {
      if (mounted) {
        DaryobToast.show(
          context,
          failureMessage(context.l10n, e),
          isError: true,
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _toggleBlock(Conversation c) async {
    final l10n = context.l10n;
    if (!c.isBlocked) {
      final ok = await DaryobConfirmationDialog.show(
        context,
        title: l10n.blockUserTitle,
        message: l10n.blockUserBody,
        confirmLabel: l10n.block,
        destructive: true,
      );
      if (!ok) return;
    }
    await ref
        .read(conversationRepositoryProvider)
        .setBlocked(c.id, !c.isBlocked);
    ref.invalidate(_conversationProvider(c.id));
    ref.invalidate(conversationsProvider);
  }

  Future<void> _reportUser(Conversation c) async {
    final l10n = context.l10n;
    final ok = await DaryobConfirmationDialog.show(
      context,
      title: l10n.reportUser,
      message: l10n.reportUserBody,
      confirmLabel: l10n.reportSend,
    );
    if (!ok) return;
    try {
      await ref
          .read(listingRepositoryProvider)
          .report(
            ListingReport(
              id: newId('r_'),
              listingId: c.listingId,
              reason: ReportReason.fraud,
              comment: 'user:${c.otherPartyId}',
              reporterId: ref.read(sessionControllerProvider)?.id,
              createdAt: ref.read(clockProvider)(),
            ),
          );
      if (mounted) {
        final local = ref.read(appConfigProvider).isDevelopment;
        DaryobToast.show(
          context,
          local ? l10n.reportSavedLocally : l10n.reportSent,
        );
      }
    } catch (e) {
      if (mounted) {
        DaryobToast.show(context, failureMessage(l10n, e), isError: true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final conversation = ref.watch(
      _conversationProvider(widget.conversationId),
    );
    final messages = ref.watch(_messagesProvider(widget.conversationId));
    final user = ref.watch(sessionControllerProvider);
    final delivers = ref.watch(conversationRepositoryProvider).deliversMessages;

    return conversation.when(
      loading: () =>
          const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(
        appBar: AppBar(),
        body: DaryobErrorState(error: e),
      ),
      data: (c) {
        if (c == null) {
          return Scaffold(
            appBar: AppBar(),
            body: DaryobEmptyState(
              icon: Icons.forum_outlined,
              title: l10n.errNotFound,
            ),
          );
        }
        return Scaffold(
          appBar: AppBar(
            title: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(c.otherPartyName, style: context.text.titleMedium),
                Text(
                  delivers ? l10n.chatOnline : l10n.chatLocalShort,
                  style: context.text.bodySmall,
                ),
              ],
            ),
            actions: [
              PopupMenuButton<String>(
                tooltip: l10n.more,
                onSelected: (v) async {
                  switch (v) {
                    case 'seller':
                      context.push(Routes.seller(c.otherPartyId));
                    case 'block':
                      await _toggleBlock(c);
                    case 'report':
                      await _reportUser(c);
                    case 'delete':
                      final ok = await DaryobConfirmationDialog.show(
                        context,
                        title: l10n.deleteChatTitle,
                        message: l10n.deleteChatBody,
                        confirmLabel: l10n.delete,
                        destructive: true,
                      );
                      if (!ok) return;
                      await ref
                          .read(conversationRepositoryProvider)
                          .delete(c.id);
                      ref.invalidate(conversationsProvider);
                      if (context.mounted) context.pop();
                  }
                },
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'seller',
                    child: Text(l10n.sellerProfile),
                  ),
                  PopupMenuItem(
                    value: 'block',
                    child: Text(c.isBlocked ? l10n.unblock : l10n.block),
                  ),
                  PopupMenuItem(value: 'report', child: Text(l10n.reportUser)),
                  PopupMenuItem(value: 'delete', child: Text(l10n.deleteChat)),
                ],
              ),
            ],
          ),
          body: Column(
            children: [
              Material(
                color: context.colors.surface,
                child: ListTile(
                  onTap: () => context.push(Routes.listing(c.listingId)),
                  leading: ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: SizedBox(
                      width: 44,
                      height: 44,
                      child: DaryobListingImage(
                        source: c.listingPhoto,
                        cacheWidth: 132,
                      ),
                    ),
                  ),
                  title: Text(
                    c.listingTitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: const Icon(Icons.chevron_right_rounded),
                ),
              ),
              const Divider(),
              if (!delivers)
                Padding(
                  padding: const EdgeInsets.all(DaryobSpacing.sm),
                  child: DaryobNotice(
                    message: l10n.chatLocalNotice,
                    tone: NoticeTone.warning,
                  ),
                ),
              Expanded(
                child: messages.when(
                  skipLoadingOnReload: true,
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (e, _) => DaryobErrorState(error: e),
                  data: (list) => list.isEmpty
                      ? DaryobEmptyState(
                          icon: Icons.waving_hand_outlined,
                          compact: true,
                          title: l10n.chatStartTitle,
                          message: l10n.chatStartBody,
                        )
                      : ListView.builder(
                          reverse: true,
                          padding: const EdgeInsets.all(DaryobSpacing.md),
                          itemCount: list.length,
                          itemBuilder: (_, i) {
                            final m = list[list.length - 1 - i];
                            return _Bubble(
                              message: m,
                              mine: m.senderId == user?.id,
                            );
                          },
                        ),
                ),
              ),
              if (c.isBlocked)
                Padding(
                  padding: const EdgeInsets.all(DaryobSpacing.lg),
                  child: Text(
                    l10n.chatBlockedNotice,
                    textAlign: TextAlign.center,
                  ),
                )
              else
                _Composer(controller: _input, sending: _sending, onSend: _send),
            ],
          ),
        );
      },
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message, required this.mine});
  final ChatMessage message;
  final bool mine;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = mine
        ? (isDark ? DaryobColors.darkSurfaceHigh : DaryobColors.navy)
        : context.colors.surface;
    final fg = mine ? Colors.white : context.colors.onSurface;
    final stateLabel = switch (message.state) {
      DeliveryState.localOnly => l10n.msgLocalOnly,
      DeliveryState.sending => l10n.msgSending,
      DeliveryState.sent => l10n.msgSent,
      DeliveryState.delivered => l10n.msgDelivered,
      DeliveryState.read => l10n.msgRead,
      DeliveryState.failed => l10n.msgFailed,
    };
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.78,
        ),
        margin: const EdgeInsets.symmetric(vertical: 3),
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 8),
        decoration: BoxDecoration(
          color: bg,
          border: mine ? null : Border.all(color: context.palette.border),
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(mine ? 18 : 4),
            bottomRight: Radius.circular(mine ? 4 : 18),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                message.text,
                style: context.text.bodyLarge?.copyWith(color: fg),
              ),
            ),
            const SizedBox(height: 2),
            Text(
              mine
                  ? '${Formatters.time(message.sentAt)} · $stateLabel'
                  : Formatters.time(message.sentAt),
              style: context.text.labelSmall?.copyWith(
                color: fg.withValues(alpha: 0.7),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.sending,
    required this.onSend,
  });
  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: context.colors.surface,
        border: Border(top: BorderSide(color: context.palette.border)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(DaryobSpacing.sm),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  minLines: 1,
                  maxLines: 4,
                  maxLength: 1000,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: InputDecoration(
                    hintText: l10n.messageHint,
                    counterText: '',
                  ),
                  onSubmitted: (_) => onSend(),
                ),
              ),
              const SizedBox(width: DaryobSpacing.sm),
              IconButton.filled(
                tooltip: l10n.send,
                style: IconButton.styleFrom(
                  backgroundColor: DaryobColors.lime,
                  foregroundColor: DaryobColors.navy,
                  minimumSize: const Size(48, 48),
                ),
                onPressed: sending ? null : onSend,
                icon: const Icon(Icons.send_rounded),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
