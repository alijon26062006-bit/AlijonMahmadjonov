import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../../../app/localization/l10n.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../core/utils/formatters.dart';
import '../../../../core/utils/validators.dart';
import '../../../../shared/models/category.dart';
import '../../../../shared/models/category_schema.dart';
import '../../../../shared/models/listing.dart';
import '../../../../shared/models/localized_text.dart';
import '../../../../shared/models/money.dart';
import '../../../../shared/providers/core_providers.dart';
import '../../../../shared/widgets/category_visuals.dart';
import '../../../../shared/widgets/daryob_text_field.dart';
import '../../../../shared/widgets/listing_image.dart';
import '../../../../shared/widgets/location_selector.dart';
import '../../../../shared/widgets/photo_picker.dart';
import '../../../../shared/widgets/states.dart';
import '../../../catalog/presentation/catalog_ui.dart';
import '../../domain/draft_validator.dart';
import '../../domain/listing_draft.dart';
import 'schema_field_input.dart';

typedef DraftUpdate = void Function(ListingDraft Function(ListingDraft) update);

String? _err(
  BuildContext context,
  Map<String, String> errors,
  String key, {
  int? min,
  int? max,
  String? other,
}) => validationMessage(context.l10n, errors[key], min: min, max: max, other: other);

class _ChoiceTile extends StatelessWidget {
  const _ChoiceTile({
    required this.title,
    required this.selected,
    required this.onTap,
    this.subtitle,
    this.leading,
  });

  final String title;
  final String? subtitle;
  final Widget? leading;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.only(bottom: DaryobSpacing.sm),
      child: Material(
        color: selected ? context.palette.limeSoft : context.colors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: DaryobRadius.cardAll,
          side: BorderSide(
            color: selected
                ? (isDark ? DaryobColors.lime : DaryobColors.navy)
                : context.palette.border,
            width: selected ? 2 : 1,
          ),
        ),
        child: ListTile(
          shape: const RoundedRectangleBorder(borderRadius: DaryobRadius.cardAll),
          leading: leading,
          title: Text(title),
          subtitle: subtitle == null || subtitle!.isEmpty
              ? null
              : Text(subtitle!, maxLines: 1, overflow: TextOverflow.ellipsis),
          trailing: selected
              ? const Icon(Icons.check_circle_rounded)
              : const Icon(Icons.chevron_right_rounded),
          onTap: onTap,
        ),
      ),
    );
  }
}

// ── Step 1: category ────────────────────────────────────────────────────────

class CategoryStep extends ConsumerWidget {
  const CategoryStep({
    super.key,
    required this.draft,
    required this.onPick,
    required this.errors,
  });

  final ListingDraft draft;
  final ValueChanged<String> onPick;
  final Map<String, String> errors;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final registry = ref.watch(categoryRegistryProvider);
    final selectedTop = registry.pathTo(draft.categoryId ?? '').firstOrNull?.id;
    final error = _err(context, errors, DraftField.category);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (error != null) ...[
          DaryobNotice(message: context.l10n.chooseCategoryError, tone: NoticeTone.warning),
          const SizedBox(height: DaryobSpacing.md),
        ],
        for (final c in registry.topLevel)
          _ChoiceTile(
            leading: DaryobCategoryIcon(icon: c.icon, size: 40),
            title: c.name.of(context),
            subtitle: c.description.of(context),
            selected: selectedTop == c.id,
            onTap: () => onPick(c.id),
          ),
      ],
    );
  }
}

// ── Step 2: subcategory ─────────────────────────────────────────────────────

class SubcategoryStep extends ConsumerWidget {
  const SubcategoryStep({
    super.key,
    required this.draft,
    required this.onPick,
    required this.errors,
  });

