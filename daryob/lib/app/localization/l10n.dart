import 'package:flutter/widgets.dart';

import '../../core/errors/failure.dart';
import '../../core/utils/formatters.dart';
import '../../core/utils/validators.dart';
import '../../features/listings/domain/listing_query.dart';
import '../../features/notifications/domain/app_notification.dart';
import '../../features/sellers/domain/business_profile.dart';
import '../../features/settings/domain/app_settings.dart';
import '../../shared/models/listing.dart';
import '../../shared/models/money.dart';
import 'gen/app_localizations.dart';

export 'gen/app_localizations.dart';

extension L10nContext on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this);
  String get languageCode => Localizations.localeOf(this).languageCode;
}

/// Localised text for an error. Never shows raw exception text.
String failureMessage(AppLocalizations l10n, Object error) {
  final failure = asFailure(error);
  return switch (failure) {
    NetworkFailure() => l10n.errNetwork,
    TimeoutFailure() => l10n.errTimeout,
    UnauthorizedFailure(sessionExpired: true) => l10n.errSessionExpired,
    UnauthorizedFailure() => l10n.errUnauthorized,
    ForbiddenFailure() => l10n.errForbidden,
    RateLimitedFailure() => l10n.errRateLimited,
    NotFoundFailure() => l10n.errNotFound,
    ValidationFailure() => l10n.errValidation,
    ServerFailure() => l10n.errServer,
    FeatureUnavailableFailure(:final feature) => unavailableMessage(
      l10n,
      feature,
    ),
    UnknownFailure() => l10n.errUnknown,
  };
}

String unavailableMessage(AppLocalizations l10n, UnavailableFeature feature) {
  return switch (feature) {
    UnavailableFeature.backend => l10n.unavailableBackend,
    UnavailableFeature.sms => l10n.unavailableSms,
    UnavailableFeature.payments => l10n.unavailablePayments,
    UnavailableFeature.push => l10n.unavailablePush,
    UnavailableFeature.realtimeChat => l10n.unavailableChat,
  };
}

/// Text for a [ValidationCode]. [min]/[max] add the limit to the message.
String? validationMessage(
  AppLocalizations l10n,
  String? code, {
  int? min,
  int? max,
  String? other,
}) {
  if (code == null) return null;
  return switch (code) {
    ValidationCode.required => l10n.valRequired,
    ValidationCode.tooShort =>
      min == null ? l10n.valTooShortGeneric : l10n.valTooShort(min),
    ValidationCode.tooLong =>
      max == null ? l10n.valTooLongGeneric : l10n.valTooLong(max),
    ValidationCode.invalidNumber => l10n.valInvalidNumber,
    ValidationCode.outOfRange => l10n.valOutOfRange,
    ValidationCode.invalidPhone => l10n.valInvalidPhone,
    ValidationCode.invalidCode => l10n.valInvalidCode,
    ValidationCode.tooManyPhotos => l10n.valTooManyPhotos(
      max ?? ListingLimits.photosMax,
    ),
    ValidationCode.tooFewPhotos => l10n.photosRequired(min ?? 1),
    ValidationCode.notAboveOther =>
      other == null ? l10n.valOutOfRange : l10n.valNotAboveOther(other),
    _ => l10n.valRequired,
  };
}

String ageLabel(AppLocalizations l10n, DateTime moment, DateTime now) {
  final age = Age.of(moment, now);
  return switch (age.unit) {
    AgeUnit.justNow => l10n.ageJustNow,
    AgeUnit.minutes => l10n.ageMinutes(age.value),
    AgeUnit.hours => l10n.ageHours(age.value),
    AgeUnit.days => l10n.ageDays(age.value),
    AgeUnit.date => Formatters.date(moment),
  };
}

String priceLabel(
  AppLocalizations l10n,
  String languageCode, {
  required int? price,
  required Currency currency,
  required bool isFreeCategory,
}) {
  if (isFreeCategory || price == 0) return l10n.priceFree;
  if (price == null) return l10n.priceOnRequest;
  return Formatters.price(price, currency, languageCode);
}

