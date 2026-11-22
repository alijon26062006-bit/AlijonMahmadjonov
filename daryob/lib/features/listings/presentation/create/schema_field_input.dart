import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/localization/l10n.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../core/location/device_location.dart';
import '../../../../shared/models/category_schema.dart';
import '../../../../shared/models/localized_text.dart';
import '../../../../shared/models/region.dart';
import '../../../../shared/providers/core_providers.dart';
import '../../../../shared/widgets/daryob_text_field.dart';
import '../../../../shared/widgets/toast.dart';
import '../../../catalog/application/catalog_providers.dart';
import '../../../catalog/presentation/catalog_ui.dart';

/// Renders one catalog field. Category data only declares fields; this
/// widget draws them, so the same code serves all 115 subcategories.
class SchemaFieldInput extends ConsumerStatefulWidget {
  const SchemaFieldInput({
    super.key,
    required this.schema,
    required this.field,
    required this.attributes,
    required this.onChanged,
    this.errorText,
    this.regionId,
  });

  final CategorySchema schema;
  final FieldSchema field;

  /// All current values — dependent fields (model → brand) read them.
  final Map<String, Object?> attributes;
  final ValueChanged<Object?> onChanged;
  final String? errorText;

  /// Selected location, for district (`location_child`) fields.
  final String? regionId;

  @override
  ConsumerState<SchemaFieldInput> createState() => _SchemaFieldInputState();
}

class _SchemaFieldInputState extends ConsumerState<SchemaFieldInput> {
  late final TextEditingController _text = TextEditingController(text: _initialText());

  Object? get _value => widget.attributes[widget.field.key];

