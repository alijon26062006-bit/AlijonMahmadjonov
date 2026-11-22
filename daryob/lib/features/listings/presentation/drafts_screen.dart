import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/models/category.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/listing_image.dart';
import '../../../shared/widgets/states.dart';
import '../domain/listing_draft.dart';

final draftsProvider = Provider.autoDispose<List<ListingDraft>>(
  (ref) => ref.watch(draftRepositoryProvider).all(),
);

class DraftsScreen extends ConsumerWidget {
  const DraftsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.myDrafts)),
      body: const DraftsList(),
    );
  }
}

/// Also embedded as the "Drafts" tab of My listings.
class DraftsList extends ConsumerWidget {
  const DraftsList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final drafts = ref.watch(draftsProvider);
    final categories = ref.watch(categoryRegistryProvider);

    if (drafts.isEmpty) {
      return DaryobEmptyState(
        icon: Icons.edit_note_rounded,
        title: l10n.draftsEmpty,
        message: l10n.draftsEmptyBody,
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(DaryobSpacing.page),
      itemCount: drafts.length,
      separatorBuilder: (_, _) => const SizedBox(height: DaryobSpacing.sm),
      itemBuilder: (context, i) {
        final d = drafts[i];
        final category = categories.byId(d.categoryId);
        return Card(
          child: ListTile(
            contentPadding: const EdgeInsets.all(DaryobSpacing.sm),
            leading: ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: SizedBox(
                width: 64,
                height: 56,
                child: DaryobListingImage(
                  source: d.photos.isEmpty ? null : d.photos.first,
                  icon: category?.icon ?? CategoryIcon.generic,
                  cacheWidth: 192,
                ),
              ),
            ),
            title: Text(
              d.title.trim().isEmpty ? l10n.untitledDraft : d.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(
              [
                if (d.isEditing) l10n.editingDraft,
                if (category != null) category.name.of(context),
                l10n.savedAt(Formatters.date(d.updatedAt)),
              ].join(' · '),
              maxLines: 2,
            ),
            onTap: () {
              if (d.isEditing) {
                context.push(Routes.editListing(d.editingListingId!));
              } else {
                context.go('${Routes.create}?draft=${d.id}');
              }
            },
            trailing: IconButton(
              tooltip: l10n.delete,
              icon: Icon(
                Icons.delete_outline_rounded,
                color: context.colors.error,
              ),
              onPressed: () async {
                final ok = await DaryobConfirmationDialog.show(
                  context,
                  title: l10n.deleteDraftTitle,
                  message: l10n.deleteDraftBody,
                  confirmLabel: l10n.delete,
                  destructive: true,
                );
                if (!ok) return;
                await ref.read(draftRepositoryProvider).delete(d.id);
                ref.invalidate(draftsProvider);
              },
            ),
          ),
        );
      },
    );
  }
}
