import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../../core/utils/validators.dart';
import '../../features/catalog/application/catalog_providers.dart';
import '../../features/catalog/presentation/catalog_ui.dart';
import '../../features/categories/data/tajikistan_regions.dart';
import '../../features/listings/domain/listing_query.dart';
import '../models/category.dart';
import '../models/category_schema.dart';
import '../models/localized_text.dart';
import '../providers/core_providers.dart';
import 'buttons.dart';
import 'daryob_text_field.dart';
import 'location_selector.dart';

/// Filter bottom sheet. Returns the new query, or null if dismissed.
///
/// Characteristic filters are generated from the chosen (sub)category's
/// catalog schema (`filters` in the catalog file), so every filterable field
/// a seller fills in can be searched — no per-category screens.
Future<ListingQuery?> showFilterSheet(
  BuildContext context, {
  required ListingQuery query,
  bool lockCategory = false,
}) {
  return showModalBottomSheet<ListingQuery>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => DaryobFilterSheet(query: query, lockCategory: lockCategory),
  );
}

class DaryobFilterSheet extends ConsumerStatefulWidget {
  const DaryobFilterSheet({super.key, required this.query, this.lockCategory = false});

  final ListingQuery query;
  final bool lockCategory;

  @override
  ConsumerState<DaryobFilterSheet> createState() => _DaryobFilterSheetState();
}

class _DaryobFilterSheetState extends ConsumerState<DaryobFilterSheet> {
  late ListingQuery _query = widget.query;
  late final _min = TextEditingController(text: _fmt(widget.query.minPrice));
  late final _max = TextEditingController(text: _fmt(widget.query.maxPrice));

  /// Text controllers for range / contains filters, by field key.
  final Map<String, (TextEditingController, TextEditingController)> _ranges = {};
  final Map<String, TextEditingController> _texts = {};

  static String _fmt(num? v) => v == null ? '' : '$v';

