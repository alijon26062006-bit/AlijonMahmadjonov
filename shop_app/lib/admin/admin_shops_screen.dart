import 'package:material_ui/material_ui.dart';

import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'admin_widgets.dart';

class AdminShopsScreen extends StatefulWidget {
  const AdminShopsScreen({super.key});

  @override
  State<AdminShopsScreen> createState() => _AdminShopsScreenState();
}

class _AdminShopsScreenState extends State<AdminShopsScreen> {
  ShopStatus? _status;
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final q = _search.text.trim().toLowerCase();
    final list =
        s.shops
            .where((x) => _status == null || x.status == _status)
            .where((x) => q.isEmpty || x.name.toLowerCase().contains(q) || x.ownerName.toLowerCase().contains(q))
            .toList()
          ..sort((a, b) => a.status.index.compareTo(b.status.index));
    return SafeArea(
      bottom: false,
      child: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            PageTitle('Магазины', badge: '${s.shops.length}'),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: TextField(
                controller: _search,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  hintText: 'Название или владелец',
                  prefixIcon: Icon(Icons.search_rounded, color: c.muted),
                ),
              ),
            ),
            FilterPills<ShopStatus?>(
              values: const [null, ShopStatus.pending, ShopStatus.active, ShopStatus.blocked],
              selected: _status,
              label: (v) => v == null ? 'Все' : '${v.label} · ${s.shops.where((x) => x.status == v).length}',
              onChanged: (v) => setState(() => _status = v),
            ),
            Expanded(
              child: list.isEmpty
                  ? const EmptyState(image: 'store', title: 'Магазинов нет', subtitle: 'Измените фильтр')
                  : ListView(
                      padding: const EdgeInsets.only(top: 8, bottom: 24),
                      children: [for (final shop in list) AdminShopTile(shop: shop)],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