  final ListingDraft draft;
  final ValueChanged<String> onPick;
  final Map<String, String> errors;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final registry = ref.watch(categoryRegistryProvider);
    final path = registry.pathTo(draft.categoryId ?? '');
    final top = path.firstOrNull;
    if (top == null) return const SizedBox.shrink();
    final error = _err(context, errors, DraftField.subcategory);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(top.name.of(context), style: context.text.titleMedium),
        const SizedBox(height: DaryobSpacing.md),
        if (error != null) ...[
          DaryobNotice(message: context.l10n.chooseSubcategoryError, tone: NoticeTone.warning),
          const SizedBox(height: DaryobSpacing.md),
        ],
        for (final c in registry.childrenOf(top.id))
          _ChoiceTile(
            title: c.name.of(context),
            selected: draft.categoryId == c.id,
            onTap: () => onPick(c.id),
          ),
      ],
    );
  }
}

// ── Step 3: characteristics ─────────────────────────────────────────────────

class DetailsStep extends ConsumerWidget {
  const DetailsStep({
    super.key,
    required this.draft,
    required this.update,
    required this.errors,
    this.fieldKeys,
  });

  final ListingDraft draft;
  final DraftUpdate update;
  final Map<String, String> errors;

  /// Limit to some fields (a schema `extraSteps` page). Null = all detail
  /// fields.
  final List<String>? fieldKeys;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final validator = ref.watch(draftValidatorProvider);
    final schema = validator.schemaOf(draft);
    if (schema == null) return const SizedBox.shrink();
    final fields = fieldKeys == null
        ? schema.detailFields
        : [for (final k in fieldKeys!) ?schema.field(k)];
    final visible = fields.where((f) => f.isVisible(draft.attributes)).toList();

    if (visible.isEmpty) {
      return DaryobNotice(message: context.l10n.noCharacteristics);
    }

    final hasDirectory = visible.any((f) => directoryFieldTypes.contains(f.type));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (hasDirectory) ...[
          DaryobNotice(message: context.l10n.catalogStarterNotice, icon: Icons.info_outline_rounded),
          const SizedBox(height: DaryobSpacing.md),
        ],
        for (final field in visible)
          Padding(
            padding: const EdgeInsets.only(bottom: DaryobSpacing.lg),
            child: SchemaFieldInput(
              key: ValueKey('attr-${draft.id}-${draft.categoryId}-${field.key}-${_dependencyKey(field)}'),
              schema: schema,
              field: field,
              attributes: draft.attributes,
              errorText: _err(
                context,
                errors,
                DraftField.attribute(field.key),
                other: _otherLabel(context, schema, field.key),
              ),
              onChanged: (v) => update((d) => d.copyWith(attributes: _setValue(schema, d.attributes, field.key, v))),
            ),
          ),
      ],
    );
  }

  /// Rebuild a dependent input when what it depends on changes.
  String _dependencyKey(FieldSchema field) =>
      field.dependsOn == null ? '' : '${draft.attributes[field.dependsOn]}';

  String? _otherLabel(BuildContext context, CategorySchema schema, String key) {
    for (final rule in schema.crossRules) {
      if (rule.field == key) return schema.field(rule.other)?.label.of(context);
    }
    return null;
  }
}

/// Sets a value and clears fields that depend on it (brand → model →
/// variant), since their old values no longer apply.
Map<String, Object?> _setValue(
  CategorySchema schema,
  Map<String, Object?> attributes,
  String key,
  Object? value,
) {
  final next = Map<String, Object?>.of(attributes);
  final changed = next[key] != value;
  next[key] = value;
  if (changed) {
    final queue = [key];
    while (queue.isNotEmpty) {
      final parent = queue.removeLast();
      for (final f in schema.fields) {
        if (f.dependsOn == parent && next.containsKey(f.key)) {
          next.remove(f.key);
          queue.add(f.key);
        }
      }
    }
  }
  return next;
}

// ── Step 4: title, description, price ───────────────────────────────────────

class BasicsStep extends ConsumerStatefulWidget {
  const BasicsStep({
    super.key,
    required this.draft,
    required this.update,
    required this.errors,
  });

  final ListingDraft draft;
  final DraftUpdate update;
  final Map<String, String> errors;

