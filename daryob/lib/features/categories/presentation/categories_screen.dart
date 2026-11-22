import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/category_visuals.dart';
import '../../listings/application/listing_providers.dart';

class CategoriesScreen extends ConsumerWidget {
  const CategoriesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final categories = ref.watch(categoryRegistryProvider).topLevel;
    // Counts are optional: shown when the data source can provide them.
    final counts = ref.watch(categoryCountsProvider).value;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.allCategories)),
      body: ListView.separated(
        itemCount: categories.length,
        separatorBuilder: (_, _) => const Divider(indent: 76),
        itemBuilder: (context, i) {
          final c = categories[i];
          final count = counts?[c.id];
          return DaryobCategoryRow(
            category: c,
            countLabel: count == null ? null : l10n.listingsCount(count),
            onTap: () => context.push(Routes.category(c.slug)),
          );
        },
      ),
    );
  }
}
