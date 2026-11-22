import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/authentication/data/demo_auth_repository.dart';
import '../../features/authentication/domain/auth_repository.dart';
import '../../features/conversations/data/local_conversation_repository.dart';
import '../../features/conversations/domain/conversation.dart';
import '../../features/favorites/data/favorites_repository.dart';
import '../../features/listings/data/api_listing_repository.dart';
import '../../features/listings/data/demo_seed.dart';
import '../../features/listings/data/local_draft_repository.dart';
import '../../features/listings/data/local_listing_repository.dart';
import '../../features/listings/domain/listing_draft.dart';
import '../../features/listings/domain/listing_repository.dart';
import '../../features/notifications/data/local_notification_repository.dart';
import '../../features/notifications/domain/app_notification.dart';
import '../../features/promotions/data/promotion_repository.dart';
import '../../features/promotions/domain/monetization.dart';
import '../../features/search/data/search_history_repository.dart';
import '../../features/sellers/data/local_seller_repository.dart';
import '../../features/sellers/domain/business_profile.dart';
import '../../features/settings/data/settings_repository.dart';
import 'core_providers.dart';

/// Chooses implementations by environment:
///  * development → local persistent repositories with demo data;
///  * production  → API repositories when an API URL is configured,
///                  otherwise explicit "unavailable" implementations.

final listingRepositoryProvider = Provider<ListingRepository>((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.isDevelopment) {
    return LocalListingRepository(
      database: ref.watch(localDatabaseProvider),
      categories: ref.watch(categoryRegistryProvider),
      schemas: ref.watch(schemaRegistryProvider),
      regions: ref.watch(regionDirectoryProvider),
      clock: ref.watch(clockProvider),
    );
  }
  final api = ref.watch(apiClientProvider);
  return api == null
      ? const UnavailableListingRepository()
      : ApiListingRepository(api);
});

final draftRepositoryProvider = Provider<DraftRepository>(
  (ref) => LocalDraftRepository(ref.watch(localDatabaseProvider)),
);

final favoritesRepositoryProvider = Provider<FavoritesRepository>(
  (ref) => LocalFavoritesRepository(ref.watch(localDatabaseProvider)),
);

final searchHistoryRepositoryProvider = Provider<SearchHistoryRepository>(
  (ref) => SearchHistoryRepository(ref.watch(localDatabaseProvider)),
);

final settingsRepositoryProvider = Provider<SettingsRepository>(
  (ref) => SettingsRepository(ref.watch(localDatabaseProvider)),
);

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.isDevelopment) {
    return DemoAuthRepository(
      database: ref.watch(localDatabaseProvider),
      session: ref.watch(sessionStorageProvider),
      clock: ref.watch(clockProvider),
    );
  }
  // A real implementation calls the backend, which talks to the SMS
  // provider. Until it exists, production reports the missing integration.
  return const UnconfiguredAuthRepository();
});

final conversationRepositoryProvider = Provider<ConversationRepository>((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.isDevelopment) {
    return LocalConversationRepository(
      ref.watch(localDatabaseProvider),
      ref.watch(clockProvider),
    );
  }
  return const UnavailableConversationRepository();
});

final notificationRepositoryProvider = Provider<NotificationRepository>(
  (ref) => LocalNotificationRepository(ref.watch(localDatabaseProvider)),
);

final pushServiceProvider = Provider<PushNotificationService>(
  (ref) => const UnconfiguredPushService(),
);

final sellerRepositoryProvider = Provider<SellerRepository>(
  (ref) => LocalSellerRepository(ref.watch(localDatabaseProvider)),
);

final promotionRepositoryProvider = Provider<PromotionRepository>(
  (ref) => ConfigPromotionRepository(
    isDevelopment: ref.watch(appConfigProvider).isDevelopment,
  ),
);

final paymentGatewayProvider = Provider<PaymentGateway>(
  (ref) => const UnconfiguredPaymentGateway(),
);

final demoSeederProvider = Provider<DemoSeeder>(
  (ref) =>
      DemoSeeder(ref.watch(localDatabaseProvider), ref.watch(clockProvider)),
);
