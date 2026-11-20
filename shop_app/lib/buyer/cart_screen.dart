import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'buyer_common.dart';
import 'checkout_screen.dart';

class CartScreen extends StatelessWidget {
  const CartScreen({super.key});

  void _remove(BuildContext context, CartItem item) {
    final s = StoreScope.read(context);
    final index = s.removeFromCart(item);
    showSnack(
      context,
      'Товар удалён из корзины',
      actionLabel: 'Вернуть',
      onAction: () => s.restoreCartItem(index, item),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);

    if (s.cart.isEmpty) {
      return SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const PageTitle('Корзина'),
            Expanded(
              child: EmptyState(
                image: 'bags',
                title: 'Корзина пуста',
                subtitle: 'Загляните на главную —\nтам скидки и хиты продаж',
                buttonLabel: 'За покупками',
                onButton: () => buyerNav.tab.value = BuyerNav.home,
              ),
            ),
          ],
        ),
      );
    }

    final groups = s.cartByShop;
    final problems = s.unavailableInCart;
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: GestureDetector(
          onTap: () => FocusScope.of(context).unfocus(),
          child: ListView(
            padding: const EdgeInsets.only(bottom: 24),
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            children: [
              PageTitle(
                'Корзина',
                badge: itemsLabel(s.cartCount),
                trailing: CircleButton(
                  icon: Icons.delete_outline_rounded,
                  tooltip: 'Очистить корзину',
                  onTap: () async {
                    if (await confirm(context, title: 'Очистить корзину?', ok: 'Очистить', danger: true)) s.clearCart();
                  },
                ),
              ),
              if (groups.length > 1)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
                  child: InfoNote(
                    text:
                        'Товары из ${groups.length} магазинов. Каждый магазин отправит свой заказ, поэтому получится ${ordersLabel(groups.length)}.',
                  ),
                ),
              for (final entry in groups.entries) ...[
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 2),
                  child: Row(
                    children: [
                      ImageTile(image: entry.key.logo, categoryId: entry.key.categoryId, size: 30),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          entry.key.name,
                          style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: c.text),
                        ),
                      ),
                      if (!entry.key.isOpen) const StatusPill(label: 'Закрыт', color: kDanger),
                    ],
                  ),
                ),
                for (final item in entry.value)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                    child: Dismissible(
                      key: ValueKey(item.key),
                      direction: DismissDirection.endToStart,
                      onDismissed: (_) => _remove(context, item),
                      background: Container(
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 26),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFF4D6D),
                          borderRadius: BorderRadius.circular(22),
                        ),
                        child: const Icon(Icons.delete_outline_rounded, color: Colors.white, size: 28),
                      ),
                      child: _CartTile(
                        item: item,
                        problem: problems.contains(item),
                        onRemove: () => _remove(context, item),
                      ),
                    ),
                  ),
              ],
              const SizedBox(height: 6),
              const _FreeDeliveryCard(),
              const _PromoField(),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
                child: Column(
                  children: [
                    SummaryRow('Товары (${s.cartCount})', money(s.itemsOldTotal)),
                    if (s.productDiscount > 0)
                      SummaryRow('Скидка на товары', '−${money(s.productDiscount)}', color: c.gradientColors.last),
                    if (s.promoDiscount > 0)
                      SummaryRow(
                        'Промокод ${s.promo!.code}',
                        '−${money(s.promoDiscount)}',
                        color: c.gradientColors.last,
                      ),
                    const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Divider()),
                    SummaryRow('Итого', money(s.cartTotal()), big: true),
                    const SizedBox(height: 4),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Стоимость доставки рассчитаем при оформлении',
                        style: TextStyle(fontSize: 12.5, color: c.muted),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: BottomBar(
        child: problems.isNotEmpty
            ? SoftButton(
                label: 'Уберите недоступные товары',
                icon: Icons.error_outline_rounded,
                color: kDanger,
                onPressed: () => showSnack(context, 'Некоторые товары закончились или магазин закрыт'),
              )
            : GradientButton(
                label: 'Оформить заказ',
                trailing: money(s.cartTotal()),
                onPressed: () =>
                    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const CheckoutScreen())),
              ),
      ),
    );
  }
}

