import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'product_edit_screen.dart';

enum _Filter { all, onSale, hidden, out }

extension on _Filter {
  String get label => switch (this) {
    _Filter.all => 'Все',
    _Filter.onSale => 'В продаже',
    _Filter.hidden => 'Сняты',
    _Filter.out => 'Закончились',
  };
}

class ProductsScreen extends StatefulWidget {
  const ProductsScreen({super.key});

  @override
  State<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends State<ProductsScreen> {
  final _search = TextEditingController();
  _Filter _filter = _Filter.all;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  bool _match(Product p) {
    final q = _search.text.trim().toLowerCase();
    if (q.isNotEmpty && !p.title.toLowerCase().contains(q)) return false;
    return switch (_filter) {
      _Filter.all => true,
      _Filter.onSale => p.active && !p.hiddenByAdmin && p.inStock,
      _Filter.hidden => !p.active || p.hiddenByAdmin,
      _Filter.out => !p.inStock,
    };
  }

  void _edit(Product? p) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ProductEditScreen(product: p)));
  }

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final all = s.productsOf(s.myShop!.id);
    final list = all.where(_match).toList()..sort((a, b) => a.title.compareTo(b.title));
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: GestureDetector(
          onTap: () => FocusScope.of(context).unfocus(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PageTitle('Товары', badge: '${all.length}'),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                child: TextField(
                  controller: _search,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    hintText: 'Найти товар',
                    prefixIcon: Icon(Icons.search_rounded, color: c.muted),
                  ),
                ),
              ),
              SizedBox(
                height: 56,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                  children: [
                    for (final f in _Filter.values)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text(f.label),
                          selected: _filter == f,
                          onSelected: (_) => setState(() => _filter = f),
                          showCheckmark: false,
                          selectedColor: c.accentSoft,
                          labelStyle: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: _filter == f ? c.accentText : c.text,
                          ),
                          side: BorderSide(color: _filter == f ? c.accentText : c.line),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(99)),
                        ),
                      ),
                  ],
                ),
              ),
              Expanded(
                child: list.isEmpty
                    ? EmptyState(
                        emoji: '📦',
                        title: all.isEmpty ? 'Добавьте первый товар' : 'Ничего не найдено',
                        subtitle: all.isEmpty
                            ? 'Покупатели увидят его сразу после сохранения'
                            : 'Измените фильтр или запрос',
                        buttonLabel: all.isEmpty ? 'Добавить товар' : null,
                        onButton: all.isEmpty ? () => _edit(null) : null,
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
                        itemCount: list.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 10),
                        itemBuilder: (_, i) => _ProductRow(product: list[i], onTap: () => _edit(list[i])),
                      ),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: DecoratedBox(
        decoration: BoxDecoration(
          gradient: c.gradient,
          borderRadius: BorderRadius.circular(18),
          boxShadow: [BoxShadow(color: c.accent.withValues(alpha: .4), blurRadius: 20, offset: const Offset(0, 8))],
        ),
        child: FloatingActionButton.extended(
          onPressed: () => _edit(null),
          backgroundColor: Colors.transparent,
          foregroundColor: Colors.white,
          elevation: 0,
          highlightElevation: 0,
          icon: const Icon(Icons.add_rounded),
          label: const Text('Товар', style: TextStyle(fontWeight: FontWeight.w800)),
        ),
      ),
    );
  }
}

class _ProductRow extends StatelessWidget {
  const _ProductRow({required this.product, required this.onTap});

  final Product product;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final p = product;
    final hidden = !p.active || p.hiddenByAdmin;
    return AppCard(
      padding: const EdgeInsets.all(10),
      onTap: onTap,
      child: Row(
        children: [
          SizedBox.square(
            dimension: 64,
            child: EmojiImage(emoji: p.emoji, categoryId: p.categoryId, size: 32, radius: 14, dimmed: hidden),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  p.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                ),
                const SizedBox(height: 3),
                Row(
                  children: [
                    Text(
                      money(p.price),
                      style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                    ),
                    const SizedBox(width: 8),
                    if (p.hiddenByAdmin)
                      const Flexible(
                        child: StatusPill(label: 'Скрыт админом', color: kDanger),
                      )
                    else if (!p.inStock)
                      const Flexible(
                        child: StatusPill(label: 'Нет в наличии', color: kDanger),
                      )
                    else
                      Flexible(
                        child: Text(
                          'Остаток: ${p.stock}',
                          style: TextStyle(
                            fontSize: 12.5,
                            color: p.stock <= 5 ? const Color(0xFFFF8A00) : c.muted,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          Switch(value: p.active, onChanged: p.hiddenByAdmin ? null : (v) => s.setProductActive(p, v)),
        ],
      ),
    );
  }
}
