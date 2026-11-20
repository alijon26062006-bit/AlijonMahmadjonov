import 'dart:async';

import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'format.dart';
import 'models.dart';
import 'store.dart';
import 'theme.dart';
import 'widgets.dart';

/// Подсказки для демо: номера, под которыми уже есть данные.
const _demoHints = <Role, List<(String, String)>>{
  Role.seller: [('900000001', 'магазин «ТехноМир»'), ('900000006', 'магазин «Фермер»')],
  Role.courier: [('930000001', 'курьер Рустам'), ('930000004', 'курьер Бехруз')],
  Role.admin: [('900000000', 'администратор')],
  Role.buyer: [],
};

String _subtitle(Role role) => switch (role) {
  Role.buyer => 'Войдите, чтобы оформлять заказы и следить за доставкой',
  Role.seller => 'Войдите, чтобы принимать заказы и управлять магазином',
  Role.courier => 'Войдите, чтобы брать заказы и доставлять их',
  Role.admin => 'Вход для администратора маркетплейса',
};

/// Открывает вход поверх текущего экрана. Возвращает true, если пользователь вошёл.
Future<bool> showLogin(BuildContext context, Role role) async {
  final ok = await Navigator.of(context)
      .push<bool>(MaterialPageRoute(builder: (_) => PhoneLoginScreen(role: role, canClose: true)));
  return ok ?? false;
}

/// Показывает [child], если пользователь вошёл, иначе — экран входа.
class AuthGate extends StatelessWidget {
  const AuthGate({super.key, required this.role, required this.child});

  final Role role;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 300),
      child: s.user == null ? PhoneLoginScreen(key: const ValueKey('login'), role: role) : child,
    );
  }
}

class PhoneLoginScreen extends StatefulWidget {
  const PhoneLoginScreen({super.key, required this.role, this.canClose = false});

  final Role role;
  final bool canClose;

  @override
  State<PhoneLoginScreen> createState() => _PhoneLoginScreenState();
}

class _PhoneLoginScreenState extends State<PhoneLoginScreen> {
  final _phone = TextEditingController();

  bool get _valid => phoneDigits(_phone.text).length == 9;

  @override
  void dispose() {
    _phone.dispose();
    super.dispose();
  }

