/// Every route path in one place.
abstract final class Routes {
  static const splash = '/splash';
  static const onboarding = '/onboarding';

  // Bottom navigation tabs.
  static const home = '/home';
  static const favorites = '/favorites';
  static const create = '/create';
  static const chats = '/chats';
  static const profile = '/profile';

  static const categories = '/categories';
  static String category(String slug) => '/category/$slug';
  static String listing(String id) => '/listing/$id';
  static String editListing(String id) => '/listing/$id/edit';
  static String seller(String id) => '/seller/$id';
  static const search = '/search';
  static const auth = '/auth';
  static String conversation(String id) => '/chat/$id';
  static const notifications = '/notifications';
  static const myListings = '/my-listings';
  static const drafts = '/drafts';
  static String promote(String listingId) => '/promote/$listingId';
  static const wallet = '/wallet';
  static const myPromotions = '/my-promotions';
  static const business = '/business';
  static const subscription = '/business/subscription';
  static const settings = '/settings';
  static const editProfile = '/profile/edit';
  static const safety = '/safety';
  static String info(String page) => '/info/$page';
  static const devTools = '/dev';
}

/// Static information pages.
abstract final class InfoPages {
  static const about = 'about';
  static const terms = 'terms';
  static const privacy = 'privacy';
  static const support = 'support';
  static const deletion = 'deletion';

  static const all = [about, terms, privacy, support, deletion];
}
