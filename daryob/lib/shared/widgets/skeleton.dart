import 'package:material_ui/material_ui.dart';

import '../../app/theme/tokens.dart';
import 'listing_card.dart';

/// Gently pulsing placeholder block.
class DaryobLoadingSkeleton extends StatefulWidget {
  const DaryobLoadingSkeleton({
    super.key,
    this.width,
    this.height = 16,
    this.radius = 8,
  });

  final double? width;
  final double height;
  final double radius;

  @override
  State<DaryobLoadingSkeleton> createState() => _DaryobLoadingSkeletonState();
}

class _DaryobLoadingSkeletonState extends State<DaryobLoadingSkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
    lowerBound: 0.55,
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _controller,
      child: Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          color: context.palette.skeleton,
          borderRadius: BorderRadius.circular(widget.radius),
        ),
      ),
    );
  }
}

class ListingCardSkeleton extends StatelessWidget {
  const ListingCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: context.colors.surface,
        borderRadius: DaryobRadius.cardAll,
        border: Border.all(color: context.palette.border),
      ),
      clipBehavior: Clip.antiAlias,
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AspectRatio(
            aspectRatio: 4 / 3,
            child: DaryobLoadingSkeleton(radius: 0, height: double.infinity),
          ),
          Padding(
            padding: EdgeInsets.all(DaryobSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DaryobLoadingSkeleton(width: 90, height: 18),
                SizedBox(height: DaryobSpacing.sm),
                DaryobLoadingSkeleton(height: 12),
                SizedBox(height: 6),
                DaryobLoadingSkeleton(width: 110, height: 12),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class SliverListingGridSkeleton extends StatelessWidget {
  const SliverListingGridSkeleton({super.key, this.count = 4});
  final int count;

  @override
  Widget build(BuildContext context) {
    return SliverLayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.crossAxisExtent - DaryobSpacing.page * 2;
        final columns = SliverListingGrid.columnsFor(width);
        const gap = DaryobSpacing.md;
        final cell = (width - gap * (columns - 1)) / columns;
        return SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: DaryobSpacing.page),
          sliver: SliverGrid(
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: columns,
              mainAxisSpacing: gap,
              crossAxisSpacing: gap,
              mainAxisExtent: SliverListingGrid.extentFor(context, cell),
            ),
            delegate: SliverChildBuilderDelegate(
              (_, _) => const ListingCardSkeleton(),
              childCount: count,
            ),
          ),
        );
      },
    );
  }
}