  @override
  ConsumerState<BasicsStep> createState() => _BasicsStepState();
}

class _BasicsStepState extends ConsumerState<BasicsStep> {
  late final _title = TextEditingController(text: widget.draft.title);
  late final _description = TextEditingController(text: widget.draft.description);
  late final _price = TextEditingController(
    text: PriceInputFormatter()
        .formatEditUpdate(TextEditingValue.empty, TextEditingValue(text: widget.draft.priceText))
        .text,
  );

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    _price.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final draft = widget.draft;
    final errors = widget.errors;
    final schema = ref.watch(draftValidatorProvider).schemaOf(draft);
    final priceMode = schema?.priceMode ?? PriceMode.required;
    final formatter = attributeFormatter(context, ref);
    final suggestion = schema == null ? null : formatter.suggestTitle(schema, draft.attributes);
    final perUnit = switch (formatter.priceUnit(draft.attributes, schema: schema)) {
      PriceUnit.perMonth => l10n.perMonth,
      PriceUnit.perDay => l10n.perDay,
      PriceUnit.item => null,
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DaryobTextField(
          controller: _title,
          label: '${l10n.fieldTitle} *',
          hint: l10n.fieldTitleHint,
          maxLength: ListingLimits.titleMax,
          errorText: _err(context, errors, DraftField.title, min: ListingLimits.titleMin, max: ListingLimits.titleMax),
          onChanged: (v) => widget.update((d) => d.copyWith(title: v)),
        ),
        if (suggestion != null && suggestion != draft.title.trim())
          Align(
            alignment: Alignment.centerLeft,
            child: ActionChip(
              avatar: const Icon(Icons.auto_awesome_outlined, size: 18),
              label: Text(l10n.useTitle(suggestion)),
              onPressed: () {
                _title.text = suggestion;
                widget.update((d) => d.copyWith(title: suggestion));
              },
            ),
          ),
        const SizedBox(height: DaryobSpacing.md),
        DaryobTextField(
          controller: _description,
          label: '${l10n.description} *',
          hint: l10n.fieldDescriptionHint,
          maxLines: 7,
          minLines: 4,
          maxLength: ListingLimits.descriptionMax,
          errorText: _err(
            context,
            errors,
            DraftField.description,
            min: ListingLimits.descriptionMin,
            max: ListingLimits.descriptionMax,
          ),
          onChanged: (v) => widget.update((d) => d.copyWith(description: v)),
        ),
        const SizedBox(height: DaryobSpacing.md),
        switch (priceMode) {
          PriceMode.free => DaryobNotice(message: l10n.freeCategoryNotice, icon: Icons.card_giftcard_outlined),
          PriceMode.none => DaryobNotice(message: l10n.salaryInCharacteristics, icon: Icons.payments_outlined),
          _ => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DaryobTextField(
                controller: _price,
                label: [
                  priceMode == PriceMode.required && !draft.isNegotiable ? '${l10n.price} *' : l10n.price,
                  ?perUnit,
                ].join(' '),
                hint: priceMode == PriceMode.optional ? l10n.priceOptionalHint : '0',
                keyboardType: TextInputType.number,
                inputFormatters: [PriceInputFormatter()],
                errorText: _err(context, errors, DraftField.price),
                // TJS is the marketplace currency (catalog `currency`).
                suffix: Padding(
                  padding: const EdgeInsets.all(DaryobSpacing.md),
                  child: Text(formatter.unit('TJS')),
                ),
                onChanged: (v) => widget.update((d) => d.copyWith(priceText: v, currency: Currency.tjs)),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(l10n.negotiable),
                subtitle: Text(l10n.negotiableHint),
                value: draft.isNegotiable,
                onChanged: (v) => widget.update((d) => d.copyWith(isNegotiable: v)),
              ),
            ],
          ),
        },
      ],
    );
  }
}

// ── Step 5: photos ──────────────────────────────────────────────────────────

