import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'admin_widgets.dart';

class AdminCouriersScreen extends StatelessWidget {
  const AdminCouriersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final list = [...s.couriers]
      ..sort((a, b) {
        if (a.online != b.online) return a.online ? -1 : 1;
        return a.name.compareTo(b.name);
      });
    final online = s.couriers.where((x) => x.online && !x.blocked).length;
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          PageTitle('Курьеры', badge: '$online на линии'),
          for (final x in list) _CourierTile(courier: x),
        ],
      ),
    );
  }
}

class _CourierTile extends StatelessWidget {
  const _CourierTile({required this.courier});

  final Courier courier;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final x = courier;
    final active = s.orders.where((o) => o.courierId == x.id && o.status.isActive).firstOrNull;
    final done = s.orders.where((o) => o.courierId == x.id && o.status == OrderStatus.delivered).toList();
    final today = done.where((o) => sameDay(o.updatedAt, DateTime.now())).length;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
      child: AppCard(
        padding: const EdgeInsets.all(14),
        onTap: () => _details(context, s, x, active),
        child: Row(
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: c.accentSoft,
                  child: Text(x.vehicle, style: const TextStyle(fontSize: 24)),
                ),
                Positioned(
                  right: -1,
                  bottom: -1,
                  child: Container(
                    width: 14,
                    height: 14,
                    decoration: BoxDecoration(
                      color: x.blocked ? kDanger : (x.online ? kSuccess : c.muted),
                      shape: BoxShape.circle,
                      border: Border.all(color: c.surface, width: 2.5),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    x.name,
                    style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                  ),
                  Text(
                    x.blocked
                        ? 'Заблокирован'
                        : active != null
                        ? 'Везёт заказ №${active.id}'
                        : (x.online ? 'Свободен, на линии' : 'Не на линии'),
                    style: TextStyle(
                      fontSize: 12.5,
                      color: active != null ? c.accentText : c.muted,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '★ ${x.rating.toStringAsFixed(1)}',
                  style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                ),
                Text('$today сегодня · ${done.length} всего', style: TextStyle(fontSize: 12, color: c.muted)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _details(BuildContext context, MarketStore s, Courier x, Order? active) {
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) {
        final c = AppColors.of(ctx);
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '${x.vehicle} ${x.name}',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: c.text),
                ),
                Text(formatPhone(x.phone), style: TextStyle(color: c.muted)),
                const SizedBox(height: 14),
                if (active != null) ...[
                  AdminOrderTile(order: active, margin: EdgeInsets.zero),
                  const SizedBox(height: 10),
                ],
                SoftButton(label: 'Позвонить', icon: Icons.call_rounded, onPressed: () => callPhone(context, x.phone)),
                const SizedBox(height: 10),
                x.blocked
                    ? GradientButton(
                        label: 'Разблокировать',
                        icon: Icons.lock_open_rounded,
                        onPressed: () {
                          s.setCourierBlocked(x, false);
                          Navigator.pop(ctx);
                        },
                      )
                    : SoftButton(
                        label: 'Заблокировать',
                        icon: Icons.block_rounded,
                        color: kDanger,
                        onPressed: () {
                          s.setCourierBlocked(x, true);
                          Navigator.pop(ctx);
                        },
                      ),
              ],
            ),
          ),
        );
      },
    );
  }
}
