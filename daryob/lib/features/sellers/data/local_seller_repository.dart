import '../../../core/storage/local_database.dart';
import '../../../shared/models/user.dart';
import '../domain/business_profile.dart';

class LocalSellerRepository implements SellerRepository {
  LocalSellerRepository(LocalDatabase database)
    : _users = database.collection(Collections.users),
      _businesses = database.collection(Collections.businesses);

  final JsonCollection _users;
  final JsonCollection _businesses;

  @override
  Future<SellerSummary?> seller(String userId) async {
    final json = _users.get(userId);
    if (json == null) return null;
    final user = AppUser.fromJson(json);
    final business = await this.business(userId);
    return SellerSummary(
      id: user.id,
      name: business?.name ?? (user.hasProfile ? user.name! : '—'),
      memberSince: user.createdAt,
      isBusiness: business != null || user.accountType == AccountType.business,
      // Verification can only come from a server; local data is never verified.
      isVerified: false,
      isDemo: user.isDemo && user.id.startsWith('demo-seller-'),
    );
  }

  @override
  Future<BusinessProfile?> business(String ownerId) async {
    final json = _businesses.get(ownerId);
    return json == null ? null : BusinessProfile.fromJson(json);
  }

  @override
  Future<BusinessProfile> saveBusiness(BusinessProfile profile) async {
    await _businesses.put(profile.ownerId, profile.toJson());
    return profile;
  }
}
