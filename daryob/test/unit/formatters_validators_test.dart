import 'package:daryob/core/utils/formatters.dart';
import 'package:daryob/core/utils/validators.dart';
import 'package:daryob/shared/models/money.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('price formatting', () {
    test('groups thousands with a narrow space', () {
      expect(Formatters.groupDigits(0), '0');
      expect(Formatters.groupDigits(950), '950');
      expect(Formatters.groupDigits(1250), '1 250');
      expect(Formatters.groupDigits(15000), '15 000');
      expect(Formatters.groupDigits(1234567), '1 234 567');
    });

    test('uses the right currency word per language', () {
      expect(Formatters.price(1250, Currency.tjs, 'tg'), '1 250 сомонӣ');
      expect(Formatters.price(15000, Currency.tjs, 'ru'), '15 000 сомони');
      expect(Formatters.price(9800, Currency.usd, 'ru'), '9 800 USD');
    });
  });

  group('phone formatting', () {
    test('formats +992 XX XXX XX XX', () {
      expect(Formatters.phone('931234567'), '+992 93 123 45 67');
      expect(Formatters.phone('+992 93 123 45 67'), '+992 93 123 45 67');
      expect(Formatters.phone('+992 93 123'), '+992 93 123');
      expect(Formatters.phone('93 12'), '+992 93 12');
    });

    test('keeps only national digits', () {
      expect(Formatters.nationalDigits('+992 (93) 123-45-67'), '931234567');
      expect(Formatters.nationalDigits('93 123 45 67'), '931234567');
    });

    test('masks the middle of the number', () {
      expect(Formatters.maskedPhone('931234567'), '+992 93 *** ** 67');
    });
  });

  group('validators', () {
    test('title length', () {
      expect(Validators.title(''), ValidationCode.required);
      expect(Validators.title('abc'), ValidationCode.tooShort);
      expect(Validators.title('Диван угловой'), isNull);
      expect(
        Validators.title('x' * (ListingLimits.titleMax + 1)),
        ValidationCode.tooLong,
      );
    });

    test('description length', () {
      expect(Validators.description('коротко'), ValidationCode.tooShort);
      expect(
        Validators.description('Описание достаточной длины для объявления'),
        isNull,
      );
    });

    test('price', () {
      expect(Validators.price(''), ValidationCode.required);
      expect(Validators.price('', required: false), isNull);
      expect(Validators.price('12 500'), isNull);
      expect(Validators.parsePrice('12 500'), 12500);
      expect(Validators.price('abc'), ValidationCode.invalidNumber);
      expect(Validators.price('9999999999'), ValidationCode.outOfRange);
    });

    test('Tajik phone needs exactly 9 national digits', () {
      expect(Validators.tajikPhone(''), ValidationCode.required);
      expect(Validators.tajikPhone('93 123 45'), ValidationCode.invalidPhone);
      expect(Validators.tajikPhone('93 123 45 67'), isNull);
      expect(Validators.tajikPhone('+992931234567'), isNull);
    });

    test('one-time code', () {
      expect(Validators.otp('12345'), ValidationCode.invalidCode);
      expect(Validators.otp('12a456'), ValidationCode.invalidCode);
      expect(Validators.otp('123456'), isNull);
    });
  });

  group('relative age', () {
    final now = DateTime(2026, 1, 10, 12);
    test('units', () {
      expect(
        Age.of(now.subtract(const Duration(seconds: 20)), now).unit,
        AgeUnit.justNow,
      );
      expect(Age.of(now.subtract(const Duration(minutes: 5)), now).value, 5);
      expect(
        Age.of(now.subtract(const Duration(hours: 3)), now).unit,
        AgeUnit.hours,
      );
      expect(
        Age.of(now.subtract(const Duration(days: 2)), now).unit,
        AgeUnit.days,
      );
      expect(
        Age.of(now.subtract(const Duration(days: 30)), now).unit,
        AgeUnit.date,
      );
    });
  });
}