String statusLabel(AppLocalizations l10n, ListingStatus status) =>
    switch (status) {
      ListingStatus.draft => l10n.statusDraft,
      ListingStatus.pending => l10n.statusPending,
      ListingStatus.active => l10n.statusActive,
      ListingStatus.sold => l10n.statusSold,
      ListingStatus.archived => l10n.statusArchived,
      ListingStatus.rejected => l10n.statusRejected,
    };

String promotionLabel(AppLocalizations l10n, PromotionType type) =>
    switch (type) {
      PromotionType.free => l10n.promoFree,
      PromotionType.boost => l10n.promoBoost,
      PromotionType.top => l10n.promoTop,
      PromotionType.vip => l10n.promoVip,
      PromotionType.vipPlus => l10n.promoVipPlus,
      PromotionType.businessSubscription => l10n.promoBusiness,
    };

String sortLabel(AppLocalizations l10n, ListingSort sort) => switch (sort) {
  ListingSort.relevance => l10n.sortRelevance,
  ListingSort.newest => l10n.sortNewest,
  ListingSort.priceAsc => l10n.sortPriceAsc,
  ListingSort.priceDesc => l10n.sortPriceDesc,
};

String reportReasonLabel(AppLocalizations l10n, ReportReason reason) =>
    switch (reason) {
      ReportReason.fraud => l10n.reportFraud,
      ReportReason.prohibited => l10n.reportProhibited,
      ReportReason.wrongCategory => l10n.reportWrongCategory,
      ReportReason.duplicate => l10n.reportDuplicate,
      ReportReason.sold => l10n.reportSold,
      ReportReason.offensive => l10n.reportOffensive,
      ReportReason.other => l10n.reportOther,
    };

String verificationLabel(AppLocalizations l10n, VerificationStatus status) =>
    switch (status) {
      VerificationStatus.notSubmitted => l10n.verNotSubmitted,
      VerificationStatus.pending => l10n.verPending,
      VerificationStatus.verified => l10n.verVerified,
      VerificationStatus.rejected => l10n.verRejected,
    };

String themeLabel(AppLocalizations l10n, AppThemePreference theme) =>
    switch (theme) {
      AppThemePreference.system => l10n.themeSystem,
      AppThemePreference.light => l10n.themeLight,
      AppThemePreference.dark => l10n.themeDark,
    };

String notificationKindLabel(AppLocalizations l10n, NotificationKind kind) =>
    switch (kind) {
      NotificationKind.newMessage => l10n.notifKindMessages,
      NotificationKind.listingApproved => l10n.notifKindApproved,
      NotificationKind.listingRejected => l10n.notifKindRejected,
      NotificationKind.listingExpiring => l10n.notifKindExpiring,
      NotificationKind.promotionEnding => l10n.notifKindPromotion,
      NotificationKind.newMatchingListing => l10n.notifKindMatching,
      NotificationKind.system => l10n.notifKindSystem,
    };

/// Title and body of a stored notification in the current language.
(String, String) notificationText(AppLocalizations l10n, AppNotification n) {
  final title = n.params['title'] ?? '';
  return switch (n.kind) {
    NotificationKind.newMessage => (
      l10n.notifMessageTitle,
      l10n.notifMessageBody(title),
    ),
    NotificationKind.listingApproved => (
      l10n.notifApprovedTitle,
      l10n.notifApprovedBody(title),
    ),
    NotificationKind.listingRejected => (
      l10n.notifRejectedTitle,
      l10n.notifRejectedBody(title),
    ),
    NotificationKind.listingExpiring => (
      l10n.notifExpiringTitle,
      l10n.notifExpiringBody(title),
    ),
    NotificationKind.promotionEnding => (
      l10n.notifPromotionTitle,
      l10n.notifPromotionBody(title),
    ),
    NotificationKind.newMatchingListing => (
      l10n.notifMatchingTitle,
      l10n.notifMatchingBody(title),
    ),
    NotificationKind.system => switch (n.params['code']) {
      'saved_locally' => (
        l10n.notifSavedLocallyTitle,
        l10n.notifSavedLocallyBody(title),
      ),
      'status_changed' => (l10n.notifStatusTitle, l10n.notifStatusBody(title)),
      _ => (l10n.notifWelcomeTitle, l10n.notifWelcomeBody),
    },
  };
}
