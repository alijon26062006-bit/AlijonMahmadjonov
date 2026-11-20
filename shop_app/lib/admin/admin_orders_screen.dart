import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'admin_widgets.dart';

enum _Group { active, placed, delivering, delivered, cancelled, all }

extension on _Group {
  String get label => switch (this) {
    _Group.active => 'Активные',
    _Group.placed => 'Новые',
    _Group.delivering => 'В пути',
    _Group.delivered => 'Доставлены',
    _Group.cancelled => 'Отменены',
    _Group.all => 'Все',
  };

  bool matches(Order o) => switch (this) {
    _Group.active => o.status.isActive,
    _Group.placed => o.status == OrderStatus.placed,
    _Group.delivering => o.status == OrderStatus.delivering,
    _Group.delivered => o.status == OrderStatus.delivered,
    _Group.cancelled => o.status == OrderStatus.cancelled,
    _Group.all => true,
  };
}

class AdminOrdersScreen extends StatefulWidget {
  const AdminOrdersScreen({super.key});

  @override
  State<AdminOrdersScreen> createState() => _AdminOrdersScreenState();
}

class _AdminOrdersScreenState extends State<AdminOrdersScreen> {
  _Group _group = _Group.active;
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
    final list = s.sorted(
      s.orders.where(_group.matches).where((o) {
        if (q.isEmpty) return true;
        return o.id.contains(q) ||
            o.buyerName.toLowerCase().contains(q) ||
            phoneDigits(o.buyerPhone).contains(q) ||
            (s.shopById(o.shopId)?.name.toLowerCase().contains(q) ?? false);
      }),
    );
    final sum = list.where((o) => o.status != OrderStatus.cancelled).fold(0, (a, o) => a + o.total);
    return SafeArea(
      bottom: false,
      child: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            PageTitle('Заказы', badge: '${s.orders.length}'),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: TextField(
                controller: _search,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  hintText: 'Номер, покупатель, телефон, магазин',
                  prefixIcon: Icon(Icons.search_rounded, color: c.muted),
                ),
              ),
            ),
            FilterPills<_Group>(
              values: _Group.values,
              selected: _group,
              label: (g) => g == _Group.all ? g.label : '${g.label} · ${s.orders.where(g.matches).length}',
              onChanged: (g) => setState(() => _group = g),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 6),
              child: Text(
                '${ordersLabel(list.length)} на ${money(sum)}',
                style: TextStyle(color: c.muted, fontWeight: FontWeight.w500),
              ),
            ),
            Expanded(
              child: list.isEmpty
                  ? const EmptyState(emoji: '🧾', title: 'Заказов нет', subtitle: 'Измените фильтр или запрос')
                  : ListView.builder(
                      padding: const EdgeInsets.only(top: 4, bottom: 24),
                      itemCount: list.length.clamp(0, 200),
                      itemBuilder: (_, i) => AdminOrderTile(order: list[i]),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
