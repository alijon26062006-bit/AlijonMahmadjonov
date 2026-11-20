import 'package:material_ui/material_ui.dart';

import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

/// Регистрация нового курьера или редактирование профиля.
class RegisterCourierScreen extends StatefulWidget {
  const RegisterCourierScreen({super.key, this.courier});

  final Courier? courier;

  @override
  State<RegisterCourierScreen> createState() => _RegisterCourierScreenState();
}

class _RegisterCourierScreenState extends State<RegisterCourierScreen> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.courier?.name ?? '');
  late String _vehicle = widget.courier?.vehicle ?? 'scooter';

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  void _save() {
    if (!_form.currentState!.validate()) return;
    final s = StoreScope.read(context);
    if (widget.courier == null) {
      s.registerCourier(name: _name.text.trim(), vehicle: _vehicle);
    } else {
      widget.courier!
        ..name = _name.text.trim()
        ..vehicle = _vehicle;
      s.setUserName(_name.text.trim());
      Navigator.of(context).pop();
      showSnack(context, 'Профиль сохранён');
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final creating = widget.courier == null;
    return Scaffold(
      appBar: AppBar(
        title: Text(creating ? 'Стать курьером' : 'Профиль курьера'),
        actions: [
          if (creating)
            TextButton(
              onPressed: s.logout,
              child: Text('Выйти', style: TextStyle(color: c.muted)),
            ),
        ],
      ),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          children: [
            if (creating)
              Text(
                'Номер ${formatPhone(s.user!.phone)} ещё не зарегистрирован. Заполните пару полей — и можно выходить на линию.',
                style: TextStyle(color: c.muted, height: 1.4),
              ),
            const FieldLabel('Имя и фамилия'),
            TextFormField(
              controller: _name,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(hintText: 'Как вас будут видеть покупатели'),
              validator: (v) => (v ?? '').trim().length < 2 ? 'Введите имя' : null,
            ),
            const FieldLabel('На чём доставляете'),
            for (final MapEntry(key: id, value: (icon, title)) in kVehicles.entries)
              ChoiceTile(
                icon: icon,
                title: title,
                selected: _vehicle == id,
                onTap: () => setState(() => _vehicle = id),
              ),
          ],
        ),
      ),
      bottomNavigationBar: BottomBar(
        child: GradientButton(label: creating ? 'Начать работу' : 'Сохранить', onPressed: _save),
      ),
    );
  }
}
