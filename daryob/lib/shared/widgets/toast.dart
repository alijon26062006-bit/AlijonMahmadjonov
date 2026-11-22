import 'package:material_ui/material_ui.dart';

abstract final class DaryobToast {
  static void show(
    BuildContext context,
    String message, {
    String? actionLabel,
    VoidCallback? onAction,
    bool isError = false,
  }) {
    final messenger = ScaffoldMessenger.maybeOf(context);
    if (messenger == null) return;
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Row(
            children: [
              if (isError) ...[
                const Icon(
                  Icons.error_outline_rounded,
                  color: Colors.white,
                  size: 20,
                ),
                const SizedBox(width: 8),
              ],
              Expanded(child: Text(message)),
            ],
          ),
          duration: const Duration(seconds: 3),
          action: actionLabel == null
              ? null
              : SnackBarAction(
                  label: actionLabel,
                  textColor: const Color(0xFFC9F24B),
                  onPressed: onAction ?? () {},
                ),
        ),
      );
  }
}
