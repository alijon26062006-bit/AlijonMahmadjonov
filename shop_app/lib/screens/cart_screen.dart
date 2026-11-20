import 'package:material_ui/material_ui.dart';

import '../format.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';
import 'checkout_screen.dart';

class CartScreen extends StatelessWidget {
  const CartScreen({super.key});

  void _remove(BuildContext context, CartItem item) {
    final s = ShopScope.read(context);
    final index = s.removeFromCart(item);
    showSnack(
      context,
      'Товар удалён из корзины',
      actionLabel: 'Вернуть',
      onAction: () => s.restoreCartItem(index, item),
    );
  }

  Future<void> _confirmClear(BuildContext context) async {
    final s = ShopScope.read(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Очистить корзину?'),
        content: const Text('Все товары будут удалены из корзины.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Очистить')),
        ],
      ),
    );
    if (ok == true) s.clearCart();
  }

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
    final c = AppColors.of(context);

    if (s.cart.isEmpty) {
      return const SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            PageTitle('Корзина'),
            Expanded(child: _EmptyCart()),
          ],
        ),
      );
    }

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
                  onTap: () => _confirmClear(context),
                ),
              ),
              const _FreeDeliveryCard(),
              const SizedBox(height: 4),
              for (final item in s.cart)
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
                    child: _CartTile(item: item, onRemove: () => _remove(context, item)),
                  ),
                ),
              const _PromoField(),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
                child: Column(
                  children: [
                    SummaryRow('Товары (${s.cartCount})', money(s.itemsOldTotal)),
                    if (s.productDiscount > 0)
                      SummaryRow('Скидка на товары', '−${money(s.productDiscount)}', color: kPink),
                    if (s.promoDiscount > 0)
                      SummaryRow('Промокод ${s.promo!.code}', '−${money(s.promoDiscount)}', color: kPink),
                    const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Divider()),
                    SummaryRow('Итого', money(s.total()), big: true),
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
        child: GradientButton(
          label: 'Оформить заказ',
          trailing: money(s.total()),
          onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const CheckoutScreen())),
        ),
      ),
    );
  }
}

class _EmptyCart extends StatelessWidget {
  const _EmptyCart();

  @override
  Widget build(BuildContext context) => EmptyState(
    emoji: '🛍️',
    title: 'Корзина пуста',
    subtitle: 'Загляните на главную —\nтам скидки и хиты продаж',
    buttonLabel: 'За покупками',
    onButton: () => appNav.tab.value = AppNav.home,
  );
}

class _FreeDeliveryCard extends StatelessWidget {
  const _FreeDeliveryCard();

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
    final c = AppColors.of(context);
    final left = s.leftForFreeDelivery;
    final progress = (s.itemsTotal / kFreeDeliveryFrom).clamp(0.0, 1.0);
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 6, 16, 0),
      padding: const EdgeInsets.fromLTRB(14, 13, 14, 14),
      decoration: BoxDecoration(color: c.accentSoft, borderRadius: BorderRadius.circular(16)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text.rich(
            left > 0
                ? TextSpan(
                    children: [
                      const TextSpan(text: 'До бесплатной доставки осталось '),
                      TextSpan(
                        text: money(left),
                        style: TextStyle(color: c.accentText, fontWeight: FontWeight.w800),
                      ),
                    ],
                  )
                : const TextSpan(text: '🎉  Доставка курьером будет бесплатной'),
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
                    child: const DecoratedBox(decoration: BoxDecoration(gradient: kBrandGradient)),
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
  const _CartTile({required this.item, required this.onRemove});

  final CartItem item;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
    final c = AppColors.of(context);
    final p = s.productOf(item);
    return Container(
      decoration: BoxDecoration(color: c.surface, borderRadius: BorderRadius.circular(22), boxShadow: c.cardShadow),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          borderRadius: BorderRadius.circular(22),
          onTap: () => openProduct(context, p),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox.square(dimension: 88, child: ProductImage(product: p, emojiSize: 42, radius: 16)),
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
                          child: Text(optionText(p, item.option), style: TextStyle(fontSize: 12.5, color: c.muted)),
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
          ),
        ),
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
    final error = ShopScope.read(context).applyPromo(_controller.text);
    if (error != null) {
      showSnack(context, error);
    } else {
      FocusScope.of(context).unfocus();
      _controller.clear();
      showSnack(context, 'Промокод применён 🎉');
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
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
              SizedBox(
                height: 54,
                child: FilledButton.tonal(
                  style: FilledButton.styleFrom(
                    backgroundColor: c.chip,
                    foregroundColor: c.text,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                  onPressed: _apply,
                  child: const Text('Применить', style: TextStyle(fontWeight: FontWeight.w700)),
                ),
              ),
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
