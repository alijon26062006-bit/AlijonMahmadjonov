import '../../../core/utils/validators.dart';
import '../../../shared/models/category.dart';
import '../../../shared/models/category_schema.dart';
import '../../../shared/models/listing.dart';
import '../../categories/domain/category_registry.dart';
import '../../categories/domain/schema_registry.dart';
import 'listing_draft.dart';

/// Field keys used in validation results. Schema attributes are reported as
/// `attr.<key>`.
abstract final class DraftField {
  static const category = 'category';
  static const subcategory = 'subcategory';
  static const title = 'title';
  static const description = 'description';
  static const price = 'price';
  static const photos = 'photos';
  static const region = 'region';
  static const contactName = 'contactName';
  static const contactPhone = 'contactPhone';

  /// Phone hidden and chat disabled: buyers would have no way to reach the
  /// seller.
  static const contactMethod = 'contactMethod';

  static String attribute(String key) => 'attr.$key';
}

/// Single source of truth for "is this draft publishable". Used by the
/// wizard (per step) and by repositories (before saving), so creating,
/// editing, searching and filtering all follow the same catalog schema.
class DraftValidator {
  DraftValidator(this._categories, this._schemas, {DateTime Function()? clock})
    : _clock = clock ?? DateTime.now;

  final CategoryRegistry _categories;
  final SchemaRegistry _schemas;
  final DateTime Function() _clock;

  CategoryDefinition? categoryOf(ListingDraft draft) => _categories.byId(draft.categoryId);

  /// Schema of the chosen (sub)category, or null before a category is set.
  CategorySchema? schemaOf(ListingDraft draft) {
    final category = categoryOf(draft);
    return category == null ? null : _schemas.schemaFor(category.formSchemaId);
  }

  /// True when the chosen category still needs a subcategory.
  bool needsSubcategory(ListingDraft draft) {
    final id = draft.categoryId;
    return id == null || _categories.childrenOf(id).isNotEmpty;
  }

  Map<String, String> validateStep(ListingDraft draft, DraftStep step) {
    final errors = <String, String>{};
    final category = categoryOf(draft);
    final schema = schemaOf(draft);

    switch (step) {
      case DraftStep.category:
        if (category == null) errors[DraftField.category] = ValidationCode.required;
      case DraftStep.subcategory:
        if (category != null && needsSubcategory(draft)) {
          errors[DraftField.subcategory] = ValidationCode.required;
        }
      case DraftStep.details:
        if (category != null && schema != null) {
          _addAttributeErrors(
            errors,
            category.formSchemaId,
            draft,
            schema.detailFields.map((f) => f.key).toSet(),
          );
        }
      case DraftStep.basics:
        _put(errors, DraftField.title, Validators.title(draft.title));
        _put(errors, DraftField.description, Validators.description(draft.description));
        final mode = schema?.priceMode ?? PriceMode.required;
        if (mode == PriceMode.required || mode == PriceMode.optional) {
          _put(
            errors,
            DraftField.price,
            Validators.price(
              draft.priceText,
              required: mode == PriceMode.required && !draft.isNegotiable,
            ),
          );
        }
      case DraftStep.photos:
        final max = schema?.photosMax ?? ListingLimits.photosMax;
        final min = schema?.photosMin ?? 0;
        if (draft.photos.length > max) {
          errors[DraftField.photos] = ValidationCode.tooManyPhotos;
        } else if (draft.photos.length < min) {
          errors[DraftField.photos] = ValidationCode.tooFewPhotos;
        }
      case DraftStep.location:
        if (draft.regionId == null) errors[DraftField.region] = ValidationCode.required;
        if (category != null && schema != null) {
          _addAttributeErrors(
            errors,
            category.formSchemaId,
            draft,
            schema.locationFields.map((f) => f.key).toSet(),
          );
        }
      case DraftStep.contact:
        _put(errors, DraftField.contactName, Validators.personName(draft.contactName));
        _put(errors, DraftField.contactPhone, Validators.tajikPhone(draft.contactPhone));
        if (draft.phoneVisibility == PhoneVisibility.hidden && !draft.chatEnabled) {
          errors[DraftField.contactMethod] = ValidationCode.required;
        }
      case DraftStep.preview:
        break;
    }
    return errors;
  }

  /// Validates a category-specific step declared in the schema.
  Map<String, String> validateExtraStep(ListingDraft draft, FormStepSchema step) {
    final category = categoryOf(draft);
    if (category == null) return const {};
    final errors = <String, String>{};
    _addAttributeErrors(errors, category.formSchemaId, draft, step.fieldKeys.toSet());
    return errors;
  }

  Map<String, String> validateAll(ListingDraft draft) {
    final errors = <String, String>{};
    for (final step in DraftStep.values) {
      errors.addAll(validateStep(draft, step));
    }
    for (final step in schemaOf(draft)?.extraSteps ?? const <FormStepSchema>[]) {
      errors.addAll(validateExtraStep(draft, step));
    }
    return errors;
  }

  void _addAttributeErrors(
    Map<String, String> errors,
    String schemaId,
    ListingDraft draft,
    Set<String> keys,
  ) {
    final attrErrors = _schemas.validate(
      schemaId,
      draft.attributes,
      onlyKeys: keys,
      now: _clock(),
    );
    attrErrors.forEach((k, v) => errors[DraftField.attribute(k)] = v);
  }

  /// Attributes worth storing: visible schema fields with values, plus the
  /// subcategory marker (`category_child`). Hidden conditional values are
  /// dropped so a listing never carries contradicting data.
  Map<String, Object?> cleanAttributes(ListingDraft draft) {
    final schema = schemaOf(draft);
    final category = categoryOf(draft);
    if (schema == null) return const {};
    bool hasValue(Object? v) =>
        v != null && !(v is String && v.trim().isEmpty) && !(v is List && v.isEmpty);
    final result = <String, Object?>{
      for (final field in schema.fields)
        if (field.isVisible(draft.attributes) && hasValue(draft.attributes[field.key]))
          field.key: draft.attributes[field.key],
    };
    final childKey = schema.categoryChildKey;
    if (childKey != null && category != null && !category.isTopLevel && category.catalogId != null) {
      result[childKey] = category.catalogId;
    }
    return result;
  }

  static void _put(Map<String, String> errors, String key, String? code) {
    if (code != null) errors[key] = code;
  }
}
