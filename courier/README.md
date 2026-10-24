# Зуд Курьер

Приложение курьера: смена «на линии», свободные заказы рядом со звуком, доставка по шагам
(магазин → забрал → покупатель → код), наличные, доход за день, неделю и месяц.

Сейчас работает в браузере по адресу `/courier/` (ставится на телефон как приложение).

## Как потом сделать APK, ничего не переписывая

Папка уже готова: все пути относительные, библиотеки лежат внутри (`js/vendor`), а всё,
что зависит от телефона, собрано в одном файле `js/platform.js` — он сам берёт нативные плагины, если они есть.

```bash
npm i @capacitor/core @capacitor/cli @capacitor/android
npx cap init "Зуд Курьер" tj.zud.courier --web-dir courier
npm i @capacitor/geolocation @capacitor-community/background-geolocation @capacitor/haptics \
      @capacitor-community/keep-awake @capacitor/local-notifications @capacitor/app-launcher \
      @capacitor/clipboard @capacitor/app
npx cap add android && npx cap sync && npx cap open android   # в Android Studio: Build → APK
```

Что даст APK сверх браузера: место курьера идёт и с выключенным экраном, уведомление
о новом заказе приходит, даже если приложение свёрнуто, навигатор открывается напрямую.
