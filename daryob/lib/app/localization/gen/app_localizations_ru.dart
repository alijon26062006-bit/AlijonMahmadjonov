// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Russian (`ru`).
class AppLocalizationsRu extends AppLocalizations {
  AppLocalizationsRu([String locale = 'ru']) : super(locale);

  @override
  String get appName => 'DARYOB';

  @override
  String get brandSlogan => 'Ищи. Находи. Покупай.';

  @override
  String get retry => 'Повторить';

  @override
  String get cancel => 'Отмена';

  @override
  String get save => 'Сохранить';

  @override
  String get saveChanges => 'Сохранить изменения';

  @override
  String get delete => 'Удалить';

  @override
  String get edit => 'Изменить';

  @override
  String get close => 'Закрыть';

  @override
  String get next => 'Далее';

  @override
  String get back => 'Назад';

  @override
  String get continueAction => 'Продолжить';

  @override
  String get done => 'Готово';

  @override
  String get ok => 'Понятно';

  @override
  String get yes => 'Да';

  @override
  String get no => 'Нет';

  @override
  String get seeAll => 'Все';

  @override
  String get all => 'Все';

  @override
  String get clear => 'Очистить';

  @override
  String get reset => 'Сбросить';

  @override
  String get confirm => 'Подтвердить';

  @override
  String get more => 'Ещё';

  @override
  String get share => 'Поделиться';

  @override
  String get skip => 'Пропустить';

  @override
  String get search => 'Поиск';

  @override
  String get send => 'Отправить';

  @override
  String get publish => 'Опубликовать';

  @override
  String get switchLanguage => 'Сменить язык';

  @override
  String get tabHome => 'Главная';

  @override
  String get tabFavorites => 'Избранное';

  @override
  String get tabCreate => 'Подать';

  @override
  String get tabChats => 'Чаты';

  @override
  String get tabProfile => 'Профиль';

  @override
  String get onboardingWelcomeTitle => 'Всё, что нужно, рядом';

  @override
  String get onboardingWelcomeBody =>
      'Покупайте и продавайте по всему Таджикистану.';

  @override
  String get onboardingSellTitle => 'Продавайте легко';

  @override
  String get onboardingSellBody =>
      'Сфотографируйте вещь, добавьте цену и опубликуйте объявление за пару минут.';

  @override
  String get onboardingNearbyTitle => 'Находите предложения рядом';

  @override
  String get onboardingNearbyBody =>
      'Выберите свой город — мы покажем объявления поблизости.';

  @override
  String get languageChangeLater =>
      'Язык можно изменить в любой момент в профиле.';

  @override
  String get onboardingCityTitle => 'Где вы находитесь?';

  @override
  String get onboardingCityBody =>
      'Город нужен, чтобы показывать объявления рядом. Местоположение телефона не запрашивается.';

  @override
  String get otherCity => 'Другой город или район';

  @override
  String get startUsing => 'Начать';

  @override
  String get searchHint => 'Что вы ищете?';

  @override
  String get heroTitle => 'Находите лучшее рядом';

  @override
  String get heroSubtitle => 'Объявления по всему Таджикистану';

  @override
  String get createListing => 'Подать объявление';

  @override
  String get categories => 'Категории';

  @override
  String get allCategories => 'Все категории';

  @override
  String get vipListings => 'VIP объявления';

  @override
  String get recommended => 'Рекомендуем вам';

  @override
  String get newListings => 'Новые объявления';

  @override
  String nearbyIn(String name) {
    return 'Рядом: $name';
  }

  @override
  String get noListingsYet => 'Объявлений пока нет';

  @override
  String get noListingsYetBody => 'Станьте первым — подайте объявление.';

  @override
  String get loadMore => 'Показать ещё';

  @override
  String get loadMoreFailed => 'Не удалось загрузить. Повторить';

  @override
  String get endOfList => 'Это все объявления';

  @override
  String get notifications => 'Уведомления';

  @override
  String get priceFree => 'Бесплатно';

  @override
  String get priceOnRequest => 'Цена договорная';

  @override
  String get negotiable => 'Торг уместен';

  @override
  String get favoriteAdd => 'Добавить в избранное';

  @override
  String get favoriteRemove => 'Убрать из избранного';

  @override
  String get favoriteAdded => 'Добавлено в избранное';

  @override
  String get favoriteRemoved => 'Убрано из избранного';

  @override
  String get demoBadgeDescription => 'Демонстрационные данные';

  @override
  String get noPhotos => 'Фото не добавлены';

  @override
  String photoOf(int index, int total) {
    return 'Фото $index из $total';
  }

  @override
  String get listingNotFound => 'Объявление не найдено';

  @override
  String get listingNotFoundBody =>
      'Возможно, его удалили или сняли с публикации.';

  @override
  String get demoListingNotice =>
      'Это демонстрационное объявление для проверки приложения. Это не реальное предложение.';

