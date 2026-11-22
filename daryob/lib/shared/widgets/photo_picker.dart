import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../../core/utils/validators.dart';
import '../models/category.dart';
import 'listing_image.dart';
import 'toast.dart';

/// Pick, remove and reorder listing photos. Images are resized and
/// compressed by the picker (max 1600 px, quality 80) before saving.
class DaryobPhotoPicker extends StatefulWidget {
  const DaryobPhotoPicker({
    super.key,
    required this.photos,
    required this.onChanged,
    this.icon = CategoryIcon.generic,
    this.picker,
  });

  final List<String> photos;
  final ValueChanged<List<String>> onChanged;
  final CategoryIcon icon;

  /// Injectable for tests.
  final ImagePicker? picker;

  @override
  State<DaryobPhotoPicker> createState() => _DaryobPhotoPickerState();
}

class _DaryobPhotoPickerState extends State<DaryobPhotoPicker> {
  late final ImagePicker _picker = widget.picker ?? ImagePicker();
  bool _busy = false;

  int get _remaining => ListingLimits.photosMax - widget.photos.length;

  Future<void> _pick(ImageSource source) async {
    if (_remaining <= 0 || _busy) return;
    setState(() => _busy = true);
    try {
      final List<XFile> files;
      if (source == ImageSource.gallery) {
        files = await _picker.pickMultiImage(
          maxWidth: 1600,
          maxHeight: 1600,
          imageQuality: 80,
          limit: _remaining > 1 ? _remaining : null,
        );
      } else {
        final file = await _picker.pickImage(
          source: ImageSource.camera,
          maxWidth: 1600,
          maxHeight: 1600,
          imageQuality: 80,
        );
        files = file == null ? const [] : [file];
      }
      if (files.isEmpty) return;
      widget.onChanged(
        [
          ...widget.photos,
          ...files.map((f) => f.path),
        ].take(ListingLimits.photosMax).toList(),
      );
    } catch (_) {
      if (mounted) {
        DaryobToast.show(context, context.l10n.photoPickFailed, isError: true);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _move(int from, int to) {
    final next = List.of(widget.photos);
    final item = next.removeAt(from);
    next.insert(to, item);
    widget.onChanged(next);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final photos = widget.photos;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: _AddButton(
                icon: Icons.photo_library_outlined,
                label: l10n.photoFromGallery,
                busy: _busy,
                enabled: _remaining > 0,
                onTap: () => _pick(ImageSource.gallery),
              ),
            ),
            const SizedBox(width: DaryobSpacing.md),
            Expanded(
              child: _AddButton(
                icon: Icons.photo_camera_outlined,
                label: l10n.photoFromCamera,
                busy: false,
                enabled: _remaining > 0 && !_busy,
                onTap: () => _pick(ImageSource.camera),
              ),
            ),
          ],
        ),
        const SizedBox(height: DaryobSpacing.sm),
        Text(
          l10n.photosCounter(photos.length, ListingLimits.photosMax),
          style: context.text.bodySmall,
        ),
        if (photos.isNotEmpty) ...[
          const SizedBox(height: DaryobSpacing.md),
          Text(l10n.photosReorderHint, style: context.text.bodySmall),
          const SizedBox(height: DaryobSpacing.sm),
          for (var i = 0; i < photos.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: DaryobSpacing.sm),
              child: _PhotoRow(
                key: ValueKey(photos[i]),
                source: photos[i],
                index: i,
                count: photos.length,
                icon: widget.icon,
                onRemove: () => widget.onChanged(List.of(photos)..removeAt(i)),
                onUp: i == 0 ? null : () => _move(i, i - 1),
                onDown: i == photos.length - 1 ? null : () => _move(i, i + 1),
              ),
            ),
        ],
      ],
    );
  }
}

class _AddButton extends StatelessWidget {
  const _AddButton({
    required this.icon,
    required this.label,
    required this.busy,
    required this.enabled,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool busy;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: context.palette.limeSoft,
      borderRadius: DaryobRadius.cardAll,
      child: InkWell(
        borderRadius: DaryobRadius.cardAll,
        onTap: enabled ? onTap : null,
        child: Opacity(
          opacity: enabled ? 1 : 0.45,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: DaryobSpacing.xl),
            child: Column(
              children: [
                busy
                    ? const SizedBox.square(
                        dimension: 26,
                        child: CircularProgressIndicator(strokeWidth: 2.4),
                      )
                    : Icon(icon, size: 28),
                const SizedBox(height: DaryobSpacing.sm),
                Text(
                  label,
                  textAlign: TextAlign.center,
                  style: context.text.labelMedium,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _PhotoRow extends StatelessWidget {
  const _PhotoRow({
    super.key,
    required this.source,
    required this.index,
    required this.count,
    required this.icon,
    required this.onRemove,
    required this.onUp,
    required this.onDown,
  });

  final String source;
  final int index;
  final int count;
  final CategoryIcon icon;
  final VoidCallback onRemove;
  final VoidCallback? onUp;
  final VoidCallback? onDown;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Container(
      decoration: BoxDecoration(
        color: context.colors.surface,
        borderRadius: DaryobRadius.inputAll,
        border: Border.all(color: context.palette.border),
      ),
      padding: const EdgeInsets.all(DaryobSpacing.sm),
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: SizedBox(
              width: 72,
              height: 56,
              child: DaryobListingImage(
                source: source,
                icon: icon,
                cacheWidth: 216,
              ),
            ),
          ),
          const SizedBox(width: DaryobSpacing.md),
          Expanded(
            child: Text(
              index == 0 ? l10n.photoCover : l10n.photoNumber(index + 1),
              style: index == 0
                  ? context.text.titleSmall
                  : context.text.bodyMedium,
            ),
          ),
          IconButton(
            tooltip: l10n.moveUp,
            onPressed: onUp,
            icon: const Icon(Icons.arrow_upward_rounded),
          ),
          IconButton(
            tooltip: l10n.moveDown,
            onPressed: onDown,
            icon: const Icon(Icons.arrow_downward_rounded),
          ),
          IconButton(
            tooltip: l10n.delete,
            onPressed: onRemove,
            icon: Icon(
              Icons.delete_outline_rounded,
              color: context.colors.error,
            ),
          ),
        ],
      ),
    );
  }
}
