import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../features/authentication/presentation/auth_screen.dart';
import '../../features/categories/presentation/categories_screen.dart';
import '../../features/categories/presentation/category_listings_screen.dart';
import '../../features/conversations/presentation/chats_screen.dart';
import '../../features/conversations/presentation/conversation_screen.dart';
import '../../features/favorites/presentation/favorites_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/listings/presentation/create/create_listing_screen.dart';
import '../../features/listings/presentation/detail/listing_detail_screen.dart';
import '../../features/listings/presentation/drafts_screen.dart';
import '../../features/listings/presentation/my_listings_screen.dart';
import '../../features/notifications/presentation/notifications_screen.dart';
import '../../features/onboarding/presentation/onboarding_screen.dart';
import '../../features/onboarding/presentation/splash_screen.dart';
import '../../features/profile/presentation/edit_profile_screen.dart';
import '../../features/profile/presentation/info_screen.dart';
import '../../features/profile/presentation/profile_screen.dart';
import '../../features/profile/presentation/safety_screen.dart';
import '../../features/promotions/presentation/my_promotions_screen.dart';
import '../../features/promotions/presentation/promote_listing_screen.dart';
import '../../features/promotions/presentation/wallet_screen.dart';
import '../../features/search/presentation/search_screen.dart';
import '../../features/sellers/presentation/business_screen.dart';
import '../../features/sellers/presentation/seller_profile_screen.dart';
import '../../features/sellers/presentation/subscription_screen.dart';
import '../../features/settings/application/settings_controller.dart';
import '../../features/settings/presentation/dev_tools_screen.dart';
import '../../features/settings/presentation/settings_screen.dart';
import '../../shared/providers/core_providers.dart';
import '../../shared/widgets/main_shell.dart';
import 'routes.dart';

final rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');

final routerProvider = Provider<GoRouter>((ref) {
  final config = ref.read(appConfigProvider);

  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: Routes.splash,
    debugLogDiagnostics: false,
    redirect: (context, state) {
      final settings = ref.read(settingsControllerProvider);
      final location = state.matchedLocation;
      final open = location == Routes.splash || location == Routes.onboarding;
      if (!settings.onboardingCompleted && !open) return Routes.onboarding;
      if (location == Routes.devTools && !config.isDevelopment) {
        return Routes.home;
      }
      return null;
    },
    routes: [
      GoRoute(path: Routes.splash, builder: (_, _) => const SplashScreen()),
      GoRoute(
        path: Routes.onboarding,
        builder: (_, _) => const OnboardingScreen(),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => MainShell(navigationShell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(path: Routes.home, builder: (_, _) => const HomeScreen()),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.favorites,
                builder: (_, _) => const FavoritesScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.create,
                builder: (_, state) => CreateListingScreen(
                  key: const ValueKey('create-tab'),
                  draftId: state.uri.queryParameters['draft'],
                  isTab: true,
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.chats,
                builder: (_, _) => const ChatsScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.profile,
                builder: (_, _) => const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: Routes.categories,
        builder: (_, _) => const CategoriesScreen(),
      ),
      GoRoute(
        path: '/category/:slug',
        builder: (_, state) =>
            CategoryListingsScreen(slug: state.pathParameters['slug']!),
      ),
      GoRoute(
        path: '/listing/:id',
        builder: (_, state) =>
            ListingDetailScreen(listingId: state.pathParameters['id']!),
        routes: [
          GoRoute(
            path: 'edit',
            builder: (_, state) =>
                CreateListingScreen(editListingId: state.pathParameters['id']),
          ),
        ],
      ),
      GoRoute(
        path: '/seller/:id',
        builder: (_, state) =>
            SellerProfileScreen(sellerId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: Routes.search,
        builder: (_, state) => SearchScreen(
          initialCategoryId: state.uri.queryParameters['category'],
        ),
      ),
      GoRoute(
        path: Routes.auth,
        pageBuilder: (_, _) =>
            const MaterialPage(fullscreenDialog: true, child: AuthScreen()),
      ),
      GoRoute(
        path: '/chat/:id',
        builder: (_, state) =>
            ConversationScreen(conversationId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: Routes.notifications,
        builder: (_, _) => const NotificationsScreen(),
      ),
      GoRoute(
        path: Routes.myListings,
        builder: (_, _) => const MyListingsScreen(),
      ),
      GoRoute(path: Routes.drafts, builder: (_, _) => const DraftsScreen()),
      GoRoute(
        path: '/promote/:id',
        builder: (_, state) =>
            PromoteListingScreen(listingId: state.pathParameters['id']!),
      ),
      GoRoute(path: Routes.wallet, builder: (_, _) => const WalletScreen()),
      GoRoute(
        path: Routes.myPromotions,
        builder: (_, _) => const MyPromotionsScreen(),
      ),
      GoRoute(
        path: Routes.business,
        builder: (_, _) => const BusinessScreen(),
        routes: [
          GoRoute(
            path: 'subscription',
            builder: (_, _) => const SubscriptionScreen(),
          ),
        ],
      ),
      GoRoute(path: Routes.settings, builder: (_, _) => const SettingsScreen()),
      GoRoute(
        path: Routes.editProfile,
        builder: (_, _) => const EditProfileScreen(),
      ),
      GoRoute(path: Routes.safety, builder: (_, _) => const SafetyScreen()),
      GoRoute(
        path: '/info/:page',
        builder: (_, state) => InfoScreen(page: state.pathParameters['page']!),
      ),
      GoRoute(path: Routes.devTools, builder: (_, _) => const DevToolsScreen()),
    ],
  );
});
