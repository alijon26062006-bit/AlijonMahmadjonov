import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../../app/theme/tokens.dart';

/// The DARYOB mark: a map pin tilted 45° so its tip becomes the handle of a
/// magnifying glass, with a spark inside — search, place and "found it".
///
/// Drawn in code so it is sharp at any size; the Android launcher icon uses
/// the same geometry (see tool/brand/icon.svg).
class DaryobMark extends StatelessWidget {
  const DaryobMark({super.key, this.size = 48, this.color = DaryobColors.lime});

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'DARYOB',
      image: true,
      child: SizedBox.square(
        dimension: size,
        child: CustomPaint(painter: _MarkPainter(color)),
      ),
    );
  }
}

class _MarkPainter extends CustomPainter {
  _MarkPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width / 100;
    canvas.save();
    canvas.scale(s);

    final stroke = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round;

    // Pin outline: circle (centre 42,42, r 24) with its tip at (66,66).
    const c = Offset(42, 42);
    const r = 24.0;
    final pin = Path()
      ..moveTo(66, 42)
      ..arcTo(Rect.fromCircle(center: c, radius: r), 0, -1.5 * math.pi, false)
      ..lineTo(66, 66)
      ..close();
    canvas.drawPath(pin, stroke);

    // Handle continuing from the tip.
    canvas.drawLine(
      const Offset(68, 68),
      const Offset(83, 83),
      stroke..strokeWidth = 12,
    );

    // Four-point spark in the centre.
    final spark = Path();
    const outer = 11.0;
    const inner = 3.4;
    for (var i = 0; i < 8; i++) {
      final radius = i.isEven ? outer : inner;
      final angle = -math.pi / 2 + i * math.pi / 4;
      final p = c + Offset(math.cos(angle) * radius, math.sin(angle) * radius);
      i == 0 ? spark.moveTo(p.dx, p.dy) : spark.lineTo(p.dx, p.dy);
    }
    spark.close();
    canvas.drawPath(spark, Paint()..color = color);

    canvas.restore();
  }

  @override
  bool shouldRepaint(_MarkPainter old) => old.color != color;
}

/// Mark on a navy rounded square — the app icon look.
class DaryobBadgeLogo extends StatelessWidget {
  const DaryobBadgeLogo({super.key, this.size = 44});
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: DaryobColors.navy,
        borderRadius: BorderRadius.circular(size * 0.28),
      ),
      alignment: Alignment.center,
      child: DaryobMark(size: size * 0.72),
    );
  }
}

/// Mark + "DARYOB" wordmark for headers.
class DaryobWordmark extends StatelessWidget {
  const DaryobWordmark({super.key, this.height = 30});
  final double height;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        DaryobBadgeLogo(size: height),
        const SizedBox(width: DaryobSpacing.sm),
        Text(
          'DARYOB',
          style: TextStyle(
            fontFamily: 'Inter',
            fontWeight: FontWeight.w800,
            fontSize: height * 0.66,
            letterSpacing: 0.5,
            color: isDark ? DaryobColors.darkTextPrimary : DaryobColors.navy,
          ),
        ),
      ],
    );
  }
}
