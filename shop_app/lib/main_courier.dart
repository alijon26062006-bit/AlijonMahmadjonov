import 'core/app.dart';
import 'core/models.dart';
import 'courier/courier_shell.dart';

/// «Витрина Курьер» — приложение для курьеров.
void main() => runMarketApp(Role.courier, const CourierRoot());
