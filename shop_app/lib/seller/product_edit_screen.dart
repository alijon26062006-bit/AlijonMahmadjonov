import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

/// Эмодзи вместо фото товара (до подключения загрузки фото на сервер).
const kProductEmojis = [
  '📱',
  '💻',
  '🎧',
  '⌚',
  '🔊',
  '🎮',
  '🔋',
  '🔌',
  '📷',
  '📲',
  '🖥️',
  '⌨️',
  '👕',
  '👖',
  '👗',
  '🧥',
  '🧢',
  '🎒',
  '👜',
  '🧣',
  '👟',
  '🥾',
  '👞',
  '👡',
  '☕',
  '💡',
  '🍳',
  '🌿',
  '🕯️',
  '🛏️',
  '🧹',
  '🧺',
  '🍽️',
  '🌸',
  '💄',
  '🧴',
  '💅',
  '🧼',
  '💍',
  '⚽',
  '🏋️',
  '🚲',
  '🧘',
  '🏀',
  '🎾',
  '🧸',
  '🤖',
  '🏎️',
  '🧩',
  '🎨',
  '🍎',
  '🍫',
  '🍵',
  '🍯',
  '🧀',
  '🥛',
  '🍞',
  '🍇',
  '🥩',
  '🍉',
];

/// Добавление и редактирование товара.
class ProductEditScreen extends StatefulWidget {
  const ProductEditScreen({super.key, this.product});

  final Product? product;

  @override
  State<ProductEditScreen> createState() => _ProductEditScreenState();
}

class _ProductEditScreenState extends State<ProductEditScreen> {
  final _form = GlobalKey<FormState>();
  late final Product? _p = widget.product;
  late String _emoji = _p?.emoji ?? '📦';
  late String _category = _p?.categoryId ?? StoreScope.read(context).myShop!.categoryId;
  late final _title = TextEditingController(text: _p?.title ?? '');
  late final _price = TextEditingController(text: _p == null ? '' : '${_p.price}');
  late final _oldPrice = TextEditingController(text: _p?.oldPrice?.toString() ?? '');
  late final _stock = TextEditingController(text: '${_p?.stock ?? 10}');
  late final _desc = TextEditingController(text: _p?.description ?? '');
  late final _optLabel = TextEditingController(text: _p?.optionsLabel ?? '');
  late final _options = TextEditingController(text: _p?.options.join(', ') ?? '');
  late bool _active = _p?.active ?? true;

  @override
  void dispose() {
    for (final c in [_title, _price, _oldPrice, _stock, _desc, _optLabel, _options]) {
      c.dispose();
    }
    super.dispose();
  }

  void _save() {
    if (!_form.currentState!.validate()) return;
    final s = StoreScope.read(context);
    final options = _options.text.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
    final old = int.tryParse(_oldPrice.text.trim());
    final p =
        _p ??
        Product(
          id: s.newProductId(),
          shopId: s.myShop!.id,
          title: '',
          categoryId: _category,
          emoji: _emoji,
          price: 0,
          rating: 5,
          reviews: 0,
        );
    p
      ..title = _title.text.trim()
      ..emoji = _emoji
      ..categoryId = _category
      ..price = int.parse(_price.text.trim())
      ..oldPrice = old != null && old > p.price ? old : null
      ..stock = int.parse(_stock.text.trim())
      ..description = _desc.text.trim()
      ..options = options
      ..optionsLabel = options.isEmpty ? null : (_optLabel.text.trim().isEmpty ? 'Вариант' : _optLabel.text.trim())
      ..active = _active;
    s.saveProduct(p);
    Navigator.of(context).pop();
    showSnack(context, _p == null ? 'Товар добавлен — покупатели уже видят его' : 'Изменения сохранены');
  }

