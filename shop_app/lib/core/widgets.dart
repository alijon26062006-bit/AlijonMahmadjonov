import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import 'demo_data.dart';
import 'format.dart';
import 'models.dart';
import 'theme.dart';

/// Сетка карточек: 2 колонки на телефоне, больше — на планшете.
const kProductGridDelegate = SliverGridDelegateWithMaxCrossAxisExtent(
  maxCrossAxisExtent: 240,
  mainAxisExtent: 296,
  crossAxisSpacing: 12,
  mainAxisSpacing: 12,
);

void showSnack(BuildContext context, String text, {String? actionLabel, VoidCallback? onAction}) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(text),
        duration: const Duration(milliseconds: 2400),
        persist: false,
        action: actionLabel == null ? null : SnackBarAction(label: actionLabel, onPressed: onAction ?? () {}),
      ),
    );
}

Future<bool> confirm(
  BuildContext context, {
  required String title,
  String? text,
  String ok = 'Да',
  bool danger = false,
}) async {
  final res = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: text == null ? null : Text(text),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
        TextButton(
          onPressed: () => Navigator.pop(ctx, true),
          child: Text(
            ok,
            style: TextStyle(color: danger ? kDanger : null, fontWeight: FontWeight.w700),
          ),
        ),
      ],
    ),
  );
  return res ?? false;
}

/// Выбор одного варианта из списка в нижней шторке.
Future<String?> pickOne(BuildContext context, {required String title, required List<String> options}) {
  return showModalBottomSheet<String>(
    context: context,
    builder: (ctx) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: Text(
              title,
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: AppColors.of(ctx).text),
            ),
          ),
          for (final o in options) ListTile(title: Text(o), onTap: () => Navigator.pop(ctx, o)),
          const SizedBox(height: 8),
        ],
      ),
    ),
  );
}

Future<void> callPhone(BuildContext context, String phone) async {
  final uri = Uri(scheme: 'tel', path: '+992${phoneDigits(phone)}');
  try {
    if (await launchUrl(uri)) return;
  } catch (_) {}
  if (context.mounted) {
    Clipboard.setData(ClipboardData(text: formatPhone(phone)));
    showSnack(context, 'Номер скопирован: ${formatPhone(phone)}');
  }
}

Future<void> openMap(BuildContext context, String address) async {
  final uri = Uri.parse('geo:0,0?q=${Uri.encodeComponent(address)}');
  try {
    if (await launchUrl(uri)) return;
  } catch (_) {}
  if (context.mounted) {
    Clipboard.setData(ClipboardData(text: address));
    showSnack(context, 'Адрес скопирован');
  }
}

List<Color> tintFor(BuildContext context, String categoryId) {
  final c = AppColors.of(context);
  final tint = categoryById(categoryId).tint;
  return c.dark ? [for (final t in tint) Color.lerp(t, c.surface, .74)!] : tint;
}

String _assetFor(String image) => 'assets/img/$image.png';

/// Картинка товара или магазина на мягком фоне категории.
///
/// [image] — имя иллюстрации из `assets/img` или ссылка `https://…`
/// (фото, загруженные продавцами, после подключения сервера).
class ProductImage extends StatelessWidget {
  const ProductImage({
    super.key,
    required this.image,
    required this.categoryId,
    this.size = 64,
    this.radius = 18,
    this.heroTag,
    this.dimmed = false,
  });

  final String image;
  final String categoryId;
  final double size;
  final double radius;
  final String? heroTag;
  final bool dimmed;

  @override
  Widget build(BuildContext context) {
    Widget picture = SizedBox.square(dimension: size * 1.3, child: AppImage(image));
    if (heroTag != null) picture = Hero(tag: heroTag!, child: picture);
    return Opacity(
      opacity: dimmed ? .45 : 1,
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(radius),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: tintFor(context, categoryId),
          ),
        ),
        child: Center(child: picture),
      ),
    );
  }
}

/// Иллюстрация из `assets/img` или изображение по ссылке.
class AppImage extends StatelessWidget {
  const AppImage(this.image, {super.key, this.fit = BoxFit.contain});

  final String image;
  final BoxFit fit;

