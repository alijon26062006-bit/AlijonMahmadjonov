import '../../../core/storage/local_database.dart';

class SearchHistoryRepository {
  SearchHistoryRepository(LocalDatabase database)
    : _store = database.collection(Collections.searchHistory);

  static const _key = 'recent';
  static const maxItems = 12;

  final JsonCollection _store;

  List<String> load() =>
      List<String>.from(_store.get(_key)?['items'] as List? ?? const []);

  Future<List<String>> add(String phrase) async {
    final clean = phrase.trim();
    if (clean.isEmpty) return load();
    final items = load()
      ..removeWhere((p) => p.toLowerCase() == clean.toLowerCase());
    final next = [clean, ...items].take(maxItems).toList();
    await _store.put(_key, {'items': next});
    return next;
  }

  Future<List<String>> remove(String phrase) async {
    final next = load()..remove(phrase);
    await _store.put(_key, {'items': next});
    return next;
  }

  Future<void> clear() => _store.delete(_key);
}
