import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/dialogs.dart';
import '../../../shared/widgets/states.dart';
import '../../../shared/widgets/toast.dart';
import '../../authentication/application/session_controller.dart';
import '../../catalog/application/catalog_providers.dart';
import '../../listings/application/listing_providers.dart';
import '../application/settings_controller.dart';

/// Development builds only (the router blocks it in production).
class DevToolsScreen extends ConsumerWidget {
  const DevToolsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final config = ref.watch(appConfigProvider);

    Future<void> confirmAndRun(
      String title,
      Future<void> Function() action,
    ) async {
      final ok = await DaryobConfirmationDialog.show(
        context,
        title: title,
        message: l10n.devConfirm,
        confirmLabel: l10n.ok,
        destructive: true,
      );
      if (!ok) return;
      await action();
      invalidateListingsFromWidget(ref);
      if (context.mounted) DaryobToast.show(context, l10n.done);
    }

    return Scaffold(
      appBar: AppBar(title: Text(l10n.devTools)),
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: DaryobSpacing.md),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
            child: DaryobNotice(
              message: l10n.devToolsNotice,
              tone: NoticeTone.warning,
            ),
          ),
          ListTile(
            title: Text(l10n.environment),
            trailing: Text(
              config.isDevelopment ? l10n.envDevelopment : l10n.envProduction,
            ),
          ),
          ListTile(
            title: Text(l10n.apiUrl),
            subtitle: Text(
              config.hasServer
                  ? config.serverUrl
                  : (config.apiBaseUrl.isNotEmpty ? config.apiBaseUrl : l10n.notConfigured),
            ),
          ),
          const Divider(),
          const _CatalogSection(),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.replay_rounded),
            title: Text(l10n.devResetOnboarding),
            onTap: () => confirmAndRun(l10n.devResetOnboarding, () async {
              await ref
                  .read(settingsControllerProvider.notifier)
                  .resetOnboarding();
              if (context.mounted) context.go(Routes.onboarding);
            }),
          ),
          ListTile(
            leading: const Icon(Icons.dataset_outlined),
            title: Text(l10n.devReseed),
            onTap: () => confirmAndRun(l10n.devReseed, () async {
              final seeder = ref.read(demoSeederProvider);
              await seeder.removeDemoData();
              await seeder.seed();
            }),
          ),
          ListTile(
            leading: const Icon(Icons.layers_clear_outlined),
            title: Text(l10n.devRemoveDemo),
            onTap: () => confirmAndRun(
              l10n.devRemoveDemo,
              () => ref.read(demoSeederProvider).removeDemoData(),
            ),
          ),
          ListTile(
            leading: Icon(
              Icons.delete_sweep_outlined,
              color: context.colors.error,
            ),
            title: Text(
              l10n.devWipe,
              style: TextStyle(color: context.colors.error),
            ),
            onTap: () => confirmAndRun(l10n.devWipe, () async {
              await ref.read(sessionControllerProvider.notifier).signOut();
              await ref.read(localDatabaseProvider).clearAll();
              ref.invalidate(settingsControllerProvider);
              if (context.mounted) context.go(Routes.splash);
            }),
          ),
        ],
      ),
    );
  }
}

/// Catalog version, authorized imports and rollback.
class _CatalogSection extends ConsumerWidget {
  const _CatalogSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final catalog = ref.watch(catalogProvider);
    final repo = ref.watch(catalogRepositoryProvider);
    final installed = repo.installed;

    Future<void> importFromClipboard() async {
      final text = (await Clipboard.getData(Clipboard.kTextPlain))?.text;
      Map<String, dynamic>? batch;
      try {
        final decoded = text == null ? null : jsonDecode(text);
        if (decoded is Map<String, dynamic>) batch = decoded;
      } on FormatException {
        batch = null;
      }
      if (!context.mounted) return;
      if (batch == null) {
        DaryobToast.show(context, l10n.devCatalogImportInvalid);
        return;
      }
      final report = await repo.importBatch(batch);
      ref.read(catalogProvider.notifier).reload();
      if (!context.mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(l10n.devCatalogImport),
          content: SingleChildScrollView(
            child: Text(
              [
                l10n.devCatalogImportResult(report.accepted.length, report.rejected.length),
                ...report.rejected.take(20).map((r) => '$r'),
              ].join('\n'),
            ),
          ),
          actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(l10n.ok))],
        ),
      );
    }

    return Column(
      children: [
        ListTile(
          leading: const Icon(Icons.category_outlined),
          title: Text(l10n.devCatalog),
          subtitle: Text(
            l10n.devCatalogInfo(
              catalog.version,
              catalog.topLevelCount,
              catalog.subcategoryCount,
              catalog.appliedImportBatches.length,
            ),
          ),
          trailing: Text(installed?.source ?? '—'),
        ),
        ListTile(
          leading: const Icon(Icons.content_paste_go_outlined),
          title: Text(l10n.devCatalogImport),
          subtitle: Text(l10n.devCatalogImportHint),
          onTap: importFromClipboard,
        ),
        ListTile(
          leading: const Icon(Icons.history_rounded),
          title: Text(l10n.devCatalogRollback),
          enabled: repo.previous != null,
          onTap: () async {
            final ok = await repo.rollback();
            ref.read(catalogProvider.notifier).reload();
            if (context.mounted) DaryobToast.show(context, ok ? l10n.done : l10n.devCatalogNoPrevious);
          },
        ),
      ],
    );
  }
}
