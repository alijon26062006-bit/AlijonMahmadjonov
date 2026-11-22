import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../app/localization/l10n.dart';
import '../../app/router/routes.dart';
import '../../app/theme/tokens.dart';
import '../../core/backend/backend.dart';
import '../../core/utils/formatters.dart';
import '../../shared/widgets/buttons.dart';
import '../../shared/widgets/states.dart';
import '../../shared/widgets/toast.dart';
import '../authentication/application/session_controller.dart';
import '../profile/presentation/info_screen.dart';

@immutable
class SupportTicket {
  const SupportTicket({
    required this.id,
    required this.userId,
    required this.subject,
    required this.status,
    required this.updatedAt,
    this.lastMessage,
    this.userUnread = 0,
    this.staffUnread = 0,
    this.userName,
  });

  final String id;
  final String userId;
  final String subject;

  /// open | answered | closed
  final String status;
  final DateTime updatedAt;
  final String? lastMessage;
  final int userUnread;
  final int staffUnread;
  final String? userName;

  factory SupportTicket.fromRow(Map<String, dynamic> r) => SupportTicket(
    id: r['id'] as String,
    userId: r['user_id'] as String,
    subject: r['subject'] as String? ?? '',
    status: r['status'] as String? ?? 'open',
    updatedAt: DateTime.parse(r['updated_at'] as String).toLocal(),
    lastMessage: r['last_message'] as String?,
    userUnread: (r['user_unread'] as num?)?.toInt() ?? 0,
    staffUnread: (r['staff_unread'] as num?)?.toInt() ?? 0,
    userName: (r['user'] as Map?)?['name'] as String?,
  );
}

@immutable
class SupportMessage {
  const SupportMessage({
    required this.id,
    required this.isStaff,
    required this.text,
    required this.sentAt,
  });
  final String id;
  final bool isStaff;
  final String text;
  final DateTime sentAt;

  factory SupportMessage.fromRow(Map<String, dynamic> r) => SupportMessage(
    id: r['id'] as String,
    isStaff: r['is_staff'] as bool? ?? false,
    text: r['text'] as String? ?? '',
    sentAt: DateTime.parse(r['created_at'] as String).toLocal(),
  );
}

/// Support tickets on the server. Used by users and by staff.
class SupportRepository {
  SupportRepository(this._client);
  final SupabaseClient _client;

  static const _columns = '*, user:profiles!support_tickets_user_id_fkey(name)';

  Future<List<SupportTicket>> myTickets() => backendCall(() async {
    final me = _client.auth.currentUser?.id;
    if (me == null) return const <SupportTicket>[];
    final rows = await _client
        .from('support_tickets')
        .select(_columns)
        .eq('user_id', me)
        .order('updated_at', ascending: false)
        .limit(100);
    return [for (final r in rows) SupportTicket.fromRow(r)];
  });

  /// Staff: all tickets, open first.
  Future<List<SupportTicket>> allTickets({String? status}) => backendCall(() async {
    var query = _client.from('support_tickets').select(_columns);
    if (status != null) query = query.eq('status', status);
    final rows = await query.order('updated_at', ascending: false).limit(200);
    return [for (final r in rows) SupportTicket.fromRow(r)];
  });

  Future<SupportTicket?> ticket(String id) => backendCall(() async {
    final row = await _client.from('support_tickets').select(_columns).eq('id', id).maybeSingle();
    return row == null ? null : SupportTicket.fromRow(row);
  });

  Future<String> create(String subject, String text) => backendCall(() async {
    final row = await _client
        .from('support_tickets')
        .insert({'subject': subject.trim()})
        .select('id')
        .single();
    final id = row['id'] as String;
    await _client.from('support_messages').insert({'ticket_id': id, 'text': text.trim()});
    return id;
  });

  Future<List<SupportMessage>> messages(String ticketId) => backendCall(() async {
    final rows = await _client
        .from('support_messages')
        .select()
        .eq('ticket_id', ticketId)
        .order('created_at')
        .limit(500);
    return [for (final r in rows) SupportMessage.fromRow(r)];
  });

  Future<void> send(String ticketId, String text) => backendCall(() async {
    await _client.from('support_messages').insert({'ticket_id': ticketId, 'text': text.trim()});
  });

  Future<void> markRead(String ticketId) async {
    try {
      await _client.rpc<void>('support_mark_read', params: {'p_ticket': ticketId});
    } catch (_) {}
  }

  Future<void> close(String ticketId) => backendCall(
    () => _client.rpc<void>('admin_close_ticket', params: {'p_ticket': ticketId}),
  );

  /// Fires when a message is added to [ticketId].
  Stream<void> watch(String ticketId) {
    late final RealtimeChannel channel;
    late final StreamController<void> controller;
    controller = StreamController<void>.broadcast(
      onListen: () {
        channel = _client.channel('support-$ticketId-${uuidV4()}')
          ..onPostgresChanges(
            event: PostgresChangeEvent.insert,
            schema: 'public',
            table: 'support_messages',
            filter: PostgresChangeFilter(
              type: PostgresChangeFilterType.eq,
              column: 'ticket_id',
              value: ticketId,
            ),
            callback: (_) {
              if (!controller.isClosed) controller.add(null);
            },
          )
          ..subscribe();
      },
      onCancel: () async {
        await _client.removeChannel(channel);
        await controller.close();
      },
    );
    return controller.stream;
  }
}

