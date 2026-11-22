import 'package:flutter/foundation.dart';

import 'money.dart';

enum ListingStatus { draft, pending, active, sold, archived, rejected }

enum PhoneVisibility {
  /// Number shown on the listing.
  visible,

  /// Number hidden; buyers can only write in chat.
  hidden,
}

enum PromotionType { free, boost, top, vip, vipPlus, businessSubscription }

@immutable
class ListingContact {
  const ListingContact({
    required this.name,
    required this.phone,
    this.phoneVisibility = PhoneVisibility.visible,
    this.chatEnabled = true,
  });

  final String name;

  /// National digits only (9), without +992.
  final String phone;
  final PhoneVisibility phoneVisibility;
  final bool chatEnabled;

  Map<String, dynamic> toJson() => {
    'name': name,
    'phone': phone,
    'phoneVisibility': phoneVisibility.name,
    'chatEnabled': chatEnabled,
  };

  factory ListingContact.fromJson(Map<String, dynamic> json) => ListingContact(
    name: json['name'] as String? ?? '',
    phone: json['phone'] as String? ?? '',
    phoneVisibility: PhoneVisibility.values.byName(
      json['phoneVisibility'] as String? ?? PhoneVisibility.visible.name,
    ),
    chatEnabled: json['chatEnabled'] as bool? ?? true,
  );
}

@immutable
class ListingPromotion {
  const ListingPromotion({
    required this.type,
    required this.startsAt,
    required this.endsAt,
    this.isDevelopmentOnly = false,
  });

  final PromotionType type;
  final DateTime startsAt;
  final DateTime endsAt;

  /// Activated without payment through the development-only switch.
  final bool isDevelopmentOnly;

  bool isActiveAt(DateTime now) =>
      now.isAfter(startsAt) && now.isBefore(endsAt);

  Map<String, dynamic> toJson() => {
    'type': type.name,
    'startsAt': startsAt.toIso8601String(),
    'endsAt': endsAt.toIso8601String(),
    'isDevelopmentOnly': isDevelopmentOnly,
  };

  factory ListingPromotion.fromJson(Map<String, dynamic> json) =>
      ListingPromotion(
        type: PromotionType.values.byName(json['type'] as String),
        startsAt: DateTime.parse(json['startsAt'] as String),
        endsAt: DateTime.parse(json['endsAt'] as String),
        isDevelopmentOnly: json['isDevelopmentOnly'] as bool? ?? false,
      );
}

@immutable
class Listing {
  const Listing({
    required this.id,
    required this.ownerId,
    required this.categoryId,
    required this.title,
    required this.description,
    required this.currency,
    required this.regionId,
    required this.contact,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
    this.price,
    this.isNegotiable = false,
    this.attributes = const {},
    this.photos = const [],
    this.addressNote,
    this.publishedAt,
    this.viewCount,
    this.promotion,
    this.rejectionReason,
    this.schemaId = 'generic.basic',
    this.schemaVersion = 1,
    this.isDemo = false,
    this.isLocalOnly = false,
  });

  final String id;
  final String ownerId;
  final String categoryId;
  final String title;
  final String description;

  /// Whole somoni (or dollars). Null means "price on request".
  final int? price;
  final Currency currency;
  final bool isNegotiable;

  /// Category-specific values keyed by `FieldSchema.key`.
  final Map<String, Object?> attributes;

  /// Local file paths or https URLs. First one is the cover.
  final List<String> photos;

  /// Most specific location chosen: a city/district id, or a region id.
  final String regionId;
  final String? addressNote;
  final ListingContact contact;
  final ListingStatus status;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? publishedAt;

  /// Null when views are not tracked (local/demo data).
  final int? viewCount;
  final ListingPromotion? promotion;
  final String? rejectionReason;
  final String schemaId;
  final int schemaVersion;

  /// Sample data shipped with development builds.
  final bool isDemo;

  /// Created on this device and never sent to a server.
  final bool isLocalOnly;

  bool isPromotedAt(DateTime now) =>
      promotion != null &&
      promotion!.type != PromotionType.free &&
      promotion!.isActiveAt(now);

  bool isVipAt(DateTime now) =>
      isPromotedAt(now) &&
      (promotion!.type == PromotionType.vip ||
          promotion!.type == PromotionType.vipPlus);

  bool isTopAt(DateTime now) =>
      isPromotedAt(now) && promotion!.type == PromotionType.top;

  DateTime get sortDate => publishedAt ?? createdAt;

