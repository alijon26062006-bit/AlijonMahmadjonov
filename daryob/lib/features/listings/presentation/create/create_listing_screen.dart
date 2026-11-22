import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../../app/localization/l10n.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../core/errors/failure.dart';
import '../../../../core/utils/debouncer.dart';
import '../../../../core/utils/ids.dart';
import '../../../../shared/models/category_schema.dart';
import '../../../../shared/models/listing.dart';
import '../../../../shared/models/region.dart';
import '../../../../shared/providers/core_providers.dart';
import '../../../../shared/providers/repository_providers.dart';
import '../../../../shared/widgets/buttons.dart';
import '../../../../shared/widgets/daryob_logo.dart';
import '../../../../shared/widgets/dialogs.dart';
import '../../../../shared/widgets/require_sign_in.dart';
import '../../../../shared/widgets/states.dart';
import '../../../../shared/widgets/toast.dart';
import '../../../authentication/application/session_controller.dart';
import '../../../notifications/application/notification_providers.dart';
import '../../../notifications/domain/app_notification.dart';
import '../../../settings/application/settings_controller.dart';
import '../../application/listing_providers.dart';
import '../../domain/listing_draft.dart';
import 'wizard_steps.dart';

/// One wizard page: a core step, or a category-specific step from the schema.
sealed class _Page {
  const _Page();
}

class _CorePage extends _Page {
  const _CorePage(this.step);
  final DraftStep step;
}

class _ExtraPage extends _Page {
  const _ExtraPage(this.step);
  final FormStepSchema step;
}

/// Create a listing (tab) or edit one (pushed route). Every change is saved
/// to a local draft, so leaving the screen never loses work.
class CreateListingScreen extends ConsumerStatefulWidget {
  const CreateListingScreen({
    super.key,
    this.draftId,
    this.editListingId,
    this.isTab = false,
  });

  final String? draftId;
  final String? editListingId;
  final bool isTab;

  @override
  ConsumerState<CreateListingScreen> createState() =>
      _CreateListingScreenState();
}

class _CreateListingScreenState extends ConsumerState<CreateListingScreen> {
  ListingDraft? _draft;
  Object? _loadError;
  int _index = 0;
  Map<String, String> _errors = const {};
  bool _publishing = false;
  Listing? _published;
  bool _resumed = false;
  final _saver = Debouncer(const Duration(milliseconds: 400));
  final _scroll = ScrollController();

  /// Captured up front: `ref` can't be used in dispose(), where the last
  /// save happens.
  late final DraftRepository _draftRepo;

  bool get _isEditing => widget.editListingId != null;

