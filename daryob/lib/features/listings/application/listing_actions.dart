import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/require_sign_in.dart';
import '../../../shared/widgets/toast.dart';
import '../../authentication/application/session_controller.dart';
import '../../notifications/application/notification_providers.dart';
import '../../notifications/domain/app_notification.dart';
import 'listing_providers.dart';

/// User actions on a listing, shared by the detail screen and "My listings".
class ListingActions {
  ListingActions(this.context, this.ref);

  final BuildContext context;
  final WidgetRef ref;

  Future<void> call(Listing listing) async {
    final l10n = context.l10n;
    final digits = Formatters.nationalDigits(listing.contact.phone);
    final uri = Uri(scheme: 'tel', path: '+992$digits');
    final ok = await canLaunchUrl(uri) && await launchUrl(uri);
    if (!ok && context.mounted) {
      DaryobToast.show(context, l10n.callFailed, isError: true);
    }
  }

  Future<void> openChat(Listing listing, String sellerName) async {
    final l10n = context.l10n;
    if (!await requireSignIn(context, ref)) return;
    final user = ref.read(sessionControllerProvider)!;
    if (user.id == listing.ownerId) {
      if (context.mounted) DaryobToast.show(context, l10n.chatOwnListing);
      return;
    }
    try {
      final conversation = await ref
          .read(conversationRepositoryProvider)
          .openForListing(
            ownerId: user.id,
            listingId: listing.id,
            listingTitle: listing.title,
            listingPhoto: listing.photos.isEmpty ? null : listing.photos.first,
            sellerId: listing.ownerId,
            sellerName: sellerName,
            isDemo: listing.isDemo,
          );
      if (context.mounted) {
        await context.push(Routes.conversation(conversation.id));
      }
    } catch (e) {
      if (context.mounted) {
        DaryobToast.show(context, failureMessage(l10n, e), isError: true);
      }
    }
  }

  Future<bool> setStatus(Listing listing, ListingStatus status) async {
    final l10n = context.l10n;
    final user = ref.read(sessionControllerProvider);
    if (user == null) return false;
    try {
      await ref
          .read(listingRepositoryProvider)
          .changeStatus(listing.id, status, actingUserId: user.id);
      invalidateListingsFromWidget(ref);
      await ref
          .read(notificationServiceProvider)
          .notify(
            NotificationKind.system,
            params: {'code': 'status_changed', 'title': listing.title},
            listingId: listing.id,
          );
      if (context.mounted) {
        DaryobToast.show(
          context,
          l10n.statusChangedTo(statusLabel(l10n, status)),
        );
      }
      return true;
    } catch (e) {
      if (context.mounted) {
        DaryobToast.show(context, failureMessage(l10n, e), isError: true);
      }
      return false;
    }
  }

  Future<bool> delete(Listing listing) async {
    final l10n = context.l10n;
    final user = ref.read(sessionControllerProvider);
    if (user == null) return false;
    final confirmed = await DaryobConfirmationDialog.show(
      context,
      title: l10n.deleteListingTitle,
      message: l10n.deleteListingBody,
      confirmLabel: l10n.delete,
      destructive: true,
    );
    if (!confirmed) return false;
    try {
      await ref
          .read(listingRepositoryProvider)
          .delete(listing.id, actingUserId: user.id);
      invalidateListingsFromWidget(ref);
      if (context.mounted) DaryobToast.show(context, l10n.listingDeleted);
      return true;
    } catch (e) {
      if (context.mounted) {
        DaryobToast.show(context, failureMessage(l10n, e), isError: true);
      }
      return false;
    }
  }
}
