import 'package:flutter/foundation.dart';

import '../../../shared/models/listing.dart';
import '../../../shared/models/money.dart';

/// Wizard steps in order (catalog `global_workflow.steps`): category →
/// subcategory → characteristics (deal type and conditional fields) →
/// title/description/price → photos → location → contact → preview.
/// Category-specific steps from a schema's `extraSteps` follow [details].
enum DraftStep {
  category,
  subcategory,
  details,
  basics,
  photos,
  location,
  contact,
  preview,
}

/// Everything the create/edit wizard collects. Saved after every change so
/// nothing is lost when the user leaves the screen.
@immutable
class ListingDraft {
  const ListingDraft({
    required this.id,
    required this.updatedAt,
    this.editingListingId,
    this.categoryId,
    this.title = '',
    this.description = '',
    this.priceText = '',
    this.currency = Currency.tjs,
    this.isNegotiable = false,
    this.attributes = const {},
    this.photos = const [],
    this.regionId,
    this.placeId,
    this.placeName,
    this.addressNote = '',
    this.contactName = '',
    this.contactPhone = '',
    this.phoneVisibility = PhoneVisibility.visible,
    this.chatEnabled = true,
    this.step = DraftStep.category,
  });

  final String id;

  /// Set when the draft edits an already published listing.
  final String? editingListingId;
  final String? categoryId;
  final String title;
  final String description;

  /// Raw text from the price field; parsed on publish.
  final String priceText;
  final Currency currency;
  final bool isNegotiable;
  final Map<String, Object?> attributes;
  final List<String> photos;
  final String? regionId;

  /// Settlement picked from the places directory, if any.
  final int? placeId;
  final String? placeName;
  final String addressNote;
  final String contactName;
  final String contactPhone;
  final PhoneVisibility phoneVisibility;
  final bool chatEnabled;
  final DraftStep step;
  final DateTime updatedAt;

  bool get isEditing => editingListingId != null;

  bool get isEmpty =>
      categoryId == null &&
      title.trim().isEmpty &&
      description.trim().isEmpty &&
      photos.isEmpty;

  factory ListingDraft.fromListing(
    Listing listing,
    String draftId,
    DateTime now,
  ) {
    return ListingDraft(
      id: draftId,
      editingListingId: listing.id,
      categoryId: listing.categoryId,
      title: listing.title,
      description: listing.description,
      priceText: listing.price?.toString() ?? '',
      currency: listing.currency,
      isNegotiable: listing.isNegotiable,
      attributes: Map.of(listing.attributes),
      photos: List.of(listing.photos),
      regionId: listing.regionId,
      placeId: listing.placeId,
      placeName: listing.placeName,
      addressNote: listing.addressNote ?? '',
      contactName: listing.contact.name,
      contactPhone: listing.contact.phone,
      phoneVisibility: listing.contact.phoneVisibility,
      chatEnabled: listing.contact.chatEnabled,
      step: DraftStep.details,
      updatedAt: now,
    );
  }

  ListingDraft copyWith({
    String? categoryId,
    String? title,
    String? description,
    String? priceText,
    Currency? currency,
    bool? isNegotiable,
    Map<String, Object?>? attributes,
    List<String>? photos,
    String? regionId,
    int? placeId,
    String? placeName,
    bool clearPlace = false,
    String? addressNote,
    String? contactName,
    String? contactPhone,
    PhoneVisibility? phoneVisibility,
    bool? chatEnabled,
    DraftStep? step,
    DateTime? updatedAt,
  }) {
    return ListingDraft(
      id: id,
      editingListingId: editingListingId,
      categoryId: categoryId ?? this.categoryId,
      title: title ?? this.title,
      description: description ?? this.description,
      priceText: priceText ?? this.priceText,
      currency: currency ?? this.currency,
      isNegotiable: isNegotiable ?? this.isNegotiable,
      attributes: attributes ?? this.attributes,
      photos: photos ?? this.photos,
      regionId: regionId ?? this.regionId,
      placeId: clearPlace ? null : (placeId ?? this.placeId),
      placeName: clearPlace ? null : (placeName ?? this.placeName),
      addressNote: addressNote ?? this.addressNote,
      contactName: contactName ?? this.contactName,
      contactPhone: contactPhone ?? this.contactPhone,
      phoneVisibility: phoneVisibility ?? this.phoneVisibility,
      chatEnabled: chatEnabled ?? this.chatEnabled,
      step: step ?? this.step,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'editingListingId': editingListingId,
    'categoryId': categoryId,
    'title': title,
    'description': description,
    'priceText': priceText,
    'currency': currency.code,
    'isNegotiable': isNegotiable,
    'attributes': attributes,
    'photos': photos,
    'regionId': regionId,
    'placeId': placeId,
    'placeName': placeName,
    'addressNote': addressNote,
    'contactName': contactName,
    'contactPhone': contactPhone,
    'phoneVisibility': phoneVisibility.name,
    'chatEnabled': chatEnabled,
    'step': step.name,
    'updatedAt': updatedAt.toIso8601String(),
  };

  factory ListingDraft.fromJson(Map<String, dynamic> json) => ListingDraft(
    id: json['id'] as String,
    editingListingId: json['editingListingId'] as String?,
    categoryId: json['categoryId'] as String?,
    title: json['title'] as String? ?? '',
    description: json['description'] as String? ?? '',
    priceText: json['priceText'] as String? ?? '',
    currency: Currency.fromCode(json['currency'] as String?),
    isNegotiable: json['isNegotiable'] as bool? ?? false,
    attributes: Map<String, Object?>.from(
      json['attributes'] as Map? ?? const {},
    ),
    photos: List<String>.from(json['photos'] as List? ?? const []),
    regionId: json['regionId'] as String?,
    placeId: (json['placeId'] as num?)?.toInt(),
    placeName: json['placeName'] as String?,
    addressNote: json['addressNote'] as String? ?? '',
    contactName: json['contactName'] as String? ?? '',
    contactPhone: json['contactPhone'] as String? ?? '',
    phoneVisibility: PhoneVisibility.values.byName(
      json['phoneVisibility'] as String? ?? PhoneVisibility.visible.name,
    ),
    chatEnabled: json['chatEnabled'] as bool? ?? true,
    step:
        DraftStep.values.asNameMap()[json['step'] as String?] ??
        DraftStep.category,
    updatedAt:
        DateTime.tryParse(json['updatedAt'] as String? ?? '') ?? DateTime.now(),
  );
}

abstract interface class DraftRepository {
  List<ListingDraft> all();
  ListingDraft? get(String id);
  Future<void> save(ListingDraft draft);
  Future<void> delete(String id);
}
