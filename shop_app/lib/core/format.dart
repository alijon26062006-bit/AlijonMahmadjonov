/// Валюта маркетплейса. Поменяйте здесь — поменяется во всех четырёх приложениях.
const String kCurrency = 'смн';

/// Код страны для входа по телефону.
const String kPhoneCode = '+992';

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

/// 1290 -> "1 290 смн"
String money(int value) => '${groupDigits(value)}$_nbsp$kCurrency';

/// Русское склонение: plural(3, 'товар', 'товара', 'товаров') -> 'товара'
String plural(int n, String one, String few, String many) {
  final m10 = n % 10, m100 = n % 100;
  if (m10 == 1 && m100 != 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few;
  return many;
}

String itemsLabel(int n) => '$n ${plural(n, 'товар', 'товара', 'товаров')}';

String ordersLabel(int n) => '$n ${plural(n, 'заказ', 'заказа', 'заказов')}';

String reviewsLabel(int n) => '${groupDigits(n)} ${plural(n, 'отзыв', 'отзыва', 'отзывов')}';

String two(int v) => v.toString().padLeft(2, '0');

String formatTime(DateTime d) => '${two(d.hour)}:${two(d.minute)}';

String formatDate(DateTime d) => '${two(d.day)}.${two(d.month)}.${d.year}, ${formatTime(d)}';

bool sameDay(DateTime a, DateTime b) => a.year == b.year && a.month == b.month && a.day == b.day;

/// «Сегодня, 14:05», «Вчера, 09:30», «12.11, 18:00»
String formatWhen(DateTime d) {
  final now = DateTime.now();
  if (sameDay(d, now)) return 'Сегодня, ${formatTime(d)}';
  if (sameDay(d, now.subtract(const Duration(days: 1)))) return 'Вчера, ${formatTime(d)}';
  return '${two(d.day)}.${two(d.month)}, ${formatTime(d)}';
}

/// «только что», «5 мин назад», «2 ч назад», дата
String timeAgo(DateTime d) {
  final diff = DateTime.now().difference(d);
  if (diff.inSeconds < 60) return 'только что';
  if (diff.inMinutes < 60) return '${diff.inMinutes} мин назад';
  if (diff.inHours < 24) return '${diff.inHours} ч назад';
  return formatWhen(d);
}

const _weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

String weekdayShort(DateTime d) => _weekdays[d.weekday - 1];

/// Только цифры номера без кода страны: "901234567"
String phoneDigits(String input) {
  var d = input.replaceAll(RegExp(r'\D'), '');
  if (d.startsWith('992') && d.length > 9) d = d.substring(3);
  return d;
}

/// "901234567" -> "+992 90 123 45 67"
String formatPhone(String input) {
  final d = phoneDigits(input);
  if (d.length != 9) return input.isEmpty ? '' : '$kPhoneCode $d';
  return '$kPhoneCode ${d.substring(0, 2)} ${d.substring(2, 5)} ${d.substring(5, 7)} ${d.substring(7)}';
}
