import '../../shared/models/money.dart';

/// Formatting rules for Tajikistan. Pure functions — no BuildContext — so
/// they are easy to test.
abstract final class Formatters {
  /// Groups digits with a narrow no-break space: 1250 → "1 250".
  static String groupDigits(int value) {
    final negative = value < 0;
    final digits = value.abs().toString();
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      final fromEnd = digits.length - i;
      buffer.write(digits[i]);
      if (fromEnd > 1 && fromEnd % 3 == 1) buffer.write(' ');
    }
    return negative ? '-$buffer' : buffer.toString();
  }

  /// "1 250 сомонӣ" (tg) / "1 250 сомони" (ru) / "1 250 USD".
  static String price(int amount, Currency currency, String languageCode) {
    final number = groupDigits(amount);
    switch (currency) {
      case Currency.tjs:
        return '$number ${languageCode == 'tg' ? 'сомонӣ' : 'сомони'}';
      case Currency.usd:
        return '$number USD';
    }
  }

  /// Keeps only the 9 national digits of a Tajik number, dropping +992.
  static String nationalDigits(String input) {
    var digits = input.replaceAll(RegExp(r'\D'), '');
    // Strip the country code when it was typed explicitly ("+992 …") or
    // when there are more digits than a national number has.
    final explicit = input.trimLeft().startsWith('+992');
    if (digits.startsWith('992') && (explicit || digits.length > 9)) {
      digits = digits.substring(3);
    }
    return digits.length > 9 ? digits.substring(0, 9) : digits;
  }

  /// "+992 XX XXX XX XX". Partial input is formatted as far as it goes.
  static String phone(String input) {
    final d = nationalDigits(input);
    if (d.isEmpty) return '+992';
    final parts = <String>[];
    final cuts = [2, 3, 2, 2];
    var index = 0;
    for (final cut in cuts) {
      if (index >= d.length) break;
      final end = (index + cut).clamp(0, d.length);
      parts.add(d.substring(index, end));
      index = end;
    }
    return '+992 ${parts.join(' ')}';
  }

  /// Masked for privacy: "+992 93 *** ** 67".
  static String maskedPhone(String input) {
    final d = nationalDigits(input);
    if (d.length < 9) return phone(input);
    return '+992 ${d.substring(0, 2)} *** ** ${d.substring(7)}';
  }

  /// dd.MM.yyyy — the format used across Tajikistan in both languages.
  static String date(DateTime value) {
    String two(int n) => n.toString().padLeft(2, '0');
    final local = value.toLocal();
    return '${two(local.day)}.${two(local.month)}.${local.year}';
  }

  static String time(DateTime value) {
    String two(int n) => n.toString().padLeft(2, '0');
    final local = value.toLocal();
    return '${two(local.hour)}:${two(local.minute)}';
  }
}

/// How long ago something happened, in units the UI can localise.
enum AgeUnit { justNow, minutes, hours, days, date }

class Age {
  const Age(this.unit, this.value);
  final AgeUnit unit;
  final int value;

  static Age of(DateTime moment, DateTime now) {
    final diff = now.difference(moment);
    if (diff.inMinutes < 1) return const Age(AgeUnit.justNow, 0);
    if (diff.inHours < 1) return Age(AgeUnit.minutes, diff.inMinutes);
    if (diff.inDays < 1) return Age(AgeUnit.hours, diff.inHours);
    if (diff.inDays < 7) return Age(AgeUnit.days, diff.inDays);
    return const Age(AgeUnit.date, 0);
  }
}
