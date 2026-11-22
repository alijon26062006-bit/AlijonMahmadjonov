import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/backend/backend.dart';
import '../../../shared/models/user.dart';
import '../domain/business_profile.dart';

/// Seller cards and business profiles on the DARYOB server.
class ServerSellerRepository implements SellerRepository {
  ServerSellerRepository(this._client);

  final SupabaseClient _client;

  @override
  Future<SellerSummary?> seller(String userId) {
    if (!isServerId(userId)) return Future.value();
    return backendCall(() async {
      final result = await _client.rpc<dynamic>(
        'seller_summary',
        params: {'p_user': userId},
      );
      if (result == null) return null;
      final row = Map<String, dynamic>.from(result as Map);
      final company = await business(userId);
      final name = (row['name'] as String?)?.trim() ?? '';
      return SellerSummary(
        id: userId,
        name: company?.name ?? (name.isEmpty ? '—' : name),
        memberSince:
            DateTime.tryParse(row['created_at'] as String? ?? '') ?? DateTime.now(),
        isVerified: row['is_phone_verified'] as bool? ?? false,
        isBusiness: company != null || row['account_type'] == AccountType.business.name,
      );
    });
  }

  @override
  Future<BusinessProfile?> business(String ownerId) {
    if (!isServerId(ownerId)) return Future.value();
    return backendCall(() async {
      final row = await _client
          .from('business_profiles')
          .select('data')
          .eq('owner_id', ownerId)
          .maybeSingle();
      if (row == null) return null;
      return _fromData(ownerId, Map<String, dynamic>.from(row['data'] as Map));
    });
  }

  @override
  Future<BusinessProfile> saveBusiness(BusinessProfile profile) {
    return backendCall(() async {
      final data = profile.toJson()
        // Verification and subscription are granted by the platform, not
        // written by the owner; local file paths mean nothing to others.
        ..remove('verification')
        ..remove('subscription')
        ..remove('ownerId');
      for (final key in ['logoPath', 'coverPath']) {
        final value = data[key] as String?;
        if (value != null && !value.startsWith('http')) data.remove(key);
      }
      await _client.from('business_profiles').upsert({
        'owner_id': profile.ownerId,
        'data': data,
        'updated_at': DateTime.now().toUtc().toIso8601String(),
      });
      return _fromData(profile.ownerId, data);
    });
  }

  BusinessProfile _fromData(String ownerId, Map<String, dynamic> data) =>
      BusinessProfile.fromJson({
        ...data,
        'ownerId': ownerId,
        'verification': VerificationStatus.notSubmitted.name,
        'subscription': SubscriptionTier.none.name,
      });
}
