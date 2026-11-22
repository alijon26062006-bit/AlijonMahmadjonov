import 'package:daryob/core/utils/validators.dart';
import 'package:daryob/features/categories/data/tajikistan_regions.dart';
import 'package:daryob/features/categories/domain/category_registry.dart';
import 'package:daryob/features/categories/domain/region_directory.dart';
import 'package:daryob/features/categories/domain/schema_registry.dart';
import 'package:daryob/shared/models/category.dart';
import 'package:daryob/shared/models/category_schema.dart';
import 'package:daryob/shared/models/localized_text.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

void main() {
  group('category registry', () {
    final registry = testCategories();
    final initialCategories = testCatalog.categories;

    test('has the 14 catalog categories with stable slugs', () {
      expect(registry.topLevel.map((c) => c.slug).toSet(), {
        'real-estate',
        'vehicles',
        'electronics',
        'jobs',
        'fashion',
        'home-furniture',
        'services',
        'construction',
        'kids',
        'business',
        'sports-hobbies',
        'agriculture',
        'animals-plants',
        'free',
      });
    });

    test('every category is named in both languages', () {
      for (final c in registry.all) {
        expect(c.name.ru, isNotEmpty, reason: c.slug);
        expect(c.name.tg, isNotEmpty, reason: c.slug);
      }
      for (final c in registry.topLevel) {
        expect(c.description.tg, isNotEmpty, reason: c.slug);
      }
    });

    test('free category has free pricing', () {
      expect(registry.bySlug('free')!.priceMode, PriceMode.free);
    });

    test('rejects duplicate slugs', () {
      expect(
        () => CategoryRegistry([
          initialCategories.first,
          initialCategories.first,
        ]),
        throwsArgumentError,
      );
    });

    test('new categories and subcategories plug in without code changes', () {
      const phones = CategoryDefinition(
        id: 'phones',
        slug: 'phones',
        parentId: 'electronics',
        order: 1,
        icon: CategoryIcon.smartphone,
        name: LocalizedText(ru: 'Телефоны', tg: 'Телефонҳо'),
        description: LocalizedText(ru: '', tg: ''),
      );
      final extended = CategoryRegistry([...initialCategories, phones]);
      expect(extended.childrenOf('electronics').map((c) => c.slug), contains('phones'));
      expect(extended.subtreeIds('electronics'), containsAll({'electronics', 'phones'}));
      expect(extended.pathTo('phones').map((c) => c.id), [
        'electronics',
        'phones',
      ]);
    });
  });

  group('schema registry', () {
    final schemas = SchemaRegistry();

    test('unknown schema falls back to the basic one', () {
      expect(schemas.schemaFor('does-not-exist').id, SchemaIds.basic);
    });

    test('goods schema requires condition', () {
      expect(schemas.validate(SchemaIds.goods, const {}), {
        'condition': ValidationCode.required,
      });
      expect(
        schemas.validate(SchemaIds.goods, const {'condition': 'new'}),
        isEmpty,
      );
      expect(
        schemas.validate(SchemaIds.goods, const {'condition': 'broken'}),
        isNotEmpty,
      );
    });

    test('future modules register their own schema', () {
      schemas.register(
        const CategorySchema(
          id: 'vehicles.v1',
          version: 1,
          fields: [
            FieldSchema(
              key: 'year',
              type: FieldType.integer,
              label: LocalizedText(ru: 'Год', tg: 'Сол'),
              required: true,
              min: 1950,
              max: 2030,
            ),
          ],
        ),
      );
      expect(schemas.validate('vehicles.v1', const {'year': 1900}), {
        'year': ValidationCode.outOfRange,
      });
      expect(schemas.validate('vehicles.v1', const {'year': 2015}), isEmpty);
    });
  });

  group('regions', () {
    final regions = RegionDirectory(tajikistanRegions);

    test('five first-level units', () {
      expect(regions.topLevel.map((r) => r.id).toSet(), {
        RegionIds.dushanbe,
        RegionIds.rrp,
        RegionIds.sughd,
        RegionIds.khatlon,
        RegionIds.gbao,
      });
    });

    test('important cities sit in the right region', () {
      expect(regions.topLevelOf('khujand')!.id, RegionIds.sughd);
      expect(regions.topLevelOf('panjakent')!.id, RegionIds.sughd);
      expect(regions.topLevelOf('bokhtar')!.id, RegionIds.khatlon);
      expect(regions.topLevelOf('kulob')!.id, RegionIds.khatlon);
      expect(regions.topLevelOf('tursunzoda')!.id, RegionIds.rrp);
      expect(regions.topLevelOf('roghun')!.id, RegionIds.rrp);
      expect(regions.topLevelOf('khorugh')!.id, RegionIds.gbao);
    });

    test('containment', () {
      expect(regions.contains(RegionIds.country, 'khorugh'), isTrue);
      expect(regions.contains(RegionIds.sughd, 'isfara'), isTrue);
      expect(regions.contains(RegionIds.sughd, 'kulob'), isFalse);
      expect(regions.contains(RegionIds.dushanbe, 'dushanbe-sino'), isTrue);
    });

    test('Tajik names use Tajik letters', () {
      expect(regions.byId('khujand')!.name.tg, 'Хуҷанд');
      expect(regions.byId('kulob')!.name.tg, 'Кӯлоб');
    });
  });
}
