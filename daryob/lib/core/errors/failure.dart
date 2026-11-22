/// Every error that reaches the UI is one of these. Screens turn them into
/// localised text with `failureMessage` — never raw exception strings or
/// stack traces.
sealed class AppFailure implements Exception {
  const AppFailure();
}

class NetworkFailure extends AppFailure {
  const NetworkFailure();
}

class TimeoutFailure extends AppFailure {
  const TimeoutFailure();
}

class UnauthorizedFailure extends AppFailure {
  const UnauthorizedFailure({this.sessionExpired = false});
  final bool sessionExpired;
}

class ForbiddenFailure extends AppFailure {
  const ForbiddenFailure();
}

class RateLimitedFailure extends AppFailure {
  const RateLimitedFailure();
}

class NotFoundFailure extends AppFailure {
  const NotFoundFailure();
}

class ValidationFailure extends AppFailure {
  const ValidationFailure([this.fieldErrors = const {}]);

  /// Field key → error code (see `ValidationCode`).
  final Map<String, String> fieldErrors;
}

class ServerFailure extends AppFailure {
  const ServerFailure([this.statusCode]);
  final int? statusCode;
}

/// A feature whose backend service is not connected in this build.
enum UnavailableFeature { backend, sms, payments, push, realtimeChat }

class FeatureUnavailableFailure extends AppFailure {
  const FeatureUnavailableFailure(this.feature);
  final UnavailableFeature feature;
}

class UnknownFailure extends AppFailure {
  const UnknownFailure([this.cause]);
  final Object? cause;
}

AppFailure asFailure(Object error) =>
    error is AppFailure ? error : UnknownFailure(error);
