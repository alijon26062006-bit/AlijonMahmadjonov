# Donatix — Android-приложение

Небольшое приложение (≈30 КБ): открывает https://donatix.tj как настоящее приложение.

- **Есть Chrome (почти у всех):** Trusted Web Activity — без адресной строки, с push-уведомлениями
  (после того как на сервер добавлены пакет и отпечаток ключа, см. ниже).
- **Нет Chrome:** своё окно (WebView) — вход, покупки, фото чека из галереи/камеры, «Назад», ссылки в Telegram.
- Иконка и заставка Donatix, ссылки `https://donatix.tj/...` открываются в приложении.

## Подписать готовый APK (2 минуты, нужен Android SDK build-tools)

```bash
# 1. Один раз создать ключ подписи. ХРАНИТЬ ФАЙЛ И ПАРОЛЬ — без них нельзя выпустить обновление.
keytool -genkeypair -v -keystore donatix-release.jks -alias donatix -keyalg RSA -keysize 2048 -validity 10950

# 2. Подписать
apksigner sign --ks donatix-release.jks --ks-key-alias donatix --out donatix.apk donatix-unsigned.apk
apksigner verify --print-certs donatix.apk

# 3. Отпечаток для сервера
keytool -list -v -keystore donatix-release.jks -alias donatix | grep SHA256
```

## На сервере (donatix/.env), затем `sudo systemctl restart donatix`

```
DONATIX_ANDROID_PACKAGE=tj.donatix.app
DONATIX_ANDROID_SHA256=AB:CD:...   (отпечаток из шага 3)
```

## Пересобрать из исходников
`build.sh` (без Android Studio) или любой Android-проект: `src/`, `res/`, `AndroidManifest.xml`.
Новая версия: увеличить `android:versionCode` в `AndroidManifest.xml`.
