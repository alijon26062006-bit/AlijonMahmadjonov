import '../../../core/errors/failure.dart';
import '../../../core/storage/local_database.dart';
import '../../../core/utils/ids.dart';
import '../domain/conversation.dart';

/// Keeps conversations on the device. Messages are saved with
/// [DeliveryState.localOnly]: there is no server to deliver them.
class LocalConversationRepository implements ConversationRepository {
  LocalConversationRepository(LocalDatabase database, this._clock)
    : _conversations = database.collection(Collections.conversations),
      _messages = database.collection(Collections.messages);

  final JsonCollection _conversations;
  final JsonCollection _messages;
  final DateTime Function() _clock;

  @override
  bool get deliversMessages => false;

  @override
  Future<List<Conversation>> list(String ownerId) async {
    return _conversations
        .values()
        .map(Conversation.fromJson)
        .where((c) => c.ownerId == ownerId)
        .toList()
      ..sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
  }

  @override
  Future<Conversation?> get(String id) async {
    final json = _conversations.get(id);
    return json == null ? null : Conversation.fromJson(json);
  }

  @override
  Future<List<ChatMessage>> messages(String conversationId) async {
    return _messages
        .values()
        .map(ChatMessage.fromJson)
        .where((m) => m.conversationId == conversationId)
        .toList()
      ..sort((a, b) => a.sentAt.compareTo(b.sentAt));
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
  }) async {
    for (final c in await list(ownerId)) {
      if (c.listingId == listingId && c.otherPartyId == sellerId) return c;
    }
    final conversation = Conversation(
      id: newId('c_'),
      ownerId: ownerId,
      listingId: listingId,
      listingTitle: listingTitle,
      listingPhoto: listingPhoto,
      otherPartyId: sellerId,
      otherPartyName: sellerName,
      updatedAt: _clock(),
      isDemo: isDemo,
    );
    await _conversations.put(conversation.id, conversation.toJson());
    return conversation;
  }

  @override
  Future<ChatMessage> send(
    String conversationId,
    String senderId,
    String text,
  ) async {
    final conversation = await get(conversationId);
    if (conversation == null) throw const NotFoundFailure();
    if (conversation.isBlocked) throw const ForbiddenFailure();
    final message = ChatMessage(
      id: newId('m_'),
      conversationId: conversationId,
      senderId: senderId,
      text: text.trim(),
      sentAt: _clock(),
      state: DeliveryState.localOnly,
    );
    await _messages.put(message.id, message.toJson());
    await _conversations.put(
      conversation.id,
      conversation
          .copyWith(lastMessage: message.text, updatedAt: message.sentAt)
          .toJson(),
    );
    return message;
  }

  @override
  Future<void> markRead(String conversationId) async {
    final conversation = await get(conversationId);
    if (conversation == null || conversation.unreadCount == 0) return;
    await _conversations.put(
      conversation.id,
      conversation.copyWith(unreadCount: 0).toJson(),
    );
  }

  @override
  Future<void> setBlocked(String conversationId, bool blocked) async {
    final conversation = await get(conversationId);
    if (conversation == null) return;
    await _conversations.put(
      conversation.id,
      conversation.copyWith(isBlocked: blocked).toJson(),
    );
  }

  @override
  Future<void> delete(String conversationId) async {
    for (final m in await messages(conversationId)) {
      await _messages.delete(m.id);
    }
    await _conversations.delete(conversationId);
  }

  @override
  Stream<void> watch(String ownerId, {String? conversationId}) =>
      const Stream.empty();
}

class UnavailableConversationRepository implements ConversationRepository {
  const UnavailableConversationRepository();

  static const _failure = FeatureUnavailableFailure(
    UnavailableFeature.realtimeChat,
  );

  @override
  bool get deliversMessages => false;
  @override
  Future<List<Conversation>> list(String ownerId) => Future.error(_failure);
  @override
  Future<Conversation?> get(String id) => Future.error(_failure);
  @override
  Future<List<ChatMessage>> messages(String conversationId) =>
      Future.error(_failure);
  @override
  Future<Conversation> openForListing({
    required String ownerId,
    required String listingId,
    required String listingTitle,
    required String? listingPhoto,
    required String sellerId,
    required String sellerName,
    required bool isDemo,
  }) => Future.error(_failure);
  @override
  Future<ChatMessage> send(
    String conversationId,
    String senderId,
    String text,
  ) => Future.error(_failure);
  @override
  Future<void> markRead(String conversationId) async {}
  @override
  Future<void> setBlocked(String conversationId, bool blocked) =>
      Future.error(_failure);
  @override
  Future<void> delete(String conversationId) => Future.error(_failure);

  @override
  Stream<void> watch(String ownerId, {String? conversationId}) =>
      const Stream.empty();
}
