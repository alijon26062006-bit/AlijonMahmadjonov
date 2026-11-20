import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

const _shopEmojis = ['🏪', '📱', '👗', '👟', '🏠', '💄', '⚽', '🧸', '🍎', '🥖', '☕', '🌸', '🎧', '📚', '🛠️', '🐾'];

/// Создание магазина (новый продавец) или редактирование данных магазина.
class CreateShopScreen extends StatefulWidget {
  const CreateShopScreen({super.key, this.shop});

  final Shop? shop;

  @override
  State<CreateShopScreen> createState() => _CreateShopScreenState();
}

class _CreateShopScreenState extends State<CreateShopScreen> {
  final _form = GlobalKey<FormState>();
  late final Shop? _shop = widget.shop;
  late final _name = TextEditingController(text: _shop?.name ?? '');
  late final _owner = TextEditingController(text: _shop?.ownerName ?? StoreScope.read(context).user?.name ?? '');
  late final _address = TextEditingController(text: _shop?.address ?? '');
  late final _desc = TextEditingController(text: _shop?.description ?? '');
  late String _emoji = _shop?.emoji ?? '🏪';
  late String _category = _shop?.categoryId ?? kCategories.first.id;

  @override
  void dispose() {
    for (final c in [_name, _owner, _address, _desc]) {
      c.dispose();
    }
    super.dispose();
  }

  void _save() {
    if (!_form.currentState!.validate()) return;
    final s = StoreScope.read(context);
    if (_shop == null) {
      s.createShop(
        name: _name.text.trim(),
        ownerName: _owner.text.trim(),
        emoji: _emoji,
        categoryId: _category,
        address: _address.text.trim(),
        description: _desc.text.trim(),
      );
    } else {
      _shop
        ..name = _name.text.trim()
        ..ownerName = _owner.text.trim()
        ..emoji = _emoji
        ..categoryId = _category
        ..address = _address.text.trim()
        ..description = _desc.text.trim();
      s.updateShop(_shop);
      Navigator.of(context).pop();
      showSnack(context, 'Данные магазина сохранены');
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final s = StoreScope.of(context);
    final creating = _shop == null;
    return Scaffold(
      appBar: AppBar(
        title: Text(creating ? 'Новый магазин' : 'Данные магазина'),
        actions: [
          if (creating)
            TextButton(
              onPressed: s.logout,
              child: Text('Выйти', style: TextStyle(color: c.muted)),
            ),
        ],
      ),
      body: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
            children: [
              if (creating) ...[
                Text(
                  'Номер ${formatPhone(s.user!.phone)} ещё не привязан к магазину. Расскажите о магазине — и можно добавлять товары.',
                  style: TextStyle(color: c.muted, height: 1.4),
                ),
                const SizedBox(height: 10),
                const DemoNote(
                  text: 'В демо магазин сразу открыт. С сервером новый магазин сначала проверит администратор.',
                ),
              ],
              const FieldLabel('Логотип'),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final e in _shopEmojis)
                    InkWell(
                      borderRadius: BorderRadius.circular(14),
                      onTap: () => setState(() => _emoji = e),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        width: 50,
                        height: 50,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: e == _emoji ? c.accentSoft : c.surface,
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(color: e == _emoji ? c.accentText : c.line, width: 1.5),
                        ),
                        child: Text(e, style: const TextStyle(fontSize: 26)),
                      ),
                    ),
                ],
              ),
              const FieldLabel('Название магазина'),
              TextFormField(
                controller: _name,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(hintText: 'Например: Гаджеты у Фарруха'),
                validator: (v) => (v ?? '').trim().length < 2 ? 'Введите название' : null,
              ),
              const FieldLabel('Ваше имя'),
              TextFormField(
                controller: _owner,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(hintText: 'Имя и фамилия'),
                validator: (v) => (v ?? '').trim().length < 2 ? 'Введите имя' : null,
              ),
              const FieldLabel('Что продаёте'),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final cat in kCategories)
                    ChoiceChip(
                      label: Text('${cat.emoji} ${cat.name}'),
                      selected: _category == cat.id,
                      showCheckmark: false,
                      selectedColor: c.accentSoft,
                      side: BorderSide(color: _category == cat.id ? c.accentText : c.line),
                      labelStyle: TextStyle(
                        fontWeight: FontWeight.w700,
                        color: _category == cat.id ? c.accentText : c.text,
                      ),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(99)),
                      onSelected: (_) => setState(() => _category = cat.id),
                    ),
                ],
              ),
              const FieldLabel('Адрес магазина'),
              TextFormField(
                controller: _address,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  hintText: 'Отсюда курьер забирает заказы',
                  prefixIcon: Icon(Icons.location_on_outlined),
                ),
                validator: (v) => (v ?? '').trim().length < 5 ? 'Введите адрес' : null,
              ),
              const FieldLabel('Описание'),
              TextFormField(
                controller: _desc,
                minLines: 2,
                maxLines: 4,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(hintText: 'Пара слов для покупателей'),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: BottomBar(
        child: GradientButton(label: creating ? 'Открыть магазин' : 'Сохранить', onPressed: _save),
      ),
    );
  }
}