class _FreeDeliveryCard extends StatelessWidget {
  const _FreeDeliveryCard();

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final groups = s.cartByShop;
    // Порог бесплатной доставки считается для каждого магазина — показываем по самому «близкому».
    final sums = [for (final items in groups.values) items.fold(0, (a, i) => a + s.productOf(i).price * i.qty)];
    final best = sums.isEmpty ? 0 : sums.reduce((a, b) => a > b ? a : b);
    final left = (s.settings.freeDeliveryFrom - best).clamp(0, s.settings.freeDeliveryFrom);
    final progress = (best / s.settings.freeDeliveryFrom).clamp(0.0, 1.0);
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      padding: const EdgeInsets.fromLTRB(14, 13, 14, 14),
      decoration: BoxDecoration(color: c.accentSoft, borderRadius: BorderRadius.circular(16)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text.rich(
            left > 0
                ? TextSpan(
                    children: [
                      TextSpan(
                        text: groups.length > 1
                            ? 'До бесплатной доставки из одного магазина '
                            : 'До бесплатной доставки осталось ',
                      ),
                      TextSpan(
                        text: money(left),
                        style: TextStyle(color: c.accentText, fontWeight: FontWeight.w800),
                      ),
                    ],
                  )
                : const TextSpan(text: 'Доставка курьером будет бесплатной'),
            style: TextStyle(fontSize: 13.5, color: c.text, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 9),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: SizedBox(
              height: 7,
              child: Stack(
                children: [
                  Positioned.fill(child: ColoredBox(color: c.line)),
                  AnimatedFractionallySizedBox(
                    duration: const Duration(milliseconds: 400),
                    curve: Curves.easeOutCubic,
                    widthFactor: progress,
                    child: DecoratedBox(decoration: BoxDecoration(gradient: c.gradient)),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CartTile extends StatelessWidget {
  const _CartTile({required this.item, required this.onRemove, required this.problem});

  final CartItem item;
  final VoidCallback onRemove;
  final bool problem;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final p = s.productOf(item);
    return AppCard(
      padding: const EdgeInsets.all(10),
      onTap: () => openProduct(context, p),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox.square(
            dimension: 88,
            child: ProductImage(image: p.image, categoryId: p.categoryId, size: 42, radius: 16, dimmed: problem),
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
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, height: 1.25, color: c.text),
                ),
                if (item.option != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      '${p.optionsLabel ?? 'Вариант'}: ${item.option}',
                      style: TextStyle(fontSize: 12.5, color: c.muted),
                    ),
                  ),
                if (problem)
                  const Padding(
                    padding: EdgeInsets.only(top: 2),
                    child: Text(
                      'Сейчас недоступен',
                      style: TextStyle(fontSize: 12.5, color: kDanger, fontWeight: FontWeight.w600),
                    ),
                  ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        money(p.price * item.qty),
                        style: TextStyle(fontSize: 16.5, fontWeight: FontWeight.w800, color: c.text),
                      ),
                    ),
                    QtyStepper(
                      compact: true,
                      min: 0,
                      max: p.stock.clamp(1, 99),
                      value: item.qty,
                      onChanged: (v) => v == 0 ? onRemove() : s.setQty(item, v),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PromoField extends StatefulWidget {
  const _PromoField();

  @override
  State<_PromoField> createState() => _PromoFieldState();
}

class _PromoFieldState extends State<_PromoField> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _apply() {
    final error = StoreScope.read(context).applyPromo(_controller.text);
    if (error != null) {
      showSnack(context, error);
    } else {
      FocusScope.of(context).unfocus();
      _controller.clear();
      showSnack(context, 'Промокод применён');
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final promo = s.promo;
    if (promo != null) {
      return Container(
        margin: const EdgeInsets.fromLTRB(16, 14, 16, 0),
        padding: const EdgeInsets.fromLTRB(14, 6, 4, 6),
        decoration: BoxDecoration(
          color: c.accentSoft,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: c.accentText.withValues(alpha: .4), width: 1.5),
        ),
        child: Row(
          children: [
            Icon(Icons.local_offer_rounded, color: c.accentText, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    promo.code,
                    style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                  ),
                  Text(promo.title, style: TextStyle(fontSize: 12.5, color: c.muted)),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Убрать промокод',
              icon: Icon(Icons.close_rounded, color: c.muted),
              onPressed: s.removePromo,
            ),
          ],
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  textCapitalization: TextCapitalization.characters,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _apply(),
                  decoration: InputDecoration(
                    hintText: 'Промокод',
                    prefixIcon: Icon(Icons.local_offer_outlined, color: c.muted),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              SoftButton(label: 'Применить', onPressed: _apply),
            ],
          ),
          Padding(
            padding: const EdgeInsets.only(left: 4, top: 6),
            child: Text('Попробуйте VITRINA20 — скидка 20%', style: TextStyle(fontSize: 12.5, color: c.muted)),
          ),
        ],
      ),
    );
  }
}