  @override
  Widget build(BuildContext context) {
    final fallback = Icon(Icons.image_outlined, color: AppColors.of(context).muted);
    if (image.startsWith('http')) {
      return Image.network(image, fit: fit, errorBuilder: (_, _, _) => fallback);
    }
    return Image.asset(
      _assetFor(image),
      fit: fit,
      filterQuality: FilterQuality.medium,
      errorBuilder: (_, _, _) => fallback,
    );
  }
}

/// Маленькая плитка с картинкой (для списков).
class ImageTile extends StatelessWidget {
  const ImageTile({super.key, required this.image, required this.categoryId, this.size = 48});

  final String image;
  final String categoryId;
  final double size;

  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    padding: EdgeInsets.all(size * .16),
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(size * .3),
      gradient: LinearGradient(
        colors: tintFor(context, categoryId),
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
    ),
    child: AppImage(image),
  );
}

class DiscountBadge extends StatelessWidget {
  const DiscountBadge(this.percent, {super.key, this.fontSize = 12});

  final int percent;
  final double fontSize;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(color: const Color(0xFFF107A3), borderRadius: BorderRadius.circular(8)),
    child: Text(
      '−$percent%',
      style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: fontSize),
    ),
  );
}

class PriceRow extends StatelessWidget {
  const PriceRow({super.key, required this.price, this.oldPrice, this.size = 17});

  final int price;
  final int? oldPrice;
  final double size;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        Flexible(
          flex: 3,
          child: FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              money(price),
              style: TextStyle(fontSize: size, fontWeight: FontWeight.w800, letterSpacing: -0.4, color: c.text),
            ),
          ),
        ),
        if (oldPrice != null) ...[
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              groupDigits(oldPrice!),
              maxLines: 1,
              overflow: TextOverflow.fade,
              softWrap: false,
              style: TextStyle(
                fontSize: size * .72,
                color: c.muted,
                decoration: TextDecoration.lineThrough,
                decorationColor: c.muted,
              ),
            ),
          ),
        ],
      ],
    );
  }
}

/// Главная кнопка с градиентом приложения.
class GradientButton extends StatelessWidget {
  const GradientButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.trailing,
    this.height = 54,
    this.colors,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final String? trailing;
  final double height;

  /// Свои цвета (например, зелёная кнопка «Доставил»).
  final List<Color>? colors;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final enabled = onPressed != null;
    final grad = colors == null ? c.gradient : LinearGradient(colors: colors!);
    return AnimatedOpacity(
      duration: const Duration(milliseconds: 200),
      opacity: enabled ? 1 : .45,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: grad,
          borderRadius: BorderRadius.circular(16),
          boxShadow: enabled
              ? [
                  BoxShadow(
                    color: grad.colors.last.withValues(alpha: .45),
                    blurRadius: 24,
                    offset: const Offset(0, 12),
                    spreadRadius: -10,
                  ),
                ]
              : null,
        ),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: onPressed == null
                ? null
                : () {
                    HapticFeedback.lightImpact();
                    onPressed!();
                  },
            child: SizedBox(
              height: height,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (icon != null) ...[Icon(icon, color: Colors.white, size: 21), const SizedBox(width: 8)],
                    Flexible(
                      child: Text(
                        label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16),
                      ),
                    ),
                    if (trailing != null)
                      Text(
                        '  ·  $trailing',
                        style: const TextStyle(color: Color(0xD9FFFFFF), fontWeight: FontWeight.w600, fontSize: 14.5),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Второстепенная кнопка (светлая).
class SoftButton extends StatelessWidget {
  const SoftButton({super.key, required this.label, this.onPressed, this.icon, this.color, this.height = 54});

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final Color? color;
  final double height;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final fg = color ?? c.text;
    return SizedBox(
      height: height,
      child: FilledButton.tonal(
        style: FilledButton.styleFrom(
          backgroundColor: color == null ? c.chip : color!.withValues(alpha: .12),
          foregroundColor: fg,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          padding: const EdgeInsets.symmetric(horizontal: 16),
        ),
        onPressed: onPressed,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[Icon(icon, size: 20), const SizedBox(width: 6)],
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class QtyStepper extends StatelessWidget {
  const QtyStepper({
    super.key,
    required this.value,
    required this.onChanged,
    this.min = 1,
    this.max = 99,
    this.compact = false,
  });

  final int value;
  final ValueChanged<int> onChanged;
  final int min;
  final int max;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final h = compact ? 34.0 : 54.0;
    Widget btn(IconData icon, VoidCallback? onTap) => InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: onTap == null
          ? null
          : () {
              HapticFeedback.selectionClick();
              onTap();
            },
      child: SizedBox(
        width: compact ? 32 : 42,
        height: h,
        child: Icon(icon, size: compact ? 18 : 22, color: onTap == null ? c.line : c.muted),
      ),
    );
    return Container(
      height: h,
      decoration: BoxDecoration(color: c.chip, borderRadius: BorderRadius.circular(compact ? 11 : 16)),
      child: Material(
        type: MaterialType.transparency,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            btn(Icons.remove_rounded, value > min ? () => onChanged(value - 1) : null),
            SizedBox(
              width: compact ? 22 : 30,
              child: Text(
                '$value',
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.w800, fontSize: compact ? 14 : 16, color: c.text),
              ),
            ),
            btn(Icons.add_rounded, value < max ? () => onChanged(value + 1) : null),
          ],
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.action, this.onAction});

  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 22, 8, 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, letterSpacing: -0.3, color: c.text),
            ),
          ),
          if (action != null)
            TextButton(
              onPressed: onAction,
              child: Text(
                action!,
                style: TextStyle(color: c.accentText, fontWeight: FontWeight.w700, fontSize: 14),
              ),
            ),
        ],
      ),
    );
  }
}

