import 'dart:convert';
import 'dart:io';

import 'package:daryob/core/storage/local_database.dart';
import 'package:daryob/core/utils/validators.dart';
import 'package:daryob/features/catalog/data/catalog_importer.dart';
import 'package:daryob/features/catalog/data/catalog_labels.dart';
import 'package:daryob/features/catalog/data/catalog_parser.dart';
import 'package:daryob/features/catalog/data/catalog_repository.dart';
import 'package:daryob/features/catalog/domain/catalog.dart';
import 'package:daryob/features/categories/domain/category_registry.dart';
import 'package:daryob/features/categories/domain/schema_registry.dart';
import 'package:daryob/shared/models/category_schema.dart';
import 'package:flutter_test/flutter_test.dart';

const _asset = 'assets/catalog/daryob_catalog_master_2026.json';

Map<String, dynamic> _raw() =>
    jsonDecode(File(_asset).readAsStringSync()) as Map<String, dynamic>;

void main() {
  final snapshot = const CatalogParser().parse(_raw());
  final categories = CategoryRegistry(snapshot.categories);
  final schemas = SchemaRegistry(snapshot.schemas);

  group('master catalog', () {
    test('14 categories and 115 subcategories, TJS, ru + tg', () {
      expect(snapshot.topLevelCount, 14);
      expect(snapshot.subcategoryCount, 115);
      expect(snapshot.currency, 'TJS');
      expect(snapshot.languages, ['ru', 'tg']);
      expect(categories.topLevel.first.id, 'vehicles');
      expect(categories.childrenOf('real-estate').map((c) => c.catalogId), contains('apartment_rent'));
    });

    test('keeps Phase 1 category ids so old listings stay valid', () {
      for (final id in [
        'real-estate', 'vehicles', 'electronics', 'jobs', 'fashion', 'home-furniture',
        'services', 'construction', 'kids', 'business', 'sports-hobbies', 'agriculture',
        'animals-plants', 'free',
      ]) {
        expect(categories.byId(id), isNotNull, reason: id);
      }
    });

    test('every option of every field has Russian and Tajik labels', () {
      for (final s in snapshot.schemas) {
        for (final f in s.fields) {
          for (final o in f.options) {
            expect(o.label.ru, isNotEmpty, reason: '${s.id}.${f.key}.${o.value}');
            expect(o.label.tg, isNotEmpty, reason: '${s.id}.${f.key}.${o.value}');
          }
          expect(f.label.tg, isNotEmpty, reason: '${s.id}.${f.key}');
        }
      }
      expect(catalogUnitLabels.keys, containsAll(['TJS', 'm2', 'km', 'GB', 'sotka']));
    });

    test('core fields are not attributes; price and photo rules come from data', () {
      final cars = schemas.schemaFor('vehicles.cars');
      expect(cars.field('price_tjs'), isNull);
      expect(cars.field('photos'), isNull);
      expect(cars.priceMode, PriceMode.required);
      expect(cars.photosMin, 1);
      expect(cars.photosMax, 16);
      expect(schemas.schemaFor('jobs.vacancy').priceMode, PriceMode.none);
      expect(schemas.schemaFor('jobs.vacancy').photosMin, 0);
      expect(schemas.schemaFor('free.books').priceMode, PriceMode.free);
    });

    test('subcategories inherit or replace fields as in the file', () {
      expect(schemas.schemaFor('vehicles.cars').field('make_id')!.type, FieldType.brand);
      final tires = schemas.schemaFor('vehicles.tires');
      expect(tires.field('make_id'), isNull);
      expect(tires.field('width_mm')!.unit, 'mm');
      final room = schemas.schemaFor('real-estate.room_rent');
      expect(room.field('total_floors'), isNull);
    });

    test('category_child fields become the subcategory, not inputs', () {
      final s = schemas.schemaFor('services.cleaning');
      expect(s.categoryChildKey, 'service_type');
      expect(s.field('service_type'), isNull);
    });

    test('invalid source field is skipped and reported', () {
      expect(snapshot.warnings.any((w) => w.contains('portfolio')), isTrue);
    });

    test('directories: vehicles 43 makes, phones 22 brands, other brands without models', () {
      final cars = snapshot.directory('vehicles')!;
      expect(cars.brands.length, 43);
      expect(cars.brands.expand((b) => b.models), hasLength(315));
      expect(cars.brands.expand((b) => b.models).where((m) => m.isVerified), isEmpty);
      expect(cars.brand('mercedes-benz'), isNotNull);
      expect(cars.model('toyota/camry')!.name, 'Camry');
      expect(cars.brands.every((b) => b.models.every((m) => !m.isVerified)), isTrue);
      final phones = snapshot.directory('smartphones')!;
      expect(phones.brands.length, 22);
      expect(phones.brands.expand((b) => b.models), hasLength(261));
      // "Galaxy S10+" is a separate model, not a duplicate of "Galaxy S10".
      expect(phones.model('samsung/galaxy-s10-plus')!.name, 'Galaxy S10+');
      expect(phones.model('samsung/galaxy-s10')!.name, 'Galaxy S10');
      // The seed contains no storage/RAM variants.
      expect(phones.brands.expand((b) => b.models).every((m) => m.variants.isEmpty), isTrue);
      final laptops = snapshot.directory('laptops')!;
      expect(laptops.modelCount, 0);
      expect(laptops.brands.first.modelStatus, 'not_collected');
    });

    test('brand fields route to the right directory', () {
      expect(schemas.schemaFor('electronics.smartphones').field('brand_id')!.directory, 'smartphones');
      expect(schemas.schemaFor('electronics.laptops').field('brand_id')!.directory, 'laptops');
      expect(schemas.schemaFor('electronics.tvs').field('brand_id')!.directory, 'tvs');
      expect(schemas.schemaFor('vehicles.tires').field('brand_id')!.directory, isNull);
      expect(schemas.schemaFor('jobs.vacancy').field('occupation_id')!.directory, isNull);
      expect(schemas.schemaFor('electronics.smartphones').field('storage_gb')!.dependsOn, 'model_id');
    });
  });

  group('conditional fields and validation', () {
    final now = DateTime(2026, 11, 22);

    test('show_if: not_empty, not_in, in, equals', () {
      final cars = schemas.schemaFor('vehicles.cars');
      expect(cars.field('model_id')!.isVisible({}), isFalse);
      expect(cars.field('model_id')!.isVisible({'make_id': 'toyota'}), isTrue);
      expect(cars.field('engine_l')!.isVisible({'fuel': 'electric'}), isFalse);
      expect(cars.field('engine_l')!.isVisible({'fuel': 'diesel'}), isTrue);
      final rent = schemas.schemaFor('real-estate.apartment_rent');
      expect(rent.field('deposit_tjs')!.isVisible({'transaction_type': 'rent_long'}), isTrue);
      expect(rent.field('deposit_tjs')!.isVisible({'transaction_type': 'sale'}), isFalse);
      final job = schemas.schemaFor('jobs.resume');
      expect(job.field('employer')!.isVisible({'listing_kind': 'resume'}), isFalse);
    });

    test('year may be at most next year', () {
      Map<String, Object?> car(int year) => {
        'make_id': 'toyota', 'model_id': 'toyota/camry', 'year': year, 'mileage_km': 1000,
        'fuel': 'gasoline', 'transmission': 'automatic', 'body': 'sedan', 'condition': 'used',
      };
      expect(schemas.validate('vehicles.cars', car(2027), now: now), isEmpty);
      expect(schemas.validate('vehicles.cars', car(2028), now: now)['year'], ValidationCode.outOfRange);
      expect(schemas.validate('vehicles.cars', car(1800), now: now)['year'], ValidationCode.outOfRange);
    });

    test('area must be above zero; floor not above total floors', () {
      final base = {
        'transaction_type': 'sale', 'rooms': 2, 'area_m2': 0, 'seller_role': 'owner',
        'floor': 9, 'total_floors': 5,
      };
      final errors = schemas.validate('real-estate.apartment_sale', base, now: now);
      expect(errors['area_m2'], ValidationCode.outOfRange);
      expect(errors['floor'], ValidationCode.notAboveOther);
    });

    test('rent subcategories allow only rent deals; sale ones preset sale', () {
      final rent = schemas.schemaFor('real-estate.apartment_rent');
      expect(rent.allowedOptions['transaction_type'], ['rent_long', 'rent_short']);
      expect(
        schemas.validate('real-estate.apartment_rent', {'transaction_type': 'sale'}, onlyKeys: {'transaction_type'}),
        {'transaction_type': ValidationCode.required},
      );
      final sale = schemas.schemaFor('real-estate.house_sale');
      expect(sale.presetAttributes['transaction_type'], 'sale');
      expect(sale.lockedAttributes, contains('transaction_type'));
    });

    test('subcategory implies its option (jobs)', () {
      expect(schemas.schemaFor('jobs.vacancy').presetAttributes['listing_kind'], 'vacancy');
      expect(schemas.schemaFor('jobs.remote').presetAttributes['schedule'], 'remote');
      expect(schemas.schemaFor('jobs.internship').presetAttributes['employment'], ['internship']);
    });
  });

  group('authorized imports', () {
    Map<String, dynamic> record({Map<String, dynamic> override = const {}}) => {
      'directory': 'smartphones',
      'brand': 'Apple',
      'model': 'iPhone 8',
      'variant_kind': 'storage_gb',
      'variant_value': '64',
      'source_url': 'https://example.com/spec',
      'source_type': 'manufacturer_spec_page',
      'verified_at': '2026-11-20',
      'import_batch_id': 'b1',
      'license_or_terms': 'Licensed dataset, contract #1',
      'market_region': 'TJ',
      'confidence': 0.9,
      'status': 'verified',
      ...override,
    };

    test('records without metadata, licence or verified status are rejected', () {
      const importer = CatalogImporter();
      final report = importer.validate({
        'import_batch_id': 'b1',
        'records': [
          record(),
          record(override: {'license_or_terms': ''}),
          record(override: {'status': 'pending'}),
          record(override: {'source_url': 'not a url'}),
          record(override: {'variant_kind': 'colour'}),
          record(), // duplicate
        ],
      }, snapshot);
      expect(report.accepted, hasLength(1));
      expect(report.rejected.map((r) => r.index), [1, 2, 3, 4, 5]);
    });

    test('accepted variants become selectable with their source', () {
      const importer = CatalogImporter();
      final merged = importer.apply(snapshot, [
        {'import_batch_id': 'b1', 'records': [record(), record(override: {'variant_value': '256'})]},
      ]);
      final model = merged.directory('smartphones')!.model('apple/iphone-8')!;
      expect(model.variantsOf('storage_gb').map((v) => v.value), ['64', '256']);
      expect(model.isVerified, isTrue);
      expect(model.variantsOf('storage_gb').first.source.sourceUrl, 'https://example.com/spec');
      expect(merged.appliedImportBatches, ['b1']);
      // The original snapshot is unchanged.
      expect(snapshot.directory('smartphones')!.model('apple/iphone-8')!.variants, isEmpty);
    });
  });

  group('versioned storage', () {
    test('installs bundled catalog, keeps previous version, rolls back', () async {
      final db = MemoryLocalDatabase();
      final raw = _raw();
      final repo = CatalogRepository(
        database: db,
        loadSeed: () async => jsonEncode(raw),
        clock: () => DateTime(2026, 11, 22),
      );
      final first = await repo.load();
      expect(first.version, '0.1.0-research-starter');
      expect(repo.installed!.source, 'bundled');

      final newer = Map<String, dynamic>.of(raw)..['version'] = '0.2.0';
      await repo.install(newer, source: 'remote');
      expect(repo.activeSnapshot().version, '0.2.0');
      expect(repo.previous!.version, '0.1.0-research-starter');

      // Loading again keeps the newer cached version over the older bundle.
      expect((await repo.load()).version, '0.2.0');

      expect(await repo.rollback(), isTrue);
      expect(repo.activeSnapshot().version, '0.1.0-research-starter');
    });

    test('a broken catalog is never installed', () async {
      final db = MemoryLocalDatabase();
      final repo = CatalogRepository(
        database: db,
        loadSeed: () async => jsonEncode(_raw()),
        clock: DateTime.now,
      );
      await repo.load();
      final broken = Map<String, dynamic>.of(_raw())..['categories'] = 'oops';
      await expectLater(repo.install(broken, source: 'remote'), throwsA(anything));
      expect(repo.activeSnapshot().subcategoryCount, 115);
    });

    test('import batches are stored and survive reload', () async {
      final db = MemoryLocalDatabase();
      final repo = CatalogRepository(
        database: db,
        loadSeed: () async => jsonEncode(_raw()),
        clock: DateTime.now,
      );
      await repo.load();
      final report = await repo.importBatch({
        'import_batch_id': 'cars-1',
        'records': [
          {
            'directory': 'vehicles', 'brand': 'Toyota', 'model': 'Camry',
            'variant_kind': 'generation_id', 'variant_value': 'XV70',
            'source_url': 'https://example.com', 'source_type': 'licensed_dataset',
            'verified_at': '2026-11-01', 'import_batch_id': 'cars-1',
            'license_or_terms': 'contract', 'market_region': 'TJ', 'confidence': 1,
            'status': 'approved',
          },
        ],
      });
      expect(report.isClean, isTrue);
      final reloaded = await repo.load();
      expect(reloaded.directory('vehicles')!.model('toyota/camry')!.variantsOf('generation_id').single.value, 'XV70');
      await repo.removeBatch('cars-1');
      expect(repo.activeSnapshot().directory('vehicles')!.model('toyota/camry')!.variants, isEmpty);
    });
  });

  test('slugs', () {
    expect(catalogSlug('Mercedes-Benz'), 'mercedes-benz');
    expect(catalogSlug('Citroën'), 'citroen');
    expect(catalogSlug('Land Cruiser Prado'), 'land-cruiser-prado');
  });
}