  @override
  String get localListingNotice =>
      'Объявление сохранено только на этом телефоне: сервер ещё не подключён, другие люди его не видят.';

  @override
  String publishedOn(String date) {
    return 'Опубликовано $date';
  }

  @override
  String listingNumber(String number) {
    return 'Объявление № $number';
  }

  @override
  String views(int count) {
    return 'Просмотров: $count';
  }

  @override
  String get viewsLabel => 'Просмотры';

  @override
  String get description => 'Описание';

  @override
  String get characteristics => 'Характеристики';

  @override
  String get category => 'Категория';

  @override
  String get seller => 'Продавец';

  @override
  String memberSince(String date) {
    return 'На DARYOB с $date';
  }

  @override
  String get verifiedSeller => 'Проверенный продавец';

  @override
  String get sellerBusiness => 'Компания';

  @override
  String get sellerPrivate => 'Частное лицо';

  @override
  String get safetyTipShort =>
      'Не переводите предоплату незнакомым людям. Проверяйте товар при встрече.';

  @override
  String get reportListing => 'Пожаловаться';

  @override
  String get moreFromSeller => 'Другие объявления продавца';

  @override
  String get similarListings => 'Похожие объявления';

  @override
  String get sharedFromDaryob => 'Найдено в DARYOB';

  @override
  String get yourListing => 'Ваше объявление';

  @override
  String get promote => 'Продвинуть';

  @override
  String get markSold => 'Продано';

  @override
  String get archive => 'В архив';

  @override
  String get republish => 'Опубликовать снова';

  @override
  String get phoneHidden => 'Номер скрыт';

  @override
  String get showPhone => 'Показать номер';

  @override
  String get call => 'Позвонить';

  @override
  String get callFailed => 'Не удалось открыть звонилку';

  @override
  String get writeMessage => 'Написать';

  @override
  String get listingNotAvailable => 'Объявление сейчас неактивно';

  @override
  String get chatOwnListing => 'Это ваше объявление';

  @override
  String statusChangedTo(String status) {
    return 'Статус: $status';
  }

  @override
  String get deleteListingTitle => 'Удалить объявление?';

  @override
  String get deleteListingBody =>
      'Объявление будет удалено без возможности восстановления.';

  @override
  String get listingDeleted => 'Объявление удалено';

  @override
  String get reportTitle => 'Жалоба на объявление';

  @override
  String get reportBody => 'Выберите причину. Модераторы проверят объявление.';

  @override
  String get reportFraud => 'Мошенничество';

  @override
  String get reportProhibited => 'Запрещённый товар';

  @override
  String get reportWrongCategory => 'Неверная категория';

  @override
  String get reportDuplicate => 'Повторное объявление';

  @override
  String get reportSold => 'Уже продано';

  @override
  String get reportOffensive => 'Оскорбительное содержание';

  @override
  String get reportOther => 'Другое';

  @override
  String get reportCommentHint => 'Комментарий (необязательно)';

  @override
  String get reportSend => 'Отправить жалобу';

  @override
  String get reportSent => 'Жалоба отправлена';

  @override
  String get reportSavedLocally =>
      'Жалоба сохранена на телефоне — сервер модерации ещё не подключён';

  @override
  String get reportUser => 'Пожаловаться на пользователя';

  @override
  String get reportUserBody =>
      'Сообщить модераторам о подозрительном поведении собеседника?';

