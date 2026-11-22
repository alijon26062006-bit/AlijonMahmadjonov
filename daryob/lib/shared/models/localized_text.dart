import 'package:flutter/widgets.dart';

/// Text that exists in both app languages. Used for data that may later come
/// from the server (category names, regions, schema labels), unlike UI
/// strings which live in ARB files.
@immutable
class LocalizedText {
  const LocalizedText({required this.ru, required this.tg});

  final String ru;
  final String tg;

  String resolve(Locale locale) => byCode(locale.languageCode);

  String byCode(String languageCode) => languageCode == 'tg' ? tg : ru;

  Map<String, dynamic> toJson() => {'ru': ru, 'tg': tg};

  factory LocalizedText.fromJson(Map<String, dynamic> json) => LocalizedText(
    ru: json['ru'] as String? ?? '',
    tg: json['tg'] as String? ?? json['ru'] as String? ?? '',
  );

  @override
  bool operator ==(Object other) =>
      other is LocalizedText && other.ru == ru && other.tg == tg;

  @override
  int get hashCode => Object.hash(ru, tg);
}

extension LocalizedTextContext on LocalizedText {
  String of(BuildContext context) => resolve(Localizations.localeOf(context));
}
