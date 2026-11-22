import 'package:flutter/foundation.dart';

import '../../../shared/models/user.dart';

enum VerificationStatus { notSubmitted, pending, verified, rejected }

enum SubscriptionTier { none, start, pro }

@immutable
class BusinessProfile {
  const BusinessProfile({
    required this.ownerId,
    required this.name,
    required this.publicSlug,
    required this.createdAt,
    this.description = '',
    this.phone = '',
    this.regionId,
    this.address = '',
    this.logoPath,
    this.coverPath,
    this.verification = VerificationStatus.notSubmitted,
    this.subscription = SubscriptionTier.none,
  });

  final String ownerId;
  final String name;
  final String description;
  final String phone;
  final String? regionId;
  final String address;
  final String? logoPath;
  final String? coverPath;

  /// Set by the server only. The client can request verification but never
  /// mark itself verified.
  final VerificationStatus verification;
  final SubscriptionTier subscription;

  /// Identifier for the future public storefront URL.
  final String publicSlug;
  final DateTime createdAt;

  BusinessProfile copyWith({
    String? name,
    String? description,
    String? phone,
    String? regionId,
    String? address,
    String? logoPath,
    String? coverPath,
  }) {
    return BusinessProfile(
      ownerId: ownerId,
      name: name ?? this.name,
      description: description ?? this.description,
      phone: phone ?? this.phone,
      regionId: regionId ?? this.regionId,
      address: address ?? this.address,
      logoPath: logoPath ?? this.logoPath,
      coverPath: coverPath ?? this.coverPath,
      verification: verification,
      subscription: subscription,
      publicSlug: publicSlug,
      createdAt: createdAt,
    );
  }

  Map<String, dynamic> toJson() => {
    'ownerId': ownerId,
    'name': name,
    'description': description,
    'phone': phone,
    'regionId': regionId,
    'address': address,
    'logoPath': logoPath,
    'coverPath': coverPath,
    'verification': verification.name,
    'subscription': subscription.name,
    'publicSlug': publicSlug,
    'createdAt': createdAt.toIso8601String(),
  };

  factory BusinessProfile.fromJson(
    Map<String, dynamic> json,
  ) => BusinessProfile(
    ownerId: json['ownerId'] as String,
    name: json['name'] as String? ?? '',
    description: json['description'] as String? ?? '',
    phone: json['phone'] as String? ?? '',
    regionId: json['regionId'] as String?,
    address: json['address'] as String? ?? '',
    logoPath: json['logoPath'] as String?,
    coverPath: json['coverPath'] as String?,
    verification: VerificationStatus.values.byName(
      json['verification'] as String? ?? VerificationStatus.notSubmitted.name,
    ),
    subscription: SubscriptionTier.values.byName(
      json['subscription'] as String? ?? SubscriptionTier.none.name,
    ),
    publicSlug: json['publicSlug'] as String? ?? '',
    createdAt:
        DateTime.tryParse(json['createdAt'] as String? ?? '') ?? DateTime.now(),
  );
}

abstract interface class SellerRepository {
  /// Public seller card for a listing owner, or null if unknown.
  Future<SellerSummary?> seller(String userId);

  Future<BusinessProfile?> business(String ownerId);
  Future<BusinessProfile> saveBusiness(BusinessProfile profile);
}
