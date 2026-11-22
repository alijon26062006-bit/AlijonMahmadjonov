import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/errors/failure.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/models/listing.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/providers/repository_providers.dart';
import '../../../shared/widgets/badges.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/daryob_text_field.dart';
import '../../../shared/widgets/location_selector.dart';
import '../../../shared/widgets/require_sign_in.dart';
import '../../../shared/widgets/states.dart';
import '../../../shared/widgets/toast.dart';
import '../../authentication/application/session_controller.dart';
import '../../listings/presentation/my_listings_screen.dart';
import '../domain/business_profile.dart';

final businessProfileProvider = FutureProvider.autoDispose<BusinessProfile?>((
  ref,
) async {
  final user = ref.watch(sessionControllerProvider);
  if (user == null) return null;
  return ref.watch(sellerRepositoryProvider).business(user.id);
});

/// Business account: profile form, real statistics from the user's own
/// listings, subscription entry point.
class BusinessScreen extends ConsumerWidget {
  const BusinessScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final user = ref.watch(sessionControllerProvider);
    if (user == null) {
      return Scaffold(
        appBar: AppBar(title: Text(l10n.businessAccount)),
        body: DaryobEmptyState(
          icon: Icons.storefront_outlined,
          title: l10n.signInRequired,
          actionLabel: l10n.signIn,
          onAction: () => requireSignIn(context, ref),
        ),
      );
    }
    final profile = ref.watch(businessProfileProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.businessAccount)),
      body: profile.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => DaryobErrorState(error: e),
        data: (p) => p == null
            ? const _BusinessForm(existing: null)
            : _BusinessOverview(profile: p),
      ),
    );
  }
}

class _BusinessOverview extends ConsumerWidget {
  const _BusinessOverview({required this.profile});
  final BusinessProfile profile;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final listings = ref.watch(myListingsProvider).value ?? const [];
    final active = listings
        .where((l) => l.status == ListingStatus.active)
        .length;
    final sold = listings.where((l) => l.status == ListingStatus.sold).length;
    final region = ref.watch(regionDirectoryProvider);