  Listing copyWith({
    String? categoryId,
    String? title,
    String? description,
    int? price,
    bool clearPrice = false,
    Currency? currency,
    bool? isNegotiable,
    Map<String, Object?>? attributes,
    List<String>? photos,
    String? regionId,
    String? addressNote,
    ListingContact? contact,
    ListingStatus? status,
    DateTime? updatedAt,
    DateTime? publishedAt,
    ListingPromotion? promotion,
    bool clearPromotion = false,
    String? rejectionReason,
    String? schemaId,
    int? schemaVersion,
  }) {
    return Listing(
      id: id,
      ownerId: ownerId,
      categoryId: categoryId ?? this.categoryId,
      title: title ?? this.title,
      description: description ?? this.description,
      price: clearPrice ? null : (price ?? this.price),
      currency: currency ?? this.currency,
      isNegotiable: isNegotiable ?? this.isNegotiable,
      attributes: attributes ?? this.attributes,
      photos: photos ?? this.photos,
      regionId: regionId ?? this.regionId,
      addressNote: addressNote ?? this.addressNote,
      contact: contact ?? this.contact,
      status: status ?? this.status,
      createdAt: createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      publishedAt: publishedAt ?? this.publishedAt,
      viewCount: viewCount,
      promotion: clearPromotion ? null : (promotion ?? this.promotion),
      rejectionReason: rejectionReason ?? this.rejectionReason,
      schemaId: schemaId ?? this.schemaId,
      schemaVersion: schemaVersion ?? this.schemaVersion,
      isDemo: isDemo,
      isLocalOnly: isLocalOnly,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'ownerId': ownerId,
    'categoryId': categoryId,
    'title': title,
    'description': description,
    'price': price,
    'currency': currency.code,
    'isNegotiable': isNegotiable,
    'attributes': attributes,
    'photos': photos,
    'regionId': regionId,
    'addressNote': addressNote,
    'contact': contact.toJson(),
    'status': status.name,
    'createdAt': createdAt.toIso8601String(),
    'updatedAt': updatedAt.toIso8601String(),
    'publishedAt': publishedAt?.toIso8601String(),
    'viewCount': viewCount,
    'promotion': promotion?.toJson(),
    'rejectionReason': rejectionReason,
    'schemaId': schemaId,
    'schemaVersion': schemaVersion,
    'isDemo': isDemo,
    'isLocalOnly': isLocalOnly,
  };

  factory Listing.fromJson(Map<String, dynamic> json) {
    DateTime? date(String key) {
      final raw = json[key] as String?;
      return raw == null ? null : DateTime.tryParse(raw);
    }

    final created = date('createdAt') ?? DateTime.fromMillisecondsSinceEpoch(0);
    return Listing(
      id: json['id'] as String,
      ownerId: json['ownerId'] as String,
      categoryId: json['categoryId'] as String,
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      price: (json['price'] as num?)?.toInt(),
      currency: Currency.fromCode(json['currency'] as String?),
      isNegotiable: json['isNegotiable'] as bool? ?? false,
      attributes: Map<String, Object?>.from(
        json['attributes'] as Map? ?? const {},
      ),
      photos: List<String>.from(json['photos'] as List? ?? const []),
      regionId: json['regionId'] as String? ?? 'tj',
      addressNote: json['addressNote'] as String?,
      contact: ListingContact.fromJson(
        Map<String, dynamic>.from(json['contact'] as Map? ?? const {}),
      ),
      status: ListingStatus.values.byName(
        json['status'] as String? ?? ListingStatus.active.name,
      ),
      createdAt: created,
      updatedAt: date('updatedAt') ?? created,
      publishedAt: date('publishedAt'),
      viewCount: (json['viewCount'] as num?)?.toInt(),
      promotion: json['promotion'] == null
          ? null
          : ListingPromotion.fromJson(
              Map<String, dynamic>.from(json['promotion'] as Map),
            ),
      rejectionReason: json['rejectionReason'] as String?,
      schemaId: json['schemaId'] as String? ?? 'generic.basic',
      schemaVersion: (json['schemaVersion'] as num?)?.toInt() ?? 1,
      isDemo: json['isDemo'] as bool? ?? false,
      isLocalOnly: json['isLocalOnly'] as bool? ?? false,
    );
  }
}

/// Reasons a buyer can report a listing.
enum ReportReason {
  fraud,
  prohibited,
  wrongCategory,
  duplicate,
  sold,
  offensive,
  other,
}

@immutable
class ListingReport {
  const ListingReport({
    required this.id,
    required this.listingId,
    required this.reason,
    required this.createdAt,
    this.comment,
    this.reporterId,
  });

  final String id;
  final String listingId;
  final ReportReason reason;
  final String? comment;
  final String? reporterId;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => {
    'id': id,
    'listingId': listingId,
    'reason': reason.name,
    'comment': comment,
    'reporterId': reporterId,
    'createdAt': createdAt.toIso8601String(),
  };
}
