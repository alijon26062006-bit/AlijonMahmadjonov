import 'dart:math' as math;

import 'package:geolocator/geolocator.dart';

/// Why the phone's position could not be used.
enum LocationProblem { serviceOff, denied, deniedForever, outsideTajikistan, failed }

class LocationException implements Exception {
  const LocationException(this.problem);
  final LocationProblem problem;
}

/// Approximate centres of the cities in the region directory. Used only to
/// pick the nearest city for the user's position; no map data is bundled.
const Map<String, (double, double)> cityCentres = {
  'dushanbe': (38.5598, 68.7870),
  'vahdat': (38.5560, 69.0140),
  'tursunzoda': (38.5120, 68.2310),
  'hisor': (38.5260, 68.5510),
  'roghun': (38.6930, 69.7830),
  'khujand': (40.2830, 69.6220),
  'istaravshan': (39.9110, 69.0000),
  'isfara': (40.1260, 70.6250),
  'konibodom': (40.2930, 70.4260),
  'panjakent': (39.4960, 67.6090),
  'buston': (40.2290, 69.7000),
  'guliston': (40.2740, 69.8180),
  'bokhtar': (37.8360, 68.7810),
  'kulob': (37.9120, 69.7840),
  'norak': (38.3880, 69.3200),
  'levakant': (37.8640, 68.9200),
  'khorugh': (37.4890, 71.5530),
};

/// Distance in kilometres (haversine).
double distanceKm((double, double) a, (double, double) b) {
  const r = 6371.0;
  double rad(double d) => d * math.pi / 180;
  final dLat = rad(b.$1 - a.$1);
  final dLng = rad(b.$2 - a.$2);
  final h = math.pow(math.sin(dLat / 2), 2) +
      math.cos(rad(a.$1)) * math.cos(rad(b.$1)) * math.pow(math.sin(dLng / 2), 2);
  return 2 * r * math.asin(math.sqrt(h));
}

/// The directory city nearest to [position], or null when the position is
/// outside Tajikistan (further than 250 km from every listed city).
String? nearestCityId((double, double) position) {
  String? best;
  var bestKm = double.infinity;
  for (final e in cityCentres.entries) {
    final km = distanceKm(position, e.value);
    if (km < bestKm) {
      bestKm = km;
      best = e.key;
    }
  }
  return bestKm <= 250 ? best : null;
}

/// Reads the phone's position after asking for permission.
abstract final class DeviceLocation {
  static Future<(double, double)> current({bool precise = false}) async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const LocationException(LocationProblem.serviceOff);
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.deniedForever) {
      throw const LocationException(LocationProblem.deniedForever);
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.unableToDetermine) {
      throw const LocationException(LocationProblem.denied);
    }
    try {
      final p = await Geolocator.getCurrentPosition(
        locationSettings: LocationSettings(
          accuracy: precise ? LocationAccuracy.high : LocationAccuracy.low,
          timeLimit: const Duration(seconds: 20),
        ),
      );
      return (p.latitude, p.longitude);
    } catch (_) {
      final last = await Geolocator.getLastKnownPosition();
      if (last != null) return (last.latitude, last.longitude);
      throw const LocationException(LocationProblem.failed);
    }
  }

  /// The nearest directory city for the phone's position.
  static Future<String> nearestCity() async {
    final id = nearestCityId(await current());
    if (id == null) throw const LocationException(LocationProblem.outsideTajikistan);
    return id;
  }

  static Future<void> openSettings() => Geolocator.openAppSettings();
}

/// Stored form of a map point: "38.55980,68.78700".
String formatGeoPoint((double, double) p) =>
    '${p.$1.toStringAsFixed(5)},${p.$2.toStringAsFixed(5)}';

(double, double)? parseGeoPoint(Object? value) {
  final m = RegExp(r'^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$').firstMatch('${value ?? ''}');
  if (m == null) return null;
  final lat = double.parse(m.group(1)!);
  final lng = double.parse(m.group(2)!);
  if (lat.abs() > 90 || lng.abs() > 180) return null;
  return (lat, lng);
}

Uri mapLink((double, double) p) =>
    Uri.parse('https://www.google.com/maps/search/?api=1&query=${p.$1},${p.$2}');
