import 'package:material_ui/material_ui.dart';

import '../core/auth.dart';
import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'success_screen.dart';

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _form = GlobalKey<FormState>();
  late final MarketStore _s = StoreScope.read(context);
  late final _name = TextEditingController(text: _s.user?.name ?? '');
  late final _address = TextEditingController(text: _s.savedAddress);
  final _comment = TextEditingController();
  bool _courier = true;
  String _payment = kPayments.first;

  @override
  void dispose() {
    _name.dispose();
    _address.dispose();
    _comment.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_s.user == null) {
      final ok = await showLogin(context, Role.buyer);
      if (!ok || !mounted) return;
      if (_name.text.isEmpty) _name.text = _s.user?.name ?? '';
    }
    if (!_form.currentState!.validate()) {
      showSnack(context, 'Заполните поля, отмеченные красным');
      return;
    }
    final orders = _s.placeOrders(
      name: _name.text.trim(),
      phone: _s.user!.phone,
      address: _address.text.trim(),
      courier: _courier,
      payment: _payment,
      comment: _comment.text.trim(),
    );
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute<void>(builder: (_) => SuccessScreen(orders: orders)));
  }

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final c = AppColors.of(context);
    final fee = s.cartDeliveryFee(courier: _courier);
    final shops = s.cartByShop.keys.toList();

    return Scaffold(
      appBar: AppBar(title: const Text('Оформление заказа')),
      body: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            children: [
              const FieldLabel('Получатель'),
              if (s.user == null)
                AppCard(
                  color: c.accentSoft,
                  onTap: () => showLogin(context, Role.buyer).then((_) {
                    if (_name.text.isEmpty) _name.text = _s.user?.name ?? '';
                  }),
                  child: Row(
                    children: [
                      Icon(Icons.phone_iphone_rounded, color: c.accentText),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Войдите по номеру телефона — пришлём SMS-код',
                          style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                        ),
                      ),
                      Icon(Icons.chevron_right_rounded, color: c.accentText),
                    ],
                  ),
                )
              else
                AppCard(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  child: InfoLine(icon: Icons.phone_outlined, title: 'Телефон', text: formatPhone(s.user!.phone)),
                ),
              const SizedBox(height: 10),
              TextFormField(
                controller: _name,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(hintText: 'Ваше имя', prefixIcon: Icon(Icons.person_outline_rounded)),
                validator: (v) => (v ?? '').trim().length < 2 ? 'Укажите имя' : null,
              ),
              const FieldLabel('Способ получения'),
              ChoiceTile(
                emoji: '🚚',
                title: 'Курьером',
                subtitle: fee == 0
                    ? 'Сегодня · бесплатно'
                    : 'Сегодня · ${money(s.settings.deliveryFee)} с магазина, бесплатно от ${money(s.settings.freeDeliveryFrom)}',
                selected: _courier,
                onTap: () => setState(() => _courier = true),
              ),
              ChoiceTile(
                emoji: '🏪',
                title: 'Самовывоз из магазина',
                subtitle: shops.length == 1 ? shops.first.address : 'Из ${shops.length} магазинов · бесплатно',
                selected: !_courier,
                onTap: () => setState(() => _courier = false),
              ),
              AnimatedSize(
                duration: const Duration(milliseconds: 250),
                curve: Curves.easeOutCubic,
                alignment: Alignment.topCenter,
                child: _courier
                    ? Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: TextFormField(
                          controller: _address,
                          minLines: 1,
                          maxLines: 2,
                          textCapitalization: TextCapitalization.sentences,
                          decoration: const InputDecoration(
                            hintText: 'Улица, дом, квартира',
                            prefixIcon: Icon(Icons.location_on_outlined),
                          ),
                          validator: (v) => _courier && (v ?? '').trim().length < 5 ? 'Укажите адрес доставки' : null,
                        ),
                      )
                    : AppCard(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                        child: Column(
                          children: [
                            for (final shop in shops)
                              InfoLine(icon: Icons.storefront_outlined, title: shop.name, text: shop.address),
                          ],
                        ),
                      ),
              ),
              const FieldLabel('Оплата'),
              for (final (emoji, title, sub) in const [
                ('💳', 'Картой при получении', 'Курьеру или в магазине'),
                ('💵', 'Наличными', 'Подготовьте сумму без сдачи'),
                ('📲', 'Онлайн', 'Демо-режим, деньги не списываются'),
              ])
                ChoiceTile(
                  emoji: emoji,
                  title: title,
                  subtitle: sub,
                  selected: _payment == title,
                  onTap: () => setState(() => _payment = title),
                ),
              const FieldLabel('Комментарий'),
              TextField(
                controller: _comment,
                minLines: 2,
                maxLines: 4,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(hintText: 'Например: позвоните за 10 минут'),
              ),
              const FieldLabel('Ваш заказ'),
              AppCard(
                child: Column(
                  children: [
                    if (shops.length > 1)
                      SummaryRow('Заказов', '${shops.length} (${shops.map((e) => e.name).join(', ')})'),
                    SummaryRow('Товары (${s.cartCount})', money(s.itemsOldTotal)),
                    if (s.productDiscount > 0)
                      SummaryRow('Скидка', '−${money(s.productDiscount)}', color: c.gradientColors.last),
                    if (s.promoDiscount > 0)
                      SummaryRow(
                        'Промокод ${s.promo!.code}',
                        '−${money(s.promoDiscount)}',
                        color: c.gradientColors.last,
                      ),
                    SummaryRow('Доставка', fee == 0 ? 'бесплатно' : money(fee)),
                    const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Divider()),
                    SummaryRow('К оплате', money(s.cartTotal(courier: _courier)), big: true),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: BottomBar(
        child: GradientButton(
          label: s.user == null ? 'Войти и оформить' : 'Подтвердить заказ',
          trailing: money(s.cartTotal(courier: _courier)),
          onPressed: s.cart.isEmpty ? null : _submit,
        ),
      ),
    );
  }
}