/// Крупный заголовок вкладки.
class PageTitle extends StatelessWidget {
  const PageTitle(this.title, {super.key, this.badge, this.trailing, this.subtitle});

  final String title;
  final String? badge;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 16, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Flexible(
                      child: Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 30,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.8,
                          color: c.text,
                          height: 1.1,
                        ),
                      ),
                    ),
                    if (badge != null)
                      Padding(
                        padding: const EdgeInsets.only(left: 6, top: 2),
                        child: Text(
                          badge!,
                          style: TextStyle(fontSize: 14, color: c.muted, fontWeight: FontWeight.w600),
                        ),
                      ),
                  ],
                ),
                if (subtitle != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(subtitle!, style: TextStyle(fontSize: 14, color: c.muted)),
                  ),
              ],
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

class CircleButton extends StatelessWidget {
  const CircleButton({
    super.key,
    required this.icon,
    required this.onTap,
    this.background,
    this.color,
    this.size = 44,
    this.tooltip,
  });

  final IconData icon;
  final VoidCallback onTap;
  final Color? background;
  final Color? color;
  final double size;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final button = Material(
      color: background ?? c.chip,
      shape: const CircleBorder(),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox.square(
          dimension: size,
          child: Icon(icon, size: size * .5, color: color ?? c.text),
        ),
      ),
    );
    return tooltip == null ? button : Tooltip(message: tooltip!, child: button);
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.image,
    required this.title,
    required this.subtitle,
    this.buttonLabel,
    this.onButton,
  });

  final String image;
  final String title;
  final String subtitle;
  final String? buttonLabel;
  final VoidCallback? onButton;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(color: c.accentSoft, shape: BoxShape.circle),
              alignment: Alignment.center,
              padding: const EdgeInsets.all(22),
              child: AppImage(image),
            ),
            const SizedBox(height: 22),
            Text(
              title,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800, color: c.text),
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, color: c.muted, height: 1.4),
            ),
            if (buttonLabel != null) ...[
              const SizedBox(height: 24),
              SizedBox(
                width: 240,
                child: GradientButton(label: buttonLabel!, onPressed: onButton),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Выбираемая плитка (способ доставки, оплаты и т.п.).
class ChoiceTile extends StatelessWidget {
  const ChoiceTile({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: selected ? c.accentSoft : c.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: selected ? c.accentText : c.line, width: 1.5),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: selected ? c.surface : c.chip,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon, size: 21, color: selected ? c.accentText : c.muted),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: c.text),
                      ),
                      if (subtitle != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(subtitle!, style: TextStyle(fontSize: 13, color: c.muted)),
                        ),
                    ],
                  ),
                ),
                Icon(
                  selected ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                  color: selected ? c.accentText : c.line,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Строка «название — сумма».
class SummaryRow extends StatelessWidget {
  const SummaryRow(this.label, this.value, {super.key, this.color, this.big = false});

  final String label;
  final String value;
  final Color? color;
  final bool big;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final style = TextStyle(
      fontSize: big ? 19 : 14.5,
      fontWeight: big ? FontWeight.w800 : FontWeight.w500,
      color: color ?? (big ? c.text : c.muted),
      letterSpacing: big ? -0.3 : 0,
    );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(label, style: style)),
          Text(
            value,
            style: style.copyWith(color: color ?? c.text, fontWeight: big ? FontWeight.w800 : FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

/// Нижняя панель с кнопкой.
class BottomBar extends StatelessWidget {
  const BottomBar({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.surface,
        boxShadow: const [
          BoxShadow(color: Color(0x1A000000), blurRadius: 24, offset: Offset(0, -6), spreadRadius: -10),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 12), child: child),
      ),
    );
  }
}

/// Белая карточка с закруглением.
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.margin,
    this.onTap,
    this.color,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final VoidCallback? onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Container(
      margin: margin,
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), boxShadow: c.cardShadow),
      child: Material(
        color: color ?? c.surface,
        borderRadius: BorderRadius.circular(20),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

/// Цветная «таблетка» со статусом.
class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.label, required this.color, this.icon});

  final String label;
  final Color color;
  final IconData? icon;

  factory StatusPill.order(Order o) => StatusPill(label: o.statusLabel, color: o.status.color);

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
    decoration: BoxDecoration(color: color.withValues(alpha: .13), borderRadius: BorderRadius.circular(99)),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) ...[Icon(icon, size: 14, color: color), const SizedBox(width: 4)],
        Flexible(
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 12.5),
          ),
        ),
      ],
    ),
  );
}

