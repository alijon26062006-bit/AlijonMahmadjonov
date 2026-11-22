import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../../features/categories/data/tajikistan_regions.dart';
import '../../core/location/device_location.dart';
import '../../features/categories/domain/region_directory.dart';
import '../models/localized_text.dart';
import '../models/region.dart';
import '../providers/core_providers.dart';
import 'toast.dart';

/// Opens the two-level picker (region → city/district). Returns the chosen
/// id, or null when dismissed.
Future<String?> showLocationPicker(
  BuildContext context, {
  String? selectedId,
  bool allowWholeCountry = true,
}) {
  return showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.75,
      maxChildSize: 0.95,
      builder: (context, scroll) => _LocationPicker(
        scrollController: scroll,
        selectedId: selectedId,
        allowWholeCountry: allowWholeCountry,
      ),
    ),
  );
}

class _LocationPicker extends ConsumerStatefulWidget {
  const _LocationPicker({
    required this.scrollController,
    required this.selectedId,
    required this.allowWholeCountry,
  });

  final ScrollController scrollController;
  final String? selectedId;
  final bool allowWholeCountry;

  @override
  ConsumerState<_LocationPicker> createState() => _LocationPickerState();
}

class _LocationPickerState extends ConsumerState<_LocationPicker> {
  Region? _openRegion;
  bool _locating = false;

  Future<void> _locate() async {
    final l10n = context.l10n;
    setState(() => _locating = true);
    try {
      final id = await DeviceLocation.nearestCity();
      if (mounted) Navigator.of(context).pop(id);
    } on LocationException catch (e) {
      if (!mounted) return;
      setState(() => _locating = false);
      DaryobToast.show(context, locationProblemText(l10n, e.problem));
      if (e.problem == LocationProblem.deniedForever) {
        await DeviceLocation.openSettings();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final directory = ref.watch(regionDirectoryProvider);
    final open = _openRegion;
    final items = open == null
        ? directory.topLevel
        : directory.childrenOf(open.id);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            DaryobSpacing.xs,
            0,
            DaryobSpacing.page,
            DaryobSpacing.sm,
          ),
          child: Row(
            children: [
              if (open != null)
                IconButton(
                  tooltip: l10n.back,
                  icon: const Icon(Icons.arrow_back_rounded),
                  onPressed: () => setState(() => _openRegion = null),
                )
              else
                const SizedBox(width: DaryobSpacing.md),
              Expanded(
                child: Text(
                  open == null ? l10n.chooseLocation : open.name.of(context),
                  style: context.text.titleLarge,
                ),
              ),
            ],
          ),
        ),
        const Divider(),
        Expanded(
          child: ListView(
            controller: widget.scrollController,
            children: [
              if (open == null)
                ListTile(
                  leading: _locating
                      ? const SizedBox.square(
                          dimension: 22,
                          child: CircularProgressIndicator(strokeWidth: 2.2),
                        )
                      : Icon(Icons.my_location_rounded, color: context.colors.primary),
                  title: Text(l10n.locateMe, style: context.text.titleSmall),
                  subtitle: Text(l10n.locateMeHint),
                  onTap: _locating ? null : _locate,
                ),
              if (open == null && widget.allowWholeCountry)
                _tile(context, directory.country, directory, bold: true),
              if (open != null)
                _tile(
                  context,
                  open,
                  directory,
                  label: l10n.wholeRegion(open.name.of(context)),
                ),
              for (final region in items) _tile(context, region, directory),
            ],
          ),
        ),
      ],
    );
  }

  Widget _tile(
    BuildContext context,
    Region region,
    RegionDirectory directory, {
    String? label,
    bool bold = false,
  }) {
    final hasChildren =
        directory.childrenOf(region.id).isNotEmpty &&
        label == null &&
        region.level != RegionLevel.country;
    final selected = widget.selectedId == region.id;
    return ListTile(
      title: Text(
        label ?? region.name.of(context),
        style: bold || selected
            ? context.text.titleSmall
            : context.text.bodyLarge,
      ),
      leading: Icon(
        region.level == RegionLevel.country
            ? Icons.public_rounded
            : Icons.place_outlined,
      ),
      trailing: selected
          ? const Icon(Icons.check_rounded)
          : hasChildren
          ? const Icon(Icons.chevron_right_rounded)
          : null,
      onTap: () {
        if (hasChildren) {
          setState(() => _openRegion = region);
        } else {
          Navigator.of(context).pop(region.id);
        }
      },
    );
  }
}

/// Chip showing the selected place; tapping opens the picker.
class DaryobLocationChip extends ConsumerWidget {
  const DaryobLocationChip({
    super.key,
    required this.regionId,
    required this.onChanged,
    this.dense = false,
  });

  final String regionId;
  final ValueChanged<String> onChanged;
  final bool dense;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final directory = ref.watch(regionDirectoryProvider);
    final region =
        directory.byId(regionId) ?? directory.byId(RegionIds.country)!;
    return Semantics(
      button: true,
      label: '${context.l10n.location}: ${region.name.of(context)}',
      child: InkWell(
        borderRadius: DaryobRadius.chipAll,
        onTap: () async {
          final picked = await showLocationPicker(
            context,
            selectedId: regionId,
          );
          if (picked != null) onChanged(picked);
        },
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: DaryobSpacing.xs,
            vertical: dense ? DaryobSpacing.xs : DaryobSpacing.sm,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.place_rounded, size: 18),
              const SizedBox(width: 4),
              Flexible(
                child: Text(
                  region.name.of(context),
                  overflow: TextOverflow.ellipsis,
                  style: context.text.labelMedium,
                ),
              ),
              const Icon(Icons.expand_more_rounded, size: 18),
            ],
          ),
        ),
      ),
    );
  }
}

/// Full label "Sughd, Khujand" for detail screens.
String regionPathLabel(
  BuildContext context,
  RegionDirectory directory,
  String id,
) {
  final path = directory.pathTo(id);
  if (path.isEmpty) return directory.country.name.of(context);
  return path.reversed.map((r) => r.name.of(context)).join(', ');
}