final supportRepositoryProvider = Provider<SupportRepository?>((ref) {
  final client = ref.watch(backendClientProvider);
  return client == null ? null : SupportRepository(client);
});

final mySupportTicketsProvider = FutureProvider.autoDispose<List<SupportTicket>>((ref) {
  ref.watch(sessionControllerProvider);
  return ref.watch(supportRepositoryProvider)?.myTickets() ?? Future.value(const []);
});

final supportTicketProvider = FutureProvider.autoDispose.family<SupportTicket?, String>(
  (ref, id) => ref.watch(supportRepositoryProvider)?.ticket(id) ?? Future.value(),
);

final supportMessagesProvider = StreamProvider.autoDispose.family<List<SupportMessage>, String>((
  ref,
  ticketId,
) {
  final repo = ref.watch(supportRepositoryProvider);
  if (repo == null) return Stream.value(const []);
  final controller = StreamController<List<SupportMessage>>();
  Future<void> load() async {
    try {
      final messages = await repo.messages(ticketId);
      if (!controller.isClosed) controller.add(messages);
      unawaited(repo.markRead(ticketId));
    } catch (e, s) {
      if (!controller.isClosed) controller.addError(e, s);
    }
  }

  unawaited(load());
  final changes = repo.watch(ticketId).listen((_) => load());
  final timer = Timer.periodic(const Duration(seconds: 30), (_) => load());
  ref.onDispose(() {
    timer.cancel();
    changes.cancel();
    controller.close();
  });
  return controller.stream;
});

String ticketStatusLabel(AppLocalizations l10n, String status) => switch (status) {
  'answered' => l10n.ticketAnswered,
  'closed' => l10n.ticketClosed,
  _ => l10n.ticketOpen,
};

/// "Support": the user's requests and a button for a new one.
class SupportScreen extends ConsumerWidget {
  const SupportScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    // Without a server the contacts page is all there is.
    if (ref.watch(supportRepositoryProvider) == null) return const InfoScreen(page: 'support');
    final user = ref.watch(sessionControllerProvider);
    final tickets = ref.watch(mySupportTicketsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.support),
        actions: [
          IconButton(
            tooltip: l10n.supportContacts,
            icon: const Icon(Icons.info_outline_rounded),
            onPressed: () => context.push(Routes.info('support')),
          ),
        ],
      ),
      floatingActionButton: user == null
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _newTicket(context, ref),
              icon: const Icon(Icons.add_comment_outlined),
              label: Text(l10n.supportNewTicket),
            ),
      body: user == null
          ? DaryobEmptyState(
              icon: Icons.support_agent_rounded,
              title: l10n.support,
              message: l10n.supportSignInBody,
              actionLabel: l10n.signIn,
              onAction: () => context.push(Routes.auth),
            )
          : RefreshIndicator(
              onRefresh: () => ref.refresh(mySupportTicketsProvider.future),
              child: tickets.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => DaryobErrorState(error: e, onRetry: () => ref.invalidate(mySupportTicketsProvider)),
                data: (list) => list.isEmpty
                    ? ListView(
                        children: [
                          DaryobEmptyState(
                            icon: Icons.support_agent_rounded,
                            title: l10n.supportEmptyTitle,
                            message: l10n.supportEmptyBody,
                          ),
                        ],
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.only(bottom: 96),
                        itemCount: list.length,
                        separatorBuilder: (_, _) => const Divider(height: 1),
                        itemBuilder: (_, i) {
                          final t = list[i];
                          return ListTile(
                            leading: const Icon(Icons.forum_outlined),
                            title: Text(t.subject, maxLines: 1, overflow: TextOverflow.ellipsis),
                            subtitle: Text(
                              '${ticketStatusLabel(l10n, t.status)} · ${Formatters.date(t.updatedAt)}\n${t.lastMessage ?? ''}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            isThreeLine: true,
                            trailing: t.userUnread > 0
                                ? Badge(label: Text('${t.userUnread}'))
                                : const Icon(Icons.chevron_right_rounded),
                            onTap: () => context.push(Routes.supportTicket(t.id)),
                          );
                        },
                      ),
              ),
            ),
    );
  }

  Future<void> _newTicket(BuildContext context, WidgetRef ref) async {
    final id = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => const _NewTicketSheet(),
    );
    ref.invalidate(mySupportTicketsProvider);
    if (id != null && context.mounted) unawaited(context.push(Routes.supportTicket(id)));
  }
}

class _NewTicketSheet extends ConsumerStatefulWidget {
  const _NewTicketSheet();

  @override
  ConsumerState<_NewTicketSheet> createState() => _NewTicketSheetState();
}

