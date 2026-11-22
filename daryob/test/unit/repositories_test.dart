import 'package:daryob/core/errors/failure.dart';
import 'package:daryob/core/security/session_storage.dart';
import 'package:daryob/core/storage/local_database.dart';
import 'package:daryob/features/authentication/data/demo_auth_repository.dart';
import 'package:daryob/features/favorites/data/favorites_repository.dart';
import 'package:daryob/features/listings/data/demo_seed.dart';
import 'package:daryob/features/listings/data/local_draft_repository.dart';
import 'package:daryob/features/listings/domain/draft_validator.dart';
import 'package:daryob/features/listings/domain/listing_draft.dart';
import 'package:daryob/features/listings/domain/listing_query.dart';
import 'package:daryob/shared/models/listing.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

void main() {
  group('listing repository', () {
    late MemoryLocalDatabase db;
    setUp(() => db = MemoryLocalDatabase());

    test('publishes a valid draft as an active local listing', () async {
      final repo = listingRepo(db);
      final listing = await repo.publish(validDraft(), ownerId: 'u1');
      expect(listing.status, ListingStatus.active);
      expect(listing.isLocalOnly, isTrue);
      expect(listing.price, 2500);
      expect(listing.contact.phone, '931234567');
      expect(await repo.getById(listing.id), isNotNull);
    });

    test('refuses invalid drafts with field errors', () async {
      final repo = listingRepo(db);
      final draft = validDraft().copyWith(title: 'ab', contactPhone: '93');
      await expectLater(
        repo.publish(draft, ownerId: 'u1'),
        throwsA(
          isA<ValidationFailure>().having(
            (f) => f.fieldErrors.keys,
            'fields',
            containsAll([DraftField.title, DraftField.contactPhone]),
          ),
        ),
      );
    });

    test('only the owner can edit, change status or delete', () async {
      final repo = listingRepo(db);
      final listing = await repo.publish(validDraft(), ownerId: 'owner');
      final edit = ListingDraft.fromListing(
        listing,
        'e',
        fixedNow,
      ).copyWith(title: 'Новый заголовок');
      await expectLater(
        repo.update(listing.id, edit, actingUserId: 'stranger'),
        throwsA(isA<ForbiddenFailure>()),
      );
      await expectLater(
        repo.changeStatus(
          listing.id,
          ListingStatus.sold,
          actingUserId: 'stranger',
        ),
        throwsA(isA<ForbiddenFailure>()),
      );
      final updated = await repo.update(
        listing.id,
        edit,
        actingUserId: 'owner',
      );
      expect(updated.title, 'Новый заголовок');
    });

    test('status changes and deletion', () async {
      final repo = listingRepo(db);
      final listing = await repo.publish(validDraft(), ownerId: 'o');
      expect(
        (await repo.changeStatus(
          listing.id,
          ListingStatus.sold,
          actingUserId: 'o',
        )).status,
        ListingStatus.sold,
      );
      // Sold listings leave the public search.
      expect((await repo.search(const ListingQuery())).items, isEmpty);
      await repo.changeStatus(
        listing.id,
        ListingStatus.archived,
        actingUserId: 'o',
      );
      expect((await repo.byOwner('o')).single.status, ListingStatus.archived);
      await repo.delete(listing.id, actingUserId: 'o');
      expect(await repo.getById(listing.id), isNull);
    });

    test('free category stores price 0 and ignores typed price', () async {
      final repo = listingRepo(db);
      final listing = await repo.publish(
        validDraft(categoryId: 'free', price: ''),
        ownerId: 'o',
      );
      expect(listing.price, 0);
    });

    test('search filters by category, region, price and sorts', () async {
      final repo = listingRepo(db);
      await repo.publish(
        validDraft(id: 'a', title: 'Телефон дешёвый', price: '500'),
        ownerId: 'o',
      );
      await repo.publish(
        validDraft(id: 'b', title: 'Телефон дорогой', price: '9000'),
        ownerId: 'o',
      );
      await repo.publish(
        validDraft(
          id: 'c',
          title: 'Диван для гостиной',
          categoryId: 'home-furniture',
          price: '3000',
          regionId: 'kulob',
        ),
        ownerId: 'o',
      );

      final electronics = await repo.search(
        const ListingQuery(categoryId: 'electronics'),
      );
      expect(electronics.total, 2);

      final sughd = await repo.search(const ListingQuery(regionId: 'sughd'));
      expect(sughd.items.every((l) => l.regionId == 'khujand'), isTrue);

      final ranged = await repo.search(
        const ListingQuery(minPrice: 1000, maxPrice: 5000),
      );
      expect(ranged.items.single.title, 'Диван для гостиной');

      final cheapFirst = await repo.search(
        const ListingQuery(sort: ListingSort.priceAsc),
      );
      expect(cheapFirst.items.map((l) => l.price), [500, 3000, 9000]);

      final text = await repo.search(const ListingQuery(text: 'дорогой'));
      expect(text.items.single.price, 9000);

      final condition = await repo.search(
        const ListingQuery(attributeFilters: {'condition': 'new'}),
      );
      expect(condition.items, isEmpty);
    });

    test('paginates', () async {
      final repo = listingRepo(db);
      for (var i = 0; i < 5; i++) {
        await repo.publish(
          validDraft(id: 'p$i', title: 'Объявление номер $i'),
          ownerId: 'o',
        );
      }
      final first = await repo.search(const ListingQuery(pageSize: 2));
      expect(first.items.length, 2);
      expect(first.hasMore, isTrue);
      final last = await repo.search(const ListingQuery(pageSize: 2), page: 3);
      expect(last.items.length, 1);
      expect(last.hasMore, isFalse);
    });

    test('demo seed is labelled and removable', () async {
      final seeder = DemoSeeder(db, () => fixedNow);
      await seeder.seedIfNeeded();
      final repo = listingRepo(db);
      final all = await repo.search(const ListingQuery(pageSize: 100));
      expect(all.items, isNotEmpty);
      expect(all.items.every((l) => l.isDemo), isTrue);
      // VIP listings come first in the default ranking.
      expect(all.items.first.isVipAt(fixedNow), isTrue);
      await seeder.removeDemoData();
      expect((await repo.search(const ListingQuery())).items, isEmpty);
    });
  });

  group('drafts', () {
    test('round-trip through storage', () async {
      final repo = LocalDraftRepository(MemoryLocalDatabase());
      final draft = validDraft().copyWith(
        step: DraftStep.photos,
        photos: ['/tmp/a.jpg'],
      );
      await repo.save(draft);
      final loaded = repo.get(draft.id)!;
      expect(loaded.title, draft.title);
      expect(loaded.step, DraftStep.photos);
      expect(loaded.photos, ['/tmp/a.jpg']);
      expect(loaded.attributes['condition'], 'used');
      await repo.delete(draft.id);
      expect(repo.all(), isEmpty);
    });
  });

  group('favorites', () {
    test('newest first, no duplicates', () async {
      final repo = LocalFavoritesRepository(MemoryLocalDatabase());
      await repo.add('u', 'a');
      await repo.add('u', 'b');
      await repo.add('u', 'a');
      expect(repo.load('u'), ['a', 'b']);
      await repo.remove('u', 'a');
      expect(repo.load('u'), ['b']);
    });

    test('guest favourites merge into the account on sign-in', () async {
      final repo = LocalFavoritesRepository(MemoryLocalDatabase());
      await repo.add(kGuestOwner, 'x');
      await repo.add(kGuestOwner, 'y');
      await repo.add('user', 'y');
      await repo.add('user', 'z');
      final merged = await repo.mergeGuestInto('user');
      expect(merged.toSet(), {'x', 'y', 'z'});
      expect(merged.length, 3);
      expect(repo.load(kGuestOwner), isEmpty);
    });
  });

  group('demo authentication', () {
    late MemoryLocalDatabase db;
    late MemorySessionStorage session;
    late DemoAuthRepository auth;
    setUp(() {
      db = MemoryLocalDatabase();
      session = MemorySessionStorage();
      auth = DemoAuthRepository(
        database: db,
        session: session,
        clock: () => fixedNow,
      );
    });

    test('rejects malformed numbers', () async {
      await expectLater(
        auth.requestCode('93 12'),
        throwsA(isA<ValidationFailure>()),
      );
    });

    test('never marks the phone verified and rejects wrong codes', () async {
      final challenge = await auth.requestCode('93 123 45 67');
      expect(challenge.isDemo, isTrue);
      await expectLater(
        auth.verifyCode(challenge, '000000'),
        throwsA(isA<ValidationFailure>()),
      );
      final user = await auth.verifyCode(
        challenge,
        DemoAuthRepository.demoCode,
      );
      expect(user.isDemo, isTrue);
      expect(user.isPhoneVerified, isFalse);
      expect((await auth.restoreSession())!.id, user.id);
      await auth.signOut();
      expect(await auth.restoreSession(), isNull);
    });

    test('account deletion removes the user and their listings', () async {
      final challenge = await auth.requestCode('931234567');
      final user = await auth.verifyCode(
        challenge,
        DemoAuthRepository.demoCode,
      );
      final repo = listingRepo(db);
      await repo.publish(validDraft(), ownerId: user.id);
      await auth.requestAccountDeletion(user);
      expect(await repo.byOwner(user.id), isEmpty);
      expect(await auth.restoreSession(), isNull);
    });

    test('production without SMS provider refuses instead of faking', () async {
      const auth = UnconfiguredAuthRepository();
      await expectLater(
        auth.requestCode('931234567'),
        throwsA(isA<FeatureUnavailableFailure>()),
      );
    });
  });

  test('JSON documents survive the database round-trip', () async {
    final db = MemoryLocalDatabase();
    await db.collection(Collections.meta).put('k', {
      'a': 1,
      'b': ['x'],
    });
    expect(db.collection(Collections.meta).get('k'), {
      'a': 1,
      'b': ['x'],
    });
  });
}
