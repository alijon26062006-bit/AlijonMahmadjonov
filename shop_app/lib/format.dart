/// Валюта магазина. Поменяйте здесь — и она поменяется во всём приложении.
const String kCurrency = '₽';

const String _nbsp = ' ';

/// 12990 -> "12 990"
String groupDigits(int value) {
  final s = value.abs().toString();
  final b = StringBuffer(value < 0 ? '−' : '');
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) b.write(_nbsp);
    b.write(s[i]);
  }
  return b.toString();
}

/// 12990 -> "12 990 ₽"
String money(int value) => '${groupDigits(value)}$_nbsp$kCurrency';

/// Русское склонение: plural(3, 'товар', 'товара', 'товаров') -> 'товара'
String plural(int n, String one, String few, String many) {
  final m10 = n % 10, m100 = n % 100;
  if (m10 == 1 && m100 != 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few;
  return many;
}

String itemsLabel(int n) => '$n ${plural(n, 'товар', 'товара', 'товаров')}';

String reviewsLabel(int n) => '${groupDigits(n)} ${plural(n, 'отзыв', 'отзыва', 'отзывов')}';

String two(int v) => v.toString().padLeft(2, '0');

String formatDate(DateTime d) => '${two(d.day)}.${two(d.month)}.${d.year}, ${two(d.hour)}:${two(d.minute)}';
