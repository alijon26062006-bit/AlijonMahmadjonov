# MyCourse Beta — Android-приложение

Бета-версия приложения для **beta.mycourse.tj** на Flutter. Внутри — сам сайт курса
(WebView), поэтому вход, уроки, ДЗ, рейтинг и геймификация работают так же, как на сайте,
и обновляются вместе с ним без новой сборки приложения.

## Что умеет

- открывает `https://beta.mycourse.tj/` (адрес меняется при сборке: `--dart-define=START_URL=...`);
- ссылки на другие сайты, Telegram, почту и звонки открываются в своих приложениях;
- кнопка «Назад» на телефоне — назад по сайту, на первой странице — выход;
- полоска загрузки сверху, экран «Интернет нест» с кнопкой «Аз нав кӯшиш кунед»;
- загрузка файлов с сайта (`<input type="file">`, например фото профиля);
- видео в уроке — во весь экран;
- иконка и тёмный экран запуска в цветах mycourse.tj;
- к User-Agent добавлено `MyCourseApp/beta` — сайт может понять, что открыт из приложения.

## Сборка

```bash
cd mycourse_app
flutter pub get
flutter analyze && flutter test
flutter build apk --release        # → build/app/outputs/flutter-apk/app-release.apk
```

На GitHub сборку делает `.github/workflows/mycourse-apk.yml`: при каждом изменении в
`mycourse_app/` собирается APK и выкладывается пре-релизом `apk-beta-N` во вкладке **Releases**.

## Подпись

Без ключа релиз подписывается отладочным ключом: каждая сборка на GitHub получает новый
ключ, поэтому новую версию можно поставить только после удаления старой.

Чтобы обновления ставились поверх, добавьте в **Settings → Secrets and variables → Actions**:

| Секрет | Что это |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | файл ключа `.jks` в base64 (`base64 -w0 upload-keystore.jks`) |
| `ANDROID_KEYSTORE_PASSWORD` | пароль хранилища |
| `ANDROID_KEY_ALIAS` | имя ключа |
| `ANDROID_KEY_PASSWORD` | пароль ключа |

Локально — файл `android/key.properties` (в git не попадает):

```
storeFile=upload-keystore.jks
storePassword=...
keyAlias=...
keyPassword=...
```

## Чего пока нет

- push-уведомлений и работы без интернета — это следующий шаг;
- iOS-версии — нужен Mac и аккаунт Apple Developer.