/// Плитка статистики: число и подпись.
class StatCard extends StatelessWidget {
  const StatCard({super.key, required this.value, required this.label, this.icon, this.color, this.onTap});

  final String value;
  final String label;
  final IconData? icon;
  final Color? color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final accent = color ?? c.accentText;
    return AppCard(
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (icon != null)
            Container(
              width: 32,
              height: 32,
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(color: accent.withValues(alpha: .13), borderRadius: BorderRadius.circular(11)),
              child: Icon(icon, size: 19, color: accent),
            ),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800, letterSpacing: -0.5, color: c.text),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 12.5, color: c.muted),
          ),
        ],
      ),
    );
  }
}

/// Строка с иконкой и текстом (адрес, телефон, оплата…).
class InfoLine extends StatelessWidget {
  const InfoLine({super.key, required this.icon, required this.text, this.title, this.trailing, this.onTap});

  final IconData icon;
  final String text;
  final String? title;
  final Widget? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(color: c.accentSoft, borderRadius: BorderRadius.circular(11)),
              child: Icon(icon, size: 19, color: c.accentText),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (title != null) Text(title!, style: TextStyle(fontSize: 12.5, color: c.muted)),
                  Text(
                    text,
                    style: TextStyle(fontSize: 14.5, color: c.text, fontWeight: FontWeight.w600, height: 1.3),
                  ),
                ],
              ),
            ),
            ?trailing,
          ],
        ),
      ),
    );
  }
}

/// Список позиций заказа.
class OrderItemsList extends StatelessWidget {
  const OrderItemsList({super.key, required this.order, this.categoryOf});

