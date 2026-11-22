import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../core/errors/failure.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/daryob_logo.dart';
import '../../../shared/widgets/daryob_text_field.dart';
import '../../../shared/widgets/location_selector.dart';
import '../../../shared/widgets/states.dart';
import '../../../shared/widgets/toast.dart';
import '../../settings/application/settings_controller.dart';
import '../../../shared/providers/repository_providers.dart';
import '../application/session_controller.dart';
import '../domain/auth_repository.dart';

enum _AuthStep { phone, code, profile }

/// Phone → one-time code → name. Pops with `true` when signed in.
class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key});

  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen> {
  _AuthStep _step = _AuthStep.phone;
  final _phone = TextEditingController();
  final _code = TextEditingController();
  final _name = TextEditingController();
  OtpChallenge? _challenge;
  String? _error;
  bool _busy = false;
  String? _regionId;
  Timer? _ticker;
  int _resendIn = 0;

  @override
  void dispose() {
    _ticker?.cancel();
    _phone.dispose();
    _code.dispose();
    _name.dispose();
    super.dispose();
  }

  void _startCooldown(DateTime until) {
    _ticker?.cancel();
    void tick() {
      final left = until.difference(DateTime.now()).inSeconds;
      if (!mounted) return;
      setState(() => _resendIn = left > 0 ? left : 0);
      if (left <= 0) _ticker?.cancel();
    }

    tick();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => tick());
  }

  Future<void> _requestCode() async {
    final l10n = context.l10n;
    final error = Validators.tajikPhone(_phone.text);
    if (error != null) {
      setState(() => _error = validationMessage(l10n, error));
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final challenge = await ref
          .read(sessionControllerProvider.notifier)
          .requestCode(_phone.text);
      if (!mounted) return;
      _code.clear();
      if (!challenge.requiresCode) {
        // No code could be sent: the number is saved unverified.
        if (challenge.fallbackReason != null) {
          DaryobToast.show(context, l10n.authTelegramUnavailable);
        }
        final user = await ref
            .read(sessionControllerProvider.notifier)
            .verify(challenge, '');
        if (!mounted) return;
        if (user.hasProfile) {
          context.pop(true);
        } else {
          _regionId = ref.read(settingsControllerProvider).regionId;
          setState(() => _step = _AuthStep.profile);
        }
        return;
      }
      setState(() {
        _challenge = challenge;
        _step = _AuthStep.code;
      });
      _startCooldown(challenge.resendAvailableAt);
    } catch (e) {
      if (mounted) setState(() => _error = failureMessage(l10n, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _verify() async {
    final l10n = context.l10n;
    final challenge = _challenge!;
    final error = Validators.otp(_code.text, length: challenge.codeLength);
    if (error != null) {
      setState(() => _error = validationMessage(l10n, error));
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final user = await ref
          .read(sessionControllerProvider.notifier)
          .verify(challenge, _code.text);
      if (!mounted) return;
      if (user.hasProfile) {
        context.pop(true);
      } else {
        _regionId = ref.read(settingsControllerProvider).regionId;
        setState(() => _step = _AuthStep.profile);
      }
    } catch (e) {
      if (!mounted) return;
      final failure = asFailure(e);
      setState(
        () => _error = failure is ValidationFailure
            ? validationMessage(
                l10n,
                failure.fieldErrors['code'] ?? ValidationCode.invalidCode,
              )
            : failureMessage(l10n, e),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _saveProfile() async {
    final l10n = context.l10n;
    final error = Validators.personName(_name.text);
    if (error != null) {
      setState(
        () => _error = validationMessage(
          l10n,
          error,
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
      if (mounted) context.pop(true);
    } catch (e) {
      if (mounted) setState(() => _error = failureMessage(l10n, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final isDevelopment = ref.watch(appConfigProvider).isDevelopment;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          tooltip: l10n.close,
          icon: const Icon(Icons.close_rounded),
          onPressed: () => context.pop(false),
        ),
        title: Text(l10n.signIn),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(DaryobSpacing.xxl),
          children: [
            const Align(
              alignment: Alignment.centerLeft,
              child: DaryobBadgeLogo(size: 56),
            ),
            const SizedBox(height: DaryobSpacing.xl),
            ...switch (_step) {
              _AuthStep.phone => _phoneStep(context, isDevelopment),
              _AuthStep.code => _codeStep(context),
              _AuthStep.profile => _profileStep(context),
            },
          ],
        ),
      ),
    );
  }

  List<Widget> _phoneStep(BuildContext context, bool isDevelopment) {
    final l10n = context.l10n;
    final verifiesPhone = ref.watch(authRepositoryProvider).verifiesPhone;
    return [
      Text(l10n.authPhoneTitle, style: context.text.headlineSmall),
      const SizedBox(height: DaryobSpacing.sm),
      Text(
        isDevelopment
            ? l10n.authPhoneBody
            : (verifiesPhone ? l10n.authPhoneBodyTelegram : l10n.authPhoneBodyNoCode),
        style: context.text.bodyMedium,
      ),
      const SizedBox(height: DaryobSpacing.xl),
      DaryobTextField(
        controller: _phone,
        label: l10n.contactPhone,
        prefixText: '+992 ',
        hint: 'XX XXX XX XX',
        autofocus: true,
        keyboardType: TextInputType.phone,
        inputFormatters: [TajikPhoneInputFormatter()],
        errorText: _error,
        onSubmitted: (_) => _requestCode(),
      ),
      if (isDevelopment) ...[
        const SizedBox(height: DaryobSpacing.md),
        DaryobNotice(message: l10n.demoAuthNotice, tone: NoticeTone.warning),
      ] else if (!verifiesPhone) ...[
        const SizedBox(height: DaryobSpacing.md),
        DaryobNotice(message: l10n.authNoCodeNotice),
      ],
      const SizedBox(height: DaryobSpacing.xl),
      DaryobPrimaryButton(
        label: verifiesPhone ? l10n.getCode : l10n.continueAction,
        isLoading: _busy,
        onPressed: _requestCode,
      ),
      const SizedBox(height: DaryobSpacing.lg),
      Text(l10n.authTermsNote, style: context.text.bodySmall),
      Wrap(
        children: [
          TextButton(
            onPressed: () => context.push(Routes.info('terms')),
            child: Text(l10n.terms),
          ),
          TextButton(
            onPressed: () => context.push(Routes.info('privacy')),
            child: Text(l10n.privacyPolicy),
          ),
        ],
      ),
    ];
  }

  List<Widget> _codeStep(BuildContext context) {
    final l10n = context.l10n;
    final challenge = _challenge!;
    return [
      Text(l10n.authCodeTitle, style: context.text.headlineSmall),
      const SizedBox(height: DaryobSpacing.sm),
      Text(
        challenge.isDemo
            ? l10n.authCodeDemoBody(Formatters.phone(challenge.phone))
            : challenge.viaTelegram
            ? l10n.authCodeTelegramBody(Formatters.phone(challenge.phone))
            : l10n.authCodeBody(Formatters.phone(challenge.phone)),
        style: context.text.bodyMedium,
      ),
      if (challenge.isDemo && challenge.demoCode != null) ...[
        const SizedBox(height: DaryobSpacing.md),
        DaryobNotice(
          message: l10n.demoCodeIs(challenge.demoCode!),
          tone: NoticeTone.warning,
          icon: Icons.science_outlined,
        ),
      ],
      const SizedBox(height: DaryobSpacing.xl),
      DaryobTextField(
        controller: _code,
        label: l10n.authCodeLabel,
        autofocus: true,
        keyboardType: TextInputType.number,
        maxLength: challenge.codeLength,
        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
        errorText: _error,
        onChanged: (v) {
          if (v.length == challenge.codeLength) _verify();
        },
      ),
      const SizedBox(height: DaryobSpacing.lg),
      DaryobPrimaryButton(
        label: l10n.confirm,
        isLoading: _busy,
        onPressed: _verify,
      ),
      const SizedBox(height: DaryobSpacing.sm),
      Row(
        children: [
          TextButton(
            onPressed: () => setState(() {
              _step = _AuthStep.phone;
              _error = null;
            }),
            child: Text(l10n.changeNumber),
          ),
          const Spacer(),
          TextButton(
            onPressed: _resendIn > 0 || _busy ? null : _requestCode,
            child: Text(
              _resendIn > 0 ? l10n.resendIn(_resendIn) : l10n.resendCode,
            ),
          ),
        ],
      ),
    ];
  }

  List<Widget> _profileStep(BuildContext context) {
    final l10n = context.l10n;
    final directory = ref.watch(regionDirectoryProvider);
    return [
      Text(l10n.authProfileTitle, style: context.text.headlineSmall),
      const SizedBox(height: DaryobSpacing.sm),
      Text(l10n.authProfileBody, style: context.text.bodyMedium),
      const SizedBox(height: DaryobSpacing.xl),
      DaryobTextField(
        controller: _name,
        label: l10n.yourName,
        autofocus: true,
        textCapitalization: TextCapitalization.words,
        errorText: _error,
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
      const SizedBox(height: DaryobSpacing.xl),
      DaryobPrimaryButton(
        label: l10n.save,
        isLoading: _busy,
        onPressed: _saveProfile,
      ),
    ];
  }
}
