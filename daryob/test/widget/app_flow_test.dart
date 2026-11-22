import 'package:daryob/core/storage/local_database.dart';
import 'package:daryob/features/listings/presentation/create/create_listing_screen.dart';
import 'package:daryob/features/listings/presentation/detail/listing_detail_screen.dart';
import 'package:daryob/features/onboarding/presentation/onboarding_screen.dart';
import 'package:daryob/shared/widgets/listing_card.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

void main() {
  testWidgets('first launch: splash → onboarding → language → city → home', (
    tester,
  ) async {
    final db = MemoryLocalDatabase();
    await startApp(tester, db);

    expect(find.byType(OnboardingScreen), findsOneWidget);
    // Default language in tests is Russian (devConfig).
    expect(find.text('Всё, что нужно, рядом'), findsOneWidget);

    // Skip to the language page and pick Tajik.
    await tester.tap(find.text('Пропустить'));
    await pumpFor(tester, const Duration(milliseconds: 600));
    await tester.tap(find.text('Тоҷикӣ'));
    await pumpFor(tester, const Duration(milliseconds: 300));
    // The interface switches immediately.
    expect(find.text('Идома додан'), findsOneWidget);

    await tester.tap(find.text('Идома додан'));
    await pumpFor(tester, const Duration(milliseconds: 600));
    await tester.tap(find.text('Хуҷанд'));
    await pumpFor(tester, const Duration(milliseconds: 300));
    await tester.tap(find.text('Оғоз кардан'));
    await pumpFor(tester, const Duration(milliseconds: 800));

    // Home in Tajik, with seeded demo data.
    expect(find.text('Категорияҳо'), findsOneWidget);
    expect(find.text('Асосӣ'), findsOneWidget);
    final settings = db.collection(Collections.settings).get('app')!;
    expect(settings['languageCode'], 'tg');
    expect(settings['regionId'], 'khujand');
    expect(settings['onboardingCompleted'], isTrue);
  });

  testWidgets('onboarding is not shown again after completion', (tester) async {
    final db = MemoryLocalDatabase();
    await seedSettings(db);
    await startApp(tester, db);
    expect(find.byType(OnboardingScreen), findsNothing);
    expect(find.text('Категории'), findsOneWidget);
  });

  testWidgets('bottom navigation switches tabs', (tester) async {
    final db = MemoryLocalDatabase();
    await seedSettings(db);
    await startApp(tester, db);

    await tester.tap(find.text('Избранное'));
    await pumpFor(tester, const Duration(milliseconds: 500));
    expect(find.text('В избранном пусто'), findsOneWidget);

    await tester.tap(find.text('Чаты'));
    await pumpFor(tester, const Duration(milliseconds: 500));
    expect(find.text('Переписка с продавцами'), findsOneWidget);

    await tester.tap(find.text('Профиль'));
    await pumpFor(tester, const Duration(milliseconds: 500));
    expect(find.text('Добро пожаловать в DARYOB'), findsOneWidget);

    await tester.tap(find.text('Подать'));
    await pumpFor(tester, const Duration(milliseconds: 500));
    expect(find.byType(CreateListingScreen), findsOneWidget);
    expect(find.textContaining('Шаг 1 из 6'), findsOneWidget);
  });

  testWidgets('browse a category, open a listing, save it to favourites', (
    tester,
  ) async {
    final db = MemoryLocalDatabase();
    await seedSettings(db);
    await startApp(tester, db);

    await tester.tap(find.text('Телефоны и электроника').first);
    await pumpFor(tester, const Duration(milliseconds: 800));
    expect(find.byType(DaryobListingCard), findsWidgets);

    await tester.tap(find.byType(DaryobListingCard).first);
    await pumpFor(tester, const Duration(milliseconds: 800));
    expect(find.byType(ListingDetailScreen), findsOneWidget);
    // Demo data is labelled as such.
    expect(find.textContaining('демонстрационное объявление'), findsOneWidget);

    await tester.tap(find.byTooltip('Добавить в избранное'));
    await pumpFor(tester, const Duration(milliseconds: 400));
    expect(find.byIcon(Icons.favorite_rounded), findsWidgets);

    final saved = db.collection(Collections.favorites).get('guest')!;
    expect((saved['ids'] as List), hasLength(1));
  });

  testWidgets('create listing: validation blocks empty basics', (tester) async {
    final db = MemoryLocalDatabase();
    await seedSettings(db);
    await startApp(tester, db);

    await tester.tap(find.text('Подать'));
    await pumpFor(tester, const Duration(milliseconds: 500));
    await tester.tap(find.text('Телефоны и электроника'));
    await pumpFor(tester, const Duration(milliseconds: 500));
    expect(find.textContaining('Шаг 2 из 6'), findsOneWidget);

    await tester.tap(find.text('Далее'));
    await pumpFor(tester, const Duration(milliseconds: 500));
    expect(find.text('Обязательное поле'), findsWidgets);
    // Still on the same step.
    expect(find.textContaining('Шаг 2 из 6'), findsOneWidget);

    await tester.enterText(find.byType(EditableText).at(0), 'Смартфон 128 ГБ');
    await pumpFor(tester, const Duration(milliseconds: 600));
    // The draft is saved automatically.
    final drafts = db.collection(Collections.drafts).values().toList();
    expect(drafts.single['title'], 'Смартфон 128 ГБ');
  });

  testWidgets(
    'production without backend shows an explicit unavailable state',
    (tester) async {
      final db = MemoryLocalDatabase();
      await seedSettings(db);
      await startApp(tester, db, config: prodConfig);
      await pumpFor(tester, const Duration(milliseconds: 500));
      expect(
        find.text('Сервер DARYOB ещё не подключён в этой сборке.'),
        findsWidgets,
      );
      // No demo data in production.
      expect(find.byType(DaryobListingCard), findsNothing);
    },
  );
}
