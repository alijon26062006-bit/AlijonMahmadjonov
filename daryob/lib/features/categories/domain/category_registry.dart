import '../../../shared/models/category.dart';

/// In-memory index of categories with parent/child navigation.
///
/// Built from whatever source provides categories (bundled list today,
/// the API later). Adding a category means adding data, not code.
class CategoryRegistry {
  CategoryRegistry(Iterable<CategoryDefinition> categories) {
    for (final c in categories) {
      if (_byId.containsKey(c.id)) {
        throw ArgumentError('Duplicate category id "${c.id}"');
      }
      if (_bySlug.containsKey(c.slug)) {
        throw ArgumentError('Duplicate category slug "${c.slug}"');
      }
      _byId[c.id] = c;
      _bySlug[c.slug] = c;
    }
  }

  final Map<String, CategoryDefinition> _byId = {};
  final Map<String, CategoryDefinition> _bySlug = {};

  List<CategoryDefinition> get all => _sorted(_byId.values);

  List<CategoryDefinition> get topLevel =>
      _sorted(_byId.values.where((c) => c.isTopLevel && c.isActive));

  CategoryDefinition? byId(String? id) => id == null ? null : _byId[id];

  CategoryDefinition? bySlug(String slug) => _bySlug[slug];

  List<CategoryDefinition> childrenOf(String id) =>
      _sorted(_byId.values.where((c) => c.parentId == id && c.isActive));

  /// The category and every descendant id — used when filtering listings by a
  /// parent category.
  Set<String> subtreeIds(String id) {
    final result = <String>{id};
    for (final child in childrenOf(id)) {
      result.addAll(subtreeIds(child.id));
    }
    return result;
  }

  /// Path from the top-level category down to [id].
  List<CategoryDefinition> pathTo(String id) {
    final path = <CategoryDefinition>[];
    var current = _byId[id];
    while (current != null) {
      path.insert(0, current);
      current = current.parentId == null ? null : _byId[current.parentId];
    }
    return path;
  }

  static List<CategoryDefinition> _sorted(Iterable<CategoryDefinition> items) =>
      items.toList()..sort((a, b) => a.order.compareTo(b.order));
}
