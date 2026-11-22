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
}) => validationMessage(context.l10n, errors[key], min: min, max: max);

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
    final categories = ref.watch(categoryRegistryProvider).topLevel;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final error = _err(context, errors, DraftField.category);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (error != null) ...[
          DaryobNotice(
            message: context.l10n.chooseCategoryError,
            tone: NoticeTone.warning,
          ),
          const SizedBox(height: DaryobSpacing.md),
        ],
        for (final c in categories)
          Padding(
            padding: const EdgeInsets.only(bottom: DaryobSpacing.sm),
            child: Material(
              color: draft.categoryId == c.id
                  ? context.palette.limeSoft
                  : context.colors.surface,
              shape: RoundedRectangleBorder(
                borderRadius: DaryobRadius.cardAll,
                side: BorderSide(
                  color: draft.categoryId == c.id
                      ? (isDark ? DaryobColors.lime : DaryobColors.navy)
                      : context.palette.border,
                  width: draft.categoryId == c.id ? 2 : 1,
                ),
              ),
              child: ListTile(
                shape: const RoundedRectangleBorder(
                  borderRadius: DaryobRadius.cardAll,
                ),
                leading: DaryobCategoryIcon(icon: c.icon, size: 40),
                title: Text(c.name.of(context)),
                subtitle: Text(
                  c.description.of(context),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                trailing: draft.categoryId == c.id
                    ? const Icon(Icons.check_circle_rounded)
                    : const Icon(Icons.chevron_right_rounded),
                onTap: () => onPick(c.id),
              ),
            ),
          ),
      ],
    );
  }
}

// ── Step 2: basic information ───────────────────────────────────────────────

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
  late final _description = TextEditingController(
    text: widget.draft.description,
  );
  late final _price = TextEditingController(
    text: PriceInputFormatter()
        .formatEditUpdate(
          TextEditingValue.empty,
          TextEditingValue(text: widget.draft.priceText),
        )
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
    final category = ref.watch(categoryRegistryProvider).byId(draft.categoryId);
    final schema = category == null
        ? null
        : ref.watch(schemaRegistryProvider).schemaFor(category.formSchemaId);
    final priceMode = category?.priceMode ?? PriceMode.required;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DaryobTextField(
          controller: _title,
          label: '${l10n.fieldTitle} *',
          hint: l10n.fieldTitleHint,
          maxLength: ListingLimits.titleMax,
          errorText: _err(
            context,
            errors,
            DraftField.title,
            min: ListingLimits.titleMin,
            max: ListingLimits.titleMax,
          ),
          onChanged: (v) => widget.update((d) => d.copyWith(title: v)),
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
        if (priceMode == PriceMode.free)
          DaryobNotice(
            message: l10n.freeCategoryNotice,
            icon: Icons.card_giftcard_outlined,
          )
        else ...[
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: DaryobTextField(
                  controller: _price,
                  label: priceMode == PriceMode.required && !draft.isNegotiable
                      ? '${l10n.price} *'
                      : l10n.price,
                  hint: priceMode == PriceMode.optional
                      ? l10n.priceOptionalHint
                      : '0',
                  keyboardType: TextInputType.number,
                  inputFormatters: [PriceInputFormatter()],
                  errorText: _err(context, errors, DraftField.price),
                  onChanged: (v) =>
                      widget.update((d) => d.copyWith(priceText: v)),
                ),
              ),
              const SizedBox(width: DaryobSpacing.md),
              Padding(
                padding: EdgeInsets.only(
                  bottom: _err(context, errors, DraftField.price) == null
                      ? 0
                      : 22,
                ),
                child: SegmentedButton<Currency>(
                  segments: const [
                    ButtonSegment(value: Currency.tjs, label: Text('TJS')),
                    ButtonSegment(value: Currency.usd, label: Text('USD')),
                  ],
                  selected: {draft.currency},
                  showSelectedIcon: false,
                  onSelectionChanged: (s) =>
                      widget.update((d) => d.copyWith(currency: s.first)),
                ),
              ),
            ],
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(l10n.negotiable),
            subtitle: Text(l10n.negotiableHint),
            value: draft.isNegotiable,
            onChanged: (v) => widget.update((d) => d.copyWith(isNegotiable: v)),
          ),
        ],
        if (schema != null)
          for (final field in schema.basicStepFields)
            if (field.isVisible(draft.attributes))
              Padding(
                padding: const EdgeInsets.only(top: DaryobSpacing.md),
                child: SchemaFieldInput(
                  key: ValueKey('attr-${field.key}'),
                  field: field,
                  value: draft.attributes[field.key],
                  errorText: _err(
                    context,
                    errors,
                    DraftField.attribute(field.key),
                  ),
                  onChanged: (v) => widget.update(
                    (d) =>
                        d.copyWith(attributes: {...d.attributes, field.key: v}),
                  ),
                ),
              ),
      ],
    );
  }
}

/// A category-specific step declared by the schema (none in Phase 1).
class ExtraSchemaStep extends StatelessWidget {
  const ExtraSchemaStep({
    super.key,
    required this.draft,
    required this.step,
    required this.schema,
    required this.update,
    required this.errors,
  });

  final ListingDraft draft;
  final FormStepSchema step;
  final CategorySchema schema;
  final DraftUpdate update;
  final Map<String, String> errors;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final key in step.fieldKeys)
          if (schema.field(key) case final field?
              when field.isVisible(draft.attributes))
            Padding(
              padding: const EdgeInsets.only(bottom: DaryobSpacing.md),
              child: SchemaFieldInput(
                key: ValueKey('attr-$key'),
                field: field,
                value: draft.attributes[key],
                errorText: _err(context, errors, DraftField.attribute(key)),
                onChanged: (v) => update(
                  (d) => d.copyWith(attributes: {...d.attributes, key: v}),
                ),
              ),
            ),
      ],
    );
  }
}

