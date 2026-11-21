import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import 'package:mycourse_beta/links.dart';
import 'package:mycourse_beta/main.dart';

void main() {
  group('ссылки', () {
    final home = Uri.parse('https://beta.mycourse.tj/');
    LinkAction go(String url, {bool main = true}) => decide(Uri.parse(url), isMainFrame: main, start: home);

    test('страницы сайта курса — внутри приложения', () {
      expect(go('https://beta.mycourse.tj/learn/22?step=hw'), LinkAction.inside);
      expect(go('https://beta.mycourse.tj/profile'), LinkAction.inside);
    });

    test('другие сайты и приложения — снаружи', () {
      expect(go('https://t.me/mycourse_tj'), LinkAction.external);
      expect(go('https://www.youtube.com/watch?v=x'), LinkAction.external);
      expect(go('https://mycourse.tj/'), LinkAction.external);
      expect(go('tel:+992900000000'), LinkAction.external);
      expect(go('mailto:info@example.com'), LinkAction.external);
    });

    test('встроенные окна (видео в уроке) и служебные адреса — внутри', () {
      expect(go('https://www.youtube.com/embed/x', main: false), LinkAction.inside);
      expect(go('about:blank'), LinkAction.inside);
      expect(go('blob:https://beta.mycourse.tj/1'), LinkAction.inside);
    });

    test('по умолчанию приложение открывает beta.mycourse.tj', () {
      expect(Uri.parse(kStartUrl).host, 'beta.mycourse.tj');
    });
  });

  testWidgets('экран «нет интернета»: текст и кнопка повтора', (tester) async {
    var retried = 0;
    await tester.pumpWidget(MyCourseApp(home: Scaffold(body: OfflineView(onRetry: () => retried++))));
    expect(find.text('Интернет нест'), findsOneWidget);
    await tester.tap(find.text('Аз нав кӯшиш кунед'));
    expect(retried, 1);
  });
}
