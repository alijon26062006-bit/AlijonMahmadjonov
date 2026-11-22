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
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: context.palette.border),
      ),
      clipBehavior: Clip.antiAlias,
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AspectRatio(
            aspectRatio: 1,
            child: DaryobLoadingSkeleton(radius: 0, height: double.infinity),
          ),
          Padding(
            padding: EdgeInsets.all(7),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DaryobLoadingSkeleton(width: 60, height: 13),
                SizedBox(height: 6),
                DaryobLoadingSkeleton(height: 10),
                SizedBox(height: 4),
                DaryobLoadingSkeleton(width: 50, height: 10),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class SliverListingGridSkeleton extends StatelessWidget {
  const SliverListingGridSkeleton({super.key, this.count = 6});
  final int count;

  @override
  Widget build(BuildContext context) {
    return SliverLayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.crossAxisExtent - DaryobSpacing.page * 2;
        final columns = SliverListingGrid.columnsFor(width);
        const gap = SliverListingGrid.gap;
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
