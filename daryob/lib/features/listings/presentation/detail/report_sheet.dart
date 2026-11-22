import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../../../app/localization/l10n.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../core/utils/ids.dart';
import '../../../../shared/models/listing.dart';
import '../../../../shared/providers/core_providers.dart';
import '../../../../shared/providers/repository_providers.dart';
import '../../../../shared/widgets/buttons.dart';
import '../../../../shared/widgets/daryob_text_field.dart';
import '../../../../shared/widgets/toast.dart';
import '../../../authentication/application/session_controller.dart';

Future<void> showReportSheet(BuildContext context, Listing listing) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => _ReportSheet(listing: listing),
  );
}

class _ReportSheet extends ConsumerStatefulWidget {
  const _ReportSheet({required this.listing});
  final Listing listing;

  @override
  ConsumerState<_ReportSheet> createState() => _ReportSheetState();
}

class _ReportSheetState extends ConsumerState<_ReportSheet> {
  ReportReason? _reason;
  final _comment = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final reason = _reason;
    if (reason == null) return;
    final l10n = context.l10n;
    final isLocal = ref.read(appConfigProvider).isDevelopment;
    setState(() => _sending = true);
    try {
      await ref
          .read(listingRepositoryProvider)
          .report(
            ListingReport(
              id: newId('r_'),
              listingId: widget.listing.id,
              reason: reason,
              comment: _comment.text.trim().isEmpty
                  ? null
                  : _comment.text.trim(),
              reporterId: ref.read(sessionControllerProvider)?.id,
              createdAt: ref.read(clockProvider)(),
            ),
          );
      if (!mounted) return;
      Navigator.of(context).pop();
      // Be honest about where the report went.
      DaryobToast.show(
        context,
        isLocal ? l10n.reportSavedLocally : l10n.reportSent,
      );
    } catch (e) {
      if (mounted) {
        setState(() => _sending = false);
        DaryobToast.show(context, failureMessage(l10n, e), isError: true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(
          DaryobSpacing.page,
          0,
          DaryobSpacing.page,
          DaryobSpacing.lg,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.reportTitle, style: context.text.titleLarge),
            const SizedBox(height: DaryobSpacing.xs),
            Text(l10n.reportBody, style: context.text.bodySmall),
            const SizedBox(height: DaryobSpacing.sm),
            RadioGroup<ReportReason>(
              groupValue: _reason,
              onChanged: (v) => setState(() => _reason = v),
              child: Column(
                children: [
                  for (final reason in ReportReason.values)
                    RadioListTile<ReportReason>(
                      value: reason,
                      contentPadding: EdgeInsets.zero,
                      title: Text(reportReasonLabel(l10n, reason)),
                    ),
                ],
              ),
            ),
            DaryobTextField(
              controller: _comment,
              hint: l10n.reportCommentHint,
              maxLines: 3,
              maxLength: 500,
            ),
            const SizedBox(height: DaryobSpacing.md),
            DaryobPrimaryButton(
              label: l10n.reportSend,
              isLoading: _sending,
              onPressed: _reason == null ? null : _send,
            ),
          ],
        ),
      ),
    );
  }
}
