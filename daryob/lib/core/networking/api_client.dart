import 'package:dio/dio.dart';

import '../errors/failure.dart';
import '../security/session_storage.dart';

/// Thin wrapper around Dio: base URL, timeouts, auth header, safe retries and
/// mapping of transport errors to [AppFailure].
class ApiClient {
  ApiClient({
    required String baseUrl,
    required SessionStorage sessionStorage,
    Dio? dio,
  }) : _dio = dio ?? Dio() {
    _dio.options
      ..baseUrl = baseUrl
      ..connectTimeout = const Duration(seconds: 10)
      ..receiveTimeout = const Duration(seconds: 20)
      ..sendTimeout = const Duration(seconds: 30)
      ..responseType = ResponseType.json
      ..headers['Accept'] = 'application/json';
    _dio.interceptors
      ..add(AuthInterceptor(sessionStorage))
      ..add(RetryInterceptor(_dio));
  }

  final Dio _dio;

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, dynamic>? query,
    CancelToken? cancelToken,
  }) => _send(
    () => _dio.get<dynamic>(
      path,
      queryParameters: query,
      cancelToken: cancelToken,
    ),
  );

  Future<Map<String, dynamic>> postJson(
    String path, {
    Object? body,
    CancelToken? cancelToken,
  }) => _send(
    () => _dio.post<dynamic>(path, data: body, cancelToken: cancelToken),
  );

  Future<Map<String, dynamic>> patchJson(
    String path, {
    Object? body,
    CancelToken? cancelToken,
  }) => _send(
    () => _dio.patch<dynamic>(path, data: body, cancelToken: cancelToken),
  );

  Future<void> delete(String path, {CancelToken? cancelToken}) async {
    await _send(() => _dio.delete<dynamic>(path, cancelToken: cancelToken));
  }

  Future<Map<String, dynamic>> _send(
    Future<Response<dynamic>> Function() request,
  ) async {
    try {
      final response = await request();
      final data = response.data;
      if (data == null || data == '') return const {};
      if (data is Map<String, dynamic>) return data;
      // The API contract always wraps payloads in an object.
      throw const ServerFailure();
    } on DioException catch (e) {
      throw mapDioException(e);
    }
  }
}

AppFailure mapDioException(DioException e) {
  switch (e.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
      return const TimeoutFailure();
    case DioExceptionType.connectionError:
      return const NetworkFailure();
    case DioExceptionType.cancel:
      return const UnknownFailure('cancelled');
    case DioExceptionType.badCertificate:
      return const NetworkFailure();
    case DioExceptionType.badResponse:
      return mapStatusCode(e.response?.statusCode, e.response?.data);
    case DioExceptionType.unknown:
      return const NetworkFailure();
    default:
      return const TimeoutFailure();
  }
}

AppFailure mapStatusCode(int? status, [Object? body]) {
  switch (status) {
    case 400:
    case 422:
      final errors = <String, String>{};
      if (body is Map && body['errors'] is Map) {
        (body['errors'] as Map).forEach((k, v) => errors['$k'] = '$v');
      }
      return ValidationFailure(errors);
    case 401:
      final expired = body is Map && body['code'] == 'session_expired';
      return UnauthorizedFailure(sessionExpired: expired);
    case 403:
      return const ForbiddenFailure();
    case 404:
      return const NotFoundFailure();
    case 429:
      return const RateLimitedFailure();
    default:
      return ServerFailure(status);
  }
}

class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._storage);
  final SessionStorage _storage;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _storage.read(SessionKeys.accessToken);
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }
}

/// Retries idempotent GET requests on connection problems only. Never retries
/// writes, so a listing or message can't be created twice.
class RetryInterceptor extends Interceptor {
  RetryInterceptor(this._dio, {this.maxRetries = 2});

  final Dio _dio;
  final int maxRetries;

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final options = err.requestOptions;
    final attempt = (options.extra['retry_attempt'] as int?) ?? 0;
    final retryable =
        options.method == 'GET' &&
        attempt < maxRetries &&
        (err.type == DioExceptionType.connectionError ||
            err.type == DioExceptionType.connectionTimeout);
    if (!retryable) return handler.next(err);

    await Future<void>.delayed(Duration(milliseconds: 400 * (attempt + 1)));
    options.extra['retry_attempt'] = attempt + 1;
    try {
      final response = await _dio.fetch<dynamic>(options);
      handler.resolve(response);
    } on DioException catch (e) {
      handler.next(e);
    }
  }
}
