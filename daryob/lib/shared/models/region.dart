import 'package:flutter/foundation.dart';

import 'localized_text.dart';

enum RegionLevel { country, region, city, district, settlement }

/// A node of the administrative hierarchy:
/// Country → Region → City/District → Settlement.
@immutable
class Region {
  const Region({
    required this.id,
    required this.level,
    required this.name,
    this.parentId,
    this.isRegionalCenter = false,
    this.latitude,
    this.longitude,
  });

  final String id;
  final String? parentId;
  final RegionLevel level;
  final LocalizedText name;
  final bool isRegionalCenter;

  /// Optional coordinates for future map features.
  final double? latitude;
  final double? longitude;
}
