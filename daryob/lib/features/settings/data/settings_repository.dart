import '../../../core/storage/local_database.dart';
import '../domain/app_settings.dart';

class SettingsRepository {
  SettingsRepository(LocalDatabase database)
    : _store = database.collection(Collections.settings);

  static const _key = 'app';
  final JsonCollection _store;

  AppSettings load() {
    final json = _store.get(_key);
    return json == null ? const AppSettings() : AppSettings.fromJson(json);
  }

  Future<void> save(AppSettings settings) =>
      _store.put(_key, settings.toJson());
}
