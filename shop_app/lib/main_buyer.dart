import 'buyer/buyer_shell.dart';
import 'core/app.dart';
import 'core/models.dart';

/// «Витрина» — приложение покупателя.
void main() => runMarketApp(Role.buyer, const BuyerShell());
