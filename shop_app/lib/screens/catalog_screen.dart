import 'package:material_ui/material_ui.dart';

import '../data.dart';
import '../format.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

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
    appNav.searchRequest.addListener(_onSearchRequest);
    appNav.catalogCategory.addListener(_rebuild);
  }

  @override
  void dispose() {
    appNav.searchRequest.removeListener(_onSearchRequest);
    appNav.catalogCategory.removeListener(_rebuild);
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

  List<Product> _results() {
    final cat = appNav.catalogCategory.value;
    final q = _search.text.trim().toLowerCase();
    final list = kProducts.where((p) {
      if (cat != null && p.categoryId != cat) return false;
      if (q.isEmpty) return true;
      return p.title.toLowerCase().contains(q) ||
          categoryById(p.categoryId).name.toLowerCase().contains(q) ||
          p.seller.toLowerCase().contains(q);
    }).toList();
    switch (_sort) {
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

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final results = _results();
    final selected = appNav.catalogCategory.value;
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
                  hintText: 'Искать товары и бренды',
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
                  _Pill(label: 'Все', selected: selected == null, onTap: () => appNav.catalogCategory.value = null),
                  for (final cat in kCategories)
                    _Pill(
                      label: '${cat.emoji}  ${cat.name}',
                      selected: selected == cat.id,
                      onTap: () => appNav.catalogCategory.value = selected == cat.id ? null : cat.id,
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
                  PopupMenuButton<SortMode>(
                    initialValue: _sort,
                    onSelected: (v) => setState(() => _sort = v),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    itemBuilder: (_) => [
                      for (final m in SortMode.values) PopupMenuItem(value: m, child: Text(m.label)),
                    ],
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.swap_vert_rounded, size: 19, color: c.accentText),
                          const SizedBox(width: 4),
                          Text(
                            _sort.label,
                            style: TextStyle(color: c.accentText, fontWeight: FontWeight.w700, fontSize: 14),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: results.isEmpty
                  ? EmptyState(
                      emoji: '🔍',
                      title: 'Ничего не нашлось',
                      subtitle: 'Попробуйте изменить запрос\nили выбрать другую категорию',
                      buttonLabel: 'Сбросить фильтры',
                      onButton: () {
                        _search.clear();
                        appNav.catalogCategory.value = null;
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

class _Pill extends StatelessWidget {
  const _Pill({required this.label, required this.selected, required this.onTap});

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
          gradient: selected ? kBrandGradient : null,
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
