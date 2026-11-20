import 'core/app.dart';
import 'core/models.dart';
import 'seller/seller_shell.dart';

/// 🏪 «Витрина Продавец» — приложение для магазинов.
void main() => runMarketApp(Role.seller, const SellerRoot());
