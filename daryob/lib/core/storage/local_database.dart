import 'dart:convert';

import 'package:hive_ce/hive_ce.dart';

/// Names of the local collections. One Hive box per collection.
abstract final class Collections {
  static const settings = 'settings';
  static const listings = 'listings';
  static const drafts = 'drafts';
  static const favorites = 'favorites';
  static const searchHistory = 'search_history';
  static const users = 'users';
  static const conversations = 'conversations';
  static const messages = 'messages';
  static const notifications = 'notifications';
  static const businesses = 'businesses';
  static const reports = 'reports';
  static const meta = 'meta';
  static const catalog = 'catalog';

  static const all = [
    settings,
    listings,
    drafts,
    favorites,
    searchHistory,
    users,
    conversations,
    messages,
    notifications,
    businesses,
    reports,
    meta,
    catalog,
  ];
}

/// A collection of JSON documents keyed by id.
///
/// Documents are stored as JSON strings so nothing depends on Hive type
/// adapters and the same data can later be sent to the API unchanged.
abstract interface class JsonCollection {
  Map<String, dynamic>? get(String id);
  Iterable<Map<String, dynamic>> values();
  Iterable<String> get keys;
  Future<void> put(String id, Map<String, dynamic> document);
  Future<void> delete(String id);
  Future<void> clear();
}

abstract interface class LocalDatabase {
  JsonCollection collection(String name);
  Future<void> clearAll();
}

class HiveLocalDatabase implements LocalDatabase {
  HiveLocalDatabase._(this._boxes);

  final Map<String, Box<String>> _boxes;

  /// Hive must be initialised (`Hive.init` / `Hive.initFlutter`) first.
  static Future<HiveLocalDatabase> open() async {
    final boxes = <String, Box<String>>{};
    for (final name in Collections.all) {
      boxes[name] = await Hive.openBox<String>(name);
    }
    return HiveLocalDatabase._(boxes);
  }

  @override
  JsonCollection collection(String name) {
    final box = _boxes[name];
    if (box == null) {
      throw StateError(
        'Unknown collection "$name". Add it to Collections.all.',
      );
    }
    return _HiveCollection(box);
  }

  @override
  Future<void> clearAll() async {
    for (final box in _boxes.values) {
      await box.clear();
    }
  }
}

class _HiveCollection implements JsonCollection {
  _HiveCollection(this._box);
  final Box<String> _box;

  Map<String, dynamic>? _decode(String? raw) {
    if (raw == null) return null;
    try {
      return jsonDecode(raw) as Map<String, dynamic>;
    } on FormatException {
      return null; // A corrupted document is skipped, not fatal.
    }
  }

  @override
  Map<String, dynamic>? get(String id) => _decode(_box.get(id));

  @override
  Iterable<Map<String, dynamic>> values() =>
      _box.values.map(_decode).whereType<Map<String, dynamic>>();

  @override
  Iterable<String> get keys => _box.keys.cast<String>();

  @override
  Future<void> put(String id, Map<String, dynamic> document) =>
      _box.put(id, jsonEncode(document));

  @override
  Future<void> delete(String id) => _box.delete(id);

  @override
  Future<void> clear() => _box.clear();
}

/// In-memory database for tests and previews.
class MemoryLocalDatabase implements LocalDatabase {
  final Map<String, _MemoryCollection> _collections = {};

  @override
  JsonCollection collection(String name) =>
      _collections.putIfAbsent(name, _MemoryCollection.new);

  @override
  Future<void> clearAll() async {
    for (final c in _collections.values) {
      await c.clear();
    }
  }
}

class _MemoryCollection implements JsonCollection {
  final Map<String, String> _data = {};

  @override
  Map<String, dynamic>? get(String id) {
    final raw = _data[id];
    return raw == null ? null : jsonDecode(raw) as Map<String, dynamic>;
  }

  @override
  Iterable<Map<String, dynamic>> values() =>
      _data.values.map((raw) => jsonDecode(raw) as Map<String, dynamic>);

  @override
  Iterable<String> get keys => _data.keys;

  @override
  Future<void> put(String id, Map<String, dynamic> document) async {
    _data[id] = jsonEncode(document);
  }

  @override
  Future<void> delete(String id) async => _data.remove(id);

  @override
  Future<void> clear() async => _data.clear();
}
