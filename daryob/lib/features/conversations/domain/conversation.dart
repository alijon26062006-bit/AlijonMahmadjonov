import 'package:flutter/foundation.dart';

/// Where a message is. Without a realtime backend, messages stay
/// [localOnly] and the UI says so — nothing pretends to be delivered.
enum DeliveryState { localOnly, sending, sent, delivered, read, failed }

@immutable
class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.conversationId,
    required this.senderId,
    required this.text,
    required this.sentAt,
    required this.state,
    this.isSystem = false,
    this.textTg,
  });

  final String id;
  final String conversationId;
  final String senderId;
  final String text;
  final DateTime sentAt;
  final DeliveryState state;

  /// A safety notice from DARYOB inside the chat (not written by a person).
  final bool isSystem;

  /// Tajik text of a system notice.
  final String? textTg;

  Map<String, dynamic> toJson() => {
    'id': id,
    'conversationId': conversationId,
    'senderId': senderId,
    'text': text,
    'sentAt': sentAt.toIso8601String(),
    'state': state.name,
  };

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
    id: json['id'] as String,
    conversationId: json['conversationId'] as String,
    senderId: json['senderId'] as String,
    text: json['text'] as String? ?? '',
    sentAt: DateTime.parse(json['sentAt'] as String),
    state: DeliveryState.values.byName(json['state'] as String? ?? 'localOnly'),
  );
}

@immutable
class Conversation {
  const Conversation({
    required this.id,
    required this.ownerId,
    required this.listingId,
    required this.listingTitle,
    required this.otherPartyId,
    required this.otherPartyName,
    required this.updatedAt,
    this.listingPhoto,
    this.lastMessage,
    this.unreadCount = 0,
    this.isBlocked = false,
    this.isDemo = false,
  });

  final String id;

  /// The user this conversation belongs to on this device.
  final String ownerId;
  final String listingId;
  final String listingTitle;
  final String? listingPhoto;
  final String otherPartyId;
  final String otherPartyName;
  final String? lastMessage;
  final DateTime updatedAt;
  final int unreadCount;
  final bool isBlocked;
  final bool isDemo;

  Conversation copyWith({
    String? lastMessage,
    DateTime? updatedAt,
    int? unreadCount,
    bool? isBlocked,
  }) {
    return Conversation(
      id: id,
      ownerId: ownerId,
      listingId: listingId,
      listingTitle: listingTitle,
      listingPhoto: listingPhoto,
      otherPartyId: otherPartyId,
      otherPartyName: otherPartyName,
      lastMessage: lastMessage ?? this.lastMessage,
      updatedAt: updatedAt ?? this.updatedAt,
      unreadCount: unreadCount ?? this.unreadCount,
      isBlocked: isBlocked ?? this.isBlocked,
      isDemo: isDemo,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'ownerId': ownerId,
    'listingId': listingId,
    'listingTitle': listingTitle,
    'listingPhoto': listingPhoto,
    'otherPartyId': otherPartyId,
    'otherPartyName': otherPartyName,
    'lastMessage': lastMessage,
    'updatedAt': updatedAt.toIso8601String(),
    'unreadCount': unreadCount,
    'isBlocked': isBlocked,
    'isDemo': isDemo,
  };

  factory Conversation.fromJson(Map<String, dynamic> json) => Conversation(
    id: json['id'] as String,
    ownerId: json['ownerId'] as String,
    listingId: json['listingId'] as String,
    listingTitle: json['listingTitle'] as String? ?? '',
    listingPhoto: json['listingPhoto'] as String?,
    otherPartyId: json['otherPartyId'] as String,
    otherPartyName: json['otherPartyName'] as String? ?? '',
    lastMessage: json['lastMessage'] as String?,
    updatedAt: DateTime.parse(json['updatedAt'] as String),
    unreadCount: (json['unreadCount'] as num?)?.toInt() ?? 0,
    isBlocked: json['isBlocked'] as bool? ?? false,
    isDemo: json['isDemo'] as bool? ?? false,
  );
}

/// Chat storage and transport. A realtime implementation (WebSocket) will
/// replace the local one without changing the screens.
abstract interface class ConversationRepository {
  /// True when messages actually reach the other person.
  bool get deliversMessages;

  Future<List<Conversation>> list(String ownerId);
  Future<Conversation?> get(String id);
  Future<List<ChatMessage>> messages(String conversationId);

  Future<Conversation> openForListing({
    required String ownerId,
    required String listingId,
    required String listingTitle,
    required String? listingPhoto,
    required String sellerId,
    required String sellerName,
    required bool isDemo,
  });

  Future<ChatMessage> send(String conversationId, String senderId, String text);
  Future<void> markRead(String conversationId);
  Future<void> setBlocked(String conversationId, bool blocked);
  Future<void> delete(String conversationId);

  /// Fires when something changed in the user's chats (a new message, a
  /// read receipt). With [conversationId], also for messages of that chat.
  /// Local storage has nothing to announce and returns an empty stream.
  Stream<void> watch(String ownerId, {String? conversationId});
}
