import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'buyer_common.dart';

enum SortMode { popular, cheap, expensive, rating, discount }

extension on SortMode {
  String get label => switch (this) {
    SortMode.popular => 'Популярные',
    SortMode.cheap => 'Сначала дешёвые',
    SortMode.expensive => 'Сначала дорогие',
    SortMode.rating => 'Высокий рейтинг',
    SortMode.discount => 'Большие скидки',
  };
}

List<Product> sortProducts(List<Product> list, SortMode sort) {
  switch (sort) {
    case SortMode.popular:
      list.sort((a, b) => b.reviews.compareTo(a.reviews));
    case SortMode.cheap:
      list.sort((a, b) => a.price.compareTo(b.price));
    case SortMode.expensive:
      list.sort((a, b) => b.price.compareTo(a.price));
    case SortMode.rating:
      list.sort((a, b) => b.rating.compareTo(a.rating));
    case SortMode.discount:
      list.sort((a, b) => b.discount.compareTo(a.discount));
  }
  return list;
}

class CatalogScreen extends StatefulWidget {
  const CatalogScreen({super.key});

  @override
  State<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends State<CatalogScreen> {
  final _search = TextEditingController();
  final _focus = FocusNode();
  SortMode _sort = SortMode.popular;

  @override
  void initState() {
    super.initState();
    buyerNav.searchRequest.addListener(_onSearchRequest);
    buyerNav.catalogCategory.addListener(_rebuild);
  }

  @override
  void dispose() {
    buyerNav.searchRequest.removeListener(_onSearchRequest);
    buyerNav.catalogCategory.removeListener(_rebuild);
    _search.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _rebuild() => setState(() {});

  void _onSearchRequest() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _focus.requestFocus();
    });
  }

  List<Product> _results(MarketStore s) {
    final cat = buyerNav.catalogCategory.value;
    final q = _search.text.trim().toLowerCase();
    final list = s.catalog.where((p) {
      if (cat != null && p.categoryId != cat) return false;
      if (q.isEmpty) return true;
      return p.title.toLowerCase().contains(q) ||
          categoryById(p.categoryId).name.toLowerCase().contains(q) ||
          (s.shopById(p.shopId)?.name.toLowerCase().contains(q) ?? false);
    }).toList();
    return sortProducts(list, _sort);
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final results = _results(s);
    final selected = buyerNav.catalogCategory.value;
    return SafeArea(
      bottom: false,
      child: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageTitle('Каталог'),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: TextField(
                controller: _search,
                focusNode: _focus,
                textInputAction: TextInputAction.search,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  hintText: 'Искать товары и магазины',
                  prefixIcon: Icon(Icons.search_rounded, color: c.muted),
                  suffixIcon: _search.text.isEmpty
                      ? null
                      : IconButton(
                          icon: Icon(Icons.close_rounded, color: c.muted),
                          onPressed: () => setState(_search.clear),
                        ),
                ),
              ),
            ),
            SizedBox(
              height: 58,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 6),
                children: [
                  Pill(label: 'Все', selected: selected == null, onTap: () => buyerNav.catalogCategory.value = null),
                  for (final cat in kCategories)
                    Pill(
                      label: cat.name,
                      selected: selected == cat.id,
                      onTap: () => buyerNav.catalogCategory.value = selected == cat.id ? null : cat.id,
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 8, 4),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Найдено: ${itemsLabel(results.length)}',
                      style: TextStyle(color: c.muted, fontSize: 14, fontWeight: FontWeight.w500),
                    ),
                  ),
                  SortButton(value: _sort, onChanged: (v) => setState(() => _sort = v)),
                ],
              ),
            ),
            Expanded(
              child: results.isEmpty
                  ? EmptyState(
                      image: 'search',
                      title: 'Ничего не нашлось',
                      subtitle: 'Попробуйте изменить запрос\nили выбрать другую категорию',
                      buttonLabel: 'Сбросить фильтры',
                      onButton: () {
                        _search.clear();
                        buyerNav.catalogCategory.value = null;
                        setState(() {});
                      },
                    )
                  : GridView.builder(
                      padding: const EdgeInsets.fromLTRB(16, 6, 16, 24),
                      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
                      gridDelegate: kProductGridDelegate,
                      itemCount: results.length,
                      itemBuilder: (_, i) => ProductCard(product: results[i], heroPrefix: 'cat'),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class SortButton extends StatelessWidget {
  const SortButton({super.key, required this.value, required this.onChanged});

  final SortMode value;
  final ValueChanged<SortMode> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return PopupMenuButton<SortMode>(
      initialValue: value,
      onSelected: onChanged,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      itemBuilder: (_) => [for (final m in SortMode.values) PopupMenuItem(value: m, child: Text(m.label))],
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.swap_vert_rounded, size: 19, color: c.accentText),
            const SizedBox(width: 4),
            Text(
              value.label,
              style: TextStyle(color: c.accentText, fontWeight: FontWeight.w700, fontSize: 14),
            ),
          ],
        ),
      ),
    );
  }
}

/// Таблетка-фильтр (категория, статус).
class Pill extends StatelessWidget {
  const Pill({super.key, required this.label, required this.selected, required this.onTap});

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          gradient: selected ? c.gradient : null,
          color: selected ? null : c.surface,
          borderRadius: BorderRadius.circular(99),
          border: Border.all(color: selected ? Colors.transparent : c.line),
        ),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            borderRadius: BorderRadius.circular(99),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Center(
                child: Text(
                  label,
                  style: TextStyle(
                    color: selected ? Colors.white : c.text,
                    fontWeight: FontWeight.w700,
                    fontSize: 13.5,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