// ── Step 3: photos ──────────────────────────────────────────────────────────

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
    final category = ref.watch(categoryRegistryProvider).byId(draft.categoryId);
    final error = _err(context, errors, DraftField.photos);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DaryobNotice(
          message: context.l10n.photosTip,
          icon: Icons.lightbulb_outline_rounded,
        ),
        const SizedBox(height: DaryobSpacing.lg),
        DaryobPhotoPicker(
          photos: draft.photos,
          icon: category?.icon ?? CategoryIcon.generic,
          onChanged: (photos) => update((d) => d.copyWith(photos: photos)),
        ),
        if (error != null)
          Text(
            error,
            style: context.text.bodySmall?.copyWith(
              color: context.colors.error,
            ),
          ),
      ],
    );
  }
}

// ── Step 4: location ────────────────────────────────────────────────────────

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
    final regionId = widget.draft.regionId;
    final error = _err(context, widget.errors, DraftField.region);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('${l10n.location} *', style: context.text.labelMedium),
        const SizedBox(height: DaryobSpacing.sm),
        Material(
          color: context.colors.surface,
          shape: RoundedRectangleBorder(
            borderRadius: DaryobRadius.inputAll,
            side: BorderSide(
              color: error != null
                  ? context.colors.error
                  : context.palette.border,
            ),
          ),
          child: ListTile(
            shape: const RoundedRectangleBorder(
              borderRadius: DaryobRadius.inputAll,
            ),
            leading: const Icon(Icons.place_outlined),
            title: Text(
              regionId == null
                  ? l10n.chooseLocation
                  : regionPathLabel(context, directory, regionId),
            ),
            trailing: const Icon(Icons.expand_more_rounded),
            onTap: () async {
              final picked = await showLocationPicker(
                context,
                selectedId: regionId,
                allowWholeCountry: false,
              );
              if (picked != null) {
                widget.update((d) => d.copyWith(regionId: picked));
              }
            },
          ),
        ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(top: DaryobSpacing.xs),
            child: Text(
              error,
              style: context.text.bodySmall?.copyWith(
                color: context.colors.error,
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
        DaryobNotice(
          message: l10n.addressPrivacyNote,
          icon: Icons.lock_outline_rounded,
        ),
      ],
    );
  }
}

// ── Step 5: contact ─────────────────────────────────────────────────────────

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
          TextEditingValue(
            text: Formatters.nationalDigits(widget.draft.contactPhone),
          ),
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
          errorText: _err(
            context,
            errors,
            DraftField.contactName,
            min: ListingLimits.nameMin,
            max: ListingLimits.nameMax,
          ),
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
          onChanged: (v) =>
              widget.update((d) => d.copyWith(phoneVisibility: v)),
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
          DaryobNotice(
            message: l10n.contactMethodError,
            tone: NoticeTone.warning,
          ),
      ],
    );
  }
}

// ── Step 6: preview ─────────────────────────────────────────────────────────

class PreviewStep extends ConsumerWidget {
  const PreviewStep({super.key, required this.draft, required this.onEditStep});

  final ListingDraft draft;
  final ValueChanged<DraftStep> onEditStep;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final category = ref.watch(categoryRegistryProvider).byId(draft.categoryId);
    final schema = category == null
        ? null
        : ref.watch(schemaRegistryProvider).schemaFor(category.formSchemaId);
    final directory = ref.watch(regionDirectoryProvider);
    final isFree = category?.priceMode == PriceMode.free;
    final price = Validators.parsePrice(draft.priceText);

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
                    Text(
                      priceLabel(
                        l10n,
                        context.languageCode,
                        price: isFree ? 0 : price,
                        currency: draft.currency,
                        isFreeCategory: isFree,
                      ),
                      style: context.text.headlineSmall,
                    ),
                    if (draft.isNegotiable && !isFree)
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
        _PreviewRow(
          label: l10n.category,
          value: category?.name.of(context) ?? '—',
          onEdit: () => onEditStep(DraftStep.category),
        ),
        _PreviewRow(
          label: l10n.photos,
          value: l10n.photosCounter(
            draft.photos.length,
            ListingLimits.photosMax,
          ),
          onEdit: () => onEditStep(DraftStep.photos),
        ),
        if (schema != null)
          for (final field in schema.fields)
            if (draft.attributes[field.key] != null)
              _PreviewRow(
                label: field.label.of(context),
                value:
                    field
                        .optionLabel(draft.attributes[field.key])
                        ?.of(context) ??
                    '${draft.attributes[field.key]}',
                onEdit: () => onEditStep(DraftStep.basics),
              ),
        _PreviewRow(
          label: l10n.location,
          value: draft.regionId == null
              ? '—'
              : [
                  regionPathLabel(context, directory, draft.regionId!),
                  if (draft.addressNote.trim().isNotEmpty)
                    draft.addressNote.trim(),
                ].join(' · '),
          onEdit: () => onEditStep(DraftStep.location),
        ),
        _PreviewRow(
          label: l10n.contacts,
          value: [
            draft.contactName,
            draft.phoneVisibility == PhoneVisibility.visible
                ? Formatters.phone(draft.contactPhone)
                : l10n.phoneHidden,
            if (draft.chatEnabled) l10n.chatEnabled,
          ].join(' · '),
          onEdit: () => onEditStep(DraftStep.contact),
        ),
      ],
    );
  }
}

class _PreviewRow extends StatelessWidget {
  const _PreviewRow({
    required this.label,
    required this.value,
    required this.onEdit,
  });
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
