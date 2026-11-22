import 'dart:math';

final Random _random = Random.secure();

/// Short sortable id: time component + random suffix. Good enough for
/// locally created records; the server issues its own ids in production.
String newId([String prefix = '']) {
  final time = DateTime.now().microsecondsSinceEpoch.toRadixString(36);
  final rand = List.generate(
    6,
    (_) => _random.nextInt(36).toRadixString(36),
  ).join();
  return '$prefix$time$rand';
}

/// Human-friendly listing number shown on the detail screen.
String listingNumber(String id) {
  final digits = id.hashCode.abs() % 100000000;
  return digits.toString().padLeft(8, '0');
}