  final Order order;
  final String Function(String productId)? categoryOf;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Column(
      children: [
        for (final i in order.items)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              children: [
                ImageTile(image: i.image, categoryId: categoryOf?.call(i.productId) ?? 'electronics', size: 46),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        i.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontWeight: FontWeight.w600, color: c.text),
                      ),
                      Text(
                        '${i.option == null ? '' : '${i.option} · '}${i.qty} шт. × ${money(i.price)}',
                        style: TextStyle(fontSize: 12.5, color: c.muted),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  money(i.sum),
                  style: TextStyle(fontWeight: FontWeight.w700, color: c.text),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

/// Шкала статусов заказа.
class OrderTimeline extends StatelessWidget {
  const OrderTimeline({super.key, required this.order});

  final Order order;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final steps = order.status == OrderStatus.cancelled
        ? [OrderStatus.placed, OrderStatus.cancelled]
        : [
            OrderStatus.placed,
            OrderStatus.accepted,
            OrderStatus.ready,
            if (order.delivery) OrderStatus.delivering,
            OrderStatus.delivered,
          ];
    final currentIndex = steps.indexOf(order.status);
    return Column(
      children: [
        for (var i = 0; i < steps.length; i++)
          _TimelineStep(
            status: steps[i],
            label: steps[i].label(delivery: order.delivery),
            time: order.timeOf(steps[i]),
            done: i <= currentIndex,
            current: i == currentIndex && !order.status.isFinal,
            last: i == steps.length - 1,
            colors: c,
          ),
      ],
    );
  }
}

class _TimelineStep extends StatelessWidget {
  const _TimelineStep({
    required this.status,
    required this.label,
    required this.time,
    required this.done,
    required this.current,
    required this.last,
    required this.colors,
  });

  final OrderStatus status;
  final String label;
  final DateTime? time;
  final bool done;
  final bool current;
  final bool last;
  final AppColors colors;

  @override
  Widget build(BuildContext context) {
    final color = done ? status.color : colors.line;
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 32,
            child: Column(
              children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  width: current ? 30 : 26,
                  height: current ? 30 : 26,
                  decoration: BoxDecoration(
                    color: done ? color : colors.surface,
                    shape: BoxShape.circle,
                    border: Border.all(color: color, width: 2),
                    boxShadow: current ? [BoxShadow(color: color.withValues(alpha: .4), blurRadius: 12)] : null,
                  ),
                  child: Icon(status.icon, size: 15, color: done ? Colors.white : colors.muted),
                ),
                if (!last)
                  Expanded(child: Container(width: 2, color: done ? color.withValues(alpha: .5) : colors.line)),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(top: 4, bottom: last ? 0 : 18),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      label,
                      style: TextStyle(
                        fontWeight: current ? FontWeight.w800 : FontWeight.w600,
                        color: done ? colors.text : colors.muted,
                        fontSize: 15,
                      ),
                    ),
                  ),
                  if (time != null && done)
                    Text(formatTime(time!), style: TextStyle(color: colors.muted, fontSize: 13)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Плашка с пояснением.
class InfoNote extends StatelessWidget {
  const InfoNote({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: c.accentSoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: c.accentText.withValues(alpha: .25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline_rounded, size: 18, color: c.accentText),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text, style: TextStyle(fontSize: 12.5, color: c.text, height: 1.35)),
          ),
        ],
      ),
    );
  }
}

/// Простой столбчатый график (заказы/выручка по дням).
class MiniBarChart extends StatelessWidget {
  const MiniBarChart({super.key, required this.values, required this.labels, this.height = 120, this.format});

  final List<int> values;
  final List<String> labels;
  final double height;
  final String Function(int)? format;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final maxV = values.fold<int>(1, (m, v) => v > m ? v : m);
    return SizedBox(
      height: height + 52,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (var i = 0; i < values.length; i++)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    FittedBox(
                      child: Text(
                        format?.call(values[i]) ?? '${values[i]}',
                        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: c.muted),
                      ),
                    ),
                    const SizedBox(height: 4),
                    TweenAnimationBuilder<double>(
                      tween: Tween(begin: 0, end: values[i] / maxV),
                      duration: const Duration(milliseconds: 600),
                      curve: Curves.easeOutCubic,
                      builder: (_, v, _) => Container(
                        height: (height * v).clamp(4, height),
                        decoration: BoxDecoration(
                          gradient: i == values.length - 1
                              ? LinearGradient(
                                  colors: [c.gradientColors.last, c.gradientColors.first],
                                  begin: Alignment.topCenter,
                                  end: Alignment.bottomCenter,
                                )
                              : null,
                          color: i == values.length - 1 ? null : c.accentSoft,
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      labels[i],
                      style: TextStyle(
                        fontSize: 12,
                        color: i == values.length - 1 ? c.accentText : c.muted,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Заголовок поля формы.
class FieldLabel extends StatelessWidget {
  const FieldLabel(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(4, 18, 4, 8),
    child: Text(
      text,
      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: AppColors.of(context).text),
    ),
  );
}