class PhotosStep extends ConsumerWidget {
  const PhotosStep({
    super.key,
    required this.draft,
    required this.update,
    required this.errors,
  });

  final ListingDraft draft;
  final DraftUpdate update;
  final Map<String, String> errors;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final validator = ref.watch(draftValidatorProvider);
    final category = validator.categoryOf(draft);
    final schema = validator.schemaOf(draft);
    final min = schema?.photosMin ?? 0;
    final max = schema?.photosMax ?? ListingLimits.photosMax;
    final error = _err(context, errors, DraftField.photos, min: min, max: max);
    final l10n = context.l10n;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DaryobNotice(
          message: min > 0 ? '${l10n.photosRequired(min)} ${l10n.photosTip}' : l10n.photosTip,
          icon: Icons.lightbulb_outline_rounded,
        ),
        if (category?.id.startsWith('vehicles') ?? false) ...[
          const SizedBox(height: DaryobSpacing.sm),
          Text(l10n.vehiclePhotoTips, style: context.text.bodySmall),
        ],
        const SizedBox(height: DaryobSpacing.lg),
        DaryobPhotoPicker(
          photos: draft.photos,
          max: max,
          icon: category?.icon ?? CategoryIcon.generic,
          onChanged: (photos) => update((d) => d.copyWith(photos: photos)),
        ),
        if (error != null)
          Text(error, style: context.text.bodySmall?.copyWith(color: context.colors.error)),
      ],
    );
  }
}

// ── Step 6: location ────────────────────────────────────────────────────────

class LocationStep extends ConsumerStatefulWidget {
  const LocationStep({
    super.key,
    required this.draft,
    required this.update,
    required this.errors,
  });

  final ListingDraft draft;
  final DraftUpdate update;
  final Map<String, String> errors;

  @override
  ConsumerState<LocationStep> createState() => _LocationStepState();
}

class _LocationStepState extends ConsumerState<LocationStep> {
  late final _address = TextEditingController(text: widget.draft.addressNote);

  @override
  void dispose() {
    _address.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final directory = ref.watch(regionDirectoryProvider);
    final draft = widget.draft;
    final regionId = draft.regionId;
    final error = _err(context, widget.errors, DraftField.region);
    final schema = ref.watch(draftValidatorProvider).schemaOf(draft);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('${l10n.location} *', style: context.text.labelMedium),
        const SizedBox(height: DaryobSpacing.sm),
        Material(
          color: context.colors.surface,
          shape: RoundedRectangleBorder(
            borderRadius: DaryobRadius.inputAll,
            side: BorderSide(color: error != null ? context.colors.error : context.palette.border),
          ),
          child: ListTile(
            shape: const RoundedRectangleBorder(borderRadius: DaryobRadius.inputAll),
            leading: const Icon(Icons.place_outlined),
            title: Text(regionId == null ? l10n.chooseLocation : regionPathLabel(context, directory, regionId)),
            trailing: const Icon(Icons.expand_more_rounded),
            onTap: () async {
              final picked = await showLocationPicker(context, selectedId: regionId, allowWholeCountry: false);
              if (picked != null) {
                widget.update((d) {
                  // A district chosen for another city no longer applies.
                  final attrs = Map<String, Object?>.of(d.attributes);
                  for (final f in schema?.locationFields ?? const <FieldSchema>[]) {
                    attrs.remove(f.key);
                  }
                  return d.copyWith(regionId: picked, attributes: attrs);
                });
              }
            },
          ),
        ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(top: DaryobSpacing.xs),
            child: Text(error, style: context.text.bodySmall?.copyWith(color: context.colors.error)),
          ),
        if (schema != null)
          for (final field in schema.locationFields)
            Padding(
              padding: const EdgeInsets.only(top: DaryobSpacing.lg),
              child: SchemaFieldInput(
                key: ValueKey('loc-${field.key}-$regionId'),
                schema: schema,
                field: field,
                attributes: draft.attributes,
                regionId: regionId,
                errorText: _err(context, widget.errors, DraftField.attribute(field.key)),
                onChanged: (v) => widget.update(
                  (d) => d.copyWith(attributes: {...d.attributes, field.key: v}),
                ),
              ),
            ),
        const SizedBox(height: DaryobSpacing.lg),
        DaryobTextField(
          controller: _address,
          label: l10n.addressNote,
          hint: l10n.addressNoteHint,
          maxLength: 120,
          onChanged: (v) => widget.update((d) => d.copyWith(addressNote: v)),
        ),
        const SizedBox(height: DaryobSpacing.sm),
        DaryobNotice(message: l10n.addressPrivacyNote, icon: Icons.lock_outline_rounded),
      ],
    );
  }
}

