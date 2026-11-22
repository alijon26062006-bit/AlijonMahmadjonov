import 'package:flutter/foundation.dart';

import '../../../shared/models/listing.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/models/money.dart';

/// A purchasable promotion. Plans come from configuration, never from code,
/// so prices can change without an app update.
@immutable
class PromotionPlan {
  const PromotionPlan({
    required this.id,
    required this.type,
    required this.durationDays,
    required this.title,
    required this.perks,
    this.price,
    this.currency = Currency.tjs,
    this.isSamplePrice = false,
  });

  final String id;
  final PromotionType type;
  final int durationDays;
  final LocalizedText title;
  final List<LocalizedText> perks;

  /// Null when the price is not set yet.
  final int? price;
  final Currency currency;

  /// Price is a placeholder from the development config, not a real tariff.
  final bool isSamplePrice;

  factory PromotionPlan.fromJson(
    Map<String, dynamic> json, {
    required bool sample,
  }) {
    return PromotionPlan(
      id: json['id'] as String,
      type: PromotionType.values.byName(json['type'] as String),
      durationDays: (json['durationDays'] as num).toInt(),
      title: LocalizedText.fromJson(
        Map<String, dynamic>.from(json['title'] as Map),
      ),
      perks: (json['perks'] as List? ?? const [])
          .map(
            (p) => LocalizedText.fromJson(Map<String, dynamic>.from(p as Map)),
          )
          .toList(),
      price: (json['price'] as num?)?.toInt(),
      currency: Currency.fromCode(json['currency'] as String?),
      isSamplePrice: sample,
    );
  }
}

enum PromotionStatus { pendingPayment, active, expired, cancelled }

enum PaymentStatus { created, pending, succeeded, failed, refunded }

enum WalletTransactionType { topUp, purchase, refund }

@immutable
class Wallet {
  const Wallet({required this.balance, this.currency = Currency.tjs});
  final int balance;
  final Currency currency;
}

@immutable
class WalletTransaction {
  const WalletTransaction({
    required this.id,
    required this.type,
    required this.amount,
    required this.createdAt,
    this.description,
  });

  final String id;
  final WalletTransactionType type;
  final int amount;
  final DateTime createdAt;
  final String? description;
}

@immutable
class Payment {
  const Payment({
    required this.id,
    required this.amount,
    required this.currency,
    required this.status,
    required this.provider,
    required this.createdAt,
  });

  final String id;
  final int amount;
  final Currency currency;
  final PaymentStatus status;
  final String provider;
  final DateTime createdAt;
}

@immutable
class PromotionPurchase {
  const PromotionPurchase({
    required this.id,
    required this.listingId,
    required this.planId,
    required this.status,
    required this.createdAt,
    this.paymentId,
    this.startsAt,
    this.endsAt,
  });

  final String id;
  final String listingId;
  final String planId;
  final String? paymentId;
  final PromotionStatus status;
  final DateTime createdAt;
  final DateTime? startsAt;
  final DateTime? endsAt;
}

@immutable
class Subscription {
  const Subscription({
    required this.id,
    required this.planId,
    required this.status,
    required this.startsAt,
    required this.endsAt,
  });

  final String id;
  final String planId;
  final PromotionStatus status;
  final DateTime startsAt;
  final DateTime endsAt;
}

/// Payment provider adapter (local Tajik providers will implement this on
/// top of the server API). Never activates anything without a confirmed
/// payment from the server.
abstract interface class PaymentGateway {
  bool get isConfigured;
  Future<Payment> payForPromotion({
    required String listingId,
    required PromotionPlan plan,
  });
}

abstract interface class PromotionRepository {
  Future<List<PromotionPlan>> plans();
  Future<Wallet> wallet(String userId);
  Future<List<WalletTransaction>> transactions(String userId);
  Future<List<PromotionPurchase>> purchases(String userId);
}
