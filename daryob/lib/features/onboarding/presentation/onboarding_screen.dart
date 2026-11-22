import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/models/localized_text.dart';
import '../../../shared/providers/core_providers.dart';
import '../../../shared/widgets/buttons.dart';
import '../../../shared/widgets/daryob_logo.dart';
import '../../../shared/widgets/language_selector.dart';
import '../../../shared/widgets/location_selector.dart';
import '../../categories/data/tajikistan_regions.dart';
import '../../settings/application/settings_controller.dart';

/// Welcome → easy selling → nearby → language → city.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _controller = PageController();
  int _page = 0;
  static const _pageCount = 5;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _next() {
    if (_page < _pageCount - 1) {
      _controller.nextPage(
        duration: DaryobDurations.normal,
        curve: Curves.easeOutCubic,
      );
    } else {
      _finish();
    }
  }

  Future<void> _finish() async {
    final settings = ref.read(settingsControllerProvider.notifier);
    // Store the visible language even if the user never tapped it.
    if (ref.read(settingsControllerProvider).languageCode == null) {
      await settings.setLanguage(context.languageCode);
    }
    await settings.completeOnboarding();
    if (mounted) context.go(Routes.home);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final isLast = _page == _pageCount - 1;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                DaryobSpacing.page,
                DaryobSpacing.sm,
                DaryobSpacing.sm,
                0,
              ),
              child: Row(
                children: [
                  const DaryobWordmark(height: 28),
                  const Spacer(),
                  if (_page < 3)
                    TextButton(
                      onPressed: () => _controller.animateToPage(
                        3,
                        duration: DaryobDurations.normal,
                        curve: Curves.easeOutCubic,
                      ),
                      child: Text(l10n.skip),
                    ),
                ],
              ),
            ),
            Expanded(
              child: PageView(
                controller: _controller,
                onPageChanged: (i) => setState(() => _page = i),
                children: [
                  _IntroPage(
                    illustration: const _Illustration(
                      center: Icons.storefront_rounded,
                      orbit: [
                        Icons.directions_car_outlined,
                        Icons.home_work_outlined,
                        Icons.smartphone_outlined,
                        Icons.checkroom_outlined,
                      ],
                    ),
                    title: l10n.onboardingWelcomeTitle,
                    body: l10n.onboardingWelcomeBody,
                  ),
                  _IntroPage(
                    illustration: const _Illustration(
                      center: Icons.photo_camera_rounded,
                      orbit: [
                        Icons.edit_outlined,
                        Icons.sell_outlined,
                        Icons.check_circle_outline_rounded,
                        Icons.image_outlined,
                      ],
                    ),
                    title: l10n.onboardingSellTitle,
                    body: l10n.onboardingSellBody,
                  ),
                  _IntroPage(
                    illustration: const _Illustration(
                      center: Icons.place_rounded,
                      orbit: [
                        Icons.chair_outlined,
                        Icons.work_outline_rounded,
                        Icons.build_outlined,
                        Icons.pets_outlined,
                      ],
                    ),
                    title: l10n.onboardingNearbyTitle,
                    body: l10n.onboardingNearbyBody,
                  ),
                  const _LanguagePage(),
                  const _CityPage(),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                DaryobSpacing.page,
                DaryobSpacing.sm,
                DaryobSpacing.page,
                DaryobSpacing.lg,
              ),
              child: Column(
                children: [
                  _Dots(count: _pageCount, index: _page),
                  const SizedBox(height: DaryobSpacing.lg),
                  DaryobPrimaryButton(
                    label: isLast ? l10n.startUsing : l10n.continueAction,
                    tone: isLast
                        ? DaryobButtonTone.accent
                        : DaryobButtonTone.primary,
                    onPressed: _next,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _IntroPage extends StatelessWidget {
  const _IntroPage({
    required this.illustration,
    required this.title,
    required this.body,
  });

  final Widget illustration;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.xxl),
      child: Column(
        children: [
          const SizedBox(height: DaryobSpacing.xxl),
          illustration,
          const SizedBox(height: DaryobSpacing.xxxl),
          Text(
            title,
            textAlign: TextAlign.center,
            style: context.text.headlineMedium,
          ),
          const SizedBox(height: DaryobSpacing.md),
          Text(
            body,
            textAlign: TextAlign.center,
            style: context.text.bodyLarge?.copyWith(
              color: context.palette.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

/// Brand illustration built from shapes and icons (no raster assets).
class _Illustration extends StatelessWidget {
  const _Illustration({required this.center, required this.orbit});

  final IconData center;
  final List<IconData> orbit;

  @override
  Widget build(BuildContext context) {
    const size = 240.0;
    const positions = [
      Alignment(-0.95, -0.7),
      Alignment(0.95, -0.55),
      Alignment(-0.85, 0.8),
      Alignment(0.9, 0.85),
    ];
    return ExcludeSemantics(
      child: SizedBox.square(
        dimension: size,
        child: Stack(
          alignment: Alignment.center,
          children: [
            Container(
              width: size * 0.82,
              height: size * 0.82,
              decoration: BoxDecoration(
                color: context.palette.limeSoft,
                shape: BoxShape.circle,
              ),
            ),
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                color: DaryobColors.navy,
                borderRadius: BorderRadius.circular(34),
              ),
              child: Icon(center, size: 58, color: DaryobColors.lime),
            ),
            for (var i = 0; i < orbit.length && i < positions.length; i++)
              Align(
                alignment: positions[i],
                child: Container(
                  width: 54,
                  height: 54,
                  decoration: BoxDecoration(
                    color: context.colors.surface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: context.palette.border),
                    boxShadow: [
                      BoxShadow(
                        color: context.palette.shadow,
                        blurRadius: 16,
                        offset: const Offset(0, 6),
                      ),
                    ],
                  ),
                  child: Icon(orbit[i], size: 26),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _LanguagePage extends StatelessWidget {
  const _LanguagePage();

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: DaryobSpacing.xxxl),
          const Icon(Icons.translate_rounded, size: 40),
          const SizedBox(height: DaryobSpacing.lg),
          // Shown in both languages so everyone can read it.
          Text(
            'Забонро интихоб кунед\nВыберите язык',
            style: context.text.headlineSmall,
          ),
          const SizedBox(height: DaryobSpacing.sm),
          Text(l10n.languageChangeLater, style: context.text.bodyMedium),
          const SizedBox(height: DaryobSpacing.xxl),
          const DaryobLanguageSelector(),
        ],
      ),
    );
  }
}

class _CityPage extends ConsumerWidget {
  const _CityPage();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final regionId = ref.watch(
      settingsControllerProvider.select((s) => s.regionId),
    );
    final directory = ref.watch(regionDirectoryProvider);
    final quick = [
      RegionIds.country,
      RegionIds.dushanbe,
      'khujand',
      'bokhtar',
      'kulob',
      'khorugh',
    ];

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: DaryobSpacing.xxxl),
          const Icon(Icons.place_outlined, size: 40),
          const SizedBox(height: DaryobSpacing.lg),
          Text(l10n.onboardingCityTitle, style: context.text.headlineSmall),
          const SizedBox(height: DaryobSpacing.sm),
          Text(l10n.onboardingCityBody, style: context.text.bodyMedium),
          const SizedBox(height: DaryobSpacing.xl),
          Wrap(
            spacing: DaryobSpacing.sm,
            runSpacing: DaryobSpacing.sm,
            children: [
              for (final id in quick)
                if (directory.byId(id) != null)
                  ChoiceChip(
                    label: Text(directory.byId(id)!.name.of(context)),
                    selected: regionId == id,
                    onSelected: (_) => ref
                        .read(settingsControllerProvider.notifier)
                        .setRegion(id),
                  ),
            ],
          ),
          const SizedBox(height: DaryobSpacing.lg),
          DaryobSecondaryButton(
            label: quick.contains(regionId)
                ? l10n.otherCity
                : regionPathLabel(context, directory, regionId),
            icon: Icons.search_rounded,
            onPressed: () async {
              final picked = await showLocationPicker(
                context,
                selectedId: regionId,
              );
              if (picked != null) {
                await ref
                    .read(settingsControllerProvider.notifier)
                    .setRegion(picked);
              }
            },
          ),
        ],
      ),
    );
  }
}

class _Dots extends StatelessWidget {
  const _Dots({required this.count, required this.index});
  final int count;
  final int index;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Semantics(
      label: '${index + 1} / $count',
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          for (var i = 0; i < count; i++)
            AnimatedContainer(
              duration: DaryobDurations.fast,
              margin: const EdgeInsets.symmetric(horizontal: 3),
              width: i == index ? 22 : 8,
              height: 8,
              decoration: BoxDecoration(
                color: i == index
                    ? (isDark ? DaryobColors.lime : DaryobColors.navy)
                    : context.palette.border,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
        ],
      ),
    );
  }
}