  @override
  String listingsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count объявления',
      many: '$count объявлений',
      few: '$count объявления',
      one: '$count объявление',
    );
    return '$_temp0';
  }

  @override
  String get categoryNotFound => 'Категория не найдена';

  @override
  String get nothingFound => 'Ничего не найдено';

  @override
  String get nothingFoundBody =>
      'Попробуйте изменить запрос, город или фильтры.';

  @override
  String get resetFilters => 'Сбросить фильтры';

  @override
  String get filters => 'Фильтры';

  @override
  String get location => 'Местоположение';

  @override
  String get chooseLocation => 'Выберите город или район';

  @override
  String wholeRegion(String name) {
    return 'Весь регион: $name';
  }

  @override
  String get priceRange => 'Цена, сомони';

  @override
  String get priceFrom => 'от';

  @override
  String get priceTo => 'до';

  @override
  String get sortBy => 'Сортировка';

  @override
  String get sortRelevance => 'Сначала подходящие';

  @override
  String get sortNewest => 'Сначала новые';

  @override
  String get sortPriceAsc => 'Сначала дешёвые';

  @override
  String get sortPriceDesc => 'Сначала дорогие';

  @override
  String get showResults => 'Показать';

  @override
  String get recentSearches => 'Недавние запросы';

  @override
  String get clearHistory => 'Очистить';

  @override
  String get searchByCategory => 'Искать в категории';

  @override
  String priceFilterChip(String from, String to) {
    return 'Цена: $from – $to';
  }

  @override
  String resultsCount(int count) {
    return 'Найдено: $count';
  }

  @override
  String get favoritesEmpty => 'В избранном пусто';

  @override
  String get favoritesEmptyBody =>
      'Нажмите ♡ на объявлении, чтобы сохранить его здесь.';

  @override
  String get browseListings => 'Смотреть объявления';

  @override
  String get favoritesGuestNotice =>
      'Избранное хранится на этом телефоне. Войдите, чтобы привязать его к аккаунту.';

  @override
  String get editListing => 'Редактирование';

  @override
  String stepOf(int current, int total, String title) {
    return 'Шаг $current из $total: $title';
  }

  @override
  String get stepCategory => 'Категория';

  @override
  String get stepBasics => 'Основное';

  @override
  String get stepPhotos => 'Фото';

  @override
  String get stepLocation => 'Место';

  @override
  String get stepContact => 'Контакты';

  @override
  String get stepPreview => 'Проверка';

  @override
  String get chooseCategoryError => 'Выберите категорию объявления';

  @override
  String get fieldTitle => 'Заголовок';

  @override
  String get fieldTitleHint => 'Например: диван раскладной, почти новый';

  @override
  String get fieldDescriptionHint => 'Состояние, особенности, причина продажи';

  @override
  String get price => 'Цена';

  @override
  String get priceOptionalHint => 'Можно не указывать';

  @override
  String get negotiableHint => 'Покупатели увидят, что цену можно обсудить';

  @override
  String get freeCategoryNotice =>
      'В этой категории вещи отдают бесплатно — цена не нужна.';

  @override
  String get photos => 'Фото';

  @override
  String get photosTip =>
      'Объявления с хорошими фото находят покупателя быстрее. Первое фото станет обложкой.';

  @override
  String get photoFromGallery => 'Из галереи';

  @override
  String get photoFromCamera => 'Сделать фото';

  @override
  String photosCounter(int count, int max) {
    return 'Фото: $count из $max';
  }

  @override
  String get photosReorderHint => 'Порядок можно менять стрелками';

  @override
  String get photoCover => 'Обложка';

  @override
  String photoNumber(int n) {
    return 'Фото $n';
  }

  @override
  String get photoPickFailed =>
      'Не удалось добавить фото. Проверьте разрешения.';

  @override
  String get moveUp => 'Выше';

  @override
  String get moveDown => 'Ниже';

  @override
  String get addressNote => 'Уточнение адреса';

  @override
  String get addressNoteHint => 'Например: рядом с рынком «Корвон»';

  @override
  String get addressPrivacyNote =>
      'Не указывайте номер квартиры — точный адрес лучше сообщить в переписке.';

  @override
  String get contactName => 'Имя';

  @override
  String get contactPhone => 'Номер телефона';

  @override
  String get phoneVisibility => 'Номер в объявлении';

  @override
  String get phoneVisible => 'Показывать номер';

  @override
  String get phoneVisibleHint =>
      'Номер откроется после нажатия «Показать номер»';

  @override
  String get phoneHiddenOption => 'Скрыть номер';

  @override
  String get phoneHiddenHint => 'Связь только через чат';

  @override
  String get chatEnabled => 'Сообщения в чате';

  @override
  String get chatEnabledHint => 'Покупатели смогут написать вам в приложении';

  @override
  String get contactMethodError =>
      'Оставьте хотя бы один способ связи: номер или чат.';

  @override
  String get contacts => 'Контакты';

  @override
  String get previewNotice =>
      'Так покупатели увидят ваше объявление. Проверьте всё перед публикацией.';

  @override
  String get localPublishNotice =>
      'Демо-режим: объявление сохранится только на этом телефоне.';

  @override
  String get draftResumed =>
      'Продолжаем ваш черновик — он сохраняется автоматически.';

  @override
  String get fixErrors => 'Проверьте отмеченные поля';

  @override
  String get changesSaved => 'Изменения сохранены';

  @override
  String get startNew => 'Новое объявление';

  @override
  String get startNewTitle => 'Начать новое объявление?';

  @override
  String get startNewBody => 'Текущий черновик останется в «Моих черновиках».';

  @override
  String get myDrafts => 'Мои черновики';

  @override
  String get publishedTitle => 'Объявление опубликовано!';

  @override
  String get publishedBody => 'Покупатели уже могут его найти.';

  @override
  String get publishedLocalBody =>
      'Демо-режим: объявление сохранено на этом телефоне и видно только вам.';

  @override
  String get openListing => 'Открыть объявление';

  @override
  String get myListings => 'Мои объявления';

  @override
  String get createAnother => 'Подать ещё одно';

  @override
  String get draftsEmpty => 'Черновиков нет';

  @override
  String get draftsEmptyBody =>
      'Незаконченные объявления сохраняются здесь автоматически.';

  @override
  String get untitledDraft => 'Без названия';

  @override
  String get editingDraft => 'Правка объявления';

  @override
  String savedAt(String date) {
    return 'сохранено $date';
  }

  @override
  String get deleteDraftTitle => 'Удалить черновик?';

  @override
  String get deleteDraftBody => 'Введённые данные будут потеряны.';

  @override
  String get signInRequired => 'Нужно войти';

  @override
  String get signInToManage => 'Войдите, чтобы управлять своими объявлениями.';

  @override
  String get noListingsInStatus => 'Здесь пока пусто';

  @override
  String get localOnlyBadge => 'На телефоне';

  @override
  String rejectedReason(String reason) {
    return 'Причина отклонения: $reason';
  }

  @override
  String get statusDraft => 'Черновики';

  @override
  String get statusPending => 'На проверке';

  @override
  String get statusActive => 'Активные';

  @override
  String get statusSold => 'Проданные';

  @override
  String get statusArchived => 'Архив';

  @override
  String get statusRejected => 'Отклонено';

  @override
  String get promoFree => 'Бесплатно';

  @override
  String get promoBoost => 'Поднятие';

  @override
  String get promoTop => 'ТОП';

  @override
  String get promoVip => 'VIP';

  @override
  String get promoVipPlus => 'VIP+';

  @override
  String get promoBusiness => 'Бизнес';

  @override
  String get signIn => 'Войти';

  @override
  String get signOut => 'Выйти';

  @override
  String get signOutTitle => 'Выйти из аккаунта?';

  @override
  String get signOutBody => 'Объявления и избранное останутся в аккаунте.';

  @override
  String get authPhoneTitle => 'Вход по номеру телефона';

  @override
  String get authPhoneBody => 'Мы отправим код подтверждения по SMS.';

  @override
  String get demoAuthNotice =>
      'Демо-режим: SMS не отправляется, код будет показан на экране. Номер не считается подтверждённым.';

  @override
  String get getCode => 'Получить код';

  @override
  String get authTermsNote =>
      'Продолжая, вы соглашаетесь с правилами и политикой конфиденциальности.';

  @override
  String get authCodeTitle => 'Введите код';

  @override
  String authCodeBody(String phone) {
    return 'Код отправлен на $phone';
  }

  @override
  String authCodeDemoBody(String phone) {
    return 'Демо-вход для $phone. SMS не отправлялось.';
  }

  @override
  String demoCodeIs(String code) {
    return 'Демо-код: $code';
  }

  @override
  String get authCodeLabel => 'Код из SMS';

  @override
  String get changeNumber => 'Изменить номер';

  @override
  String get resendCode => 'Отправить ещё раз';

  @override
  String resendIn(int seconds) {
    return 'Повторно через $seconds с';
  }

  @override
  String get authProfileTitle => 'Как вас зовут?';

  @override
  String get authProfileBody => 'Имя увидят покупатели и продавцы.';

  @override
  String get yourName => 'Ваше имя';

  @override
  String get guestTitle => 'Добро пожаловать в DARYOB';

  @override
  String get guestBody =>
      'Войдите, чтобы подавать объявления, писать продавцам и сохранять избранное в аккаунте.';

  @override
  String get noName => 'Без имени';

  @override
  String get phoneNotVerified => 'не подтверждён';

  @override
  String get editProfile => 'Профиль';

  @override
  String get phoneChangeNote =>
      'Номер используется для входа и не меняется здесь.';

  @override
  String get sectionListings => 'Объявления';

  @override
  String get sectionMoney => 'Продвижение и оплата';

  @override
  String get sectionApp => 'Приложение';

  @override
  String get sectionHelp => 'Помощь';

  @override
  String get myPromotions => 'Мои продвижения';

  @override
  String get wallet => 'Кошелёк';

  @override
  String get businessAccount => 'Бизнес-аккаунт';

  @override
  String get language => 'Язык';

  @override
  String get theme => 'Тема';

  @override
  String get themeSystem => 'Как в системе';

  @override
  String get themeLight => 'Светлая';

  @override
  String get themeDark => 'Тёмная';

  @override
  String get settings => 'Настройки';

  @override
  String get support => 'Поддержка';

  @override
  String get terms => 'Правила использования';

  @override
  String get privacyPolicy => 'Политика конфиденциальности';

  @override
  String get aboutApp => 'О приложении';

  @override
  String get devTools => 'Инструменты разработчика';

  @override
  String get deleteAccount => 'Удалить аккаунт';

  @override
  String get aboutBody =>
      'DARYOB — площадка объявлений для Таджикистана: покупайте, продавайте, ищите работу и услуги рядом с домом.';

  @override
  String get appVersion => 'Версия';

  @override
  String get environment => 'Режим';

  @override
  String get envDevelopment => 'Разработка (демо)';

  @override
  String get envProduction => 'Рабочий';

  @override
  String get licenses => 'Лицензии';

  @override
  String get legalDraftNotice =>
      'Черновик. Окончательный текст подготовит и утвердит юрист перед запуском.';

  @override
  String get termsBody =>
      'Размещая объявление, вы подтверждаете, что вправе продавать товар или оказывать услугу, а информация в объявлении достоверна. Запрещены мошенничество, запрещённые законом товары и оскорбительный контент. DARYOB может снять объявление, нарушающее правила.';

  @override
  String get privacyBody =>
      'DARYOB хранит номер телефона, имя и данные объявлений, чтобы работали вход, публикация и связь с покупателями. Номер показывается в объявлении только если вы это разрешили. Вы можете запросить удаление аккаунта и данных в профиле.';

  @override
  String get supportBody =>
      'Если что-то не работает или вы столкнулись с мошенничеством, сообщите нам.';

  @override
  String get supportNotConfigured =>
      'Контакты службы поддержки появятся после запуска сервиса.';

  @override
  String get deletionBody =>
      'Будут удалены ваш аккаунт, объявления и переписка. Действие нельзя отменить.';

  @override
  String get deletionDevNotice =>
      'Демо-режим: удаляются данные на этом телефоне.';

  @override
  String get deleteAccountConfirmTitle => 'Удалить аккаунт навсегда?';

  @override
  String get deleteAccountConfirmBody => 'Все ваши объявления будут удалены.';

  @override
  String get accountDeleted => 'Аккаунт удалён';

  @override
  String get safetyTitle => 'Безопасные сделки';

  @override
  String get safetyIntro =>
      'Большинство людей на DARYOB честные, но мошенники бывают везде. Несколько простых правил защитят ваши деньги.';

  @override
  String get safetyForBuyers => 'Покупателям';

  @override
  String get safetyBuyer1 => 'Осматривайте товар лично, до оплаты.';

  @override
  String get safetyBuyer2 => 'Не переводите предоплату незнакомым продавцам.';

  @override
  String get safetyBuyer3 => 'Встречайтесь в людных местах днём.';

  @override
  String get safetyBuyer4 => 'Для дорогих покупок проверяйте документы.';

  @override
  String get safetyForSellers => 'Продавцам';

  @override
  String get safetySeller1 => 'Никому не сообщайте коды из SMS.';

  @override
  String get safetySeller2 =>
      'Не сообщайте данные карты — для перевода нужен только номер.';

  @override
  String get safetySeller3 =>
      'Не переходите по ссылкам «для получения оплаты».';

  @override
  String get safetyReport =>
      'Заметили подозрительное объявление — нажмите «Пожаловаться».';

  @override
  String get chatsSignInTitle => 'Переписка с продавцами';

  @override
  String get chatsSignInBody =>
      'Войдите, чтобы писать продавцам и получать ответы.';

  @override
  String get chatLocalNotice =>
      'Чат-сервер ещё не подключён: сообщения сохраняются на телефоне и не доходят до собеседника.';

  @override
  String get chatLocalShort => 'Сообщения не отправляются (демо)';

  @override
  String get chatOnline => 'Чат';

  @override
  String get chatsEmpty => 'Пока нет переписок';

  @override
  String get chatsEmptyBody => 'Откройте объявление и нажмите «Написать».';

  @override
  String get blocked => 'Заблокирован';

  @override
  String get noMessagesYet => 'Нет сообщений';

  @override
  String get block => 'Заблокировать';

  @override
  String get unblock => 'Разблокировать';

  @override
  String get blockUserTitle => 'Заблокировать пользователя?';

  @override
  String get blockUserBody =>
      'Вы не сможете переписываться в этом чате, пока не разблокируете.';

  @override
  String get deleteChat => 'Удалить чат';

  @override
  String get deleteChatTitle => 'Удалить чат?';

  @override
  String get deleteChatBody => 'Переписка будет удалена с этого телефона.';

  @override
  String get sellerProfile => 'Профиль продавца';

  @override
  String get chatStartTitle => 'Начните разговор';

  @override
  String get chatStartBody => 'Спросите о состоянии, цене или месте встречи.';

  @override
  String get chatBlockedNotice => 'Пользователь заблокирован';

  @override
  String get messageHint => 'Сообщение';

  @override
  String get msgLocalOnly => 'не отправлено';

  @override
  String get msgSending => 'отправляется';

  @override
  String get msgSent => 'отправлено';

  @override
  String get msgDelivered => 'доставлено';

  @override
  String get msgRead => 'прочитано';

  @override
  String get msgFailed => 'ошибка';

  @override
  String get markAllRead => 'Прочитать все';

  @override
  String get notificationsEmpty => 'Уведомлений пока нет';

  @override
  String get pushNotConfigured =>
      'Push-уведомления ещё не подключены — новые события видны здесь, в приложении.';

  @override
  String get notifKindMessages => 'Новые сообщения';

  @override
  String get notifKindApproved => 'Объявление одобрено';

  @override
  String get notifKindRejected => 'Объявление отклонено';

  @override
  String get notifKindExpiring => 'Срок объявления истекает';

  @override
  String get notifKindPromotion => 'Окончание продвижения';

  @override
  String get notifKindMatching => 'Новые подходящие объявления';

  @override
  String get notifKindSystem => 'Системные сообщения';

  @override
  String get notifMessageTitle => 'Новое сообщение';

  @override
  String notifMessageBody(String title) {
    return 'По объявлению «$title»';
  }

  @override
  String get notifApprovedTitle => 'Объявление одобрено';

  @override
  String notifApprovedBody(String title) {
    return '«$title» опубликовано';
  }

  @override
  String get notifRejectedTitle => 'Объявление отклонено';

  @override
  String notifRejectedBody(String title) {
    return 'Проверьте причину для «$title»';
  }

  @override
  String get notifExpiringTitle => 'Срок истекает';

  @override
  String notifExpiringBody(String title) {
    return 'Продлите «$title», чтобы его видели';
  }

  @override
  String get notifPromotionTitle => 'Продвижение заканчивается';

  @override
  String notifPromotionBody(String title) {
    return 'Для «$title»';
  }

  @override
  String get notifMatchingTitle => 'Новые объявления';

  @override
  String notifMatchingBody(String title) {
    return 'По вашему запросу «$title»';
  }

  @override
  String get notifWelcomeTitle => 'Добро пожаловать в DARYOB!';

  @override
  String get notifWelcomeBody =>
      'Ищите, находите и продавайте по всему Таджикистану.';

  @override
  String get notifSavedLocallyTitle => 'Объявление сохранено';

  @override
  String notifSavedLocallyBody(String title) {
    return '«$title» сохранено на телефоне (демо-режим)';
  }

  @override
  String get notifStatusTitle => 'Статус изменён';

  @override
  String notifStatusBody(String title) {
    return 'Объявление «$title» обновлено';
  }

  @override
  String get sellerNotFound => 'Продавец не найден';

  @override
  String get sellerListings => 'Объявления продавца';

  @override
  String get noActiveListings => 'Нет активных объявлений';

  @override
  String get statistics => 'Статистика';

  @override
  String get statsNotTracked =>
      'Просмотры и звонки будут считаться после подключения сервера.';

  @override
  String get businessListings => 'Объявления компании';

  @override
  String get subscription => 'Подписка';

  @override
  String get subscriptionNone => 'Не оформлена';

  @override
  String get editBusiness => 'Данные компании';

  @override
  String get businessComingSoon =>
      'Сотрудники, массовая загрузка и витрина магазина появятся в следующих версиях.';

  @override
  String get requestVerification => 'Запросить проверку компании';

  @override
  String get businessIntroTitle => 'Продаёте как компания?';

  @override
  String get businessIntroBody =>
      'Создайте бизнес-профиль: название компании будет видно на объявлениях.';

  @override
  String get businessName => 'Название компании';

  @override
  String get businessDescription => 'О компании';

  @override
  String get businessAddress => 'Адрес';

  @override
  String get createBusiness => 'Создать бизнес-профиль';

  @override
  String get verNotSubmitted => 'Не проверена';

  @override
  String get verPending => 'На проверке';

  @override
  String get verVerified => 'Проверена';

  @override
  String get verRejected => 'Проверка не пройдена';

  @override
  String get planStart => 'Старт';

  @override
  String get planStartPerk1 => 'Страница компании';

  @override
  String get planStartPerk2 => 'Больше активных объявлений';

  @override
  String get planPro => 'Про';

  @override
  String get planProPerk1 => 'Всё из «Старт»';

  @override
  String get planProPerk2 => 'Подробная статистика';

  @override
  String get planProPerk3 => 'Пакет продвижений каждый месяц';

  @override
  String get choosePlan => 'Выбрать';

  @override
  String get priceNotSet => 'Цена будет объявлена';

  @override
  String durationDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days дня',
      many: '$days дней',
      few: '$days дня',
      one: '$days день',
    );
    return '$_temp0';
  }

  @override
  String get samplePriceNote =>
      'Цена-пример из демо-настроек, не реальный тариф.';

  @override
  String get payAndPromote => 'Оплатить и продвинуть';

  @override
  String get paymentUnavailableTitle => 'Оплата недоступна';

  @override
  String get devActivate => 'Включить без оплаты (только DEV)';

  @override
  String get devActivateTitle => 'Тестовое продвижение';

  @override
  String get devActivateBody =>
      'Продвижение включится без оплаты только в демо-сборке, чтобы проверить отображение VIP и ТОП.';

  @override
  String get devActivated => 'Тестовое продвижение включено';

  @override
  String get walletBalance => 'Баланс';

  @override
  String get topUp => 'Пополнить';

  @override
  String get transactionHistory => 'История операций';

  @override
  String get noTransactions => 'Операций пока нет';

  @override
  String get noPromotions => 'Нет продвижений';

  @override
  String get noPromotionsBody =>
      'Продвигайте объявления, чтобы их видели больше покупателей.';

  @override
  String until(String date) {
    return 'до $date';
  }

  @override
  String get promotionActive => 'Активно';

  @override
  String get promotionEnded => 'Завершено';

  @override
  String get defaultRegionHint => 'Для раздела «Рядом» и поиска';

  @override
  String get privacy => 'Приватность';

  @override
  String get hidePhoneByDefault => 'Скрывать номер в новых объявлениях';

  @override
  String get hidePhoneByDefaultHint => 'Покупатели смогут писать только в чат';

  @override
  String get dataDeletion => 'Удаление данных';

  @override
  String get devToolsNotice =>
      'Только для сборки разработчика. В рабочей версии этого экрана нет.';

  @override
  String get devConfirm =>
      'Действие изменит локальные данные на этом телефоне.';

  @override
  String get apiUrl => 'Адрес API';

  @override
  String get notConfigured => 'Не настроен';

  @override
  String get devResetOnboarding => 'Показать онбординг заново';

  @override
  String get devReseed => 'Пересоздать демо-объявления';

  @override
  String get devRemoveDemo => 'Удалить демо-объявления';

  @override
  String get devWipe => 'Стереть все локальные данные';

  @override
  String get errTitle => 'Что-то пошло не так';

  @override
  String get errNetwork =>
      'Нет подключения к интернету. Проверьте сеть и попробуйте снова.';

  @override
  String get errTimeout => 'Сервер долго не отвечает. Попробуйте ещё раз.';

  @override
  String get errUnauthorized => 'Нужно войти заново.';

  @override
  String get errSessionExpired => 'Сессия истекла. Войдите снова.';

  @override
  String get errForbidden => 'У вас нет прав на это действие.';

  @override
  String get errRateLimited => 'Слишком много попыток. Подождите немного.';

  @override
  String get errNotFound => 'Не найдено';

  @override
  String get errValidation => 'Проверьте введённые данные.';

  @override
  String get errServer => 'Ошибка на сервере. Мы уже разбираемся.';

  @override
  String get errUnknown => 'Неизвестная ошибка. Попробуйте ещё раз.';

  @override
  String get unavailableTitle => 'Пока недоступно';

  @override
  String get unavailableBackend =>
      'Сервер DARYOB ещё не подключён в этой сборке.';

  @override
  String get unavailableSms =>
      'Вход по SMS станет доступен после подключения SMS-сервиса.';

  @override
  String get unavailablePayments =>
      'Оплата ещё не подключена. Платёжный сервис будет добавлен позже.';

  @override
  String get unavailablePush => 'Push-уведомления ещё не подключены.';

  @override
  String get unavailableChat =>
      'Чат станет доступен после подключения чат-сервера.';

  @override
  String get valRequired => 'Обязательное поле';

  @override
  String valTooShort(int count) {
    return 'Минимум $count символов';
  }

  @override
  String valTooLong(int count) {
    return 'Максимум $count символов';
  }

  @override
  String get valTooShortGeneric => 'Слишком коротко';

  @override
  String get valTooLongGeneric => 'Слишком длинно';

  @override
  String get valInvalidNumber => 'Введите число';

  @override
  String get valOutOfRange => 'Недопустимое значение';

  @override
  String get valInvalidPhone => 'Введите 9 цифр номера после +992';

  @override
  String get valInvalidCode => 'Неверный код';

  @override
  String valTooManyPhotos(int count) {
    return 'Не больше $count фото';
  }

  @override
  String get ageJustNow => 'только что';

  @override
  String ageMinutes(int count) {
    return '$count мин назад';
  }

  @override
  String ageHours(int count) {
    return '$count ч назад';
  }

  @override
  String ageDays(int count) {
    return '$count дн. назад';
  }

  @override
  String get salaryNotSpecified => 'Зарплата не указана';

  @override
  String get perMonth => '/мес';

  @override
  String get perDay => '/сутки';

  @override
  String get pickerSearchHint => 'Поиск';

  @override
  String get pickerOther => 'Нет в списке — ввести вручную';

  @override
  String get pickerOtherHint => 'Введите название';

  @override
  String get pickerOtherNote =>
      'Значение сохранится как текст продавца и не будет отмечено как проверенное.';

  @override
  String get catalogNotLoaded =>
      'Справочник для этого поля ещё не загружен — введите значение вручную.';

  @override
  String get stepSubcategory => 'Подкатегория';

  @override
  String get stepDetails => 'Характеристики';

  @override
  String get tagsHint => 'Через запятую';

  @override
  String get mapPinComingSoon =>
      'Отметка на карте появится после подключения карт. Укажите город и район.';

  @override
  String atLeast(String value) {
    return 'от $value';
  }

  @override
  String get modelsUnverifiedNote =>
      'Список моделей — стартовый и не проверен производителем. Если модели нет, введите её вручную.';

  @override
  String verifiedSource(String source) {
    return 'Проверено: $source';
  }

  @override
  String get variantNotVerified =>
      'Проверенных вариантов для этой модели пока нет — укажите значение вручную.';

  @override
  String get modelFreeText =>
      'Сначала выберите марку или введите модель вручную';

  @override
  String get choose => 'Выбрать';

  @override
  String get notInCatalog => 'введено вручную';

  @override
  String get chooseSubcategoryError => 'Выберите подкатегорию';

  @override
  String get noCharacteristics =>
      'Для этой подкатегории дополнительных характеристик нет.';

  @override
  String get catalogStarterNotice =>
      'Справочники брендов и моделей пока стартовые. Если чего-то нет — введите вручную.';

  @override
  String useTitle(String title) {
    return 'Использовать: $title';
  }

  @override
  String get salaryInCharacteristics =>
      'Зарплата указывается в характеристиках вакансии.';

  @override
  String photosRequired(int count) {
    return 'Нужно минимум $count фото';
  }

  @override
  String get vehiclePhotoTips =>
      'Снимите машину спереди, сзади, сбоку, салон и приборную панель.';

  @override
  String get subcategory => 'Подкатегория';

  @override
  String get chooseCategoryForFilters =>
      'Выберите категорию, чтобы увидеть её фильтры.';

  @override
  String get any => 'Любой';

  @override
  String get containsHint => 'Содержит текст';

  @override
  String valNotAboveOther(String other) {
    return 'Не больше, чем «$other»';
  }

  @override
  String get devCatalog => 'Каталог категорий';

  @override
  String devCatalogInfo(String version, int top, int sub, int batches) {
    return 'Версия $version · $top категорий, $sub подкатегорий · импортов: $batches';
  }

  @override
  String get devCatalogImport => 'Импорт проверенных данных';

  @override
  String get devCatalogImportHint =>
      'JSON-пакет из буфера обмена. Записи без источника, даты проверки и лицензии отклоняются.';

  @override
  String get devCatalogImportInvalid => 'В буфере нет JSON-пакета импорта';

  @override
  String devCatalogImportResult(int accepted, int rejected) {
    return 'Принято: $accepted. Отклонено: $rejected.';
  }

  @override
  String get devCatalogRollback => 'Вернуть предыдущую версию каталога';

  @override
  String get devCatalogNoPrevious => 'Предыдущей версии нет';

  @override
  String get authPhoneBodyNoCode =>
      'Укажите номер, по которому с вами свяжутся покупатели.';

  @override
  String get authNoCodeNotice =>
      'Подтверждение номера кодом пока не подключено. Аккаунт привязан к этому телефону: при смене телефона или удалении приложения войти в него не получится.';

  @override
  String get authPhoneBodyTelegram =>
      'Мы пришлём код подтверждения в Telegram на этот номер.';

  @override
  String authCodeTelegramBody(String phone) {
    return 'Код отправлен в Telegram на $phone. Откройте чат «Verification Codes».';
  }

  @override
  String get authTelegramUnavailable =>
      'Не удалось отправить код в Telegram — номер сохранён без подтверждения.';

  @override
  String get valCodeExpired => 'Код устарел. Запросите новый.';

  @override
  String get valCodeTooManyAttempts =>
      'Слишком много попыток. Запросите новый код.';

  @override
  String get locateMe => 'Определить моё местоположение';

  @override
  String get locateMeHint => 'По GPS телефона — выберем ближайший город';

  @override
  String get locationServiceOff =>
      'Геолокация выключена. Включите её в настройках телефона.';

  @override
  String get locationDenied =>
      'Нет доступа к местоположению. Выберите город вручную.';

  @override
  String get locationDeniedForever =>
      'Доступ к местоположению запрещён. Разрешите его в настройках приложения.';

  @override
  String get locationOutside =>
      'Похоже, вы не в Таджикистане. Выберите город вручную.';

  @override
  String get locationFailed =>
      'Не удалось определить местоположение. Попробуйте ещё раз.';

  @override
  String get mapPinHere => 'Отметить, где я сейчас';

  @override
  String get mapPinSaved => 'Точка на карте сохранена';

  @override
  String get mapPinHint =>
      'Встаньте у объекта и нажмите кнопку — покупатели увидят его на карте.';

  @override
  String get showOnMap => 'На карте';
}
