import 'dart:convert';

import 'package:flutter/services.dart';

import '../../../core/errors/failure.dart';
import '../domain/monetization.dart';

/// Reads plans from `assets/config/promotion_plans.json`. Wallet and history
/// are empty until a payment provider is connected — no invented balances
/// or transactions.
class ConfigPromotionRepository implements PromotionRepository {
  ConfigPromotionRepository({required this.isDevelopment, AssetBundle? bundle})
    : _bundle = bundle ?? rootBundle;

  final bool isDevelopment;
  final AssetBundle _bundle;
  List<PromotionPlan>? _cache;

  static const assetPath = 'assets/config/promotion_plans.json';

  @override
  Future<List<PromotionPlan>> plans() async {
    if (_cache != null) return _cache!;
    final raw = await _bundle.loadString(assetPath);
    final json = jsonDecode(raw) as Map<String, dynamic>;
    // Prices in the bundled file are samples; production reads real prices
    // from the server.
    final sample = json['pricesAreSamples'] as bool? ?? true;
    final plans = (json['plans'] as List)
        .map(
          (p) => PromotionPlan.fromJson(
            Map<String, dynamic>.from(p as Map),
            sample: sample,
          ),
        )
        .map(
          (p) => isDevelopment || !sample
              ? p
              : PromotionPlan(
                  id: p.id,
                  type: p.type,
                  durationDays: p.durationDays,
                  title: p.title,
                  perks: p.perks,
                ),
        )
        .toList();
    return _cache = plans;
  }

  @override
  Future<Wallet> wallet(String userId) async => const Wallet(balance: 0);

  @override
  Future<List<WalletTransaction>> transactions(String userId) async => const [];

  @override
  Future<List<PromotionPurchase>> purchases(String userId) async => const [];
}

/// No payment provider configured. Every payment attempt says so.
class UnconfiguredPaymentGateway implements PaymentGateway {
  const UnconfiguredPaymentGateway();

  @override
  bool get isConfigured => false;

  @override
  Future<Payment> payForPromotion({
    required String listingId,
    required PromotionPlan plan,
  }) => Future.error(
    const FeatureUnavailableFailure(UnavailableFeature.payments),
  );
}
