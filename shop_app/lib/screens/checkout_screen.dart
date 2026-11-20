import 'package:material_ui/material_ui.dart';

import '../format.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';
import 'success_screen.dart';

const kPickupPoints = <String>[
  'Пункт выдачи «Центральный», ул. Центральная, 1',
  'Пункт выдачи «Садовый», ул. Садовая, 12',
  'Пункт выдачи «Парковый», пр. Парковый, 3',
];

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _form = GlobalKey<FormState>();
  late final ShopState _s = ShopScope.read(context);
  late final _name = TextEditingController(text: _s.name);
  late final _phone = TextEditingController(text: _s.phone);
  late final _address = TextEditingController(text: _s.address);
  final _comment = TextEditingController();
  bool _courier = true;
  int _pickup = 0;
  String _payment = 'Картой при получении';

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _address.dispose();
    _comment.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_form.currentState!.validate()) {
      showSnack(context, 'Заполните поля, отмеченные красным');
      return;
    }
    final order = _s.placeOrder(
      name: _name.text.trim(),
      phone: _phone.text.trim(),
      address: _courier ? _address.text.trim() : kPickupPoints[_pickup],
      courier: _courier,
      payment: _payment,
      comment: _comment.text.trim(),
    );
    Navigator.of(context).pushReplacement(MaterialPageRoute<void>(builder: (_) => SuccessScreen(order: order)));
  }

  @override
  Widget build(BuildContext context) {
    final s = ShopScope.of(context);
    final c = AppColors.of(context);
    final fee = s.deliveryFee(courier: _courier);

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
              const _Section('Получатель'),
              TextFormField(
                controller: _name,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  hintText: 'Имя и фамилия',
                  prefixIcon: Icon(Icons.person_outline_rounded),
                ),
                validator: (v) => (v ?? '').trim().length < 2 ? 'Укажите имя' : null,
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(hintText: 'Телефон', prefixIcon: Icon(Icons.phone_outlined)),
                validator: (v) {
                  final digits = (v ?? '').replaceAll(RegExp(r'\D'), '');
                  return digits.length < 9 ? 'Укажите номер телефона' : null;
                },
              ),
              const _Section('Способ получения'),
              ChoiceTile(
                emoji: '🚚',
                title: 'Курьером',
                subtitle: s.leftForFreeDelivery == 0
                    ? 'Завтра · бесплатно'
                    : 'Завтра · ${money(kDeliveryFee)}, бесплатно от ${money(kFreeDeliveryFrom)}',
                selected: _courier,
                onTap: () => setState(() => _courier = true),
              ),
              ChoiceTile(
                emoji: '🏪',
                title: 'Самовывоз',
                subtitle: 'Сегодня после 18:00 · бесплатно',
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
                            hintText: 'Город, улица, дом, квартира',
                            prefixIcon: Icon(Icons.location_on_outlined),
                          ),
                          validator: (v) => _courier && (v ?? '').trim().length < 5 ? 'Укажите адрес доставки' : null,
                        ),
                      )
                    : Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Material(
                          color: c.surface,
                          borderRadius: BorderRadius.circular(18),
                          clipBehavior: Clip.antiAlias,
                          child: Column(
                            children: [
                              for (var i = 0; i < kPickupPoints.length; i++)
                                ListTile(
                                  onTap: () => setState(() => _pickup = i),
                                  leading: Icon(
                                    i == _pickup ? Icons.radio_button_checked_rounded : Icons.radio_button_off_rounded,
                                    color: i == _pickup ? c.accentText : c.muted,
                                  ),
                                  title: Text(kPickupPoints[i], style: TextStyle(fontSize: 14, color: c.text)),
                                ),
                            ],
                          ),
                        ),
                      ),
              ),
              const _Section('Оплата'),
              for (final (emoji, title, sub) in const [
                ('💳', 'Картой при получении', 'Курьеру или в пункте выдачи'),
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
              const _Section('Комментарий'),
              TextField(
                controller: _comment,
                minLines: 2,
                maxLines: 4,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(hintText: 'Например: позвоните за час до доставки'),
              ),
              const _Section('Ваш заказ'),
              Container(
                padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
                decoration: BoxDecoration(
                  color: c.surface,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: c.cardShadow,
                ),
                child: Column(
                  children: [
                    SummaryRow('Товары (${s.cartCount})', money(s.itemsOldTotal)),
                    if (s.productDiscount > 0) SummaryRow('Скидка', '−${money(s.productDiscount)}', color: kPink),
                    if (s.promoDiscount > 0)
                      SummaryRow('Промокод ${s.promo!.code}', '−${money(s.promoDiscount)}', color: kPink),
                    SummaryRow('Доставка', fee == 0 ? 'бесплатно' : money(fee)),
                    const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Divider()),
                    SummaryRow('К оплате', money(s.total(courier: _courier)), big: true),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: BottomBar(
        child: GradientButton(
          label: 'Подтвердить заказ',
          trailing: money(s.total(courier: _courier)),
          onPressed: s.cart.isEmpty ? null : _submit,
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.title);

  final String title;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(4, 20, 4, 10),
    child: Text(
      title,
      style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: AppColors.of(context).text),
    ),
  );
}