    return ListView(
      padding: const EdgeInsets.all(DaryobSpacing.page),
      children: [
        Container(
          padding: const EdgeInsets.all(DaryobSpacing.xl),
          decoration: const BoxDecoration(
            color: DaryobColors.navy,
            borderRadius: DaryobRadius.heroAll,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                profile.name,
                style: context.text.headlineSmall?.copyWith(
                  color: Colors.white,
                ),
              ),
              if (profile.description.isNotEmpty) ...[
                const SizedBox(height: DaryobSpacing.xs),
                Text(
                  profile.description,
                  style: context.text.bodyMedium?.copyWith(
                    color: Colors.white70,
                  ),
                ),
              ],
              const SizedBox(height: DaryobSpacing.md),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  DaryobStatusBadge(
                    label: verificationLabel(l10n, profile.verification),
                    tone: profile.verification == VerificationStatus.verified
                        ? BadgeTone.success
                        : BadgeTone.lime,
                  ),
                  if (profile.regionId != null)
                    DaryobStatusBadge(
                      label: regionPathLabel(
                        context,
                        region,
                        profile.regionId!,
                      ),
                      tone: BadgeTone.lime,
                    ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: DaryobSpacing.lg),
        Text(l10n.statistics, style: context.text.titleMedium),
        const SizedBox(height: DaryobSpacing.sm),
        Row(
          children: [
            Expanded(
              child: _Stat(label: l10n.statusActive, value: '$active'),
            ),
            const SizedBox(width: DaryobSpacing.md),
            Expanded(
              child: _Stat(label: l10n.statusSold, value: '$sold'),
            ),
            const SizedBox(width: DaryobSpacing.md),
            // Views and contacts need server-side tracking; never invented.
            Expanded(
              child: _Stat(label: l10n.viewsLabel, value: '—'),
            ),
          ],
        ),
        const SizedBox(height: DaryobSpacing.sm),
        Text(l10n.statsNotTracked, style: context.text.bodySmall),
        const SizedBox(height: DaryobSpacing.xl),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.list_alt_rounded),
          title: Text(l10n.businessListings),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: () => context.push(Routes.myListings),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.workspace_premium_outlined),
          title: Text(l10n.subscription),
          subtitle: Text(l10n.subscriptionNone),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: () => context.push(Routes.subscription),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.edit_outlined),
          title: Text(l10n.editBusiness),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => Scaffold(
                appBar: AppBar(title: Text(l10n.editBusiness)),
                body: _BusinessForm(existing: profile),
              ),
            ),
          ),
        ),
        const SizedBox(height: DaryobSpacing.lg),
        DaryobNotice(message: l10n.businessComingSoon),
        if (profile.verification == VerificationStatus.notSubmitted) ...[
          const SizedBox(height: DaryobSpacing.lg),
          DaryobSecondaryButton(
            label: l10n.requestVerification,
            icon: Icons.verified_outlined,
            onPressed: () => DaryobToast.show(
              context,
              // Verification is decided by DARYOB staff on the server.
              failureMessage(
                l10n,
                const FeatureUnavailableFailure(UnavailableFeature.backend),
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(DaryobSpacing.md),
        child: Column(
          children: [
            Text(value, style: context.text.headlineSmall),
            Text(
              label,
              style: context.text.bodySmall,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _BusinessForm extends ConsumerStatefulWidget {
  const _BusinessForm({required this.existing});
  final BusinessProfile? existing;

  @override
  ConsumerState<_BusinessForm> createState() => _BusinessFormState();
}

class _BusinessFormState extends ConsumerState<_BusinessForm> {
  late final _name = TextEditingController(text: widget.existing?.name ?? '');
  late final _description = TextEditingController(
    text: widget.existing?.description ?? '',
  );
  late final _address = TextEditingController(
    text: widget.existing?.address ?? '',
  );
  late String? _regionId = widget.existing?.regionId;
  String? _nameError;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    _address.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final l10n = context.l10n;
    final user = ref.read(sessionControllerProvider);
    if (user == null) return;
    final error = Validators.personName(_name.text);
    if (error != null) {
      setState(
        () => _nameError = validationMessage(
          l10n,
          error,
          min: ListingLimits.nameMin,
          max: ListingLimits.nameMax,
        ),
      );
      return;
    }
    setState(() => _busy = true);
    final now = ref.read(clockProvider)();
    final base =
        widget.existing ??
        BusinessProfile(
          ownerId: user.id,
          name: _name.text.trim(),
          publicSlug: 'b-${user.id.hashCode.abs()}',
          createdAt: now,
          phone: user.phone,
        );
    try {
      await ref
          .read(sellerRepositoryProvider)
          .saveBusiness(
            base.copyWith(
              name: _name.text.trim(),
              description: _description.text.trim(),
              address: _address.text.trim(),
              regionId: _regionId,
            ),
          );
      await ref.read(sessionControllerProvider.notifier).markBusiness();
      ref.invalidate(businessProfileProvider);
      if (!mounted) return;
      DaryobToast.show(context, l10n.changesSaved);
      if (widget.existing != null) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        DaryobToast.show(context, failureMessage(l10n, e), isError: true);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final directory = ref.watch(regionDirectoryProvider);
    return ListView(
      padding: const EdgeInsets.all(DaryobSpacing.page),
      children: [
        if (widget.existing == null) ...[
          Text(l10n.businessIntroTitle, style: context.text.headlineSmall),
          const SizedBox(height: DaryobSpacing.sm),
          Text(l10n.businessIntroBody, style: context.text.bodyMedium),
          const SizedBox(height: DaryobSpacing.xl),
        ],
        DaryobTextField(
          controller: _name,
          label: '${l10n.businessName} *',
          errorText: _nameError,
          textCapitalization: TextCapitalization.words,
        ),
        const SizedBox(height: DaryobSpacing.md),
        DaryobTextField(
          controller: _description,
          label: l10n.businessDescription,
          maxLines: 4,
          maxLength: 600,
        ),
        const SizedBox(height: DaryobSpacing.md),
        Text(l10n.location, style: context.text.labelMedium),
        const SizedBox(height: DaryobSpacing.sm),
        OutlinedButton.icon(
          onPressed: () async {
            final picked = await showLocationPicker(
              context,
              selectedId: _regionId,
              allowWholeCountry: false,
            );
            if (picked != null) setState(() => _regionId = picked);
          },
          icon: const Icon(Icons.place_outlined),
          label: Text(
            _regionId == null
                ? l10n.chooseLocation
                : regionPathLabel(context, directory, _regionId!),
          ),
        ),
        const SizedBox(height: DaryobSpacing.md),
        DaryobTextField(
          controller: _address,
          label: l10n.businessAddress,
          maxLength: 160,
        ),
        const SizedBox(height: DaryobSpacing.xl),
        DaryobPrimaryButton(
          label: widget.existing == null ? l10n.createBusiness : l10n.save,
          isLoading: _busy,
          onPressed: _save,
        ),
      ],
    );
  }
}