class _NewTicketSheetState extends ConsumerState<_NewTicketSheet> {
  final _subject = TextEditingController();
  final _text = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _subject.dispose();
    _text.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final l10n = context.l10n;
    if (_subject.text.trim().isEmpty || _text.text.trim().isEmpty) {
      DaryobToast.show(context, l10n.supportFillBoth);
      return;
    }
    setState(() => _busy = true);
    try {
      final id = await ref.read(supportRepositoryProvider)!.create(_subject.text, _text.text);
      if (mounted) Navigator.of(context).pop(id);
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        DaryobToast.show(context, failureMessage(l10n, e));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        DaryobSpacing.page,
        DaryobSpacing.sm,
        DaryobSpacing.page,
        MediaQuery.viewInsetsOf(context).bottom + DaryobSpacing.lg,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(l10n.supportNewTicket, style: context.text.titleLarge),
          const SizedBox(height: DaryobSpacing.md),
          TextField(
            controller: _subject,
            maxLength: 200,
            textCapitalization: TextCapitalization.sentences,
            decoration: InputDecoration(labelText: l10n.supportSubject),
          ),
          TextField(
            controller: _text,
            minLines: 4,
            maxLines: 8,
            maxLength: 4000,
            textCapitalization: TextCapitalization.sentences,
            decoration: InputDecoration(labelText: l10n.supportMessage, alignLabelWithHint: true),
          ),
          const SizedBox(height: DaryobSpacing.sm),
          DaryobPrimaryButton(label: l10n.send, isLoading: _busy, onPressed: _submit),
        ],
      ),
    );
  }
}

/// One support conversation. [asStaff] shows it from the support side.
class SupportTicketScreen extends ConsumerStatefulWidget {
  const SupportTicketScreen({super.key, required this.ticketId, this.asStaff = false});
  final String ticketId;
  final bool asStaff;

  @override
  ConsumerState<SupportTicketScreen> createState() => _SupportTicketScreenState();
}

class _SupportTicketScreenState extends ConsumerState<SupportTicketScreen> {
  final _input = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty) return;
    setState(() => _sending = true);
    try {
      await ref.read(supportRepositoryProvider)!.send(widget.ticketId, text);
      _input.clear();
      ref.invalidate(supportMessagesProvider(widget.ticketId));
      ref.invalidate(supportTicketProvider(widget.ticketId));
    } catch (e) {
      if (mounted) DaryobToast.show(context, failureMessage(context.l10n, e));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final ticket = ref.watch(supportTicketProvider(widget.ticketId)).value;
    final messages = ref.watch(supportMessagesProvider(widget.ticketId));
    return Scaffold(
      appBar: AppBar(
        title: Text(ticket?.subject ?? l10n.support, maxLines: 1, overflow: TextOverflow.ellipsis),
        actions: [
          if (widget.asStaff && ticket != null && ticket.status != 'closed')
            TextButton(
              onPressed: () async {
                await ref.read(supportRepositoryProvider)!.close(widget.ticketId);
                ref.invalidate(supportTicketProvider(widget.ticketId));
                if (context.mounted) DaryobToast.show(context, 'Обращение закрыто');
              },
              child: const Text('Закрыть'),
            ),
        ],
      ),
      body: Column(
        children: [
          if (widget.asStaff && ticket != null)
            ListTile(
              dense: true,
              leading: const Icon(Icons.person_outline_rounded),
              title: Text(ticket.userName ?? '—'),
              subtitle: Text(ticketStatusLabel(l10n, ticket.status)),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => context.push(Routes.adminUser(ticket.userId)),
            ),
          Expanded(
            child: messages.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => DaryobErrorState(error: e),
              data: (list) => ListView.builder(
                reverse: true,
                padding: const EdgeInsets.all(DaryobSpacing.md),
                itemCount: list.length,
                itemBuilder: (_, i) {
                  final m = list[list.length - 1 - i];
                  final mine = widget.asStaff ? m.isStaff : !m.isStaff;
                  return Align(
                    alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                    child: Container(
                      constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.8),
                      margin: const EdgeInsets.symmetric(vertical: 3),
                      padding: const EdgeInsets.fromLTRB(14, 10, 14, 8),
                      decoration: BoxDecoration(
                        color: mine ? DaryobColors.navy : context.colors.surface,
                        border: mine ? null : Border.all(color: context.palette.border),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (m.isStaff && !widget.asStaff)
                            Text(l10n.supportTeam, style: context.text.labelSmall?.copyWith(color: context.colors.primary)),
                          Text(m.text, style: TextStyle(color: mine ? Colors.white : context.colors.onSurface)),
                          const SizedBox(height: 2),
                          Text(
                            Formatters.time(m.sentAt),
                            style: context.text.labelSmall?.copyWith(
                              color: mine ? Colors.white70 : context.palette.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(DaryobSpacing.md, DaryobSpacing.xs, DaryobSpacing.sm, DaryobSpacing.sm),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _input,
                      minLines: 1,
                      maxLines: 5,
                      maxLength: 4000,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: InputDecoration(hintText: l10n.messageHint, counterText: ''),
                    ),
                  ),
                  IconButton.filled(
                    tooltip: l10n.send,
                    onPressed: _sending ? null : _send,
                    icon: const Icon(Icons.send_rounded),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
