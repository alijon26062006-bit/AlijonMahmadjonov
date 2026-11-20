import 'package:material_ui/material_ui.dart';

import '../format.dart';
import '../state.dart';
import '../widgets.dart';

class FavoritesScreen extends StatelessWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
    final items = s.favoriteProducts;
    return SafeArea(
      bottom: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PageTitle('Избранное', badge: items.isEmpty ? null : itemsLabel(items.length)),
          Expanded(
            child: items.isEmpty
                ? EmptyState(
                    emoji: '💜',
                    title: 'Здесь пока пусто',
                    subtitle: 'Нажимайте ♡ на товарах,\nчтобы сохранить их на потом',
                    buttonLabel: 'Смотреть товары',
                    onButton: () => appNav.openCatalog(),
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
