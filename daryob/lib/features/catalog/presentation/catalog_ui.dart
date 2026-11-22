import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/models/category.dart';
import '../../../shared/models/category_schema.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/providers/core_providers.dart';
import '../application/attribute_formatter.dart';
import '../application/catalog_providers.dart';

/// Formatter in the current language.
AttributeFormatter attributeFormatter(BuildContext context, WidgetRef ref) {
  final l10n = context.l10n;
  return AttributeFormatter(
    catalog: ref.watch(catalogProvider),
    languageCode: context.languageCode,
    regions: ref.watch(regionDirectoryProvider),
    yes: l10n.yes,
    no: l10n.no,
  );
}

/// Price line for cards and the listing page, following the catalog:
/// free items, salary for jobs, "/month" or "/day" for rent.
String listingPriceText(BuildContext context, WidgetRef ref, Listing listing) {
  final l10n = context.l10n;
  final category = ref.watch(categoryRegistryProvider).byId(listing.categoryId);
  final schema = ref.watch(schemaRegistryProvider).schemaFor(listing.schemaId);
  final formatter = attributeFormatter(context, ref);
  if (schema.priceMode == PriceMode.none) {
    return formatter.salary(listing.attributes) ?? l10n.salaryNotSpecified;
  }
  final base = priceLabel(
    l10n,
    context.languageCode,
    price: listing.price,
    currency: listing.currency,
    isFreeCategory: category?.priceMode == PriceMode.free || schema.priceMode == PriceMode.free,
  );
  if (listing.price == null || listing.price == 0) return base;
  return switch (formatter.priceUnit(listing.attributes, schema: schema)) {
    PriceUnit.perMonth => '$base ${l10n.perMonth}',
    PriceUnit.perDay => '$base ${l10n.perDay}',
    PriceUnit.item => base,
  };
}

/// One entry of a directory picker.
class PickerItem {
  const PickerItem(this.id, this.label, {this.subtitle});
  final String id;
  final String label;
  final String? subtitle;
}

/// Result of [showDirectoryPicker]: an id from the list, or the seller's own
/// text when the item is not listed (catalog `manual_fallback`).
class PickerResult {
  const PickerResult.item(String this.id) : text = null;
  const PickerResult.other(String this.text) : id = null;
  final String? id;
  final String? text;

  String get value => id ?? text!;
}

/// Searchable list with an "Other / not listed" entry.
Future<PickerResult?> showDirectoryPicker(
  BuildContext context, {
  required String title,
  required List<PickerItem> items,
  String? selectedId,
  String? note,
}) {
  return showModalBottomSheet<PickerResult>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.8,
      maxChildSize: 0.95,
      builder: (context, scroll) => _DirectoryPicker(
        title: title,
        items: items,
        selectedId: selectedId,
        note: note,
        scroll: scroll,
      ),
    ),
  );
}

class _DirectoryPicker extends StatefulWidget {
  const _DirectoryPicker({
    required this.title,
    required this.items,
    required this.selectedId,
    required this.note,
    required this.scroll,
  });

  final String title;
  final List<PickerItem> items;
  final String? selectedId;
  final String? note;
  final ScrollController scroll;

  @override
  State<_DirectoryPicker> createState() => _DirectoryPickerState();
}

class _DirectoryPickerState extends State<_DirectoryPicker> {
  final _query = TextEditingController();
  bool _otherMode = false;
  final _other = TextEditingController();

  @override
  void dispose() {
    _query.dispose();
    _other.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final q = _query.text.trim().toLowerCase();
    final items = q.isEmpty
        ? widget.items
        : widget.items.where((i) => i.label.toLowerCase().contains(q)).toList();

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(DaryobSpacing.page, 0, DaryobSpacing.page, DaryobSpacing.sm),
            child: Text(widget.title, style: context.text.titleLarge),
          ),
          if (!_otherMode)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
              child: TextField(
                controller: _query,
                autofocus: widget.items.length > 12,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  hintText: l10n.pickerSearchHint,
                  prefixIcon: const Icon(Icons.search_rounded),
                ),
              ),
            ),
          if (widget.note != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(DaryobSpacing.page, DaryobSpacing.sm, DaryobSpacing.page, 0),
              child: Text(widget.note!, style: context.text.bodySmall),
            ),
          const SizedBox(height: DaryobSpacing.sm),
          Expanded(
            child: _otherMode
                ? ListView(
                    controller: widget.scroll,
                    padding: const EdgeInsets.all(DaryobSpacing.page),
                    children: [
                      TextField(
                        controller: _other,
                        autofocus: true,
                        textCapitalization: TextCapitalization.sentences,
                        decoration: InputDecoration(hintText: l10n.pickerOtherHint),
                      ),
                      const SizedBox(height: DaryobSpacing.sm),
                      Text(l10n.pickerOtherNote, style: context.text.bodySmall),
                      const SizedBox(height: DaryobSpacing.lg),
                      FilledButton(
                        onPressed: () {
                          final text = _other.text.trim();
                          if (text.isEmpty) return;
                          Navigator.of(context).pop(PickerResult.other(text));
                        },
                        child: Text(l10n.done),
                      ),
                    ],
                  )
                : ListView.builder(
                    controller: widget.scroll,
                    itemCount: items.length + 1,
                    itemBuilder: (context, i) {
                      if (i == items.length) {
                        return ListTile(
                          leading: const Icon(Icons.edit_outlined),
                          title: Text(l10n.pickerOther),
                          onTap: () => setState(() => _otherMode = true),
                        );
                      }
                      final item = items[i];
                      return ListTile(
                        title: Text(item.label),
                        subtitle: item.subtitle == null ? null : Text(item.subtitle!),
                        trailing: item.id == widget.selectedId ? const Icon(Icons.check_rounded) : null,
                        onTap: () => Navigator.of(context).pop(PickerResult.item(item.id)),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

/// Text explaining why a directory field accepts free text.
String? directoryNote(BuildContext context, WidgetRef ref, FieldSchema field) {
  final l10n = context.l10n;
  if (field.type == FieldType.occupation || field.type == FieldType.species || field.type == FieldType.family) {
    return l10n.catalogNotLoaded;
  }
  if (field.directory == null) return l10n.catalogNotLoaded;
  return null;
}

/// Directory id for a category's brand fields (for the "unverified" note).
String? directoryOf(CategoryDefinition? category, CategorySchema schema) {
  for (final f in schema.fields) {
    if (f.type == FieldType.brand) return f.directory;
  }
  return null;
}
