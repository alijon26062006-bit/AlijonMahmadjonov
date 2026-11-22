import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../../core/utils/validators.dart';
import '../../features/categories/data/tajikistan_regions.dart';
import '../../features/listings/domain/listing_query.dart';
import '../models/category_schema.dart';
import '../models/localized_text.dart';
import '../providers/core_providers.dart';
import 'buttons.dart';
import 'daryob_text_field.dart';
import 'location_selector.dart';

/// Filter bottom sheet. Returns the new query, or null if dismissed.
/// Category-specific filters come from the category's filter schema, so
/// future category modules get their filters here automatically.
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
  const DaryobFilterSheet({
    super.key,
    required this.query,
    this.lockCategory = false,
  });

  final ListingQuery query;
  final bool lockCategory;

  @override
  ConsumerState<DaryobFilterSheet> createState() => _DaryobFilterSheetState();
}

class _DaryobFilterSheetState extends ConsumerState<DaryobFilterSheet> {
  late ListingQuery _query = widget.query;
  late final _min = TextEditingController(text: _fmt(widget.query.minPrice));
  late final _max = TextEditingController(text: _fmt(widget.query.maxPrice));

  static String _fmt(int? v) => v == null ? '' : '$v';

  @override
  void dispose() {
    _min.dispose();
    _max.dispose();
    super.dispose();
  }

  void _apply() {
    final min = Validators.parsePrice(_min.text);
    final max = Validators.parsePrice(_max.text);
    // Swap if entered the wrong way round.
    final (lo, hi) = (min != null && max != null && min > max)
        ? (max, min)
        : (min, max);
    Navigator.of(context).pop(
      _query.copyWith(
        minPrice: lo,
        clearMinPrice: lo == null,
        maxPrice: hi,
        clearMaxPrice: hi == null,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final categories = ref.watch(categoryRegistryProvider);
    final schemas = ref.watch(schemaRegistryProvider);
    final category = categories.byId(_query.categoryId);
    final filterFields = category == null
        ? const <FieldSchema>[]
        : schemas.schemaFor(category.filterSchemaId).filterFields;

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * 0.88,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                DaryobSpacing.page,
                0,
                DaryobSpacing.sm,
                DaryobSpacing.sm,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(l10n.filters, style: context.text.titleLarge),
                  ),
                  TextButton(
                    onPressed: () {
                      _min.clear();
                      _max.clear();
                      setState(() {
                        _query = ListingQuery(
                          text: _query.text,
                          regionId: _query.regionId,
                          categoryId: widget.lockCategory
                              ? _query.categoryId
                              : null,
                        );
                      });
                    },
                    child: Text(l10n.reset),
                  ),
                ],
              ),
            ),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                padding: const EdgeInsets.symmetric(
                  horizontal: DaryobSpacing.page,
                ),
                children: [
                  if (!widget.lockCategory) ...[
                    _Label(l10n.category),
                    _Picker(
                      value: category?.name.of(context) ?? l10n.allCategories,
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
                                  trailing: c.id == _query.categoryId
                                      ? const Icon(Icons.check_rounded)
                                      : null,
                                  onTap: () => Navigator.of(context).pop(c.id),
                                ),
                            ],
                          ),
                        );
                        if (picked == null) return;
                        setState(() {
                          _query = picked.isEmpty
                              ? _query.copyWith(
                                  clearCategory: true,
                                  attributeFilters: const {},
                                )
                              : _query.copyWith(
                                  categoryId: picked,
                                  attributeFilters: const {},
                                );
                        });
                      },
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
                      final picked = await showLocationPicker(
                        context,
                        selectedId: _query.regionId,
                      );
                      if (picked != null) {
                        setState(
                          () => _query = _query.copyWith(regionId: picked),
                        );
                      }
                    },
                  ),
                  _Label(l10n.priceRange),
                  Row(
                    children: [
                      Expanded(
                        child: DaryobTextField(
                          controller: _min,
                          hint: l10n.priceFrom,
                          keyboardType: TextInputType.number,
                          inputFormatters: [
                            FilteringTextInputFormatter.digitsOnly,
                          ],
                        ),
                      ),
                      const SizedBox(width: DaryobSpacing.md),
                      Expanded(
                        child: DaryobTextField(
                          controller: _max,
                          hint: l10n.priceTo,
                          keyboardType: TextInputType.number,
                          inputFormatters: [
                            FilteringTextInputFormatter.digitsOnly,
                          ],
                        ),
                      ),
                    ],
                  ),
                  for (final field in filterFields)
                    if (field.type == FieldType.singleSelect) ...[
                      _Label(field.label.of(context)),
                      Wrap(
                        spacing: DaryobSpacing.sm,
                        runSpacing: DaryobSpacing.sm,
                        children: [
                          for (final option in field.options)
                            FilterChip(
                              label: Text(option.label.of(context)),
                              selected:
                                  _query.attributeFilters[field.key] ==
                                  option.value,
                              onSelected: (on) {
                                final next = Map.of(_query.attributeFilters);
                                on
                                    ? next[field.key] = option.value
                                    : next.remove(field.key);
                                setState(
                                  () => _query = _query.copyWith(
                                    attributeFilters: next,
                                  ),
                                );
                              },
                            ),
                        ],
                      ),
                    ],
                  _Label(l10n.sortBy),
                  RadioGroup<ListingSort>(
                    groupValue: _query.sort,
                    onChanged: (v) =>
                        setState(() => _query = _query.copyWith(sort: v)),
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
                padding: const EdgeInsets.fromLTRB(
                  DaryobSpacing.page,
                  DaryobSpacing.sm,
                  DaryobSpacing.page,
                  DaryobSpacing.md,
                ),
                child: DaryobPrimaryButton(
                  label: l10n.showResults,
                  onPressed: _apply,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Label extends StatelessWidget {
  const _Label(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(
      top: DaryobSpacing.lg,
      bottom: DaryobSpacing.sm,
    ),
    child: Text(text, style: context.text.labelMedium),
  );
}

class _Picker extends StatelessWidget {
  const _Picker({required this.value, required this.onTap});
  final String value;
  final VoidCallback onTap;

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
              Expanded(
                child: Text(
                  value,
                  overflow: TextOverflow.ellipsis,
                  style: context.text.bodyLarge,
                ),
              ),
              const Icon(Icons.expand_more_rounded),
              const SizedBox(width: DaryobSpacing.md),
            ],
          ),
        ),
      ),
    );
  }
}
