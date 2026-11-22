import 'formatters.dart';

/// Validation error codes. The UI maps them to localised text; repositories
/// and the API use the same codes.
abstract final class ValidationCode {
  static const required = 'required';
  static const tooShort = 'too_short';
  static const tooLong = 'too_long';
  static const invalidNumber = 'invalid_number';
  static const outOfRange = 'out_of_range';
  static const invalidPhone = 'invalid_phone';
  static const invalidCode = 'invalid_code';
  static const tooManyPhotos = 'too_many_photos';
  static const tooFewPhotos = 'too_few_photos';

  /// A value larger than the field it must not exceed (floor > floors).
  static const notAboveOther = 'not_above_other';
}

abstract final class ListingLimits {
  static const titleMin = 5;
  static const titleMax = 80;
  static const descriptionMin = 20;
  static const descriptionMax = 4000;
  static const priceMax = 999999999;
  static const photosMax = 16;
  static const nameMin = 2;
  static const nameMax = 50;
}

abstract final class Validators {
  static String? title(String? value) {
    final v = value?.trim() ?? '';
    if (v.isEmpty) return ValidationCode.required;
    if (v.length < ListingLimits.titleMin) return ValidationCode.tooShort;
    if (v.length > ListingLimits.titleMax) return ValidationCode.tooLong;
    return null;
  }

  static String? description(String? value) {
    final v = value?.trim() ?? '';
    if (v.isEmpty) return ValidationCode.required;
    if (v.length < ListingLimits.descriptionMin) return ValidationCode.tooShort;
    if (v.length > ListingLimits.descriptionMax) return ValidationCode.tooLong;
    return null;
  }

  /// Price is optional unless [required]; when present it must be a whole
  /// number of somoni within range.
  static String? price(String? value, {bool required = true}) {
    final v = (value ?? '').replaceAll(RegExp(r'[\s ]'), '');
    if (v.isEmpty) return required ? ValidationCode.required : null;
    final parsed = int.tryParse(v);
    if (parsed == null) return ValidationCode.invalidNumber;
    if (parsed < 0 || parsed > ListingLimits.priceMax) {
      return ValidationCode.outOfRange;
    }
    return null;
  }

  static int? parsePrice(String? value) =>
      int.tryParse((value ?? '').replaceAll(RegExp(r'[\s ]'), ''));

  static String? personName(String? value) {
    final v = value?.trim() ?? '';
    if (v.isEmpty) return ValidationCode.required;
    if (v.length < ListingLimits.nameMin) return ValidationCode.tooShort;
    if (v.length > ListingLimits.nameMax) return ValidationCode.tooLong;
    return null;
  }

  /// Tajik numbers have 9 national digits after +992. Operator prefixes are
  /// deliberately not checked here: the list changes, and rejecting a real
  /// number is worse than letting the SMS provider reject a fake one.
  static String? tajikPhone(String? value) {
    final d = Formatters.nationalDigits(value ?? '');
    if (d.isEmpty) return ValidationCode.required;
    if (d.length != 9) return ValidationCode.invalidPhone;
    return null;
  }

  static String? otp(String? value, {int length = 6}) {
    final v = value?.trim() ?? '';
    if (v.isEmpty) return ValidationCode.required;
    if (!RegExp('^\\d{$length}\$').hasMatch(v)) {
      return ValidationCode.invalidCode;
    }
    return null;
  }
}
