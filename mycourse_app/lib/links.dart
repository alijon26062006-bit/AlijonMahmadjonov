/// Какие адреса открываются внутри приложения, а какие — снаружи.
///
/// Адрес сайта можно заменить при сборке:
/// `flutter build apk --dart-define=START_URL=https://mycourse.tj/`
library;

const String kStartUrl = String.fromEnvironment(
  'START_URL',
  defaultValue: 'https://beta.mycourse.tj/',
);

/// Что делать со ссылкой, по которой переходит пользователь.
enum LinkAction {
  /// Открыть в приложении (сам сайт курса).
  inside,

  /// Отдать системе: браузер, Telegram, почта, звонок и т. п.
  external,
}

/// Решает, где открыть [uri]. [isMainFrame] — переход всей страницы, а не
/// встроенного окна (например, видео YouTube внутри урока).
LinkAction decide(Uri uri, {required bool isMainFrame, Uri? start}) {
  // встроенные окна (iframe) — видео и т. п. — всегда внутри страницы
  if (!isMainFrame) return LinkAction.inside;
  switch (uri.scheme) {
    case 'about':
    case 'data':
    case 'blob':
    case 'javascript':
      return LinkAction.inside;
    case 'http':
    case 'https':
      final home = start ?? Uri.parse(kStartUrl);
      return uri.host == home.host ? LinkAction.inside : LinkAction.external;
    default: // tel:, mailto:, tg:, intent: …
      return LinkAction.external;
  }
}
