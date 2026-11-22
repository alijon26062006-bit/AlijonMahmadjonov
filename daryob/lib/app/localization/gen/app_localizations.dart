import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ru.dart';
import 'app_localizations_tg.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'gen/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ru'),
    Locale('tg'),
  ];

  /// No description provided for @appName.
  ///
  /// In ru, this message translates to:
  /// **'DARYOB'**
  String get appName;

  /// No description provided for @brandSlogan.
  ///
  /// In ru, this message translates to:
  /// **'Ищи. Находи. Покупай.'**
  String get brandSlogan;

  /// No description provided for @retry.
  ///
  /// In ru, this message translates to:
  /// **'Повторить'**
  String get retry;

  /// No description provided for @cancel.
  ///
  /// In ru, this message translates to:
  /// **'Отмена'**
  String get cancel;

  /// No description provided for @save.
  ///
  /// In ru, this message translates to:
  /// **'Сохранить'**
  String get save;

  /// No description provided for @saveChanges.
  ///
  /// In ru, this message translates to:
  /// **'Сохранить изменения'**
  String get saveChanges;

  /// No description provided for @delete.
  ///
  /// In ru, this message translates to:
  /// **'Удалить'**
  String get delete;

  /// No description provided for @edit.
  ///
  /// In ru, this message translates to:
  /// **'Изменить'**
  String get edit;

  /// No description provided for @close.
  ///
  /// In ru, this message translates to:
  /// **'Закрыть'**
  String get close;

  /// No description provided for @next.
  ///
  /// In ru, this message translates to:
  /// **'Далее'**
  String get next;

  /// No description provided for @back.
  ///
  /// In ru, this message translates to:
  /// **'Назад'**
  String get back;

  /// No description provided for @continueAction.
  ///
  /// In ru, this message translates to:
  /// **'Продолжить'**
  String get continueAction;

  /// No description provided for @done.
  ///
  /// In ru, this message translates to:
  /// **'Готово'**
  String get done;

  /// No description provided for @ok.
  ///
  /// In ru, this message translates to:
  /// **'Понятно'**
  String get ok;

  /// No description provided for @yes.
  ///
  /// In ru, this message translates to:
  /// **'Да'**
  String get yes;

  /// No description provided for @no.
  ///
  /// In ru, this message translates to:
  /// **'Нет'**
  String get no;

  /// No description provided for @seeAll.
  ///
  /// In ru, this message translates to:
  /// **'Все'**
  String get seeAll;

  /// No description provided for @all.
  ///
  /// In ru, this message translates to:
  /// **'Все'**
  String get all;

  /// No description provided for @clear.
  ///
  /// In ru, this message translates to:
  /// **'Очистить'**
  String get clear;

  /// No description provided for @reset.
  ///
  /// In ru, this message translates to:
  /// **'Сбросить'**
  String get reset;

  /// No description provided for @confirm.
  ///
  /// In ru, this message translates to:
  /// **'Подтвердить'**
  String get confirm;

  /// No description provided for @more.
  ///
  /// In ru, this message translates to:
  /// **'Ещё'**
  String get more;

  /// No description provided for @share.
  ///
  /// In ru, this message translates to:
  /// **'Поделиться'**
  String get share;

  /// No description provided for @skip.
  ///
  /// In ru, this message translates to:
  /// **'Пропустить'**
  String get skip;

  /// No description provided for @search.
  ///
  /// In ru, this message translates to:
  /// **'Поиск'**
  String get search;

  /// No description provided for @send.
  ///
  /// In ru, this message translates to:
  /// **'Отправить'**
  String get send;

  /// No description provided for @publish.
  ///
  /// In ru, this message translates to:
  /// **'Опубликовать'**
  String get publish;

  /// No description provided for @switchLanguage.
  ///
  /// In ru, this message translates to:
  /// **'Сменить язык'**
  String get switchLanguage;

  /// No description provided for @tabHome.
  ///
  /// In ru, this message translates to:
  /// **'Главная'**
  String get tabHome;

  /// No description provided for @tabFavorites.
  ///
  /// In ru, this message translates to:
  /// **'Избранное'**
  String get tabFavorites;

  /// No description provided for @tabCreate.
  ///
  /// In ru, this message translates to:
  /// **'Подать'**
  String get tabCreate;

  /// No description provided for @tabChats.
  ///
  /// In ru, this message translates to:
  /// **'Чаты'**
  String get tabChats;

  /// No description provided for @tabProfile.
  ///
  /// In ru, this message translates to:
  /// **'Профиль'**
  String get tabProfile;

  /// No description provided for @onboardingWelcomeTitle.
  ///
  /// In ru, this message translates to:
  /// **'Всё, что нужно, рядом'**
  String get onboardingWelcomeTitle;

  /// No description provided for @onboardingWelcomeBody.
  ///
  /// In ru, this message translates to:
  /// **'Покупайте и продавайте по всему Таджикистану.'**
  String get onboardingWelcomeBody;

  /// No description provided for @onboardingSellTitle.
  ///
  /// In ru, this message translates to:
  /// **'Продавайте легко'**
  String get onboardingSellTitle;

  /// No description provided for @onboardingSellBody.
  ///
  /// In ru, this message translates to:
  /// **'Сфотографируйте вещь, добавьте цену и опубликуйте объявление за пару минут.'**
  String get onboardingSellBody;

  /// No description provided for @onboardingNearbyTitle.
  ///
  /// In ru, this message translates to:
  /// **'Находите предложения рядом'**
  String get onboardingNearbyTitle;

  /// No description provided for @onboardingNearbyBody.
  ///
  /// In ru, this message translates to:
  /// **'Выберите свой город — мы покажем объявления поблизости.'**
  String get onboardingNearbyBody;

  /// No description provided for @languageChangeLater.
  ///
  /// In ru, this message translates to:
  /// **'Язык можно изменить в любой момент в профиле.'**
  String get languageChangeLater;

  /// No description provided for @onboardingCityTitle.
  ///
  /// In ru, this message translates to:
  /// **'Где вы находитесь?'**
  String get onboardingCityTitle;

  /// No description provided for @onboardingCityBody.
  ///
  /// In ru, this message translates to:
  /// **'Город нужен, чтобы показывать объявления рядом. Местоположение телефона не запрашивается.'**
  String get onboardingCityBody;

  /// No description provided for @otherCity.
  ///
  /// In ru, this message translates to:
  /// **'Другой город или район'**
  String get otherCity;

  /// No description provided for @startUsing.
  ///
  /// In ru, this message translates to:
  /// **'Начать'**
  String get startUsing;

  /// No description provided for @searchHint.
  ///
  /// In ru, this message translates to:
  /// **'Что вы ищете?'**
  String get searchHint;

  /// No description provided for @heroTitle.
  ///
  /// In ru, this message translates to:
  /// **'Находите лучшее рядом'**
  String get heroTitle;

  /// No description provided for @heroSubtitle.
  ///
  /// In ru, this message translates to:
  /// **'Объявления по всему Таджикистану'**
  String get heroSubtitle;

  /// No description provided for @createListing.
  ///
  /// In ru, this message translates to:
  /// **'Подать объявление'**
  String get createListing;

  /// No description provided for @categories.
  ///
  /// In ru, this message translates to:
  /// **'Категории'**
  String get categories;

  /// No description provided for @allCategories.
  ///
  /// In ru, this message translates to:
  /// **'Все категории'**
  String get allCategories;

  /// No description provided for @vipListings.
  ///
  /// In ru, this message translates to:
  /// **'VIP объявления'**
  String get vipListings;

  /// No description provided for @recommended.
  ///
  /// In ru, this message translates to:
  /// **'Рекомендуем вам'**
  String get recommended;

  /// No description provided for @newListings.
  ///
  /// In ru, this message translates to:
  /// **'Новые объявления'**
  String get newListings;

  /// No description provided for @nearbyIn.
  ///
  /// In ru, this message translates to:
  /// **'Рядом: {name}'**
  String nearbyIn(String name);

  /// No description provided for @noListingsYet.
  ///
  /// In ru, this message translates to:
  /// **'Объявлений пока нет'**
  String get noListingsYet;

  /// No description provided for @noListingsYetBody.
  ///
  /// In ru, this message translates to:
  /// **'Станьте первым — подайте объявление.'**
  String get noListingsYetBody;

  /// No description provided for @loadMore.
  ///
  /// In ru, this message translates to:
  /// **'Показать ещё'**
  String get loadMore;

  /// No description provided for @loadMoreFailed.
  ///
  /// In ru, this message translates to:
  /// **'Не удалось загрузить. Повторить'**
  String get loadMoreFailed;

  /// No description provided for @endOfList.
  ///
  /// In ru, this message translates to:
  /// **'Это все объявления'**
  String get endOfList;

  /// No description provided for @notifications.
  ///
  /// In ru, this message translates to:
  /// **'Уведомления'**
  String get notifications;

  /// No description provided for @priceFree.
  ///
  /// In ru, this message translates to:
  /// **'Бесплатно'**
  String get priceFree;

  /// No description provided for @priceOnRequest.
  ///
  /// In ru, this message translates to:
  /// **'Цена договорная'**
  String get priceOnRequest;

  /// No description provided for @negotiable.
  ///
  /// In ru, this message translates to:
  /// **'Торг уместен'**
  String get negotiable;

  /// No description provided for @favoriteAdd.
  ///
  /// In ru, this message translates to:
  /// **'Добавить в избранное'**
  String get favoriteAdd;

  /// No description provided for @favoriteRemove.
  ///
  /// In ru, this message translates to:
  /// **'Убрать из избранного'**
  String get favoriteRemove;

  /// No description provided for @favoriteAdded.
  ///
  /// In ru, this message translates to:
  /// **'Добавлено в избранное'**
  String get favoriteAdded;

  /// No description provided for @favoriteRemoved.
  ///
  /// In ru, this message translates to:
  /// **'Убрано из избранного'**
  String get favoriteRemoved;

  /// No description provided for @demoBadgeDescription.
  ///
  /// In ru, this message translates to:
  /// **'Демонстрационные данные'**
  String get demoBadgeDescription;

  /// No description provided for @noPhotos.
  ///
  /// In ru, this message translates to:
  /// **'Фото не добавлены'**
  String get noPhotos;

  /// No description provided for @photoOf.
  ///
  /// In ru, this message translates to:
  /// **'Фото {index} из {total}'**
  String photoOf(int index, int total);

  /// No description provided for @listingNotFound.
  ///
  /// In ru, this message translates to:
  /// **'Объявление не найдено'**
  String get listingNotFound;

  /// No description provided for @listingNotFoundBody.
  ///
  /// In ru, this message translates to:
  /// **'Возможно, его удалили или сняли с публикации.'**
  String get listingNotFoundBody;

  /// No description provided for @demoListingNotice.
  ///
  /// In ru, this message translates to:
  /// **'Это демонстрационное объявление для проверки приложения. Это не реальное предложение.'**
  String get demoListingNotice;

  /// No description provided for @localListingNotice.
  ///
  /// In ru, this message translates to:
  /// **'Объявление сохранено только на этом телефоне: сервер ещё не подключён, другие люди его не видят.'**
  String get localListingNotice;

  /// No description provided for @publishedOn.
  ///
  /// In ru, this message translates to:
  /// **'Опубликовано {date}'**
  String publishedOn(String date);

  /// No description provided for @listingNumber.
  ///
  /// In ru, this message translates to:
  /// **'Объявление № {number}'**
  String listingNumber(String number);

  /// No description provided for @views.
  ///
  /// In ru, this message translates to:
  /// **'Просмотров: {count}'**
  String views(int count);

  /// No description provided for @viewsLabel.
  ///
  /// In ru, this message translates to:
  /// **'Просмотры'**
  String get viewsLabel;

  /// No description provided for @description.
  ///
  /// In ru, this message translates to:
  /// **'Описание'**
  String get description;

  /// No description provided for @characteristics.
  ///
  /// In ru, this message translates to:
  /// **'Характеристики'**
  String get characteristics;

  /// No description provided for @category.
  ///
  /// In ru, this message translates to:
  /// **'Категория'**
  String get category;

  /// No description provided for @seller.
  ///
  /// In ru, this message translates to:
  /// **'Продавец'**
  String get seller;

  /// No description provided for @memberSince.
  ///
  /// In ru, this message translates to:
  /// **'На DARYOB с {date}'**
  String memberSince(String date);

  /// No description provided for @verifiedSeller.
  ///
  /// In ru, this message translates to:
  /// **'Проверенный продавец'**
  String get verifiedSeller;

  /// No description provided for @sellerBusiness.
  ///
  /// In ru, this message translates to:
  /// **'Компания'**
  String get sellerBusiness;

  /// No description provided for @sellerPrivate.
  ///
  /// In ru, this message translates to:
  /// **'Частное лицо'**
  String get sellerPrivate;

  /// No description provided for @safetyTipShort.
  ///
  /// In ru, this message translates to:
  /// **'Не переводите предоплату незнакомым людям. Проверяйте товар при встрече.'**
  String get safetyTipShort;

  /// No description provided for @reportListing.
  ///
  /// In ru, this message translates to:
  /// **'Пожаловаться'**
  String get reportListing;

  /// No description provided for @moreFromSeller.
  ///
  /// In ru, this message translates to:
  /// **'Другие объявления продавца'**
  String get moreFromSeller;

  /// No description provided for @similarListings.
  ///
  /// In ru, this message translates to:
  /// **'Похожие объявления'**
  String get similarListings;

  /// No description provided for @sharedFromDaryob.
  ///
  /// In ru, this message translates to:
  /// **'Найдено в DARYOB'**
  String get sharedFromDaryob;

  /// No description provided for @yourListing.
  ///
  /// In ru, this message translates to:
  /// **'Ваше объявление'**
  String get yourListing;

  /// No description provided for @promote.
  ///
  /// In ru, this message translates to:
  /// **'Продвинуть'**
  String get promote;

  /// No description provided for @markSold.
  ///
  /// In ru, this message translates to:
  /// **'Продано'**
  String get markSold;

  /// No description provided for @archive.
  ///
  /// In ru, this message translates to:
  /// **'В архив'**
  String get archive;

  /// No description provided for @republish.
  ///
  /// In ru, this message translates to:
  /// **'Опубликовать снова'**
  String get republish;

  /// No description provided for @phoneHidden.
  ///
  /// In ru, this message translates to:
  /// **'Номер скрыт'**
  String get phoneHidden;

  /// No description provided for @showPhone.
  ///
  /// In ru, this message translates to:
  /// **'Показать номер'**
  String get showPhone;

  /// No description provided for @call.
  ///
  /// In ru, this message translates to:
  /// **'Позвонить'**
  String get call;

  /// No description provided for @callFailed.
  ///
  /// In ru, this message translates to:
  /// **'Не удалось открыть звонилку'**
  String get callFailed;

  /// No description provided for @writeMessage.
  ///
  /// In ru, this message translates to:
  /// **'Написать'**
  String get writeMessage;

  /// No description provided for @listingNotAvailable.
  ///
  /// In ru, this message translates to:
  /// **'Объявление сейчас неактивно'**
  String get listingNotAvailable;

  /// No description provided for @chatOwnListing.
  ///
  /// In ru, this message translates to:
  /// **'Это ваше объявление'**
  String get chatOwnListing;

  /// No description provided for @statusChangedTo.
  ///
  /// In ru, this message translates to:
  /// **'Статус: {status}'**
  String statusChangedTo(String status);

  /// No description provided for @deleteListingTitle.
  ///
  /// In ru, this message translates to:
  /// **'Удалить объявление?'**
  String get deleteListingTitle;

  /// No description provided for @deleteListingBody.
  ///
  /// In ru, this message translates to:
  /// **'Объявление будет удалено без возможности восстановления.'**
  String get deleteListingBody;

  /// No description provided for @listingDeleted.
  ///
  /// In ru, this message translates to:
  /// **'Объявление удалено'**
  String get listingDeleted;

  /// No description provided for @reportTitle.
  ///
  /// In ru, this message translates to:
  /// **'Жалоба на объявление'**
  String get reportTitle;

  /// No description provided for @reportBody.
  ///
  /// In ru, this message translates to:
  /// **'Выберите причину. Модераторы проверят объявление.'**
  String get reportBody;

  /// No description provided for @reportFraud.
  ///
  /// In ru, this message translates to:
  /// **'Мошенничество'**
  String get reportFraud;

  /// No description provided for @reportProhibited.
  ///
  /// In ru, this message translates to:
  /// **'Запрещённый товар'**
  String get reportProhibited;

  /// No description provided for @reportWrongCategory.
  ///
  /// In ru, this message translates to:
  /// **'Неверная категория'**
  String get reportWrongCategory;

  /// No description provided for @reportDuplicate.
  ///
  /// In ru, this message translates to:
  /// **'Повторное объявление'**
  String get reportDuplicate;

  /// No description provided for @reportSold.
  ///
  /// In ru, this message translates to:
  /// **'Уже продано'**
  String get reportSold;

  /// No description provided for @reportOffensive.
  ///
  /// In ru, this message translates to:
  /// **'Оскорбительное содержание'**
  String get reportOffensive;

  /// No description provided for @reportOther.
  ///
  /// In ru, this message translates to:
  /// **'Другое'**
  String get reportOther;

  /// No description provided for @reportCommentHint.
  ///
  /// In ru, this message translates to:
  /// **'Комментарий (необязательно)'**
  String get reportCommentHint;

  /// No description provided for @reportSend.
  ///
  /// In ru, this message translates to:
  /// **'Отправить жалобу'**
  String get reportSend;

  /// No description provided for @reportSent.
  ///
  /// In ru, this message translates to:
  /// **'Жалоба отправлена'**
  String get reportSent;

  /// No description provided for @reportSavedLocally.
  ///
  /// In ru, this message translates to:
  /// **'Жалоба сохранена на телефоне — сервер модерации ещё не подключён'**
  String get reportSavedLocally;

  /// No description provided for @reportUser.
  ///
  /// In ru, this message translates to:
  /// **'Пожаловаться на пользователя'**
  String get reportUser;

  /// No description provided for @reportUserBody.
  ///
  /// In ru, this message translates to:
  /// **'Сообщить модераторам о подозрительном поведении собеседника?'**
  String get reportUserBody;

  /// No description provided for @listingsCount.
  ///
  /// In ru, this message translates to:
  /// **'{count, plural, one{{count} объявление} few{{count} объявления} many{{count} объявлений} other{{count} объявления}}'**
  String listingsCount(int count);

  /// No description provided for @categoryNotFound.
  ///
  /// In ru, this message translates to:
  /// **'Категория не найдена'**
  String get categoryNotFound;

  /// No description provided for @nothingFound.
  ///
  /// In ru, this message translates to:
  /// **'Ничего не найдено'**
  String get nothingFound;

  /// No description provided for @nothingFoundBody.
  ///
  /// In ru, this message translates to:
  /// **'Попробуйте изменить запрос, город или фильтры.'**
  String get nothingFoundBody;

  /// No description provided for @resetFilters.
  ///
  /// In ru, this message translates to:
  /// **'Сбросить фильтры'**
  String get resetFilters;

  /// No description provided for @filters.
  ///
  /// In ru, this message translates to:
  /// **'Фильтры'**
  String get filters;

  /// No description provided for @location.
  ///
  /// In ru, this message translates to:
  /// **'Местоположение'**
  String get location;

  /// No description provided for @chooseLocation.
  ///
  /// In ru, this message translates to:
  /// **'Выберите город или район'**
  String get chooseLocation;

  /// No description provided for @wholeRegion.
  ///
  /// In ru, this message translates to:
  /// **'Весь регион: {name}'**
  String wholeRegion(String name);

  /// No description provided for @priceRange.
  ///
  /// In ru, this message translates to:
  /// **'Цена, сомони'**
  String get priceRange;

  /// No description provided for @priceFrom.
  ///
  /// In ru, this message translates to:
  /// **'от'**
  String get priceFrom;

  /// No description provided for @priceTo.
  ///
  /// In ru, this message translates to:
  /// **'до'**
  String get priceTo;

  /// No description provided for @sortBy.
  ///
  /// In ru, this message translates to:
  /// **'Сортировка'**
  String get sortBy;

  /// No description provided for @sortRelevance.
  ///
  /// In ru, this message translates to:
  /// **'Сначала подходящие'**
  String get sortRelevance;

  /// No description provided for @sortNewest.
  ///
  /// In ru, this message translates to:
  /// **'Сначала новые'**
  String get sortNewest;

  /// No description provided for @sortPriceAsc.
  ///
  /// In ru, this message translates to:
  /// **'Сначала дешёвые'**
  String get sortPriceAsc;

  /// No description provided for @sortPriceDesc.
  ///
  /// In ru, this message translates to:
  /// **'Сначала дорогие'**
  String get sortPriceDesc;

  /// No description provided for @showResults.
  ///
  /// In ru, this message translates to:
  /// **'Показать'**
  String get showResults;

  /// No description provided for @recentSearches.
  ///
  /// In ru, this message translates to:
  /// **'Недавние запросы'**
  String get recentSearches;

  /// No description provided for @clearHistory.
  ///
  /// In ru, this message translates to:
  /// **'Очистить'**
  String get clearHistory;

  /// No description provided for @searchByCategory.
  ///
  /// In ru, this message translates to:
  /// **'Искать в категории'**
  String get searchByCategory;

  /// No description provided for @priceFilterChip.
  ///
  /// In ru, this message translates to:
  /// **'Цена: {from} – {to}'**
  String priceFilterChip(String from, String to);

  /// No description provided for @resultsCount.
  ///
  /// In ru, this message translates to:
  /// **'Найдено: {count}'**
  String resultsCount(int count);

  /// No description provided for @favoritesEmpty.
  ///
  /// In ru, this message translates to:
  /// **'В избранном пусто'**
  String get favoritesEmpty;

  /// No description provided for @favoritesEmptyBody.
  ///
  /// In ru, this message translates to:
  /// **'Нажмите ♡ на объявлении, чтобы сохранить его здесь.'**
  String get favoritesEmptyBody;

  /// No description provided for @browseListings.
  ///
  /// In ru, this message translates to:
  /// **'Смотреть объявления'**
  String get browseListings;

  /// No description provided for @favoritesGuestNotice.
  ///
  /// In ru, this message translates to:
  /// **'Избранное хранится на этом телефоне. Войдите, чтобы привязать его к аккаунту.'**
  String get favoritesGuestNotice;

  /// No description provided for @editListing.
  ///
  /// In ru, this message translates to:
  /// **'Редактирование'**
  String get editListing;

  /// No description provided for @stepOf.
  ///
  /// In ru, this message translates to:
  /// **'Шаг {current} из {total}: {title}'**
  String stepOf(int current, int total, String title);

  /// No description provided for @stepCategory.
  ///
  /// In ru, this message translates to:
  /// **'Категория'**
  String get stepCategory;

  /// No description provided for @stepBasics.
  ///
  /// In ru, this message translates to:
  /// **'Основное'**
  String get stepBasics;

  /// No description provided for @stepPhotos.
  ///
  /// In ru, this message translates to:
  /// **'Фото'**
  String get stepPhotos;

  /// No description provided for @stepLocation.
  ///
  /// In ru, this message translates to:
  /// **'Место'**
  String get stepLocation;

  /// No description provided for @stepContact.
  ///
  /// In ru, this message translates to:
  /// **'Контакты'**
  String get stepContact;

  /// No description provided for @stepPreview.
  ///
  /// In ru, this message translates to:
  /// **'Проверка'**
  String get stepPreview;

  /// No description provided for @chooseCategoryError.
  ///
  /// In ru, this message translates to:
  /// **'Выберите категорию объявления'**
  String get chooseCategoryError;

  /// No description provided for @fieldTitle.
  ///
  /// In ru, this message translates to:
  /// **'Заголовок'**
  String get fieldTitle;

  /// No description provided for @fieldTitleHint.
  ///
  /// In ru, this message translates to:
  /// **'Например: диван раскладной, почти новый'**
  String get fieldTitleHint;

  /// No description provided for @fieldDescriptionHint.
  ///
  /// In ru, this message translates to:
  /// **'Состояние, особенности, причина продажи'**
  String get fieldDescriptionHint;

  /// No description provided for @price.
  ///
  /// In ru, this message translates to:
  /// **'Цена'**
  String get price;

  /// No description provided for @priceOptionalHint.
  ///
  /// In ru, this message translates to:
  /// **'Можно не указывать'**
  String get priceOptionalHint;

  /// No description provided for @negotiableHint.
  ///
  /// In ru, this message translates to:
  /// **'Покупатели увидят, что цену можно обсудить'**
  String get negotiableHint;

  /// No description provided for @freeCategoryNotice.
  ///
  /// In ru, this message translates to:
  /// **'В этой категории вещи отдают бесплатно — цена не нужна.'**
  String get freeCategoryNotice;

  /// No description provided for @photos.
  ///
  /// In ru, this message translates to:
  /// **'Фото'**
  String get photos;

  /// No description provided for @photosTip.
  ///
  /// In ru, this message translates to:
  /// **'Объявления с хорошими фото находят покупателя быстрее. Первое фото станет обложкой.'**
  String get photosTip;

  /// No description provided for @photoFromGallery.
  ///
  /// In ru, this message translates to:
  /// **'Из галереи'**
  String get photoFromGallery;

  /// No description provided for @photoFromCamera.
  ///
  /// In ru, this message translates to:
  /// **'Сделать фото'**
  String get photoFromCamera;

  /// No description provided for @photosCounter.
  ///
  /// In ru, this message translates to:
  /// **'Фото: {count} из {max}'**
  String photosCounter(int count, int max);

  /// No description provided for @photosReorderHint.
  ///
  /// In ru, this message translates to:
  /// **'Порядок можно менять стрелками'**
  String get photosReorderHint;

  /// No description provided for @photoCover.
  ///
  /// In ru, this message translates to:
  /// **'Обложка'**
  String get photoCover;

  /// No description provided for @photoNumber.
  ///
  /// In ru, this message translates to:
  /// **'Фото {n}'**
  String photoNumber(int n);

  /// No description provided for @photoPickFailed.
  ///
  /// In ru, this message translates to:
  /// **'Не удалось добавить фото. Проверьте разрешения.'**
  String get photoPickFailed;

  /// No description provided for @moveUp.
  ///
  /// In ru, this message translates to:
  /// **'Выше'**
  String get moveUp;

  /// No description provided for @moveDown.
  ///
  /// In ru, this message translates to:
  /// **'Ниже'**
  String get moveDown;

  /// No description provided for @addressNote.
  ///
  /// In ru, this message translates to:
  /// **'Уточнение адреса'**
  String get addressNote;

  /// No description provided for @addressNoteHint.
  ///
  /// In ru, this message translates to:
  /// **'Например: рядом с рынком «Корвон»'**
  String get addressNoteHint;

  /// No description provided for @addressPrivacyNote.
  ///
  /// In ru, this message translates to:
  /// **'Не указывайте номер квартиры — точный адрес лучше сообщить в переписке.'**
  String get addressPrivacyNote;

  /// No description provided for @contactName.
  ///
  /// In ru, this message translates to:
  /// **'Имя'**
  String get contactName;

  /// No description provided for @contactPhone.
  ///
  /// In ru, this message translates to:
  /// **'Номер телефона'**
  String get contactPhone;

  /// No description provided for @phoneVisibility.
  ///
  /// In ru, this message translates to:
  /// **'Номер в объявлении'**
  String get phoneVisibility;

  /// No description provided for @phoneVisible.
  ///
  /// In ru, this message translates to:
  /// **'Показывать номер'**
  String get phoneVisible;

  /// No description provided for @phoneVisibleHint.
  ///
  /// In ru, this message translates to:
  /// **'Номер откроется после нажатия «Показать номер»'**
  String get phoneVisibleHint;

  /// No description provided for @phoneHiddenOption.
  ///
  /// In ru, this message translates to:
  /// **'Скрыть номер'**
  String get phoneHiddenOption;

  /// No description provided for @phoneHiddenHint.
  ///
  /// In ru, this message translates to:
  /// **'Связь только через чат'**
  String get phoneHiddenHint;

  /// No description provided for @chatEnabled.
  ///
  /// In ru, this message translates to:
  /// **'Сообщения в чате'**
  String get chatEnabled;

  /// No description provided for @chatEnabledHint.
  ///
  /// In ru, this message translates to:
  /// **'Покупатели смогут написать вам в приложении'**
  String get chatEnabledHint;

  /// No description provided for @contactMethodError.
  ///
  /// In ru, this message translates to:
  /// **'Оставьте хотя бы один способ связи: номер или чат.'**
  String get contactMethodError;

  /// No description provided for @contacts.
  ///
  /// In ru, this message translates to:
  /// **'Контакты'**
  String get contacts;

  /// No description provided for @previewNotice.
  ///
  /// In ru, this message translates to:
  /// **'Так покупатели увидят ваше объявление. Проверьте всё перед публикацией.'**
  String get previewNotice;

  /// No description provided for @localPublishNotice.
  ///
  /// In ru, this message translates to:
  /// **'Демо-режим: объявление сохранится только на этом телефоне.'**
  String get localPublishNotice;

  /// No description provided for @draftResumed.
  ///
  /// In ru, this message translates to:
  /// **'Продолжаем ваш черновик — он сохраняется автоматически.'**
  String get draftResumed;

  /// No description provided for @fixErrors.
  ///
  /// In ru, this message translates to:
  /// **'Проверьте отмеченные поля'**
  String get fixErrors;

  /// No description provided for @changesSaved.
  ///
  /// In ru, this message translates to:
  /// **'Изменения сохранены'**
  String get changesSaved;

  /// No description provided for @startNew.
  ///
  /// In ru, this message translates to:
  /// **'Новое объявление'**
  String get startNew;

  /// No description provided for @startNewTitle.
  ///
  /// In ru, this message translates to:
  /// **'Начать новое объявление?'**
  String get startNewTitle;

  /// No description provided for @startNewBody.
  ///
  /// In ru, this message translates to:
  /// **'Текущий черновик останется в «Моих черновиках».'**
  String get startNewBody;

  /// No description provided for @myDrafts.
  ///
  /// In ru, this message translates to:
  /// **'Мои черновики'**
  String get myDrafts;

  /// No description provided for @publishedTitle.
  ///
  /// In ru, this message translates to:
  /// **'Объявление опубликовано!'**
  String get publishedTitle;

  /// No description provided for @publishedBody.
  ///
  /// In ru, this message translates to:
  /// **'Покупатели уже могут его найти.'**
  String get publishedBody;

  /// No description provided for @publishedLocalBody.
  ///
  /// In ru, this message translates to:
  /// **'Демо-режим: объявление сохранено на этом телефоне и видно только вам.'**
  String get publishedLocalBody;

  /// No description provided for @openListing.
  ///
  /// In ru, this message translates to:
  /// **'Открыть объявление'**
  String get openListing;

  /// No description provided for @myListings.
  ///
  /// In ru, this message translates to:
  /// **'Мои объявления'**
  String get myListings;

  /// No description provided for @createAnother.
  ///
  /// In ru, this message translates to:
  /// **'Подать ещё одно'**
  String get createAnother;

  /// No description provided for @draftsEmpty.
  ///
  /// In ru, this message translates to:
  /// **'Черновиков нет'**
  String get draftsEmpty;

  /// No description provided for @draftsEmptyBody.
  ///
  /// In ru, this message translates to:
  /// **'Незаконченные объявления сохраняются здесь автоматически.'**
  String get draftsEmptyBody;

  /// No description provided for @untitledDraft.
  ///
  /// In ru, this message translates to:
  /// **'Без названия'**
  String get untitledDraft;

  /// No description provided for @editingDraft.
  ///
  /// In ru, this message translates to:
  /// **'Правка объявления'**
  String get editingDraft;

  /// No description provided for @savedAt.
  ///
  /// In ru, this message translates to:
  /// **'сохранено {date}'**
  String savedAt(String date);

  /// No description provided for @deleteDraftTitle.
  ///
  /// In ru, this message translates to:
  /// **'Удалить черновик?'**
  String get deleteDraftTitle;

  /// No description provided for @deleteDraftBody.
  ///
  /// In ru, this message translates to:
  /// **'Введённые данные будут потеряны.'**
  String get deleteDraftBody;

  /// No description provided for @signInRequired.
  ///
  /// In ru, this message translates to:
  /// **'Нужно войти'**
  String get signInRequired;

  /// No description provided for @signInToManage.
  ///
  /// In ru, this message translates to:
  /// **'Войдите, чтобы управлять своими объявлениями.'**
  String get signInToManage;

  /// No description provided for @noListingsInStatus.
  ///
  /// In ru, this message translates to:
  /// **'Здесь пока пусто'**
  String get noListingsInStatus;

  /// No description provided for @localOnlyBadge.
  ///
  /// In ru, this message translates to:
  /// **'На телефоне'**
  String get localOnlyBadge;

  /// No description provided for @rejectedReason.
  ///
  /// In ru, this message translates to:
  /// **'Причина отклонения: {reason}'**
  String rejectedReason(String reason);

  /// No description provided for @statusDraft.
  ///
  /// In ru, this message translates to:
  /// **'Черновики'**
  String get statusDraft;

  /// No description provided for @statusPending.
  ///
  /// In ru, this message translates to:
  /// **'На проверке'**
  String get statusPending;

  /// No description provided for @statusActive.
  ///
  /// In ru, this message translates to:
  /// **'Активные'**
  String get statusActive;

  /// No description provided for @statusSold.
  ///
  /// In ru, this message translates to:
  /// **'Проданные'**
  String get statusSold;

  /// No description provided for @statusArchived.
  ///
  /// In ru, this message translates to:
  /// **'Архив'**
  String get statusArchived;

  /// No description provided for @statusRejected.
  ///
  /// In ru, this message translates to:
  /// **'Отклонено'**
  String get statusRejected;

  /// No description provided for @promoFree.
  ///
  /// In ru, this message translates to:
  /// **'Бесплатно'**
  String get promoFree;

  /// No description provided for @promoBoost.
  ///
  /// In ru, this message translates to:
  /// **'Поднятие'**
  String get promoBoost;

  /// No description provided for @promoTop.
  ///
  /// In ru, this message translates to:
  /// **'ТОП'**
  String get promoTop;

  /// No description provided for @promoVip.
  ///
  /// In ru, this message translates to:
  /// **'VIP'**
  String get promoVip;

  /// No description provided for @promoVipPlus.
  ///
  /// In ru, this message translates to:
  /// **'VIP+'**
  String get promoVipPlus;

  /// No description provided for @promoBusiness.
  ///
  /// In ru, this message translates to:
  /// **'Бизнес'**
  String get promoBusiness;

  /// No description provided for @signIn.
  ///
  /// In ru, this message translates to:
  /// **'Войти'**
  String get signIn;

  /// No description provided for @signOut.
  ///
  /// In ru, this message translates to:
  /// **'Выйти'**
  String get signOut;

  /// No description provided for @signOutTitle.
  ///
  /// In ru, this message translates to:
  /// **'Выйти из аккаунта?'**
  String get signOutTitle;

  /// No description provided for @signOutBody.
  ///
  /// In ru, this message translates to:
  /// **'Объявления и избранное останутся в аккаунте.'**
  String get signOutBody;

  /// No description provided for @authPhoneTitle.
  ///
  /// In ru, this message translates to:
  /// **'Вход по номеру телефона'**
  String get authPhoneTitle;

  /// No description provided for @authPhoneBody.
  ///
  /// In ru, this message translates to:
  /// **'Мы отправим код подтверждения по SMS.'**
  String get authPhoneBody;

  /// No description provided for @demoAuthNotice.
  ///
  /// In ru, this message translates to:
  /// **'Демо-режим: SMS не отправляется, код будет показан на экране. Номер не считается подтверждённым.'**
  String get demoAuthNotice;

  /// No description provided for @getCode.
  ///
  /// In ru, this message translates to:
  /// **'Получить код'**
  String get getCode;

  /// No description provided for @authTermsNote.
  ///
  /// In ru, this message translates to:
  /// **'Продолжая, вы соглашаетесь с правилами и политикой конфиденциальности.'**
  String get authTermsNote;

  /// No description provided for @authCodeTitle.
  ///
  /// In ru, this message translates to:
  /// **'Введите код'**
  String get authCodeTitle;

  /// No description provided for @authCodeBody.
  ///
  /// In ru, this message translates to:
  /// **'Код отправлен на {phone}'**
  String authCodeBody(String phone);

  /// No description provided for @authCodeDemoBody.
  ///
  /// In ru, this message translates to:
  /// **'Демо-вход для {phone}. SMS не отправлялось.'**
  String authCodeDemoBody(String phone);

  /// No description provided for @demoCodeIs.
  ///
  /// In ru, this message translates to:
  /// **'Демо-код: {code}'**
  String demoCodeIs(String code);

  /// No description provided for @authCodeLabel.
  ///
  /// In ru, this message translates to:
  /// **'Код из SMS'**
  String get authCodeLabel;

  /// No description provided for @changeNumber.
  ///
  /// In ru, this message translates to:
  /// **'Изменить номер'**
  String get changeNumber;

  /// No description provided for @resendCode.
  ///
  /// In ru, this message translates to:
  /// **'Отправить ещё раз'**
  String get resendCode;

  /// No description provided for @resendIn.
  ///
  /// In ru, this message translates to:
  /// **'Повторно через {seconds} с'**
  String resendIn(int seconds);

  /// No description provided for @authProfileTitle.
  ///
  /// In ru, this message translates to:
  /// **'Как вас зовут?'**
  String get authProfileTitle;

  /// No description provided for @authProfileBody.
  ///
  /// In ru, this message translates to:
  /// **'Имя увидят покупатели и продавцы.'**
  String get authProfileBody;

  /// No description provided for @yourName.
  ///
  /// In ru, this message translates to:
  /// **'Ваше имя'**
  String get yourName;

  /// No description provided for @guestTitle.
  ///
  /// In ru, this message translates to:
  /// **'Добро пожаловать в DARYOB'**
  String get guestTitle;

  /// No description provided for @guestBody.
  ///
  /// In ru, this message translates to:
  /// **'Войдите, чтобы подавать объявления, писать продавцам и сохранять избранное в аккаунте.'**
  String get guestBody;

  /// No description provided for @noName.
  ///
  /// In ru, this message translates to:
  /// **'Без имени'**
  String get noName;

  /// No description provided for @phoneNotVerified.
  ///
  /// In ru, this message translates to:
  /// **'не подтверждён'**
  String get phoneNotVerified;

  /// No description provided for @editProfile.
  ///
  /// In ru, this message translates to:
  /// **'Профиль'**
  String get editProfile;

  /// No description provided for @phoneChangeNote.
  ///
  /// In ru, this message translates to:
  /// **'Номер используется для входа и не меняется здесь.'**
  String get phoneChangeNote;

  /// No description provided for @sectionListings.
  ///
  /// In ru, this message translates to:
  /// **'Объявления'**
  String get sectionListings;

  /// No description provided for @sectionMoney.
  ///
  /// In ru, this message translates to:
  /// **'Продвижение и оплата'**
  String get sectionMoney;

  /// No description provided for @sectionApp.
  ///
  /// In ru, this message translates to:
  /// **'Приложение'**
  String get sectionApp;

  /// No description provided for @sectionHelp.
  ///
  /// In ru, this message translates to:
  /// **'Помощь'**
  String get sectionHelp;

  /// No description provided for @myPromotions.
  ///
  /// In ru, this message translates to:
  /// **'Мои продвижения'**
  String get myPromotions;

  /// No description provided for @wallet.
  ///
  /// In ru, this message translates to:
  /// **'Кошелёк'**
  String get wallet;

  /// No description provided for @businessAccount.
  ///
  /// In ru, this message translates to:
  /// **'Бизнес-аккаунт'**
  String get businessAccount;

  /// No description provided for @language.
  ///
  /// In ru, this message translates to:
  /// **'Язык'**
  String get language;

  /// No description provided for @theme.
  ///
  /// In ru, this message translates to:
  /// **'Тема'**
  String get theme;

  /// No description provided for @themeSystem.
  ///
  /// In ru, this message translates to:
  /// **'Как в системе'**
  String get themeSystem;

  /// No description provided for @themeLight.
  ///
  /// In ru, this message translates to:
  /// **'Светлая'**
  String get themeLight;

  /// No description provided for @themeDark.
  ///
  /// In ru, this message translates to:
  /// **'Тёмная'**
  String get themeDark;

  /// No description provided for @settings.
  ///
  /// In ru, this message translates to:
  /// **'Настройки'**
  String get settings;

  /// No description provided for @support.
  ///
  /// In ru, this message translates to:
  /// **'Поддержка'**
  String get support;

  /// No description provided for @terms.
  ///
  /// In ru, this message translates to:
  /// **'Правила использования'**
  String get terms;

  /// No description provided for @privacyPolicy.
  ///
  /// In ru, this message translates to:
  /// **'Политика конфиденциальности'**
  String get privacyPolicy;

  /// No description provided for @aboutApp.
  ///
  /// In ru, this message translates to:
  /// **'О приложении'**
  String get aboutApp;

  /// No description provided for @devTools.
  ///
  /// In ru, this message translates to:
  /// **'Инструменты разработчика'**
  String get devTools;

  /// No description provided for @deleteAccount.
  ///
  /// In ru, this message translates to:
  /// **'Удалить аккаунт'**
  String get deleteAccount;

  /// No description provided for @aboutBody.
  ///
  /// In ru, this message translates to:
  /// **'DARYOB — площадка объявлений для Таджикистана: покупайте, продавайте, ищите работу и услуги рядом с домом.'**
  String get aboutBody;

  /// No description provided for @appVersion.
  ///
  /// In ru, this message translates to:
  /// **'Версия'**
  String get appVersion;

  /// No description provided for @environment.
  ///
  /// In ru, this message translates to:
  /// **'Режим'**
  String get environment;

  /// No description provided for @envDevelopment.
  ///
  /// In ru, this message translates to:
  /// **'Разработка (демо)'**
  String get envDevelopment;

  /// No description provided for @envProduction.
  ///
  /// In ru, this message translates to:
  /// **'Рабочий'**
  String get envProduction;

  /// No description provided for @licenses.
  ///
  /// In ru, this message translates to:
  /// **'Лицензии'**
  String get licenses;

  /// No description provided for @legalDraftNotice.
  ///
  /// In ru, this message translates to:
  /// **'Черновик. Окончательный текст подготовит и утвердит юрист перед запуском.'**
  String get legalDraftNotice;

  /// No description provided for @termsBody.
  ///
  /// In ru, this message translates to:
  /// **'Размещая объявление, вы подтверждаете, что вправе продавать товар или оказывать услугу, а информация в объявлении достоверна. Запрещены мошенничество, запрещённые законом товары и оскорбительный контент. DARYOB может снять объявление, нарушающее правила.'**
  String get termsBody;

  /// No description provided for @privacyBody.
  ///
  /// In ru, this message translates to:
  /// **'DARYOB хранит номер телефона, имя и данные объявлений, чтобы работали вход, публикация и связь с покупателями. Номер показывается в объявлении только если вы это разрешили. Вы можете запросить удаление аккаунта и данных в профиле.'**
  String get privacyBody;

  /// No description provided for @supportBody.
  ///
  /// In ru, this message translates to:
  /// **'Если что-то не работает или вы столкнулись с мошенничеством, сообщите нам.'**
  String get supportBody;

  /// No description provided for @supportNotConfigured.
  ///
  /// In ru, this message translates to:
  /// **'Контакты службы поддержки появятся после запуска сервиса.'**
  String get supportNotConfigured;

  /// No description provided for @deletionBody.
  ///
  /// In ru, this message translates to:
  /// **'Будут удалены ваш аккаунт, объявления и переписка. Действие нельзя отменить.'**
  String get deletionBody;

  /// No description provided for @deletionDevNotice.
  ///
  /// In ru, this message translates to:
  /// **'Демо-режим: удаляются данные на этом телефоне.'**
  String get deletionDevNotice;

  /// No description provided for @deleteAccountConfirmTitle.
  ///
  /// In ru, this message translates to:
  /// **'Удалить аккаунт навсегда?'**
  String get deleteAccountConfirmTitle;

  /// No description provided for @deleteAccountConfirmBody.
  ///
  /// In ru, this message translates to:
  /// **'Все ваши объявления будут удалены.'**
  String get deleteAccountConfirmBody;

  /// No description provided for @accountDeleted.
  ///
  /// In ru, this message translates to:
  /// **'Аккаунт удалён'**
  String get accountDeleted;

  /// No description provided for @safetyTitle.
  ///
  /// In ru, this message translates to:
  /// **'Безопасные сделки'**
  String get safetyTitle;

  /// No description provided for @safetyIntro.
  ///
  /// In ru, this message translates to:
  /// **'Большинство людей на DARYOB честные, но мошенники бывают везде. Несколько простых правил защитят ваши деньги.'**
  String get safetyIntro;

  /// No description provided for @safetyForBuyers.
  ///
  /// In ru, this message translates to:
  /// **'Покупателям'**
  String get safetyForBuyers;

  /// No description provided for @safetyBuyer1.
  ///
  /// In ru, this message translates to:
  /// **'Осматривайте товар лично, до оплаты.'**
  String get safetyBuyer1;

  /// No description provided for @safetyBuyer2.
  ///
  /// In ru, this message translates to:
  /// **'Не переводите предоплату незнакомым продавцам.'**
  String get safetyBuyer2;

  /// No description provided for @safetyBuyer3.
  ///
  /// In ru, this message translates to:
  /// **'Встречайтесь в людных местах днём.'**
  String get safetyBuyer3;

  /// No description provided for @safetyBuyer4.
  ///
  /// In ru, this message translates to:
  /// **'Для дорогих покупок проверяйте документы.'**
  String get safetyBuyer4;

  /// No description provided for @safetyForSellers.
  ///
  /// In ru, this message translates to:
  /// **'Продавцам'**
  String get safetyForSellers;

  /// No description provided for @safetySeller1.
  ///
  /// In ru, this message translates to:
  /// **'Никому не сообщайте коды из SMS.'**
  String get safetySeller1;

  /// No description provided for @safetySeller2.
  ///
  /// In ru, this message translates to:
  /// **'Не сообщайте данные карты — для перевода нужен только номер.'**
  String get safetySeller2;

  /// No description provided for @safetySeller3.
  ///
  /// In ru, this message translates to:
  /// **'Не переходите по ссылкам «для получения оплаты».'**
  String get safetySeller3;

  /// No description provided for @safetyReport.
  ///
  /// In ru, this message translates to:
  /// **'Заметили подозрительное объявление — нажмите «Пожаловаться».'**
  String get safetyReport;

  /// No description provided for @chatsSignInTitle.
  ///
  /// In ru, this message translates to:
  /// **'Переписка с продавцами'**
  String get chatsSignInTitle;

  /// No description provided for @chatsSignInBody.
  ///
  /// In ru, this message translates to:
  /// **'Войдите, чтобы писать продавцам и получать ответы.'**
  String get chatsSignInBody;

  /// No description provided for @chatLocalNotice.
  ///
  /// In ru, this message translates to:
  /// **'Чат-сервер ещё не подключён: сообщения сохраняются на телефоне и не доходят до собеседника.'**
  String get chatLocalNotice;

  /// No description provided for @chatLocalShort.
  ///
  /// In ru, this message translates to:
  /// **'Сообщения не отправляются (демо)'**
  String get chatLocalShort;

  /// No description provided for @chatOnline.
  ///
  /// In ru, this message translates to:
  /// **'Чат'**
  String get chatOnline;

  /// No description provided for @chatsEmpty.
  ///
  /// In ru, this message translates to:
  /// **'Пока нет переписок'**
  String get chatsEmpty;

  /// No description provided for @chatsEmptyBody.
  ///
  /// In ru, this message translates to:
  /// **'Откройте объявление и нажмите «Написать».'**
  String get chatsEmptyBody;

  /// No description provided for @blocked.
  ///
  /// In ru, this message translates to:
  /// **'Заблокирован'**
  String get blocked;

  /// No description provided for @noMessagesYet.
  ///
  /// In ru, this message translates to:
  /// **'Нет сообщений'**
  String get noMessagesYet;

  /// No description provided for @block.
  ///
  /// In ru, this message translates to:
  /// **'Заблокировать'**
  String get block;

  /// No description provided for @unblock.
  ///
  /// In ru, this message translates to:
  /// **'Разблокировать'**
  String get unblock;

  /// No description provided for @blockUserTitle.
  ///
  /// In ru, this message translates to:
  /// **'Заблокировать пользователя?'**
  String get blockUserTitle;

  /// No description provided for @blockUserBody.
  ///
  /// In ru, this message translates to:
  /// **'Вы не сможете переписываться в этом чате, пока не разблокируете.'**
  String get blockUserBody;

  /// No description provided for @deleteChat.
  ///
  /// In ru, this message translates to:
  /// **'Удалить чат'**
  String get deleteChat;

  /// No description provided for @deleteChatTitle.
  ///
  /// In ru, this message translates to:
  /// **'Удалить чат?'**
  String get deleteChatTitle;

  /// No description provided for @deleteChatBody.
  ///
  /// In ru, this message translates to:
  /// **'Переписка будет удалена с этого телефона.'**
  String get deleteChatBody;

  /// No description provided for @sellerProfile.
  ///
  /// In ru, this message translates to:
  /// **'Профиль продавца'**
  String get sellerProfile;

  /// No description provided for @chatStartTitle.
  ///
  /// In ru, this message translates to:
  /// **'Начните разговор'**
  String get chatStartTitle;

  /// No description provided for @chatStartBody.
  ///
  /// In ru, this message translates to:
  /// **'Спросите о состоянии, цене или месте встречи.'**
  String get chatStartBody;

  /// No description provided for @chatBlockedNotice.
  ///
  /// In ru, this message translates to:
  /// **'Пользователь заблокирован'**
  String get chatBlockedNotice;

  /// No description provided for @messageHint.
  ///
  /// In ru, this message translates to:
  /// **'Сообщение'**
  String get messageHint;

  /// No description provided for @msgLocalOnly.
  ///
  /// In ru, this message translates to:
  /// **'не отправлено'**
  String get msgLocalOnly;

  /// No description provided for @msgSending.
  ///
  /// In ru, this message translates to:
  /// **'отправляется'**
  String get msgSending;

  /// No description provided for @msgSent.
  ///
  /// In ru, this message translates to:
  /// **'отправлено'**
  String get msgSent;

  /// No description provided for @msgDelivered.
  ///
  /// In ru, this message translates to:
  /// **'доставлено'**
  String get msgDelivered;

  /// No description provided for @msgRead.
  ///
  /// In ru, this message translates to:
  /// **'прочитано'**
  String get msgRead;

  /// No description provided for @msgFailed.
  ///
  /// In ru, this message translates to:
  /// **'ошибка'**
  String get msgFailed;

  /// No description provided for @markAllRead.
  ///
  /// In ru, this message translates to:
  /// **'Прочитать все'**
  String get markAllRead;

  /// No description provided for @notificationsEmpty.
  ///
  /// In ru, this message translates to:
  /// **'Уведомлений пока нет'**
  String get notificationsEmpty;

  /// No description provided for @pushNotConfigured.
  ///
  /// In ru, this message translates to:
  /// **'Push-уведомления ещё не подключены — новые события видны здесь, в приложении.'**
  String get pushNotConfigured;

  /// No description provided for @notifKindMessages.
  ///
  /// In ru, this message translates to:
  /// **'Новые сообщения'**
  String get notifKindMessages;

  /// No description provided for @notifKindApproved.
  ///
  /// In ru, this message translates to:
  /// **'Объявление одобрено'**
  String get notifKindApproved;

  /// No description provided for @notifKindRejected.
  ///
  /// In ru, this message translates to:
  /// **'Объявление отклонено'**
  String get notifKindRejected;

  /// No description provided for @notifKindExpiring.
  ///
  /// In ru, this message translates to:
  /// **'Срок объявления истекает'**
  String get notifKindExpiring;

  /// No description provided for @notifKindPromotion.
  ///
  /// In ru, this message translates to:
  /// **'Окончание продвижения'**
  String get notifKindPromotion;

  /// No description provided for @notifKindMatching.
  ///
  /// In ru, this message translates to:
  /// **'Новые подходящие объявления'**
  String get notifKindMatching;

  /// No description provided for @notifKindSystem.
  ///
  /// In ru, this message translates to:
  /// **'Системные сообщения'**
  String get notifKindSystem;

  /// No description provided for @notifMessageTitle.
  ///
  /// In ru, this message translates to:
  /// **'Новое сообщение'**
  String get notifMessageTitle;

  /// No description provided for @notifMessageBody.
  ///
  /// In ru, this message translates to:
  /// **'По объявлению «{title}»'**
  String notifMessageBody(String title);

  /// No description provided for @notifApprovedTitle.
  ///
  /// In ru, this message translates to:
  /// **'Объявление одобрено'**
  String get notifApprovedTitle;

  /// No description provided for @notifApprovedBody.
  ///
  /// In ru, this message translates to:
  /// **'«{title}» опубликовано'**
  String notifApprovedBody(String title);

  /// No description provided for @notifRejectedTitle.
  ///
  /// In ru, this message translates to:
  /// **'Объявление отклонено'**
  String get notifRejectedTitle;

  /// No description provided for @notifRejectedBody.
  ///
  /// In ru, this message translates to:
  /// **'Проверьте причину для «{title}»'**
  String notifRejectedBody(String title);

  /// No description provided for @notifExpiringTitle.
  ///
  /// In ru, this message translates to:
  /// **'Срок истекает'**
  String get notifExpiringTitle;

  /// No description provided for @notifExpiringBody.
  ///
  /// In ru, this message translates to:
  /// **'Продлите «{title}», чтобы его видели'**
  String notifExpiringBody(String title);

  /// No description provided for @notifPromotionTitle.
  ///
  /// In ru, this message translates to:
  /// **'Продвижение заканчивается'**
  String get notifPromotionTitle;

  /// No description provided for @notifPromotionBody.
  ///
  /// In ru, this message translates to:
  /// **'Для «{title}»'**
  String notifPromotionBody(String title);

  /// No description provided for @notifMatchingTitle.
  ///
  /// In ru, this message translates to:
  /// **'Новые объявления'**
  String get notifMatchingTitle;

  /// No description provided for @notifMatchingBody.
  ///
  /// In ru, this message translates to:
  /// **'По вашему запросу «{title}»'**
  String notifMatchingBody(String title);

  /// No description provided for @notifWelcomeTitle.
  ///
  /// In ru, this message translates to:
  /// **'Добро пожаловать в DARYOB!'**
  String get notifWelcomeTitle;

  /// No description provided for @notifWelcomeBody.
  ///
  /// In ru, this message translates to:
  /// **'Ищите, находите и продавайте по всему Таджикистану.'**
  String get notifWelcomeBody;

  /// No description provided for @notifSavedLocallyTitle.
  ///
  /// In ru, this message translates to:
  /// **'Объявление сохранено'**
  String get notifSavedLocallyTitle;

  /// No description provided for @notifSavedLocallyBody.
  ///
  /// In ru, this message translates to:
  /// **'«{title}» сохранено на телефоне (демо-режим)'**
  String notifSavedLocallyBody(String title);

  /// No description provided for @notifStatusTitle.
  ///
  /// In ru, this message translates to:
  /// **'Статус изменён'**
  String get notifStatusTitle;

  /// No description provided for @notifStatusBody.
  ///
  /// In ru, this message translates to:
  /// **'Объявление «{title}» обновлено'**
  String notifStatusBody(String title);

  /// No description provided for @sellerNotFound.
  ///
  /// In ru, this message translates to:
  /// **'Продавец не найден'**
  String get sellerNotFound;

  /// No description provided for @sellerListings.
  ///
  /// In ru, this message translates to:
  /// **'Объявления продавца'**
  String get sellerListings;

  /// No description provided for @noActiveListings.
  ///
  /// In ru, this message translates to:
  /// **'Нет активных объявлений'**
  String get noActiveListings;

  /// No description provided for @statistics.
  ///
  /// In ru, this message translates to:
  /// **'Статистика'**
  String get statistics;

  /// No description provided for @statsNotTracked.
  ///
  /// In ru, this message translates to:
  /// **'Просмотры и звонки будут считаться после подключения сервера.'**
  String get statsNotTracked;

  /// No description provided for @businessListings.
  ///
  /// In ru, this message translates to:
  /// **'Объявления компании'**
  String get businessListings;

  /// No description provided for @subscription.
  ///
  /// In ru, this message translates to:
  /// **'Подписка'**
  String get subscription;

  /// No description provided for @subscriptionNone.
  ///
  /// In ru, this message translates to:
  /// **'Не оформлена'**
  String get subscriptionNone;

  /// No description provided for @editBusiness.
  ///
  /// In ru, this message translates to:
  /// **'Данные компании'**
  String get editBusiness;

  /// No description provided for @businessComingSoon.
  ///
  /// In ru, this message translates to:
  /// **'Сотрудники, массовая загрузка и витрина магазина появятся в следующих версиях.'**
  String get businessComingSoon;

  /// No description provided for @requestVerification.
  ///
  /// In ru, this message translates to:
  /// **'Запросить проверку компании'**
  String get requestVerification;

  /// No description provided for @businessIntroTitle.
  ///
  /// In ru, this message translates to:
  /// **'Продаёте как компания?'**
  String get businessIntroTitle;

  /// No description provided for @businessIntroBody.
  ///
  /// In ru, this message translates to:
  /// **'Создайте бизнес-профиль: название компании будет видно на объявлениях.'**
  String get businessIntroBody;

  /// No description provided for @businessName.
  ///
  /// In ru, this message translates to:
  /// **'Название компании'**
  String get businessName;

  /// No description provided for @businessDescription.
  ///
  /// In ru, this message translates to:
  /// **'О компании'**
  String get businessDescription;

  /// No description provided for @businessAddress.
  ///
  /// In ru, this message translates to:
  /// **'Адрес'**
  String get businessAddress;

  /// No description provided for @createBusiness.
  ///
  /// In ru, this message translates to:
  /// **'Создать бизнес-профиль'**
  String get createBusiness;

  /// No description provided for @verNotSubmitted.
  ///
  /// In ru, this message translates to:
  /// **'Не проверена'**
  String get verNotSubmitted;

  /// No description provided for @verPending.
  ///
  /// In ru, this message translates to:
  /// **'На проверке'**
  String get verPending;

  /// No description provided for @verVerified.
  ///
  /// In ru, this message translates to:
  /// **'Проверена'**
  String get verVerified;

  /// No description provided for @verRejected.
  ///
  /// In ru, this message translates to:
  /// **'Проверка не пройдена'**
  String get verRejected;

  /// No description provided for @planStart.
  ///
  /// In ru, this message translates to:
  /// **'Старт'**
  String get planStart;

  /// No description provided for @planStartPerk1.
  ///
  /// In ru, this message translates to:
  /// **'Страница компании'**
  String get planStartPerk1;

  /// No description provided for @planStartPerk2.
  ///
  /// In ru, this message translates to:
  /// **'Больше активных объявлений'**
  String get planStartPerk2;

  /// No description provided for @planPro.
  ///
  /// In ru, this message translates to:
  /// **'Про'**
  String get planPro;

  /// No description provided for @planProPerk1.
  ///
  /// In ru, this message translates to:
  /// **'Всё из «Старт»'**
  String get planProPerk1;

  /// No description provided for @planProPerk2.
  ///
  /// In ru, this message translates to:
  /// **'Подробная статистика'**
  String get planProPerk2;

  /// No description provided for @planProPerk3.
  ///
  /// In ru, this message translates to:
  /// **'Пакет продвижений каждый месяц'**
  String get planProPerk3;

  /// No description provided for @choosePlan.
  ///
  /// In ru, this message translates to:
  /// **'Выбрать'**
  String get choosePlan;

  /// No description provided for @priceNotSet.
  ///
  /// In ru, this message translates to:
  /// **'Цена будет объявлена'**
  String get priceNotSet;

  /// No description provided for @durationDays.
  ///
  /// In ru, this message translates to:
  /// **'{days, plural, one{{days} день} few{{days} дня} many{{days} дней} other{{days} дня}}'**
  String durationDays(int days);

  /// No description provided for @samplePriceNote.
  ///
  /// In ru, this message translates to:
  /// **'Цена-пример из демо-настроек, не реальный тариф.'**
  String get samplePriceNote;

  /// No description provided for @payAndPromote.
  ///
  /// In ru, this message translates to:
  /// **'Оплатить и продвинуть'**
  String get payAndPromote;

  /// No description provided for @paymentUnavailableTitle.
  ///
  /// In ru, this message translates to:
  /// **'Оплата недоступна'**
  String get paymentUnavailableTitle;

  /// No description provided for @devActivate.
  ///
  /// In ru, this message translates to:
  /// **'Включить без оплаты (только DEV)'**
  String get devActivate;

  /// No description provided for @devActivateTitle.
  ///
  /// In ru, this message translates to:
  /// **'Тестовое продвижение'**
  String get devActivateTitle;

  /// No description provided for @devActivateBody.
  ///
  /// In ru, this message translates to:
  /// **'Продвижение включится без оплаты только в демо-сборке, чтобы проверить отображение VIP и ТОП.'**
  String get devActivateBody;

  /// No description provided for @devActivated.
  ///
  /// In ru, this message translates to:
  /// **'Тестовое продвижение включено'**
  String get devActivated;

  /// No description provided for @walletBalance.
  ///
  /// In ru, this message translates to:
  /// **'Баланс'**
  String get walletBalance;

  /// No description provided for @topUp.
  ///
  /// In ru, this message translates to:
  /// **'Пополнить'**
  String get topUp;

  /// No description provided for @transactionHistory.
  ///
  /// In ru, this message translates to:
  /// **'История операций'**
  String get transactionHistory;

  /// No description provided for @noTransactions.
  ///
  /// In ru, this message translates to:
  /// **'Операций пока нет'**
  String get noTransactions;

  /// No description provided for @noPromotions.
  ///
  /// In ru, this message translates to:
  /// **'Нет продвижений'**
  String get noPromotions;

  /// No description provided for @noPromotionsBody.
  ///
  /// In ru, this message translates to:
  /// **'Продвигайте объявления, чтобы их видели больше покупателей.'**
  String get noPromotionsBody;

  /// No description provided for @until.
  ///
  /// In ru, this message translates to:
  /// **'до {date}'**
  String until(String date);

  /// No description provided for @promotionActive.
  ///
  /// In ru, this message translates to:
  /// **'Активно'**
  String get promotionActive;

  /// No description provided for @promotionEnded.
  ///
  /// In ru, this message translates to:
  /// **'Завершено'**
  String get promotionEnded;

  /// No description provided for @defaultRegionHint.
  ///
  /// In ru, this message translates to:
  /// **'Для раздела «Рядом» и поиска'**
  String get defaultRegionHint;

  /// No description provided for @privacy.
  ///
  /// In ru, this message translates to:
  /// **'Приватность'**
  String get privacy;

  /// No description provided for @hidePhoneByDefault.
  ///
  /// In ru, this message translates to:
  /// **'Скрывать номер в новых объявлениях'**
  String get hidePhoneByDefault;

  /// No description provided for @hidePhoneByDefaultHint.
  ///
  /// In ru, this message translates to:
  /// **'Покупатели смогут писать только в чат'**
  String get hidePhoneByDefaultHint;

  /// No description provided for @dataDeletion.
  ///
  /// In ru, this message translates to:
  /// **'Удаление данных'**
  String get dataDeletion;

  /// No description provided for @devToolsNotice.
  ///
  /// In ru, this message translates to:
  /// **'Только для сборки разработчика. В рабочей версии этого экрана нет.'**
  String get devToolsNotice;

  /// No description provided for @devConfirm.
  ///
  /// In ru, this message translates to:
  /// **'Действие изменит локальные данные на этом телефоне.'**
  String get devConfirm;

  /// No description provided for @apiUrl.
  ///
  /// In ru, this message translates to:
  /// **'Адрес API'**
  String get apiUrl;

  /// No description provided for @notConfigured.
  ///
  /// In ru, this message translates to:
  /// **'Не настроен'**
  String get notConfigured;

  /// No description provided for @devResetOnboarding.
  ///
  /// In ru, this message translates to:
  /// **'Показать онбординг заново'**
  String get devResetOnboarding;

  /// No description provided for @devReseed.
  ///
  /// In ru, this message translates to:
  /// **'Пересоздать демо-объявления'**
  String get devReseed;

  /// No description provided for @devRemoveDemo.
  ///
  /// In ru, this message translates to:
  /// **'Удалить демо-объявления'**
  String get devRemoveDemo;

  /// No description provided for @devWipe.
  ///
  /// In ru, this message translates to:
  /// **'Стереть все локальные данные'**
  String get devWipe;

  /// No description provided for @errTitle.
  ///
  /// In ru, this message translates to:
  /// **'Что-то пошло не так'**
  String get errTitle;

  /// No description provided for @errNetwork.
  ///
  /// In ru, this message translates to:
  /// **'Нет подключения к интернету. Проверьте сеть и попробуйте снова.'**
  String get errNetwork;

  /// No description provided for @errTimeout.
  ///
  /// In ru, this message translates to:
  /// **'Сервер долго не отвечает. Попробуйте ещё раз.'**
  String get errTimeout;

  /// No description provided for @errUnauthorized.
  ///
  /// In ru, this message translates to:
  /// **'Нужно войти заново.'**
  String get errUnauthorized;

  /// No description provided for @errSessionExpired.
  ///
  /// In ru, this message translates to:
  /// **'Сессия истекла. Войдите снова.'**
  String get errSessionExpired;

  /// No description provided for @errForbidden.
  ///
  /// In ru, this message translates to:
  /// **'У вас нет прав на это действие.'**
  String get errForbidden;

  /// No description provided for @errRateLimited.
  ///
  /// In ru, this message translates to:
  /// **'Слишком много попыток. Подождите немного.'**
  String get errRateLimited;

  /// No description provided for @errNotFound.
  ///
  /// In ru, this message translates to:
  /// **'Не найдено'**
  String get errNotFound;

  /// No description provided for @errValidation.
  ///
  /// In ru, this message translates to:
  /// **'Проверьте введённые данные.'**
  String get errValidation;

  /// No description provided for @errServer.
  ///
  /// In ru, this message translates to:
  /// **'Ошибка на сервере. Мы уже разбираемся.'**
  String get errServer;

  /// No description provided for @errUnknown.
  ///
  /// In ru, this message translates to:
  /// **'Неизвестная ошибка. Попробуйте ещё раз.'**
  String get errUnknown;

  /// No description provided for @unavailableTitle.
  ///
  /// In ru, this message translates to:
  /// **'Пока недоступно'**
  String get unavailableTitle;

  /// No description provided for @unavailableBackend.
  ///
  /// In ru, this message translates to:
  /// **'Сервер DARYOB ещё не подключён в этой сборке.'**
  String get unavailableBackend;

  /// No description provided for @unavailableSms.
  ///
  /// In ru, this message translates to:
  /// **'Вход по SMS станет доступен после подключения SMS-сервиса.'**
  String get unavailableSms;

  /// No description provided for @unavailablePayments.
  ///
  /// In ru, this message translates to:
  /// **'Оплата ещё не подключена. Платёжный сервис будет добавлен позже.'**
  String get unavailablePayments;

  /// No description provided for @unavailablePush.
  ///
  /// In ru, this message translates to:
  /// **'Push-уведомления ещё не подключены.'**
  String get unavailablePush;

  /// No description provided for @unavailableChat.
  ///
  /// In ru, this message translates to:
  /// **'Чат станет доступен после подключения чат-сервера.'**
  String get unavailableChat;

  /// No description provided for @valRequired.
  ///
  /// In ru, this message translates to:
  /// **'Обязательное поле'**
  String get valRequired;

  /// No description provided for @valTooShort.
  ///
  /// In ru, this message translates to:
  /// **'Минимум {count} символов'**
  String valTooShort(int count);

  /// No description provided for @valTooLong.
  ///
  /// In ru, this message translates to:
  /// **'Максимум {count} символов'**
  String valTooLong(int count);

  /// No description provided for @valTooShortGeneric.
  ///
  /// In ru, this message translates to:
  /// **'Слишком коротко'**
  String get valTooShortGeneric;

  /// No description provided for @valTooLongGeneric.
  ///
  /// In ru, this message translates to:
  /// **'Слишком длинно'**
  String get valTooLongGeneric;

  /// No description provided for @valInvalidNumber.
  ///
  /// In ru, this message translates to:
  /// **'Введите число'**
  String get valInvalidNumber;

  /// No description provided for @valOutOfRange.
  ///
  /// In ru, this message translates to:
  /// **'Недопустимое значение'**
  String get valOutOfRange;

  /// No description provided for @valInvalidPhone.
  ///
  /// In ru, this message translates to:
  /// **'Введите 9 цифр номера после +992'**
  String get valInvalidPhone;

  /// No description provided for @valInvalidCode.
  ///
  /// In ru, this message translates to:
  /// **'Неверный код'**
  String get valInvalidCode;

  /// No description provided for @valTooManyPhotos.
  ///
  /// In ru, this message translates to:
  /// **'Не больше {count} фото'**
  String valTooManyPhotos(int count);

  /// No description provided for @ageJustNow.
  ///
  /// In ru, this message translates to:
  /// **'только что'**
  String get ageJustNow;

  /// No description provided for @ageMinutes.
  ///
  /// In ru, this message translates to:
  /// **'{count} мин назад'**
  String ageMinutes(int count);

  /// No description provided for @ageHours.
  ///
  /// In ru, this message translates to:
  /// **'{count} ч назад'**
  String ageHours(int count);

  /// No description provided for @ageDays.
  ///
  /// In ru, this message translates to:
  /// **'{count} дн. назад'**
  String ageDays(int count);

  /// No description provided for @salaryNotSpecified.
  ///
  /// In ru, this message translates to:
  /// **'Зарплата не указана'**
  String get salaryNotSpecified;

  /// No description provided for @perMonth.
  ///
  /// In ru, this message translates to:
  /// **'/мес'**
  String get perMonth;

  /// No description provided for @perDay.
  ///
  /// In ru, this message translates to:
  /// **'/сутки'**
  String get perDay;

  /// No description provided for @pickerSearchHint.
  ///
  /// In ru, this message translates to:
  /// **'Поиск'**
  String get pickerSearchHint;

  /// No description provided for @pickerOther.
  ///
  /// In ru, this message translates to:
  /// **'Нет в списке — ввести вручную'**
  String get pickerOther;

  /// No description provided for @pickerOtherHint.
  ///
  /// In ru, this message translates to:
  /// **'Введите название'**
  String get pickerOtherHint;

  /// No description provided for @pickerOtherNote.
  ///
  /// In ru, this message translates to:
  /// **'Значение сохранится как текст продавца и не будет отмечено как проверенное.'**
  String get pickerOtherNote;

  /// No description provided for @catalogNotLoaded.
  ///
  /// In ru, this message translates to:
  /// **'Справочник для этого поля ещё не загружен — введите значение вручную.'**
  String get catalogNotLoaded;

  /// No description provided for @stepSubcategory.
  ///
  /// In ru, this message translates to:
  /// **'Подкатегория'**
  String get stepSubcategory;

  /// No description provided for @stepDetails.
  ///
  /// In ru, this message translates to:
  /// **'Характеристики'**
  String get stepDetails;

  /// No description provided for @tagsHint.
  ///
  /// In ru, this message translates to:
  /// **'Через запятую'**
  String get tagsHint;

  /// No description provided for @mapPinComingSoon.
  ///
  /// In ru, this message translates to:
  /// **'Отметка на карте появится после подключения карт. Укажите город и район.'**
  String get mapPinComingSoon;

  /// No description provided for @atLeast.
  ///
  /// In ru, this message translates to:
  /// **'от {value}'**
  String atLeast(String value);

  /// No description provided for @modelsUnverifiedNote.
  ///
  /// In ru, this message translates to:
  /// **'Список моделей — стартовый и не проверен производителем. Если модели нет, введите её вручную.'**
  String get modelsUnverifiedNote;

  /// No description provided for @verifiedSource.
  ///
  /// In ru, this message translates to:
  /// **'Проверено: {source}'**
  String verifiedSource(String source);

  /// No description provided for @variantNotVerified.
  ///
  /// In ru, this message translates to:
  /// **'Проверенных вариантов для этой модели пока нет — укажите значение вручную.'**
  String get variantNotVerified;

  /// No description provided for @modelFreeText.
  ///
  /// In ru, this message translates to:
  /// **'Сначала выберите марку или введите модель вручную'**
  String get modelFreeText;

  /// No description provided for @choose.
  ///
  /// In ru, this message translates to:
  /// **'Выбрать'**
  String get choose;

  /// No description provided for @notInCatalog.
  ///
  /// In ru, this message translates to:
  /// **'введено вручную'**
  String get notInCatalog;

  /// No description provided for @chooseSubcategoryError.
  ///
  /// In ru, this message translates to:
  /// **'Выберите подкатегорию'**
  String get chooseSubcategoryError;

  /// No description provided for @noCharacteristics.
  ///
  /// In ru, this message translates to:
  /// **'Для этой подкатегории дополнительных характеристик нет.'**
  String get noCharacteristics;

  /// No description provided for @catalogStarterNotice.
  ///
  /// In ru, this message translates to:
  /// **'Справочники брендов и моделей пока стартовые. Если чего-то нет — введите вручную.'**
  String get catalogStarterNotice;

  /// No description provided for @useTitle.
  ///
  /// In ru, this message translates to:
  /// **'Использовать: {title}'**
  String useTitle(String title);

  /// No description provided for @salaryInCharacteristics.
  ///
  /// In ru, this message translates to:
  /// **'Зарплата указывается в характеристиках вакансии.'**
  String get salaryInCharacteristics;

  /// No description provided for @photosRequired.
  ///
  /// In ru, this message translates to:
  /// **'Нужно минимум {count} фото'**
  String photosRequired(int count);

  /// No description provided for @vehiclePhotoTips.
  ///
  /// In ru, this message translates to:
  /// **'Снимите машину спереди, сзади, сбоку, салон и приборную панель.'**
  String get vehiclePhotoTips;

  /// No description provided for @subcategory.
  ///
  /// In ru, this message translates to:
  /// **'Подкатегория'**
  String get subcategory;

  /// No description provided for @chooseCategoryForFilters.
  ///
  /// In ru, this message translates to:
  /// **'Выберите категорию, чтобы увидеть её фильтры.'**
  String get chooseCategoryForFilters;

  /// No description provided for @any.
  ///
  /// In ru, this message translates to:
  /// **'Любой'**
  String get any;

  /// No description provided for @containsHint.
  ///
  /// In ru, this message translates to:
  /// **'Содержит текст'**
  String get containsHint;

  /// No description provided for @valNotAboveOther.
  ///
  /// In ru, this message translates to:
  /// **'Не больше, чем «{other}»'**
  String valNotAboveOther(String other);

  /// No description provided for @devCatalog.
  ///
  /// In ru, this message translates to:
  /// **'Каталог категорий'**
  String get devCatalog;

  /// No description provided for @devCatalogInfo.
  ///
  /// In ru, this message translates to:
  /// **'Версия {version} · {top} категорий, {sub} подкатегорий · импортов: {batches}'**
  String devCatalogInfo(String version, int top, int sub, int batches);

  /// No description provided for @devCatalogImport.
  ///
  /// In ru, this message translates to:
  /// **'Импорт проверенных данных'**
  String get devCatalogImport;

  /// No description provided for @devCatalogImportHint.
  ///
  /// In ru, this message translates to:
  /// **'JSON-пакет из буфера обмена. Записи без источника, даты проверки и лицензии отклоняются.'**
  String get devCatalogImportHint;

  /// No description provided for @devCatalogImportInvalid.
  ///
  /// In ru, this message translates to:
  /// **'В буфере нет JSON-пакета импорта'**
  String get devCatalogImportInvalid;

  /// No description provided for @devCatalogImportResult.
  ///
  /// In ru, this message translates to:
  /// **'Принято: {accepted}. Отклонено: {rejected}.'**
  String devCatalogImportResult(int accepted, int rejected);

  /// No description provided for @devCatalogRollback.
  ///
  /// In ru, this message translates to:
  /// **'Вернуть предыдущую версию каталога'**
  String get devCatalogRollback;

  /// No description provided for @devCatalogNoPrevious.
  ///
  /// In ru, this message translates to:
  /// **'Предыдущей версии нет'**
  String get devCatalogNoPrevious;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ru', 'tg'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ru':
      return AppLocalizationsRu();
    case 'tg':
      return AppLocalizationsTg();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