  @override
  void initState() {
    super.initState();
    _draftRepo = ref.read(draftRepositoryProvider);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void didUpdateWidget(CreateListingScreen old) {
    super.didUpdateWidget(old);
    // Opening a specific draft from "My drafts" while the tab is alive.
    if (widget.draftId != null && widget.draftId != old.draftId) _load();
  }

  @override
  void dispose() {
    _saver.dispose();
    _saveNow();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final drafts = _draftRepo;
    final now = ref.read(clockProvider)();
    try {
      if (_isEditing) {
        final id = widget.editListingId!;
        final existingDraft = drafts.get('edit_$id');
        if (existingDraft != null) {
          _setLoaded(existingDraft, resumed: true);
          return;
        }
        final listing = await ref.read(listingRepositoryProvider).getById(id);
        final user = ref.read(sessionControllerProvider);
        if (listing == null) throw const NotFoundFailure();
        if (user == null || user.id != listing.ownerId) {
          throw const ForbiddenFailure();
        }
        _setLoaded(ListingDraft.fromListing(listing, 'edit_$id', now));
        return;
      }
      if (widget.draftId != null) {
        final draft = drafts.get(widget.draftId!);
        if (draft != null) {
          _setLoaded(draft, resumed: true);
          return;
        }
      }
      final latest = drafts.all().where((d) => !d.isEditing).firstOrNull;
      if (latest != null) {
        _setLoaded(latest, resumed: true);
      } else {
        _setLoaded(_freshDraft(now));
      }
    } catch (e) {
      if (mounted) setState(() => _loadError = e);
    }
  }

  ListingDraft _freshDraft(DateTime now) {
    final user = ref.read(sessionControllerProvider);
    final settings = ref.read(settingsControllerProvider);
    final region = ref
        .read(regionDirectoryProvider)
        .byId(user?.regionId ?? settings.regionId);
    return ListingDraft(
      id: newId('d_'),
      updatedAt: now,
      contactName: user?.name ?? '',
      contactPhone: user?.phone ?? '',
      // Only pre-fill a concrete place, not "all Tajikistan".
      regionId: region == null || region.level == RegionLevel.country
          ? null
          : region.id,
      phoneVisibility: settings.hidePhoneByDefault
          ? PhoneVisibility.hidden
          : PhoneVisibility.visible,
    );
  }

  void _setLoaded(ListingDraft draft, {bool resumed = false}) {
    if (!mounted) return;
    setState(() {
      _draft = draft;
      _resumed = resumed && !draft.isEmpty;
      _published = null;
      _errors = const {};
      _index = _pages(draft)
          .indexWhere((p) => p is _CorePage && p.step == draft.step);
      if (_index < 0) _index = 0;
    });
  }

  List<_Page> _pages(ListingDraft draft) {
    final schema = ref.read(draftValidatorProvider).schemaOf(draft);
    return [
      const _CorePage(DraftStep.category),
      const _CorePage(DraftStep.subcategory),
      const _CorePage(DraftStep.details),
      for (final s in schema?.extraSteps ?? const <FormStepSchema>[])
        _ExtraPage(s),
      const _CorePage(DraftStep.basics),
      const _CorePage(DraftStep.photos),
      const _CorePage(DraftStep.location),
      const _CorePage(DraftStep.contact),
      const _CorePage(DraftStep.preview),
    ];
  }

  void _update(ListingDraft Function(ListingDraft) change) {
    final current = _draft;
    if (current == null) return;
    setState(() {
      _draft = change(current).copyWith(updatedAt: ref.read(clockProvider)());
      // Re-validate the visible step live once errors were shown.
      if (_errors.isNotEmpty) {
        _errors = _validate(_draft!, _pages(_draft!)[_index]);
      }
    });
    _saver(_saveNow);
  }

  void _saveNow() {
    final draft = _draft;
    if (draft == null || _published != null || draft.isEmpty) return;
    _draftRepo.save(draft);
  }

  Map<String, String> _validate(ListingDraft draft, _Page page) {
    final validator = ref.read(draftValidatorProvider);
    return switch (page) {
      _CorePage(:final step) => validator.validateStep(draft, step),
      _ExtraPage(:final step) => validator.validateExtraStep(draft, step),
    };
  }

  void _goTo(int index) {
    final draft = _draft!;
    final pages = _pages(draft);
    final page = pages[index];
    setState(() {
      _index = index;
      _errors = const {};
      if (page is _CorePage) _draft = draft.copyWith(step: page.step);
    });
    _saveNow();
    if (_scroll.hasClients) _scroll.jumpTo(0);
  }

  void _next() {
    final draft = _draft!;
    final pages = _pages(draft);
    final errors = _validate(draft, pages[_index]);
    if (errors.isNotEmpty) {
      setState(() => _errors = errors);
      DaryobToast.show(context, context.l10n.fixErrors, isError: true);
      return;
    }
    if (_index < pages.length - 1) _goTo(_index + 1);
  }

  void _back() {
    if (_index > 0) _goTo(_index - 1);
  }

  Future<void> _publish() async {
    final l10n = context.l10n;
    final draft = _draft!;
    final validator = ref.read(draftValidatorProvider);
    final invalid = validator.validateAll(draft);
    if (invalid.isNotEmpty) {
      final step = DraftStep.values.firstWhere(
        (s) => validator.validateStep(draft, s).isNotEmpty,
        orElse: () => DraftStep.basics,
      );
      _goTo(_pages(draft).indexWhere((p) => p is _CorePage && p.step == step));
      setState(() => _errors = validator.validateStep(draft, step));
      DaryobToast.show(context, l10n.fixErrors, isError: true);
      return;
    }
    if (!await requireSignIn(context, ref)) return;
    final user = ref.read(sessionControllerProvider)!;

    setState(() => _publishing = true);
    try {
      final repo = ref.read(listingRepositoryProvider);
      final listing = _isEditing
          ? await repo.update(
              widget.editListingId!,
              draft,
              actingUserId: user.id,
            )
          : await repo.publish(draft, ownerId: user.id);
      // Only now — after the repository confirmed — clean up and celebrate.
      await ref.read(draftRepositoryProvider).delete(draft.id);
      invalidateListingsFromWidget(ref);
      if (!_isEditing && listing.isLocalOnly) {
        await ref
            .read(notificationServiceProvider)
            .notify(
              NotificationKind.system,
              params: {'code': 'saved_locally', 'title': listing.title},
              listingId: listing.id,
            );
      }
      if (!mounted) return;
      if (_isEditing) {
        DaryobToast.show(context, l10n.changesSaved);
        context.pop();
        return;
      }
      setState(() {
        _publishing = false;
        _published = listing;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _publishing = false);
      final failure = asFailure(e);
      if (failure is ValidationFailure && failure.fieldErrors.isNotEmpty) {
        setState(() => _errors = failure.fieldErrors);
      }
      DaryobToast.show(context, failureMessage(l10n, e), isError: true);
    }
  }

  Future<void> _startNew() async {
    final draft = _draft;
    final l10n = context.l10n;
    if (draft != null && !draft.isEmpty && _published == null) {
      final keep = await DaryobConfirmationDialog.show(
        context,
        title: l10n.startNewTitle,
        message: l10n.startNewBody,
        confirmLabel: l10n.startNew,
      );
      if (!keep) return;
      _saveNow(); // The old draft stays in "My drafts".
    }
    _setLoaded(_freshDraft(ref.read(clockProvider)()));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;

    if (_loadError != null) {
      return Scaffold(
        appBar: AppBar(),
        body: DaryobErrorState(error: _loadError!),
      );
    }
    final draft = _draft;
    if (draft == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_published != null) {
      return _PublishedView(
        listing: _published!,
        onCreateAnother: () =>
            _setLoaded(_freshDraft(ref.read(clockProvider)())),
      );
    }

    final pages = _pages(draft);
    final index = _index.clamp(0, pages.length - 1);
    final page = pages[index];
    final isLast = index == pages.length - 1;
    final title = _pageTitle(context, page);

    return Scaffold(
      appBar: AppBar(
        title: Text(_isEditing ? l10n.editListing : l10n.createListing),
        automaticallyImplyLeading: !widget.isTab,
        actions: [
          if (!_isEditing)
            PopupMenuButton<String>(
              tooltip: l10n.more,
              onSelected: (v) {
                if (v == 'new') _startNew();
                if (v == 'drafts') context.push(Routes.drafts);
              },
              itemBuilder: (_) => [
                PopupMenuItem(value: 'new', child: Text(l10n.startNew)),
                PopupMenuItem(value: 'drafts', child: Text(l10n.myDrafts)),
              ],
            ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(52),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              DaryobSpacing.page,
              0,
              DaryobSpacing.page,
              DaryobSpacing.sm,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l10n.stepOf(index + 1, pages.length, title),
                  style: context.text.labelMedium,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: DaryobSpacing.sm),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: (index + 1) / pages.length,
                    minHeight: 6,
                    backgroundColor: context.palette.border,
                    color: DaryobColors.lime,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      body: ListView(
        controller: _scroll,
        padding: const EdgeInsets.all(DaryobSpacing.page),
        children: [
          if (_resumed && index == 0) ...[
            DaryobNotice(
              message: l10n.draftResumed,
              icon: Icons.history_rounded,
            ),
            const SizedBox(height: DaryobSpacing.md),
          ],
          if (ref.watch(appConfigProvider).isDevelopment &&
              page is _CorePage &&
              page.step == DraftStep.preview) ...[
            DaryobNotice(
              message: l10n.localPublishNotice,
              tone: NoticeTone.warning,
            ),
            const SizedBox(height: DaryobSpacing.md),
          ],
          _buildPage(draft, page),
          const SizedBox(height: DaryobSpacing.xl),
        ],
      ),
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          color: context.colors.surface,
          border: Border(top: BorderSide(color: context.palette.border)),
        ),
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.all(DaryobSpacing.md),
            child: Row(
              children: [
                if (index > 0) ...[
                  Expanded(
                    child: DaryobSecondaryButton(
                      label: l10n.back,
                      onPressed: _back,
                    ),
                  ),
                  const SizedBox(width: DaryobSpacing.md),
                ],
                Expanded(
                  flex: 2,
                  child: isLast
                      ? DaryobPrimaryButton(
                          label: _isEditing ? l10n.saveChanges : l10n.publish,
                          tone: DaryobButtonTone.accent,
                          isLoading: _publishing,
                          onPressed: _publish,
                        )
                      : DaryobPrimaryButton(
                          label: l10n.next,
                          onPressed:
                              page is _CorePage &&
                                  ((page.step == DraftStep.category &&
                                          draft.categoryId == null) ||
                                      (page.step == DraftStep.subcategory &&
                                          ref
                                              .read(draftValidatorProvider)
                                              .needsSubcategory(draft)))
                              ? null
                              : _next,
                        ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _pageTitle(BuildContext context, _Page page) {
    final l10n = context.l10n;
    return switch (page) {
      _ExtraPage(:final step) => step.title.resolve(
        Localizations.localeOf(context),
      ),
      _CorePage(:final step) => switch (step) {
        DraftStep.category => l10n.stepCategory,
        DraftStep.subcategory => l10n.stepSubcategory,
        DraftStep.details => l10n.stepDetails,
        DraftStep.basics => l10n.stepBasics,
        DraftStep.photos => l10n.stepPhotos,
        DraftStep.location => l10n.stepLocation,
        DraftStep.contact => l10n.stepContact,
        DraftStep.preview => l10n.stepPreview,
      },
    };
  }

  Widget _buildPage(ListingDraft draft, _Page page) {
    // Keys make each step rebuild its text fields from the draft.
    return switch (page) {
      _ExtraPage(:final step) => DetailsStep(
        key: ValueKey('extra-${step.id}-${draft.id}'),
        draft: draft,
        fieldKeys: step.fieldKeys,
        update: _update,
        errors: _errors,
      ),
      _CorePage(:final step) => switch (step) {
        DraftStep.category => CategoryStep(
          draft: draft,
          errors: _errors,
          onPick: (id) {
            final registry = ref.read(categoryRegistryProvider);
            final currentTop = registry.pathTo(draft.categoryId ?? '').firstOrNull?.id;
            if (currentTop != id) {
              // Attributes belong to the old category's schema.
              _update((d) => d.copyWith(categoryId: id, attributes: const {}));
            }
            _next();
          },
        ),
        DraftStep.subcategory => SubcategoryStep(
          draft: draft,
          errors: _errors,
          onPick: (id) {
            if (id != draft.categoryId) {
              final schema = ref
                  .read(schemaRegistryProvider)
                  .schemaFor(ref.read(categoryRegistryProvider).byId(id)!.formSchemaId);
              _update(
                (d) => d.copyWith(
                  categoryId: id,
                  attributes: withPresets(schema, const {}),
                ),
              );
            }
            _next();
          },
        ),
        DraftStep.details => DetailsStep(
          draft: draft,
          update: _update,
          errors: _errors,
        ),
        DraftStep.basics => BasicsStep(
          key: ValueKey('basics-${draft.id}-${draft.categoryId}'),
          draft: draft,
          update: _update,
          errors: _errors,
        ),
        DraftStep.photos => PhotosStep(
          draft: draft,
          update: _update,
          errors: _errors,
        ),
        DraftStep.location => LocationStep(
          key: ValueKey('location-${draft.id}'),
          draft: draft,
          update: _update,
          errors: _errors,
        ),
        DraftStep.contact => ContactStep(
          key: ValueKey('contact-${draft.id}'),
          draft: draft,
          update: _update,
          errors: _errors,
        ),
        DraftStep.preview => PreviewStep(
          draft: draft,
          onEditStep: (s) => _goTo(
            _pages(draft).indexWhere((p) => p is _CorePage && p.step == s),
          ),
        ),
      },
    };
  }
}

class _PublishedView extends StatelessWidget {
  const _PublishedView({required this.listing, required this.onCreateAnother});
  final Listing listing;
  final VoidCallback onCreateAnother;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(DaryobSpacing.xxl),
            child: Column(
              children: [
                const DaryobBadgeLogo(size: 88),
                const SizedBox(height: DaryobSpacing.xl),
                Text(
                  listing.status == ListingStatus.pending
                      ? l10n.publishedPendingTitle
                      : l10n.publishedTitle,
                  textAlign: TextAlign.center,
                  style: context.text.headlineSmall,
                ),
                const SizedBox(height: DaryobSpacing.sm),
                Text(
                  listing.status == ListingStatus.pending
                      ? l10n.publishedPendingBody
                      : listing.isLocalOnly
                      ? l10n.publishedLocalBody
                      : l10n.publishedBody,
                  textAlign: TextAlign.center,
                  style: context.text.bodyMedium,
                ),
                const SizedBox(height: DaryobSpacing.xxl),
                DaryobPrimaryButton(
                  label: l10n.openListing,
                  onPressed: () => context.push(Routes.listing(listing.id)),
                ),
                const SizedBox(height: DaryobSpacing.md),
                DaryobSecondaryButton(
                  label: l10n.myListings,
                  onPressed: () => context.push(Routes.myListings),
                ),
                const SizedBox(height: DaryobSpacing.md),
                TextButton(
                  onPressed: onCreateAnother,
                  child: Text(l10n.createAnother),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