  @override
  void dispose() {
    _min.dispose();
    _max.dispose();
    for (final (a, b) in _ranges.values) {
      a.dispose();
      b.dispose();
    }
    for (final c in _texts.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _setFilter(String key, AttributeFilter? filter) {
    final next = Map.of(_query.attributeFilters);
    filter == null ? next.remove(key) : next[key] = filter;
    setState(() => _query = _query.copyWith(attributeFilters: next));
  }

  void _apply() {
    final min = Validators.parsePrice(_min.text);
    final max = Validators.parsePrice(_max.text);
    final (lo, hi) = (min != null && max != null && min > max) ? (max, min) : (min, max);
    Navigator.of(context).pop(
      _query.copyWith(
        minPrice: lo,
        clearMinPrice: lo == null,
        maxPrice: hi,
        clearMaxPrice: hi == null,
      ),
    );
  }

  void _resetAll() {
    _min.clear();
    _max.clear();
    for (final (a, b) in _ranges.values) {
      a.clear();
      b.clear();
    }
    for (final c in _texts.values) {
      c.clear();
    }
    setState(() {
      _query = ListingQuery(
        text: _query.text,
        regionId: _query.regionId,
        categoryId: widget.lockCategory ? _query.categoryId : null,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final categories = ref.watch(categoryRegistryProvider);
    final schemas = ref.watch(schemaRegistryProvider);
    final category = categories.byId(_query.categoryId);
    final schema = category == null ? null : schemas.schemaFor(category.filterSchemaId);
    final top = category == null ? null : categories.pathTo(category.id).first;
    final subcategories = top == null ? const <CategoryDefinition>[] : categories.childrenOf(top.id);
    final priceHidden = schema != null &&
        (schema.priceMode == PriceMode.none || schema.priceMode == PriceMode.free);

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.9),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(DaryobSpacing.page, 0, DaryobSpacing.sm, DaryobSpacing.sm),
              child: Row(
                children: [
                  Expanded(child: Text(l10n.filters, style: context.text.titleLarge)),
                  TextButton(onPressed: _resetAll, child: Text(l10n.reset)),
                ],
              ),
            ),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
                children: [
                  if (!widget.lockCategory) ...[
                    _Label(l10n.category),
                    _Picker(
                      value: top?.name.of(context) ?? l10n.allCategories,
                      onTap: () async {
                        final picked = await showModalBottomSheet<String>(
                          context: context,
                          isScrollControlled: true,
                          useSafeArea: true,
                          builder: (context) => ListView(
                            shrinkWrap: true,
                            children: [
                              ListTile(
                                title: Text(l10n.allCategories),
                                onTap: () => Navigator.of(context).pop(''),
                              ),
                              for (final c in categories.topLevel)
                                ListTile(
                                  title: Text(c.name.of(context)),
                                  trailing: c.id == top?.id ? const Icon(Icons.check_rounded) : null,
                                  onTap: () => Navigator.of(context).pop(c.id),
                                ),
                            ],
                          ),
                        );
                        if (picked == null) return;
                        setState(() {
                          _query = picked.isEmpty
                              ? _query.copyWith(clearCategory: true, attributeFilters: const {})
                              : _query.copyWith(categoryId: picked, attributeFilters: const {});
                        });
                      },
                    ),
                  ],
                  if (subcategories.isNotEmpty) ...[
                    _Label(l10n.subcategory),
                    Wrap(
                      spacing: DaryobSpacing.sm,
                      runSpacing: DaryobSpacing.sm,
                      children: [
                        ChoiceChip(
                          label: Text(l10n.all),
                          selected: category?.id == top?.id,
                          onSelected: (_) => setState(
                            () => _query = _query.copyWith(categoryId: top!.id, attributeFilters: const {}),
                          ),
                        ),
                        for (final c in subcategories)
                          ChoiceChip(
                            label: Text(c.name.of(context)),
                            selected: category?.id == c.id,
                            onSelected: (_) => setState(
                              () => _query = _query.copyWith(categoryId: c.id, attributeFilters: const {}),
                            ),
                          ),
                      ],
                    ),
                  ],
                  _Label(l10n.location),
                  _Picker(
                    value: regionPathLabel(
                      context,
                      ref.watch(regionDirectoryProvider),
                      _query.regionId ?? RegionIds.country,
                    ),
                    onTap: () async {
                      final picked = await showLocationPicker(context, selectedId: _query.regionId);
                      if (picked != null) setState(() => _query = _query.copyWith(regionId: picked));
                    },
                  ),
                  if (!priceHidden) ...[
                    _Label('${l10n.price}, ${attributeFormatter(context, ref).unit('TJS')}'),
                    _RangeInputs(from: _min, to: _max),
                  ],
                  if (schema != null)
                    for (final field in schema.filterFields)
                      ..._fieldFilter(schema, field),
                  if (schema == null) ...[
                    const SizedBox(height: DaryobSpacing.lg),
                    Text(l10n.chooseCategoryForFilters, style: context.text.bodySmall),
                  ],
                  _Label(l10n.sortBy),
                  RadioGroup<ListingSort>(
                    groupValue: _query.sort,
                    onChanged: (v) => setState(() => _query = _query.copyWith(sort: v)),
                    child: Column(
                      children: [
                        for (final sort in ListingSort.values)
                          RadioListTile<ListingSort>(
                            value: sort,
                            contentPadding: EdgeInsets.zero,
                            title: Text(sortLabel(l10n, sort)),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: DaryobSpacing.lg),
                ],
              ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(DaryobSpacing.page, DaryobSpacing.sm, DaryobSpacing.page, DaryobSpacing.md),
                child: DaryobPrimaryButton(label: l10n.showResults, onPressed: _apply),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Widgets for one filterable field, chosen by its type.
  List<Widget> _fieldFilter(CategorySchema schema, FieldSchema field) {
    final label = field.label.of(context);
    final current = _query.attributeFilters[field.key];
    final formatter = attributeFormatter(context, ref);

    switch (field.type) {
      case FieldType.singleSelect:
      case FieldType.multiSelect:
      case FieldType.color:
        final selected = current is AnyOfFilter
            ? current.values
            : current is EqualsFilter
            ? {current.value}
            : <String>{};
        return [
          _Label(label),
          Wrap(
            spacing: DaryobSpacing.sm,
            runSpacing: DaryobSpacing.sm,
            children: [
              for (final option in schema.optionsFor(field))
                FilterChip(
                  label: Text(option.label.of(context)),
                  selected: selected.contains(option.value),
                  onSelected: (on) {
                    final next = {...selected};
                    on ? next.add(option.value) : next.remove(option.value);
                    _setFilter(field.key, next.isEmpty ? null : AnyOfFilter(next));
                  },
                ),
            ],
          ),
        ];
      case FieldType.boolean:
        return [
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(label),
            value: current is IsTrueFilter,
            onChanged: (on) => _setFilter(field.key, on ? const IsTrueFilter() : null),
          ),
        ];
      case FieldType.integer:
      case FieldType.number:
      case FieldType.money:
        final (from, to) = _ranges.putIfAbsent(field.key, () {
          final r = current is RangeFilter ? current : null;
          return (TextEditingController(text: _fmt(r?.min)), TextEditingController(text: _fmt(r?.max)));
        });
        void update() {
          num? parse(String t) => num.tryParse(t.replaceAll(RegExp(r'[\s ]'), '').replaceAll(',', '.'));
          final lo = parse(from.text);
          final hi = parse(to.text);
          _setFilter(field.key, lo == null && hi == null ? null : RangeFilter(min: lo, max: hi));
        }

        final unit = field.type == FieldType.money ? formatter.unit('TJS') : formatter.unit(field.unit);
        return [
          _Label(unit.isEmpty ? label : '$label, $unit'),
          _RangeInputs(from: from, to: to, onChanged: update, decimal: field.type == FieldType.number),
        ];
      case FieldType.brand:
      case FieldType.model:
        final directory = ref.watch(catalogProvider).directory(field.directory);
        List<PickerItem> items = const [];
        if (directory != null && field.type == FieldType.brand) {
          items = [for (final b in directory.brands) PickerItem(b.id, b.name)];
        } else if (directory != null) {
          final brandFilter = _query.attributeFilters[field.dependsOn];
          final brand = brandFilter is EqualsFilter ? directory.brand(brandFilter.value) : null;
          if (brand == null) return const [];
          items = [for (final m in brand.models) PickerItem(m.id, m.name)];
        }
        if (items.isEmpty) return _containsFilter(field, label);
        final value = current is EqualsFilter ? current.value : null;
        return [
          _Label(label),
          _Picker(
            value: value == null ? context.l10n.any : formatter.directoryValue(field, value),
            onTap: () async {
              final picked = await showDirectoryPicker(context, title: label, items: items, selectedId: value);
              if (picked == null) return;
              final next = Map.of(_query.attributeFilters)..[field.key] = EqualsFilter(picked.value);
              // A new brand invalidates the model filter.
              for (final f in schema.fields) {
                if (f.dependsOn == field.key) next.remove(f.key);
              }
              setState(() => _query = _query.copyWith(attributeFilters: next));
            },
            onClear: value == null ? null : () => _setFilter(field.key, null),
          ),
        ];
      case FieldType.text:
      case FieldType.multilineText:
      case FieldType.size:
      case FieldType.tags:
      case FieldType.variant:
      case FieldType.family:
      case FieldType.occupation:
      case FieldType.species:
        return _containsFilter(field, label);
      case FieldType.locationChild:
      case FieldType.geoPoint:
      case FieldType.numberRange:
        return const []; // Location is filtered by the region picker.
    }
  }

  List<Widget> _containsFilter(FieldSchema field, String label) {
    final current = _query.attributeFilters[field.key];
    final controller = _texts.putIfAbsent(
      field.key,
      () => TextEditingController(text: current is ContainsFilter ? current.text : ''),
    );
    return [
      _Label(label),
      DaryobTextField(
        controller: controller,
        hint: context.l10n.containsHint,
        onChanged: (v) => _setFilter(field.key, v.trim().isEmpty ? null : ContainsFilter(v.trim())),
      ),
    ];
  }
}

class _RangeInputs extends StatelessWidget {
  const _RangeInputs({required this.from, required this.to, this.onChanged, this.decimal = false});
  final TextEditingController from;
  final TextEditingController to;
  final VoidCallback? onChanged;
  final bool decimal;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final formatters = decimal
        ? [FilteringTextInputFormatter.allow(RegExp(r'[\d.,]'))]
        : [FilteringTextInputFormatter.digitsOnly];
    return Row(
      children: [
        Expanded(
          child: DaryobTextField(
            controller: from,
            hint: l10n.priceFrom,
            keyboardType: TextInputType.numberWithOptions(decimal: decimal),
            inputFormatters: formatters,
            onChanged: (_) => onChanged?.call(),
          ),
        ),
        const SizedBox(width: DaryobSpacing.md),
        Expanded(
          child: DaryobTextField(
            controller: to,
            hint: l10n.priceTo,
            keyboardType: TextInputType.numberWithOptions(decimal: decimal),
            inputFormatters: formatters,
            onChanged: (_) => onChanged?.call(),
          ),
        ),
      ],
    );
  }
}

class _Label extends StatelessWidget {
  const _Label(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: DaryobSpacing.lg, bottom: DaryobSpacing.sm),
    child: Text(text, style: context.text.labelMedium),
  );
}

class _Picker extends StatelessWidget {
  const _Picker({required this.value, required this.onTap, this.onClear});
  final String value;
  final VoidCallback onTap;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: context.colors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: DaryobRadius.inputAll,
        side: BorderSide(color: context.palette.border),
      ),
      child: InkWell(
        borderRadius: DaryobRadius.inputAll,
        onTap: onTap,
        child: SizedBox(
          height: DaryobSizes.inputHeight,
          child: Row(
            children: [
              const SizedBox(width: DaryobSpacing.lg),
              Expanded(child: Text(value, overflow: TextOverflow.ellipsis, style: context.text.bodyLarge)),
              if (onClear != null)
                IconButton(
                  tooltip: context.l10n.clear,
                  onPressed: onClear,
                  icon: const Icon(Icons.close_rounded),
                )
              else ...[
                const Icon(Icons.expand_more_rounded),
                const SizedBox(width: DaryobSpacing.md),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
