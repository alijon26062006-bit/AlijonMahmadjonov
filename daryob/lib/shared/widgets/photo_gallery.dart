import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../models/category.dart';
import 'category_visuals.dart';
import 'listing_image.dart';

/// Swipeable photo gallery with a counter. Tap opens full screen.
class DaryobPhotoGallery extends StatefulWidget {
  const DaryobPhotoGallery({
    super.key,
    required this.photos,
    required this.icon,
    this.height = 320,
  });

  final List<String> photos;
  final CategoryIcon icon;
  final double height;

  @override
  State<DaryobPhotoGallery> createState() => _DaryobPhotoGalleryState();
}

class _DaryobPhotoGalleryState extends State<DaryobPhotoGallery> {
  final _controller = PageController();
  int _index = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final photos = widget.photos;
    if (photos.isEmpty) {
      return SizedBox(
        height: widget.height,
        child: Stack(
          fit: StackFit.expand,
          children: [
            DaryobListingImage(source: null, icon: widget.icon),
            Positioned(
              left: 0,
              right: 0,
              bottom: DaryobSpacing.lg,
              child: Text(
                context.l10n.noPhotos,
                textAlign: TextAlign.center,
                style: context.text.bodySmall?.copyWith(
                  color: categoryColors(context, widget.icon).foreground,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      );
    }

    return SizedBox(
      height: widget.height,
      child: Stack(
        children: [
          PageView.builder(
            controller: _controller,
            itemCount: photos.length,
            onPageChanged: (i) => setState(() => _index = i),
            itemBuilder: (context, i) => GestureDetector(
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  fullscreenDialog: true,
                  builder: (_) => _FullScreenGallery(
                    photos: photos,
                    initial: i,
                    icon: widget.icon,
                  ),
                ),
              ),
              child: Semantics(
                image: true,
                label: context.l10n.photoOf(i + 1, photos.length),
                child: DaryobListingImage(source: photos[i], icon: widget.icon),
              ),
            ),
          ),
          if (photos.length > 1)
            Positioned(
              right: DaryobSpacing.md,
              bottom: DaryobSpacing.md,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.6),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  '${_index + 1} / ${photos.length}',
                  style: context.text.labelMedium?.copyWith(
                    color: Colors.white,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _FullScreenGallery extends StatefulWidget {
  const _FullScreenGallery({
    required this.photos,
    required this.initial,
    required this.icon,
  });
  final List<String> photos;
  final int initial;
  final CategoryIcon icon;

  @override
  State<_FullScreenGallery> createState() => _FullScreenGalleryState();
}

class _FullScreenGalleryState extends State<_FullScreenGallery> {
  late final _controller = PageController(initialPage: widget.initial);
  late int _index = widget.initial;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text('${_index + 1} / ${widget.photos.length}'),
      ),
      body: PageView.builder(
        controller: _controller,
        itemCount: widget.photos.length,
        onPageChanged: (i) => setState(() => _index = i),
        itemBuilder: (_, i) => InteractiveViewer(
          maxScale: 4,
          child: Center(
            child: DaryobListingImage(
              source: widget.photos[i],
              icon: widget.icon,
              fit: BoxFit.contain,
            ),
          ),
        ),
      ),
    );
  }
}
