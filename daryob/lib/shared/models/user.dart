import 'package:flutter/foundation.dart';

enum AccountType { individual, business }

@immutable
class AppUser {
  const AppUser({
    required this.id,
    required this.phone,
    required this.createdAt,
    this.name,
    this.regionId,
    this.isPhoneVerified = false,
    this.accountType = AccountType.individual,
    this.isDemo = false,
  });

  final String id;

  /// National digits (9), without +992.
  final String phone;
  final String? name;
  final String? regionId;

  /// True only when a real SMS provider confirmed the number. Never set by
  /// the client in production; demo sign-in always leaves it false.
  final bool isPhoneVerified;
  final AccountType accountType;
  final DateTime createdAt;

  /// Signed in through the development-only demo flow (no SMS was sent).
  final bool isDemo;

  bool get hasProfile => (name ?? '').trim().isNotEmpty;

  AppUser copyWith({String? name, String? regionId, AccountType? accountType}) {
    return AppUser(
      id: id,
      phone: phone,
      createdAt: createdAt,
      name: name ?? this.name,
      regionId: regionId ?? this.regionId,
      isPhoneVerified: isPhoneVerified,
      accountType: accountType ?? this.accountType,
      isDemo: isDemo,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'phone': phone,
    'name': name,
    'regionId': regionId,
    'isPhoneVerified': isPhoneVerified,
    'accountType': accountType.name,
    'createdAt': createdAt.toIso8601String(),
    'isDemo': isDemo,
  };

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
    id: json['id'] as String,
    phone: json['phone'] as String? ?? '',
    name: json['name'] as String?,
    regionId: json['regionId'] as String?,
    isPhoneVerified: json['isPhoneVerified'] as bool? ?? false,
    accountType: AccountType.values.byName(
      json['accountType'] as String? ?? AccountType.individual.name,
    ),
    createdAt:
        DateTime.tryParse(json['createdAt'] as String? ?? '') ??
        DateTime.fromMillisecondsSinceEpoch(0),
    isDemo: json['isDemo'] as bool? ?? false,
  );
}

/// Public information about a seller shown on listings.
@immutable
class SellerSummary {
  const SellerSummary({
    required this.id,
    required this.name,
    required this.memberSince,
    this.avatarUrl,
    this.isVerified = false,
    this.isBusiness = false,
    this.isDemo = false,
  });

  final String id;
  final String name;
  final String? avatarUrl;
  final DateTime memberSince;

  /// Shown only when a backend actually verified the seller.
  final bool isVerified;
  final bool isBusiness;
  final bool isDemo;

  String get initials {
    final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty);
    return parts
        .take(2)
        .map((p) => String.fromCharCode(p.runes.first).toUpperCase())
        .join();
  }
}
