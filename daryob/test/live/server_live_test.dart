// End-to-end checks against the real DARYOB server. They create two
// throw-away accounts and delete them at the end.
//
// Skipped unless DARYOB_LIVE=1:
//   DARYOB_LIVE=1 flutter test test/live/server_live_test.dart
import 'dart:async';
import 'dart:io';

import 'package:daryob/core/errors/failure.dart';
import 'package:daryob/core/security/session_storage.dart';
import 'package:daryob/features/authentication/data/server_auth_repository.dart';
import 'package:daryob/features/categories/data/tajikistan_regions.dart';
import 'package:daryob/features/categories/domain/region_directory.dart';
import 'package:daryob/features/conversations/data/server_conversation_repository.dart';
import 'package:daryob/features/conversations/domain/conversation.dart';
import 'package:daryob/features/favorites/data/favorites_repository.dart';
import 'package:daryob/features/favorites/data/synced_favorites_repository.dart';
import 'package:daryob/features/listings/data/server_listing_repository.dart';
import 'package:daryob/features/listings/domain/draft_validator.dart';
import 'package:daryob/features/listings/domain/listing_query.dart';
import 'package:daryob/features/sellers/data/server_seller_repository.dart';
import 'package:daryob/core/storage/local_database.dart';
import 'package:daryob/shared/models/listing.dart';
import 'package:daryob/shared/models/user.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart' show SupabaseClient;

import '../helpers.dart';

const _url = 'https://thmptlegknxlbxmmkyrl.supabase.co';
const _key = 'sb_publishable_tZDxituO7EfLL4NYag1nVw_ndkPeLdO';

class _EnvProxy extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      super.createHttpClient(context)..findProxy = HttpClient.findProxyFromEnvironment;
}

class _Device {
  _Device() : client = SupabaseClient(_url, _key) {
    auth = ServerAuthRepository(client: client, storage: storage, clock: DateTime.now);
    listings = ServerListingRepository(
      client: client,
      categories: testCategories(),
      schemas: testSchemas(),
      regions: RegionDirectory(tajikistanRegions),
      validator: DraftValidator(testCategories(), testSchemas()),
    );
    chat = ServerConversationRepository(client);
    sellers = ServerSellerRepository(client);
  }

  final SupabaseClient client;
  final storage = MemorySessionStorage();
  late final ServerAuthRepository auth;
  late final ServerListingRepository listings;
  late final ServerConversationRepository chat;
  late final ServerSellerRepository sellers;
  late AppUser user;

  Future<void> signIn(String phone, String name) async {
    final challenge = await auth.requestCode(phone);
    expect(challenge.requiresCode, isFalse);
    user = await auth.verifyCode(challenge, '');
    user = await auth.updateProfile(user.copyWith(name: name, regionId: 'khujand'));
  }
}

