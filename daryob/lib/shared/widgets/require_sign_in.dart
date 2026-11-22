import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/router/routes.dart';
import '../../features/authentication/application/session_controller.dart';

/// Guests can browse freely; publishing, chatting and managing listings
/// need an account. Returns true when a user is signed in (possibly after
/// completing the sign-in screen).
Future<bool> requireSignIn(BuildContext context, WidgetRef ref) async {
  if (ref.read(sessionControllerProvider) != null) return true;
  await context.push<bool>(Routes.auth);
  return ref.read(sessionControllerProvider) != null;
}
