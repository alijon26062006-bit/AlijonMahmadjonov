import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/store.dart';
import '../core/widgets.dart';
import 'buyer_common.dart';

class FavoritesScreen extends StatelessWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final items = StoreScope.of(context).favoriteProducts;
    return SafeArea(
      bottom: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PageTitle('Избранное', badge: items.isEmpty ? null : itemsLabel(items.length)),
          Expanded(
            child: items.isEmpty
                ? EmptyState(
                    image: 'heart',
                    title: 'Здесь пока пусто',
                    subtitle: 'Нажмите на сердечко у товара,\nчтобы сохранить его на потом',
                    buttonLabel: 'Смотреть товары',
                    onButton: () => buyerNav.openCatalog(),
                  )
                : GridView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                    gridDelegate: kProductGridDelegate,
                    itemCount: items.length,
                    itemBuilder: (_, i) => ProductCard(product: items[i], heroPrefix: 'fav'),
                  ),
          ),
        ],
      ),
    );
  }
}