// ── Step 7: contact ─────────────────────────────────────────────────────────

class ContactStep extends StatefulWidget {
  const ContactStep({
    super.key,
    required this.draft,
    required this.update,
    required this.errors,
  });

  final ListingDraft draft;
  final DraftUpdate update;
  final Map<String, String> errors;

  @override
  State<ContactStep> createState() => _ContactStepState();
}

class _ContactStepState extends State<ContactStep> {
  late final _name = TextEditingController(text: widget.draft.contactName);
  late final _phone = TextEditingController(
    text: TajikPhoneInputFormatter()
        .formatEditUpdate(
          TextEditingValue.empty,
          TextEditingValue(text: Formatters.nationalDigits(widget.draft.contactPhone)),
        )
        .text,
  );

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final draft = widget.draft;
    final errors = widget.errors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DaryobTextField(
          controller: _name,
          label: '${l10n.contactName} *',
          textCapitalization: TextCapitalization.words,
          errorText: _err(context, errors, DraftField.contactName, min: ListingLimits.nameMin, max: ListingLimits.nameMax),
          onChanged: (v) => widget.update((d) => d.copyWith(contactName: v)),
        ),
        const SizedBox(height: DaryobSpacing.md),
        DaryobTextField(
          controller: _phone,
          label: '${l10n.contactPhone} *',
          prefixText: '+992 ',
          hint: 'XX XXX XX XX',
          keyboardType: TextInputType.phone,
          inputFormatters: [TajikPhoneInputFormatter()],
          errorText: _err(context, errors, DraftField.contactPhone),
          onChanged: (v) => widget.update((d) => d.copyWith(contactPhone: v)),
        ),
        const SizedBox(height: DaryobSpacing.lg),
        Text(l10n.phoneVisibility, style: context.text.labelMedium),
        RadioGroup<PhoneVisibility>(
          groupValue: draft.phoneVisibility,
          onChanged: (v) => widget.update((d) => d.copyWith(phoneVisibility: v)),
          child: Column(
            children: [
              RadioListTile<PhoneVisibility>(
                value: PhoneVisibility.visible,
                contentPadding: EdgeInsets.zero,
                title: Text(l10n.phoneVisible),
                subtitle: Text(l10n.phoneVisibleHint),
              ),
              RadioListTile<PhoneVisibility>(
                value: PhoneVisibility.hidden,
                contentPadding: EdgeInsets.zero,
                title: Text(l10n.phoneHiddenOption),
                subtitle: Text(l10n.phoneHiddenHint),
              ),
            ],
          ),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(l10n.chatEnabled),
          subtitle: Text(l10n.chatEnabledHint),
          value: draft.chatEnabled,
          onChanged: (v) => widget.update((d) => d.copyWith(chatEnabled: v)),
        ),
        if (errors.containsKey(DraftField.contactMethod))
          DaryobNotice(message: l10n.contactMethodError, tone: NoticeTone.warning),
      ],
    );
  }
}

// ── Step 8: preview ─────────────────────────────────────────────────────────

class PreviewStep extends ConsumerWidget {
  const PreviewStep({super.key, required this.draft, required this.onEditStep});