  Future<void> _next() async {
    if (!_valid) return;
    final digits = phoneDigits(_phone.text);
    final code = StoreScope.read(context).requestCode(digits);
    final ok = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => _CodeScreen(phone: digits, demoCode: code, role: widget.role),
      ),
    );
    if (ok == true && mounted && widget.canClose) Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final brand = Brand.of(widget.role);
    final top = MediaQuery.paddingOf(context).top;
    final hints = _demoHints[widget.role]!;
    return Scaffold(
      body: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            Container(
              padding: EdgeInsets.fromLTRB(24, top + 12, 24, 30),
              decoration: BoxDecoration(
                gradient: c.headerGradient,
                borderRadius: const BorderRadius.vertical(bottom: Radius.circular(32)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    height: 44,
                    child: widget.canClose
                        ? Align(
                            alignment: Alignment.centerLeft,
                            child: CircleButton(
                              icon: Icons.close_rounded,
                              background: const Color(0x2EFFFFFF),
                              color: Colors.white,
                              onTap: () => Navigator.of(context).pop(false),
                            ),
                          )
                        : null,
                  ),
                  const SizedBox(height: 18),
                  Container(
                    width: 76,
                    height: 76,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: const Color(0x33FFFFFF),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: const Color(0x55FFFFFF), width: 1.5),
                    ),
                    child: Text(brand.emoji, style: const TextStyle(fontSize: 38)),
                  ),
                  const SizedBox(height: 18),
                  Text(
                    brand.appName,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 30,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.8,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _subtitle(widget.role),
                    style: const TextStyle(color: Color(0xE6FFFFFF), fontSize: 15, height: 1.35),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 28, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Номер телефона',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: c.text),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _phone,
                    autofocus: !widget.canClose,
                    keyboardType: TextInputType.phone,
                    inputFormatters: [PhoneInputFormatter()],
                    onChanged: (_) => setState(() {}),
                    onSubmitted: (_) => _next(),
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, letterSpacing: 1, color: c.text),
                    decoration: InputDecoration(
                      hintText: '90 123 45 67',
                      prefixIcon: Padding(
                        padding: const EdgeInsets.only(left: 16, right: 8),
                        child: Text(
                          '🇹🇯 $kPhoneCode',
                          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: c.text),
                        ),
                      ),
                      prefixIconConstraints: const BoxConstraints(minHeight: 0, minWidth: 0),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text('Пришлём SMS с кодом подтверждения', style: TextStyle(color: c.muted, fontSize: 13.5)),
                  const SizedBox(height: 22),
                  GradientButton(label: 'Получить код', onPressed: _valid ? _next : null),
                  if (hints.isNotEmpty) ...[
                    const SizedBox(height: 28),
                    Text(
                      'Демо-вход',
                      style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                    ),
                    const SizedBox(height: 8),
                    for (final (phone, who) in hints)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: AppCard(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                          onTap: () => setState(() => _phone.text = PhoneInputFormatter.format(phone)),
                          child: Row(
                            children: [
                              Icon(Icons.touch_app_outlined, color: c.accentText, size: 20),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text.rich(
                                  TextSpan(
                                    children: [
                                      TextSpan(
                                        text: formatPhone(phone),
                                        style: const TextStyle(fontWeight: FontWeight.w700),
                                      ),
                                      TextSpan(
                                        text: ' — $who',
                                        style: TextStyle(color: c.muted),
                                      ),
                                    ],
                                  ),
                                  style: TextStyle(color: c.text, fontSize: 14),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    Text(
                      widget.role == Role.admin
                          ? 'В демо-режиме войти можно с любым номером.'
                          : 'С любым другим номером вы зарегистрируетесь как новый ${widget.role == Role.seller ? 'продавец' : 'курьер'}.',
                      style: TextStyle(color: c.muted, fontSize: 12.5),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CodeScreen extends StatefulWidget {
  const _CodeScreen({required this.phone, required this.demoCode, required this.role});

  final String phone;
  final String demoCode;
  final Role role;

  @override
  State<_CodeScreen> createState() => _CodeScreenState();
}

class _CodeScreenState extends State<_CodeScreen> {
  final _code = TextEditingController();
  final _focus = FocusNode();
  late String _demoCode = widget.demoCode;
  bool _error = false;
  int _resendIn = 30;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startTimer();
  }

  void _startTimer() {
    _timer?.cancel();
    _resendIn = 30;
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      setState(() => _resendIn--);
      if (_resendIn <= 0) t.cancel();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _code.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _onChanged(String v) {
    setState(() => _error = false);
    if (v.length == 4) _verify();
  }

  void _verify() {
    final s = StoreScope.read(context);
    if (s.verifyCode(widget.phone, _code.text)) {
      HapticFeedback.mediumImpact();
      Navigator.of(context).pop(true);
    } else {
      HapticFeedback.heavyImpact();
      setState(() => _error = true);
      _code.clear();
    }
  }

  void _resend() {
    setState(() => _demoCode = StoreScope.read(context).requestCode(widget.phone));
    _startTimer();
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Scaffold(
      appBar: AppBar(),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
        children: [
          Text(
            'Код из SMS',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.w900, letterSpacing: -0.6, color: c.text),
          ),
          const SizedBox(height: 8),
          Text.rich(
            TextSpan(
              children: [
                const TextSpan(text: 'Отправили код на номер '),
                TextSpan(
                  text: formatPhone(widget.phone),
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ],
            ),
            style: TextStyle(fontSize: 15, color: c.muted, height: 1.4),
          ),
          const SizedBox(height: 18),
          DemoNote(text: 'Демо-режим: SMS пока не отправляется. Ваш код: $_demoCode'),
          const SizedBox(height: 22),
          GestureDetector(
            onTap: () => _focus.requestFocus(),
            child: Stack(
              children: [
                Opacity(
                  opacity: 0,
                  child: TextField(
                    controller: _code,
                    focusNode: _focus,
                    autofocus: true,
                    keyboardType: TextInputType.number,
                    maxLength: 4,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    onChanged: _onChanged,
                  ),
                ),
                ListenableBuilder(
                  listenable: Listenable.merge([_code, _focus]),
                  builder: (_, _) => Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      for (var i = 0; i < 4; i++)
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 150),
                          width: 60,
                          height: 68,
                          margin: const EdgeInsets.symmetric(horizontal: 6),
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: c.surface,
                            borderRadius: BorderRadius.circular(18),
                            border: Border.all(
                              color: _error
                                  ? kDanger
                                  : (_focus.hasFocus && i == _code.text.length.clamp(0, 3) ? c.accentText : c.line),
                              width: 2,
                            ),
                          ),
                          child: Text(
                            i < _code.text.length ? _code.text[i] : '',
                            style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: c.text),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          if (_error)
            const Center(
              child: Text(
                'Неверный код, попробуйте ещё раз',
                style: TextStyle(color: kDanger, fontWeight: FontWeight.w600),
              ),
            ),
          const SizedBox(height: 10),
          Center(
            child: _resendIn > 0
                ? Text('Отправить код повторно через $_resendIn с', style: TextStyle(color: c.muted))
                : TextButton(
                    onPressed: _resend,
                    child: Text(
                      'Отправить код ещё раз',
                      style: TextStyle(color: c.accentText, fontWeight: FontWeight.w700),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

/// Форматирует ввод номера как «90 123 45 67».
class PhoneInputFormatter extends TextInputFormatter {
  static String format(String digits) {
    final d = digits.replaceAll(RegExp(r'\D'), '');
    final b = StringBuffer();
    for (var i = 0; i < d.length && i < 9; i++) {
      if (i == 2 || i == 5 || i == 7) b.write(' ');
      b.write(d[i]);
    }
    return b.toString();
  }

  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    var digits = newValue.text.replaceAll(RegExp(r'\D'), '');
    if (digits.startsWith('992') && digits.length > 9) digits = digits.substring(3);
    final text = format(digits);
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}
