import '../../../shared/models/region.dart';
import '../data/tajikistan_regions.dart';

/// Lookup and hierarchy helpers over the region list.
class RegionDirectory {
  RegionDirectory(Iterable<Region> regions) {
    for (final r in regions) {
      _byId[r.id] = r;
    }
  }

  final Map<String, Region> _byId = {};

  Region get country => _byId[RegionIds.country]!;

  Region? byId(String? id) => id == null ? null : _byId[id];

  List<Region> childrenOf(String id) =>
      _byId.values.where((r) => r.parentId == id).toList();

  /// First-level units (Dushanbe, RRP, Sughd, Khatlon, GBAO).
  List<Region> get topLevel => childrenOf(RegionIds.country);

  /// The region and every unit inside it.
  Set<String> subtreeIds(String id) {
    final result = <String>{id};
    for (final child in childrenOf(id)) {
      result.addAll(subtreeIds(child.id));
    }
    return result;
  }

  /// True when [candidateId] is [ancestorId] or lies inside it.
  /// "All Tajikistan" contains everything.
  bool contains(String ancestorId, String candidateId) {
    if (ancestorId == RegionIds.country) return true;
    String? current = candidateId;
    while (current != null) {
      if (current == ancestorId) return true;
      current = _byId[current]?.parentId;
    }
    return false;
  }

  /// Country → … → [id], without the country node.
  List<Region> pathTo(String id) {
    final path = <Region>[];
    var current = _byId[id];
    while (current != null && current.level != RegionLevel.country) {
      path.insert(0, current);
      current = current.parentId == null ? null : _byId[current.parentId];
    }
    return path;
  }

  /// First-level unit containing [id], used for "nearby" matching.
  Region? topLevelOf(String id) {
    final path = pathTo(id);
    return path.isEmpty ? null : path.first;
  }
}
