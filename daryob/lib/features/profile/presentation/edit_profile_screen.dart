import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/daryob_text_field.dart';
import '../../../shared/widgets/location_selector.dart';
import '../../../shared/widgets/toast.dart';
import '../../authentication/application/session_controller.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  late final _name = TextEditingController(
    text: ref.read(sessionControllerProvider)?.name ?? '',
  );
  late String? _regionId = ref.read(sessionControllerProvider)?.regionId;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final l10n = context.l10n;
    final code = Validators.personName(_name.text);
    if (code != null) {
      setState(
        () => _error = validationMessage(
          l10n,
          code,
          min: ListingLimits.nameMin,
          max: ListingLimits.nameMax,
        ),
      );
      return;
    }
    setState(() => _busy = true);
    try {
      await ref
          .read(sessionControllerProvider.notifier)
          .updateProfile(name: _name.text.trim(), regionId: _regionId);
      if (!mounted) return;
      DaryobToast.show(context, l10n.changesSaved);
      context.pop();
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        DaryobToast.show(context, failureMessage(l10n, e), isError: true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final user = ref.watch(sessionControllerProvider);
    final directory = ref.watch(regionDirectoryProvider);
    if (user == null) {
      return Scaffold(
        appBar: AppBar(),
        body: Center(child: Text(l10n.signInRequired)),
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text(l10n.editProfile)),
      body: ListView(
        padding: const EdgeInsets.all(DaryobSpacing.page),
        children: [
          DaryobTextField(
            controller: _name,
            label: l10n.yourName,
            errorText: _error,
            textCapitalization: TextCapitalization.words,
          ),
          const SizedBox(height: DaryobSpacing.lg),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.phone_outlined),
            title: Text(Formatters.phone(user.phone)),
            subtitle: Text(l10n.phoneChangeNote),
          ),
          const SizedBox(height: DaryobSpacing.lg),
          Text(l10n.location, style: context.text.labelMedium),
          const SizedBox(height: DaryobSpacing.sm),
          OutlinedButton.icon(
            onPressed: () async {
              final picked = await showLocationPicker(
                context,
                selectedId: _regionId,
              );
              if (picked != null) setState(() => _regionId = picked);
            },
            icon: const Icon(Icons.place_outlined),
            label: Text(regionPathLabel(context, directory, _regionId ?? 'tj')),
          ),
          const SizedBox(height: DaryobSpacing.xxl),
          DaryobPrimaryButton(
            label: l10n.save,
            isLoading: _busy,
            onPressed: _save,
          ),
        ],
      ),
    );
  }
}