void main() {
  final live = Platform.environment['DARYOB_LIVE'] == '1';

  test('real server: account, listing with photo, search, chat', () async {
    HttpOverrides.global = _EnvProxy();
    final seller = _Device();
    final buyer = _Device();
    addTearDown(() async {
      for (final d in [seller, buyer]) {
        try {
          await d.auth.requestAccountDeletion(d.user);
        } catch (_) {}
        await d.client.dispose();
      }
    });

    // ── Accounts ────────────────────────────────────────────────────────
    await seller.signIn('93 123 45 67', 'Живой Тест Продавец');
    await buyer.signIn('90 765 43 21', 'Живой Тест Покупатель');
    expect(seller.user.phone, '931234567');
    expect(seller.user.name, 'Живой Тест Продавец');
    expect(seller.user.isPhoneVerified, isFalse);
    expect(seller.user.id, isNot(buyer.user.id));

    // The same device signs back into the same account.
    await seller.auth.signOut();
    expect(await seller.auth.restoreSession(), isNull);
    final again = await seller.auth.verifyCode(await seller.auth.requestCode('931234567'), '');
    expect(again.id, seller.user.id);

    // ── Publish with a photo and a hidden phone ─────────────────────────
    final photo = File('${Directory.systemTemp.path}/daryob-live-${DateTime.now().microsecondsSinceEpoch}.png')
      ..writeAsBytesSync(_png);
    addTearDown(photo.deleteSync);
    final marker = 'LIVE${DateTime.now().millisecondsSinceEpoch}';
    final draft = validDraft(title: 'iPhone 13 $marker', price: '4900').copyWith(
      photos: [photo.path],
      phoneVisibility: PhoneVisibility.hidden,
    );
    final listing = await seller.listings.publish(draft, ownerId: seller.user.id);
    expect(listing.status, ListingStatus.active);
    expect(listing.ownerId, seller.user.id);
    expect(listing.categoryId, 'electronics.smartphones');
    expect(listing.price, 4900);
    expect(listing.photos.single, startsWith('$_url/storage/v1/object/public/listing-photos/${seller.user.id}/'));
    expect(listing.isLocalOnly, isFalse);

    // The photo is really downloadable.
    final http = HttpClient()..findProxy = HttpClient.findProxyFromEnvironment;
    final response = await (await http.getUrl(Uri.parse(listing.photos.single))).close();
    expect(response.statusCode, 200);
    await response.drain<void>();
    http.close();

    // The buyer sees the listing but not the hidden number; the owner does.
    final seenByBuyer = (await buyer.listings.getById(listing.id))!;
    expect(seenByBuyer.contact.phone, isEmpty);
    expect(seenByBuyer.contact.phoneVisibility, PhoneVisibility.hidden);
    expect((await seller.listings.getById(listing.id))!.contact.phone, '931234567');
    expect((await seller.listings.byOwner(seller.user.id)).single.contact.phone, '931234567');

    // ── Search with the catalog filters ─────────────────────────────────
    Future<int> count(ListingQuery q) async => (await buyer.listings.search(q)).total!;
    expect(await count(ListingQuery(text: marker)), 1);
    expect(await count(ListingQuery(text: marker, categoryId: 'electronics')), 1);
    expect(await count(ListingQuery(text: marker, categoryId: 'vehicles')), 0);
    expect(await count(ListingQuery(text: marker, regionId: 'sughd')), 1);
    expect(await count(ListingQuery(text: marker, regionId: 'khatlon')), 0);
    expect(await count(ListingQuery(text: marker, minPrice: 1000, maxPrice: 5000)), 1);
    expect(await count(ListingQuery(text: marker, minPrice: 5000)), 0);
    expect(
      await count(
        ListingQuery(
          text: marker,
          attributeFilters: const {
            'brand_id': EqualsFilter('apple'),
            'storage_gb': RangeFilter(min: 64, max: 256),
            'condition': AnyOfFilter({'used', 'like_new'}),
          },
        ),
      ),
      1,
    );
    expect(
      await count(ListingQuery(text: marker, attributeFilters: const {'storage_gb': RangeFilter(min: 256)})),
      0,
    );
    expect((await buyer.listings.countByCategory())['electronics'], greaterThanOrEqualTo(1));

    // ── Somebody else cannot change or delete it ────────────────────────
    await expectLater(
      buyer.listings.changeStatus(listing.id, ListingStatus.archived, actingUserId: buyer.user.id),
      throwsA(isA<ForbiddenFailure>()),
    );
    await expectLater(
      buyer.listings.delete(listing.id, actingUserId: buyer.user.id),
      throwsA(isA<ForbiddenFailure>()),
    );

    // ── Favourites follow the account ───────────────────────────────────
    final favorites = SyncedFavoritesRepository(LocalFavoritesRepository(MemoryLocalDatabase()), buyer.client);
    await favorites.add(buyer.user.id, listing.id);
    final otherPhone = SyncedFavoritesRepository(LocalFavoritesRepository(MemoryLocalDatabase()), buyer.client);
    expect(await otherPhone.mergeGuestInto(buyer.user.id), [listing.id]);

    // ── Seller card ─────────────────────────────────────────────────────
    final card = (await buyer.sellers.seller(seller.user.id))!;
    expect(card.name, 'Живой Тест Продавец');
    expect(card.isVerified, isFalse);

    // ── Chat with realtime delivery ─────────────────────────────────────
    final conversation = await buyer.chat.openForListing(
      ownerId: buyer.user.id,
      listingId: listing.id,
      listingTitle: listing.title,
      listingPhoto: null,
      sellerId: seller.user.id,
      sellerName: '',
      isDemo: false,
    );
    expect(conversation.otherPartyName, 'Живой Тест Продавец');
    expect(conversation.listingTitle, listing.title);

    final arrived = Completer<void>();
    final subscription = seller.chat.watch(seller.user.id).listen((_) {
      if (!arrived.isCompleted) arrived.complete();
    });
    // The server needs a few seconds to start streaming a new subscription.
    await Future<void>.delayed(const Duration(seconds: 8));
    final sent = await buyer.chat.send(conversation.id, buyer.user.id, 'Салом! Ещё продаётся?');
    expect(sent.state, DeliveryState.sent);
    var realtime = true;
    await arrived.future.timeout(const Duration(seconds: 15), onTimeout: () => realtime = false);
    await subscription.cancel();

    final inbox = await seller.chat.list(seller.user.id);
    expect(inbox.single.lastMessage, 'Салом! Ещё продаётся?');
    expect(inbox.single.unreadCount, 1);
    expect(inbox.single.otherPartyName, 'Живой Тест Покупатель');
    await seller.chat.markRead(conversation.id);
    expect((await seller.chat.list(seller.user.id)).single.unreadCount, 0);
    expect((await buyer.chat.messages(conversation.id)).single.state, DeliveryState.read);

    // Blocking stops new messages.
    await seller.chat.setBlocked(conversation.id, true);
    await expectLater(
      buyer.chat.send(conversation.id, buyer.user.id, 'ещё одно'),
      throwsA(isA<ForbiddenFailure>()),
    );

    // ── Edit, sell, delete ──────────────────────────────────────────────
    final edited = await seller.listings.update(
      listing.id,
      draft.copyWith(title: 'iPhone 13 $marker торг', photos: listing.photos),
      actingUserId: seller.user.id,
    );
    expect(edited.title, endsWith('торг'));
    expect(edited.photos, listing.photos);
    final sold = await seller.listings.changeStatus(listing.id, ListingStatus.sold, actingUserId: seller.user.id);
    expect(sold.status, ListingStatus.sold);
    expect(await count(ListingQuery(text: marker)), 0);
    await seller.listings.delete(listing.id, actingUserId: seller.user.id);
    expect(await seller.listings.getById(listing.id), isNull);

    // Report this last so the outcome is visible in the test log.
    // ignore: avoid_print
    print('realtime delivery: ${realtime ? 'OK' : 'NOT CONFIRMED (no event within 15 s)'}');
    expect(realtime, isTrue, reason: 'no realtime event reached the seller');
  }, skip: live ? false : 'set DARYOB_LIVE=1 to run against the real server', timeout: const Timeout(Duration(minutes: 3)));
}

final _png = <int>[
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
  0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
  0x89, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x60, 0x00, 0x00, 0x02,
  0x00, 0x00, 0x01, 0xe2, 0x21, 0xbc, 0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae,
  0x42, 0x60, 0x82,
];