  final ListingDraft draft;
  final ValueChanged<DraftStep> onEditStep;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final validator = ref.watch(draftValidatorProvider);
    final registry = ref.watch(categoryRegistryProvider);
    final category = validator.categoryOf(draft);
    final schema = validator.schemaOf(draft);
    final directory = ref.watch(regionDirectoryProvider);
    final formatter = attributeFormatter(context, ref);
    final attributes = validator.cleanAttributes(draft);
    final priceMode = schema?.priceMode ?? PriceMode.required;
    final price = Validators.parsePrice(draft.priceText);
    final priceText = switch (priceMode) {
      PriceMode.none => formatter.salary(attributes) ?? l10n.salaryNotSpecified,
      _ => priceLabel(
        l10n,
        context.languageCode,
        price: priceMode == PriceMode.free ? 0 : price,
        currency: Currency.tjs,
        isFreeCategory: priceMode == PriceMode.free,
      ),
    };
    final categoryPath = category == null
        ? '—'
        : registry.pathTo(category.id).map((c) => c.name.of(context)).join(' › ');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DaryobNotice(message: l10n.previewNotice, tone: NoticeTone.brand),
        const SizedBox(height: DaryobSpacing.lg),
        Card(
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              AspectRatio(
                aspectRatio: 4 / 3,
                child: DaryobListingImage(
                  source: draft.photos.isEmpty ? null : draft.photos.first,
                  icon: category?.icon ?? CategoryIcon.generic,
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(DaryobSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(priceText, style: context.text.headlineSmall),
                    if (draft.isNegotiable && priceMode != PriceMode.free && priceMode != PriceMode.none)
                      Text(l10n.negotiable, style: context.text.bodySmall),
                    const SizedBox(height: DaryobSpacing.sm),
                    Text(draft.title, style: context.text.titleMedium),
                    const SizedBox(height: DaryobSpacing.sm),
                    Text(draft.description, style: context.text.bodyMedium),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: DaryobSpacing.lg),
        _PreviewRow(label: l10n.category, value: categoryPath, onEdit: () => onEditStep(DraftStep.category)),
        if (schema != null)
          for (final (label, value) in formatter.characteristics(schema, attributes))
            _PreviewRow(label: label, value: value, onEdit: () => onEditStep(DraftStep.details)),
        _PreviewRow(
          label: l10n.photos,
          value: l10n.photosCounter(draft.photos.length, schema?.photosMax ?? ListingLimits.photosMax),
          onEdit: () => onEditStep(DraftStep.photos),
        ),
        _PreviewRow(
          label: l10n.location,
          value: draft.regionId == null
              ? '—'
              : [
                  regionPathLabel(context, directory, draft.regionId!),
                  if (draft.addressNote.trim().isNotEmpty) draft.addressNote.trim(),
                ].join(' · '),
          onEdit: () => onEditStep(DraftStep.location),
        ),
        _PreviewRow(
          label: l10n.contacts,
          value: [
            draft.contactName,
            draft.phoneVisibility == PhoneVisibility.visible ? Formatters.phone(draft.contactPhone) : l10n.phoneHidden,
            if (draft.chatEnabled) l10n.chatEnabled,
          ].join(' · '),
          onEdit: () => onEditStep(DraftStep.contact),
        ),
      ],
    );
  }
}

class _PreviewRow extends StatelessWidget {
  const _PreviewRow({required this.label, required this.value, required this.onEdit});
  final String label;
  final String value;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: DaryobSpacing.xs),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: context.text.bodySmall),
                Text(value, style: context.text.bodyMedium),
              ],
            ),
          ),
          TextButton(onPressed: onEdit, child: Text(context.l10n.edit)),
        ],
      ),
    );
  }
}

/// Applies a subcategory's preset values (e.g. listing_kind = vacancy).
Map<String, Object?> withPresets(CategorySchema schema, Map<String, Object?> attributes) {
  final next = Map<String, Object?>.of(attributes);
  schema.presetAttributes.forEach((k, v) {
    if (schema.lockedAttributes.contains(k) || next[k] == null) next[k] = v;
  });
  return next;
}