  Future<void> _delete() async {
    final s = StoreScope.read(context);
    if (await confirm(context, title: 'Удалить товар?', text: _p!.title, ok: 'Удалить', danger: true)) {
      s.deleteProduct(_p);
      if (mounted) Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    String? positive(String? v) {
      final n = int.tryParse((v ?? '').trim());
      return n == null || n <= 0 ? 'Введите число больше 0' : null;
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(_p == null ? 'Новый товар' : 'Редактирование'),
        actions: [
          if (_p != null)
            IconButton(
              tooltip: 'Удалить',
              icon: const Icon(Icons.delete_outline_rounded, color: kDanger),
              onPressed: _delete,
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
              Center(
                child: GestureDetector(
                  onTap: _pickEmoji,
                  child: SizedBox(
                    width: 150,
                    height: 150,
                    child: Stack(
                      children: [
                        Positioned.fill(
                          child: EmojiImage(emoji: _emoji, categoryId: _category, size: 70, radius: 32),
                        ),
                        Positioned(
                          right: 8,
                          bottom: 8,
                          child: CircleButton(
                            icon: Icons.edit_rounded,
                            size: 38,
                            background: c.surface,
                            onTap: _pickEmoji,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 6),
              Center(
                child: Text('Нажмите, чтобы выбрать картинку', style: TextStyle(color: c.muted, fontSize: 12.5)),
              ),
              const FieldLabel('Название'),
              TextFormField(
                controller: _title,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(hintText: 'Например: Смартфон Nova X12'),
                validator: (v) => (v ?? '').trim().length < 3 ? 'Минимум 3 символа' : null,
              ),
              const FieldLabel('Категория'),
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
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const FieldLabel('Цена, $kCurrency'),
                        TextFormField(
                          controller: _price,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          decoration: const InputDecoration(hintText: '0'),
                          validator: positive,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const FieldLabel('Старая цена'),
                        TextFormField(
                          controller: _oldPrice,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          decoration: const InputDecoration(hintText: 'для скидки'),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const FieldLabel('Остаток на складе, шт.'),
              TextFormField(
                controller: _stock,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                validator: (v) => int.tryParse((v ?? '').trim()) == null ? 'Введите число' : null,
              ),
              const FieldLabel('Варианты (необязательно)'),
              TextFormField(
                controller: _optLabel,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(hintText: 'Что выбирают: Размер, Цвет, Память'),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _options,
                decoration: const InputDecoration(hintText: 'Через запятую: S, M, L, XL'),
              ),
              const FieldLabel('Описание'),
              TextFormField(
                controller: _desc,
                minLines: 3,
                maxLines: 6,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(hintText: 'Чем хорош товар, размеры, материал…'),
              ),
              const SizedBox(height: 12),
              AppCard(
                padding: EdgeInsets.zero,
                child: SwitchListTile(
                  value: _active,
                  onChanged: (v) => setState(() => _active = v),
                  title: Text(
                    'В продаже',
                    style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                  ),
                  subtitle: Text(
                    'Выключите, чтобы временно скрыть товар',
                    style: TextStyle(color: c.muted, fontSize: 12.5),
                  ),
                ),
              ),
              if (_p?.hiddenByAdmin ?? false) ...[
                const SizedBox(height: 10),
                const DemoNote(text: 'Товар скрыт администратором и не виден покупателям. Свяжитесь с поддержкой.'),
              ],
            ],
          ),
        ),
      ),
      bottomNavigationBar: BottomBar(
        child: GradientButton(label: _p == null ? 'Добавить товар' : 'Сохранить', onPressed: _save),
      ),
    );
  }

  Future<void> _pickEmoji() async {
    final picked = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final e in kProductEmojis)
                InkWell(
                  borderRadius: BorderRadius.circular(14),
                  onTap: () => Navigator.pop(ctx, e),
                  child: Container(
                    width: 52,
                    height: 52,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: e == _emoji ? AppColors.of(ctx).accentSoft : Colors.transparent,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Text(e, style: const TextStyle(fontSize: 30)),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
    if (picked != null) setState(() => _emoji = picked);
  }
}
