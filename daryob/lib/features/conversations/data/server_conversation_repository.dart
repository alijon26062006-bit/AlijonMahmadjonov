import 'dart:async';

import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/backend/backend.dart';
import '../../../core/errors/failure.dart';
import '../domain/conversation.dart';

/// Chat on the DARYOB server: messages are stored in the database and
/// pushed to the other person over a realtime channel.
class ServerConversationRepository implements ConversationRepository {
  ServerConversationRepository(this._client);

  final SupabaseClient _client;

  static const _columns =
      '*, buyer:profiles!conversations_buyer_id_fkey(name), seller:profiles!conversations_seller_id_fkey(name)';

  String get _me {
    final id = _client.auth.currentUser?.id;
    if (id == null) throw const UnauthorizedFailure();
    return id;
  }

  @override
  bool get deliversMessages => true;

  @override
  Future<List<Conversation>> list(String ownerId) {
    if (!isServerId(ownerId)) return Future.value(const []);
    return backendCall(() async {
      final me = _me;
      final rows = await _client
          .from('conversations')
          .select(_columns)
          .or('and(buyer_id.eq.$me,buyer_hidden.eq.false),and(seller_id.eq.$me,seller_hidden.eq.false)')
          .order('updated_at', ascending: false)
          .limit(200);
      return [for (final row in rows) _conversation(row, me)];
    });
  }

  @override
  Future<Conversation?> get(String id) {
    if (!isServerId(id)) return Future.value();
    return backendCall(() async {
      final row = await _client
          .from('conversations')
          .select(_columns)
          .eq('id', id)
          .maybeSingle();
      return row == null ? null : _conversation(row, _me);
    });
  }

  @override
  Future<List<ChatMessage>> messages(String conversationId) {
    if (!isServerId(conversationId)) return Future.value(const []);
    return backendCall(() async {
      // The latest 300 messages, shown oldest first.
      final rows = await _client
          .from('messages')
          .select()
          .eq('conversation_id', conversationId)
          .order('created_at', ascending: false)
          .limit(300);
      return [for (final row in rows.reversed) _message(row)];
    });
  }

  @override
  Future<Conversation> openForListing({
    required String ownerId,
    required String listingId,
    required String listingTitle,
    required String? listingPhoto,
    required String sellerId,
    required String sellerName,
    required bool isDemo,
  }) {
    return backendCall(() async {
      final created = await _client.rpc<dynamic>(
        'open_conversation',
        params: {'p_listing': listingId},
      );
      final id = (created as Map)['id'] as String;
      final row = await _client
          .from('conversations')
          .select(_columns)
          .eq('id', id)
          .single();
      return _conversation(row, _me);
    });
  }

  @override
  Future<ChatMessage> send(String conversationId, String senderId, String text) {
    return backendCall(() async {
      final row = await _client
          .from('messages')
          .insert({'conversation_id': conversationId, 'text': text.trim()})
          .select()
          .single();
      return _message(row);
    });
  }

  @override
  Future<void> markRead(String conversationId) {
    if (!isServerId(conversationId)) return Future.value();
    return backendCall(
      () => _client.rpc<void>(
        'mark_conversation_read',
        params: {'p_conversation': conversationId},
      ),
    );
  }

  @override
  Future<void> setBlocked(String conversationId, bool blocked) {
    return backendCall(
      () => _client.rpc<void>(
        'set_conversation_blocked',
        params: {'p_conversation': conversationId, 'p_blocked': blocked},
      ),
    );
  }

  @override
  Future<void> delete(String conversationId) {
    return backendCall(
      () => _client.rpc<void>(
        'hide_conversation',
        params: {'p_conversation': conversationId},
      ),
    );
  }

  @override
  Stream<void> watch(String ownerId, {String? conversationId}) {
    if (!isServerId(ownerId)) return const Stream.empty();
    late final RealtimeChannel channel;
    late final StreamController<void> controller;
    void ping(PostgresChangePayload _) {
      if (!controller.isClosed) controller.add(null);
    }

    controller = StreamController<void>.broadcast(
      onListen: () {
        channel = _client.channel('chat-${conversationId ?? ownerId}-${uuidV4()}');
        if (conversationId != null) {
          channel.onPostgresChanges(
            event: PostgresChangeEvent.all,
            schema: 'public',
            table: 'messages',
            filter: PostgresChangeFilter(
              type: PostgresChangeFilterType.eq,
              column: 'conversation_id',
              value: conversationId,
            ),
            callback: ping,
          );
        }
        // Row level security limits these events to the user's own chats.
        channel.onPostgresChanges(
          event: PostgresChangeEvent.all,
          schema: 'public',
          table: 'conversations',
          callback: ping,
        );
        channel.subscribe();
      },
      onCancel: () async {
        await _client.removeChannel(channel);
        await controller.close();
      },
    );
    return controller.stream;
  }

  Conversation _conversation(Map<String, dynamic> row, String me) {
    final iAmBuyer = row['buyer_id'] == me;
    final other = (iAmBuyer ? row['seller'] : row['buyer']) as Map?;
    final name = (other?['name'] as String?)?.trim() ?? '';
    return Conversation(
      id: row['id'] as String,
      ownerId: me,
      listingId: row['listing_id'] as String? ?? '',
      listingTitle: row['listing_title'] as String? ?? '',
      listingPhoto: row['listing_photo'] as String?,
      otherPartyId: (iAmBuyer ? row['seller_id'] : row['buyer_id']) as String,
      otherPartyName: name.isEmpty ? '—' : name,
      lastMessage: row['last_message'] as String?,
      updatedAt: DateTime.parse(row['updated_at'] as String),
      unreadCount:
          ((iAmBuyer ? row['buyer_unread'] : row['seller_unread']) as num?)?.toInt() ?? 0,
      isBlocked: (iAmBuyer ? row['buyer_blocked'] : row['seller_blocked']) as bool? ?? false,
    );
  }

  ChatMessage _message(Map<String, dynamic> row) => ChatMessage(
    id: row['id'] as String,
    conversationId: row['conversation_id'] as String,
    senderId: row['sender_id'] as String,
    text: row['text'] as String? ?? '',
    sentAt: DateTime.parse(row['created_at'] as String).toLocal(),
    state: row['read_at'] != null ? DeliveryState.read : DeliveryState.sent,
  );
}
