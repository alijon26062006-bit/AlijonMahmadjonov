import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../../../../app/localization/l10n.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../shared/models/category_schema.dart';
import '../../../../shared/models/localized_text.dart';
import '../../../../shared/widgets/daryob_text_field.dart';

/// Renders one schema field. Category modules only declare fields; this
/// widget draws them in the wizard.
class SchemaFieldInput extends StatefulWidget {
  const SchemaFieldInput({
    super.key,
    required this.field,
    required this.value,
    required this.onChanged,
    this.errorText,
  });

  final FieldSchema field;
  final Object? value;
  final ValueChanged<Object?> onChanged;
  final String? errorText;

  @override
  State<SchemaFieldInput> createState() => _SchemaFieldInputState();
}

class _SchemaFieldInputState extends State<SchemaFieldInput> {
  TextEditingController? _text;
  TextEditingController? _to;

  @override
  void initState() {
    super.initState();
    final v = widget.value;
    switch (widget.field.type) {
      case FieldType.text:
      case FieldType.multilineText:
      case FieldType.number:
        _text = TextEditingController(text: v == null ? '' : '$v');
      case FieldType.numberRange:
        final list = v is List ? v : const [];
        _text = TextEditingController(
          text: list.isNotEmpty ? '${list[0] ?? ''}' : '',
        );
        _to = TextEditingController(
          text: list.length > 1 ? '${list[1] ?? ''}' : '',
        );
      case FieldType.singleSelect:
      case FieldType.multiSelect:
      case FieldType.boolean:
        break;
    }
  }

  @override
  void dispose() {
    _text?.dispose();
    _to?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final field = widget.field;
    final label = field.required
        ? '${field.label.of(context)} *'
        : field.label.of(context);
    final hint = field.hint?.of(context);

    switch (field.type) {
      case FieldType.text:
      case FieldType.multilineText:
        return DaryobTextField(
          controller: _text,
          label: label,
          hint: hint,
          errorText: widget.errorText,
          maxLines: field.type == FieldType.multilineText ? 4 : 1,
          onChanged: (v) => widget.onChanged(v.trim().isEmpty ? null : v),
        );
      case FieldType.number:
        return DaryobTextField(
          controller: _text,
          label: label,
          hint: hint,
          errorText: widget.errorText,
          keyboardType: TextInputType.number,
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp(r'[\d.]')),
          ],
          suffix: field.unit == null
              ? null
              : Padding(
                  padding: const EdgeInsets.all(DaryobSpacing.md),
                  child: Text(field.unit!.of(context)),
                ),
          onChanged: (v) => widget.onChanged(num.tryParse(v)),
        );
      case FieldType.numberRange:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: context.text.labelMedium),
            const SizedBox(height: DaryobSpacing.sm),
            Row(
              children: [
                Expanded(
                  child: DaryobTextField(
                    controller: _text,
                    hint: context.l10n.priceFrom,
                    keyboardType: TextInputType.number,
                    onChanged: (_) => _emitRange(),
                  ),
                ),
                const SizedBox(width: DaryobSpacing.md),
                Expanded(
                  child: DaryobTextField(
                    controller: _to,
                    hint: context.l10n.priceTo,
                    keyboardType: TextInputType.number,
                    onChanged: (_) => _emitRange(),
                  ),
                ),
              ],
            ),
          ],
        );
      case FieldType.singleSelect:
        return _Labeled(
          label: label,
          error: widget.errorText,
          child: Wrap(
            spacing: DaryobSpacing.sm,
            runSpacing: DaryobSpacing.sm,
            children: [
              for (final option in field.options)
                ChoiceChip(
                  label: Text(option.label.of(context)),
                  selected: widget.value == option.value,
                  onSelected: (on) =>
                      widget.onChanged(on ? option.value : null),
                ),
            ],
          ),
        );
      case FieldType.multiSelect:
        final selected = widget.value is List
            ? List.of(widget.value as List)
            : <Object?>[];
        return _Labeled(
          label: label,
          error: widget.errorText,
          child: Wrap(
            spacing: DaryobSpacing.sm,
            runSpacing: DaryobSpacing.sm,
            children: [
              for (final option in field.options)
                FilterChip(
                  label: Text(option.label.of(context)),
                  selected: selected.contains(option.value),
                  onSelected: (on) {
                    on
                        ? selected.add(option.value)
                        : selected.remove(option.value);
                    widget.onChanged(selected.isEmpty ? null : selected);
                  },
                ),
            ],
          ),
        );
      case FieldType.boolean:
        return SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(label),
          value: widget.value == true,
          onChanged: (v) => widget.onChanged(v),
        );
    }
  }

  void _emitRange() {
    final from = num.tryParse(_text!.text);
    final to = num.tryParse(_to!.text);
    widget.onChanged(from == null && to == null ? null : [from, to]);
  }
}

class _Labeled extends StatelessWidget {
  const _Labeled({required this.label, required this.child, this.error});
  final String label;
  final Widget child;
  final String? error;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: context.text.labelMedium),
        const SizedBox(height: DaryobSpacing.sm),
        child,
        if (error != null) ...[
          const SizedBox(height: DaryobSpacing.xs),
          Text(
            error!,
            style: context.text.bodySmall?.copyWith(
              color: context.colors.error,
            ),
          ),
        ],
      ],
    );
  }
}
