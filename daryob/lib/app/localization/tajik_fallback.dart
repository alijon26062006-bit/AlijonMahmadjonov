import 'package:cupertino_ui/cupertino_ui.dart';
import 'package:flutter/foundation.dart';
import 'package:material_ui/material_ui.dart';

/// Flutter ships no built-in Material/Cupertino strings for Tajik ("tg").
/// These delegates serve the Russian system strings (date pickers, "Paste",
/// "Back" tooltips) when the app language is Tajik. All DARYOB texts are
/// still Tajik — they come from our own ARB files.
const List<LocalizationsDelegate<dynamic>> tajikFallbackDelegates = [
  _TgMaterialDelegate(),
  _TgCupertinoDelegate(),
  _TgWidgetsDelegate(),
];

const Locale _fallback = Locale('ru');

class _TgMaterialDelegate extends LocalizationsDelegate<MaterialLocalizations> {
  const _TgMaterialDelegate();

  @override
  bool isSupported(Locale locale) => locale.languageCode == 'tg';

  @override
  Future<MaterialLocalizations> load(Locale locale) =>
      GlobalMaterialLocalizations.delegate.load(_fallback);

  @override
  bool shouldReload(_TgMaterialDelegate old) => false;
}

class _TgCupertinoDelegate
    extends LocalizationsDelegate<CupertinoLocalizations> {
  const _TgCupertinoDelegate();

  @override
  bool isSupported(Locale locale) => locale.languageCode == 'tg';

  @override
  Future<CupertinoLocalizations> load(Locale locale) =>
      GlobalCupertinoLocalizations.delegate.load(_fallback);

  @override
  bool shouldReload(_TgCupertinoDelegate old) => false;
}

class _TgWidgetsDelegate extends LocalizationsDelegate<WidgetsLocalizations> {
  const _TgWidgetsDelegate();

  @override
  bool isSupported(Locale locale) => locale.languageCode == 'tg';

  @override
  Future<WidgetsLocalizations> load(Locale locale) =>
      SynchronousFuture(const _LtrWidgetsLocalizations());

  @override
  bool shouldReload(_TgWidgetsDelegate old) => false;
}

class _LtrWidgetsLocalizations extends DefaultWidgetsLocalizations {
  const _LtrWidgetsLocalizations();
}
