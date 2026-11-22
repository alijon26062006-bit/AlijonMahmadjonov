import 'package:cupertino_ui/cupertino_ui.dart' show GlobalCupertinoLocalizations;
import 'package:daryob/app/localization/l10n.dart';
import 'package:daryob/app/localization/tajik_fallback.dart';
import 'package:daryob/app/theme/app_theme.dart';
import 'package:daryob/core/storage/local_database.dart';
import 'package:daryob/features/catalog/application/catalog_providers.dart';
import 'package:daryob/features/listings/domain/listing_draft.dart';
import 'package:daryob/features/listings/domain/listing_query.dart';
import 'package:daryob/features/listings/presentation/create/wizard_steps.dart';
import 'package:daryob/shared/providers/core_providers.dart';
import 'package:daryob/shared/widgets/filter_sheet.dart';
import 'package:flutter_localizations/flutter_localizations.dart' show GlobalWidgetsLocalizations;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../helpers.dart';

/// Hosts a single widget with the app's theme, localizations and catalog.
Widget _host(Widget child, {String language = 'ru'}) {
  return ProviderScope(
    overrides: [
      appConfigProvider.overrideWithValue(devConfig),
      localDatabaseProvider.overrideWithValue(MemoryLocalDatabase()),
      initialCatalogProvider.overrideWithValue(testCatalog),
    ],
    retry: (_, _) => null,
    child: MaterialApp(
      theme: DaryobTheme.light(),
      locale: Locale(language),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        ...tajikFallbackDelegates,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: Scaffold(body: child),
    ),
  );
}

void main() {
  testWidgets('car filters are generated from the catalog schema', (tester) async {
    tester.view.physicalSize = const Size(1080, 2340);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      _host(const DaryobFilterSheet(query: ListingQuery(categoryId: 'vehicles.cars'))),
    );
    await tester.pumpAndSettle();

    // Labels come from the catalog file, not from hand-written screens.
    await tester.scrollUntilVisible(find.text('Марка'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.text('Марка'), findsWidgets);
    await tester.scrollUntilVisible(find.text('КПП'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.text('КПП'), findsOneWidget);
    expect(find.text('Автомат'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('filter sheet renders in Tajik', (tester) async {
    tester.view.physicalSize = const Size(1080, 2340);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      _host(
        const DaryobFilterSheet(
          query: ListingQuery(
            categoryId: 'real-estate.apartment_sale',
            attributeFilters: {'rooms': RangeFilter(min: 2)},
          ),
        ),
        language: 'tg',
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.textContaining('ҳуҷраҳо'), findsWidgets);
  });

  testWidgets('every subcategory filter sheet renders in both languages', (tester) async {
    tester.view.physicalSize = const Size(1080, 2340);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);

    final subcategories = testCatalog.categories.where((c) => c.parentId != null).toList();
    expect(subcategories, hasLength(115));
    for (final language in ['ru', 'tg']) {
      for (final c in subcategories) {
        await tester.pumpWidget(
          _host(DaryobFilterSheet(key: ValueKey('$language-${c.id}'), query: ListingQuery(categoryId: c.id)), language: language),
        );
        await tester.pump();
        expect(tester.takeException(), isNull, reason: '$language ${c.id}');
      }
    }
  });

  testWidgets('every subcategory form and preview renders with errors shown', (tester) async {
    tester.view.physicalSize = const Size(1080, 2340);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);

    final schemas = testSchemas();
    for (final language in ['ru', 'tg']) {
      for (final c in testCatalog.categories.where((c) => c.parentId != null)) {
        final schema = schemas.schemaFor(c.formSchemaId);
        final draft = ListingDraft(
          id: 'x',
          updatedAt: fixedNow,
          categoryId: c.id,
          attributes: withPresets(schema, const {}),
          regionId: 'dushanbe',
        );
        // Every required field shows its error.
        final errors = {
          for (final f in schema.detailFields.where((f) => f.required)) 'attr.${f.key}': 'required',
        };
        await tester.pumpWidget(
          _host(
            ListView(
              key: ValueKey('$language-${c.id}'),
              children: [
                DetailsStep(draft: draft, update: (_) {}, errors: errors),
                PreviewStep(draft: draft, onEditStep: (_) {}),
              ],
            ),
            language: language,
          ),
        );
        await tester.pump();
        expect(tester.takeException(), isNull, reason: '$language ${c.id}');
      }
    }
  });
}