  String _initialText() {
    final v = widget.attributes[widget.field.key];
    if (v == null) return '';
    if (v is List) return v.join(', ');
    if (widget.field.type == FieldType.money && v is num) {
      return PriceInputFormatter()
          .formatEditUpdate(TextEditingValue.empty, TextEditingValue(text: '${v.round()}'))
          .text;
    }
    if (v is num) return v == v.roundToDouble() ? '${v.toInt()}' : '$v'.replaceAll('.', ',');
    return '$v';
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  String get _label {
    final label = widget.field.label.of(context);
    return widget.field.required ? '$label *' : label;
  }

  String? get _unit {
    final u = widget.field.unit;
    if (u == null) return null;
    return attributeFormatter(context, ref).unit(u);
  }

  bool get _locked => widget.schema.lockedAttributes.contains(widget.field.key);

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final field = widget.field;
    switch (field.type) {
      case FieldType.text:
      case FieldType.size:
        return DaryobTextField(
          controller: _text,
          label: _label,
          errorText: widget.errorText,
          maxLength: 120,
          onChanged: (v) => widget.onChanged(v.trim().isEmpty ? null : v.trim()),
        );
      case FieldType.multilineText:
        return DaryobTextField(
          controller: _text,
          label: _label,
          errorText: widget.errorText,
          maxLines: 4,
          maxLength: 1000,
          onChanged: (v) => widget.onChanged(v.trim().isEmpty ? null : v),
        );
      case FieldType.tags:
        return DaryobTextField(
          controller: _text,
          label: _label,
          hint: l10n.tagsHint,
          errorText: widget.errorText,
          onChanged: (v) {
            final tags = v.split(',').map((t) => t.trim()).where((t) => t.isNotEmpty).toList();
            widget.onChanged(tags.isEmpty ? null : tags);
          },
        );
      case FieldType.integer:
      case FieldType.number:
      case FieldType.money:
        return _numberField(field);
      case FieldType.singleSelect:
      case FieldType.color:
        final options = widget.schema.optionsFor(field);
        return _Labeled(
          label: _label,
          error: widget.errorText,
          child: Wrap(
            spacing: DaryobSpacing.sm,
            runSpacing: DaryobSpacing.sm,
            children: [
              for (final option in options)
                ChoiceChip(
                  label: Text(option.label.of(context)),
                  selected: _value == option.value,
                  onSelected: _locked ? null : (on) => widget.onChanged(on ? option.value : null),
                ),
            ],
          ),
        );
      case FieldType.multiSelect:
        final selected = _value is List ? List<Object?>.of(_value as List) : <Object?>[];
        return _Labeled(
          label: _label,
          error: widget.errorText,
          child: Wrap(
            spacing: DaryobSpacing.sm,
            runSpacing: DaryobSpacing.sm,
            children: [
              for (final option in widget.schema.optionsFor(field))
                FilterChip(
                  label: Text(option.label.of(context)),
                  selected: selected.contains(option.value),
                  onSelected: (on) {
                    final next = List<Object?>.of(selected);
                    on ? next.add(option.value) : next.remove(option.value);
                    widget.onChanged(next.isEmpty ? null : next);
                  },
                ),
            ],
          ),
        );
      case FieldType.boolean:
        if (field.required) {
          return _Labeled(
            label: _label,
            error: widget.errorText,
            child: Wrap(
              spacing: DaryobSpacing.sm,
              children: [
                ChoiceChip(
                  label: Text(l10n.yes),
                  selected: _value == true,
                  onSelected: (_) => widget.onChanged(true),
                ),
                ChoiceChip(
                  label: Text(l10n.no),
                  selected: _value == false,
                  onSelected: (_) => widget.onChanged(false),
                ),
              ],
            ),
          );
        }
        return SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(_label),
          value: _value == true,
          onChanged: (v) => widget.onChanged(v),
        );
      case FieldType.brand:
      case FieldType.model:
      case FieldType.variant:
      case FieldType.family:
      case FieldType.occupation:
      case FieldType.species:
        return _directoryField(field);
      case FieldType.locationChild:
        return _districtField(field);
      case FieldType.geoPoint:
        return _geoPointField(field);
      case FieldType.numberRange:
        return const SizedBox.shrink();
    }
  }

  Widget _numberField(FieldSchema field) {
    final l10n = context.l10n;
    final money = field.type == FieldType.money;
    final decimal = field.type == FieldType.number;
    final min = field.minExclusive != null ? '> ${field.minExclusive}' : field.min?.toString();
    final max = field.maxFor(DateTime.now())?.toString();
    final hint = switch ((min, max)) {
      (String a, String b) => '$a – $b',
      (String a, null) => l10n.atLeast(a),
      _ => null,
    };
    return DaryobTextField(
      controller: _text,
      label: _label,
      hint: hint,
      errorText: widget.errorText,
      keyboardType: TextInputType.numberWithOptions(decimal: decimal),
      inputFormatters: money
          ? [PriceInputFormatter()]
          : decimal
          ? [FilteringTextInputFormatter.allow(RegExp(r'[\d.,]'))]
          : [FilteringTextInputFormatter.allow(RegExp(r'^-?\d*'))],
      suffix: _unit == null && !money
          ? null
          : Padding(
              padding: const EdgeInsets.all(DaryobSpacing.md),
              child: Text(money ? attributeFormatter(context, ref).unit('TJS') : _unit!),
            ),
      onChanged: (v) {
        final clean = v.replaceAll(RegExp(r'[\s ]'), '').replaceAll(',', '.');
        if (clean.isEmpty || clean == '-') return widget.onChanged(null);
        final n = num.tryParse(clean);
        widget.onChanged(n == null ? clean : (field.type == FieldType.number ? n : n.round()));
      },
    );
  }

  /// Brand / model / variant / family / occupation / species.
  Widget _directoryField(FieldSchema field) {
    final l10n = context.l10n;
    final catalog = ref.watch(catalogProvider);
    final directory = catalog.directory(field.directory);
    final formatter = attributeFormatter(context, ref);

    List<PickerItem> items = const [];
    String? note;
    switch (field.type) {
      case FieldType.brand:
        if (directory != null && directory.brands.isNotEmpty) {
          items = [for (final b in directory.brands) PickerItem(b.id, b.name)];
        }
      case FieldType.model:
        final brand = directory?.brand('${widget.attributes[field.dependsOn] ?? ''}');
        if (brand != null && brand.models.isNotEmpty) {
          items = [for (final m in brand.models) PickerItem(m.id, m.name)];
          if (brand.models.any((m) => !m.isVerified)) note = l10n.modelsUnverifiedNote;
        }
      case FieldType.variant:
        final model = directory?.model('${widget.attributes[field.dependsOn] ?? ''}');
        final variants = model?.variantsOf(field.key) ?? const [];
        if (variants.isNotEmpty) {
          items = [
            for (final v in variants)
              PickerItem(v.value, field.unit == null ? v.value : '${v.value} ${formatter.unit(field.unit)}',
                  subtitle: l10n.verifiedSource(v.source.sourceType)),
          ];
        }
      default:
        break;
    }

    // No directory data: free text (catalog manual_fallback), clearly marked.
    if (items.isEmpty) {
      final numeric = field.type == FieldType.variant && field.unit == 'GB';
      final helper = switch (field.type) {
        FieldType.variant => l10n.variantNotVerified,
        FieldType.model when directory != null => l10n.modelFreeText,
        _ => directoryNote(context, ref, field),
      };
      return DaryobTextField(
        controller: _text,
        label: _label,
        helperText: helper,
        errorText: widget.errorText,
        keyboardType: numeric ? TextInputType.number : TextInputType.text,
        inputFormatters: numeric ? [FilteringTextInputFormatter.digitsOnly] : null,
        suffix: numeric
            ? Padding(padding: const EdgeInsets.all(DaryobSpacing.md), child: Text(formatter.unit('GB')))
            : null,
        onChanged: (v) {
          final t = v.trim();
          if (t.isEmpty) return widget.onChanged(null);
          widget.onChanged(numeric ? int.tryParse(t) ?? t : t);
        },
      );
    }

    final value = _value;
    final display = value == null ? null : formatter.directoryValue(field, value);
    final unlisted = value != null && !items.any((i) => i.id == '$value');
    return _Labeled(
      label: _label,
      error: widget.errorText,
      child: Material(
        color: context.colors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: DaryobRadius.inputAll,
          side: BorderSide(
            color: widget.errorText != null ? context.colors.error : context.palette.border,
          ),
        ),
        child: ListTile(
          shape: const RoundedRectangleBorder(borderRadius: DaryobRadius.inputAll),
          title: Text(
            display ?? l10n.choose,
            style: display == null
                ? context.text.bodyLarge?.copyWith(color: context.palette.textSecondary)
                : context.text.bodyLarge,
          ),
          subtitle: unlisted ? Text(l10n.notInCatalog) : null,
          trailing: value == null
              ? const Icon(Icons.expand_more_rounded)
              : IconButton(
                  tooltip: l10n.clear,
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => widget.onChanged(null),
                ),
          onTap: () async {
            final picked = await showDirectoryPicker(
              context,
              title: field.label.of(context),
              items: items,
              selectedId: value?.toString(),
              note: note,
            );
            if (picked != null) {
              final v = picked.value;
              widget.onChanged(field.type == FieldType.variant && field.unit == 'GB' ? int.tryParse(v) ?? v : v);
            }
          },
        ),
      ),
    );
  }

  /// A point on the map from the phone's position (no map view yet).
  Widget _geoPointField(FieldSchema field) {
    final l10n = context.l10n;
    final point = parseGeoPoint(widget.attributes[field.key]);
    return _Labeled(
      label: _label,
      error: widget.errorText,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (point != null)
            Row(
              children: [
                Icon(Icons.place_rounded, size: 18, color: context.colors.primary),
                const SizedBox(width: DaryobSpacing.xs),
                Expanded(child: Text(l10n.mapPinSaved, style: context.text.bodyMedium)),
                TextButton(
                  onPressed: () => launchUrl(mapLink(point), mode: LaunchMode.externalApplication),
                  child: Text(l10n.showOnMap),
                ),
                IconButton(
                  tooltip: l10n.delete,
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => widget.onChanged(null),
                ),
              ],
            )
          else
            OutlinedButton.icon(
              onPressed: _pinBusy ? null : () => _pinHere(field),
              icon: _pinBusy
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.my_location_rounded),
              label: Text(l10n.mapPinHere),
            ),
          const SizedBox(height: DaryobSpacing.xs),
          Text(l10n.mapPinHint, style: context.text.bodySmall),
        ],
      ),
    );
  }

  bool _pinBusy = false;

  Future<void> _pinHere(FieldSchema field) async {
    final l10n = context.l10n;
    setState(() => _pinBusy = true);
    try {
      final point = await DeviceLocation.current(precise: true);
      widget.onChanged(formatGeoPoint(point));
    } on LocationException catch (e) {
      if (mounted) DaryobToast.show(context, locationProblemText(l10n, e.problem));
    } finally {
      if (mounted) setState(() => _pinBusy = false);
    }
  }

  Widget _districtField(FieldSchema field) {
    final regions = ref.watch(regionDirectoryProvider);
    final parent = widget.regionId;
    final children = parent == null ? const <Region>[] : regions.childrenOf(parent);
    if (children.isEmpty) return const SizedBox.shrink();
    return _Labeled(
      label: _label,
      error: widget.errorText,
      child: Wrap(
        spacing: DaryobSpacing.sm,
        runSpacing: DaryobSpacing.sm,
        children: [
          for (final r in children)
            ChoiceChip(
              label: Text(r.name.of(context)),
              selected: _value == r.id,
              onSelected: (on) => widget.onChanged(on ? r.id : null),
            ),
        ],
      ),
    );
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
          Text(error!, style: context.text.bodySmall?.copyWith(color: context.colors.error)),
        ],
      ],
    );
  }
}
