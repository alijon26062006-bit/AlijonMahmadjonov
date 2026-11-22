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
/// wizard (per step) and by repositories (before saving).
class DraftValidator {
  DraftValidator(this._categories, this._schemas);

  final CategoryRegistry _categories;
  final SchemaRegistry _schemas;

  CategorySchema? schemaOf(ListingDraft draft) {
    final category = _categories.byId(draft.categoryId);
    return category == null ? null : _schemas.schemaFor(category.formSchemaId);
  }

  Map<String, String> validateStep(ListingDraft draft, DraftStep step) {
    final errors = <String, String>{};
    final category = _categories.byId(draft.categoryId);

    switch (step) {
      case DraftStep.category:
        if (category == null) {
          errors[DraftField.category] = ValidationCode.required;
        }
      case DraftStep.basics:
        _put(errors, DraftField.title, Validators.title(draft.title));
        _put(
          errors,
          DraftField.description,
          Validators.description(draft.description),
        );
        if (category != null && category.priceMode != PriceMode.free) {
          _put(
            errors,
            DraftField.price,
            Validators.price(
              draft.priceText,
              required:
                  category.priceMode == PriceMode.required &&
                  !draft.isNegotiable,
            ),
          );
        }
        final schema = schemaOf(draft);
        if (category != null && schema != null) {
          _addAttributeErrors(
            errors,
            category.formSchemaId,
            draft,
            schema.basicStepFields.map((f) => f.key).toSet(),
          );
        }
      case DraftStep.photos:
        if (draft.photos.length > ListingLimits.photosMax) {
          errors[DraftField.photos] = ValidationCode.tooManyPhotos;
        }
      case DraftStep.location:
        if (draft.regionId == null) {
          errors[DraftField.region] = ValidationCode.required;
        }
      case DraftStep.contact:
        _put(
          errors,
          DraftField.contactName,
          Validators.personName(draft.contactName),
        );
        _put(
          errors,
          DraftField.contactPhone,
          Validators.tajikPhone(draft.contactPhone),
        );
        if (draft.phoneVisibility == PhoneVisibility.hidden &&
            !draft.chatEnabled) {
          errors[DraftField.contactMethod] = ValidationCode.required;
        }
      case DraftStep.preview:
        break;
    }
    return errors;
  }

  /// Validates a category-specific step declared in the schema.
  Map<String, String> validateExtraStep(
    ListingDraft draft,
    FormStepSchema step,
  ) {
    final category = _categories.byId(draft.categoryId);
    if (category == null) return const {};
    final errors = <String, String>{};
    _addAttributeErrors(
      errors,
      category.formSchemaId,
      draft,
      step.fieldKeys.toSet(),
    );
    return errors;
  }

  Map<String, String> validateAll(ListingDraft draft) {
    final errors = <String, String>{};
    for (final step in DraftStep.values) {
      errors.addAll(validateStep(draft, step));
    }
    for (final step
        in schemaOf(draft)?.extraSteps ?? const <FormStepSchema>[]) {
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
    );
    attrErrors.forEach((k, v) => errors[DraftField.attribute(k)] = v);
  }

  static void _put(Map<String, String> errors, String key, String? code) {
    if (code != null) errors[key] = code;
  }
}
