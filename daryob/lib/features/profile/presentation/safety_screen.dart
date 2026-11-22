import 'package:material_ui/material_ui.dart';

import '../../../app/localization/l10n.dart';
import '../../../app/theme/tokens.dart';

/// Basic safety advice for buyers and sellers.
class SafetyScreen extends StatelessWidget {
  const SafetyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final buyer = [
      (Icons.visibility_outlined, l10n.safetyBuyer1),
      (Icons.payments_outlined, l10n.safetyBuyer2),
      (Icons.groups_outlined, l10n.safetyBuyer3),
      (Icons.description_outlined, l10n.safetyBuyer4),
    ];
    final seller = [
      (Icons.sms_failed_outlined, l10n.safetySeller1),
      (Icons.credit_card_off_outlined, l10n.safetySeller2),
      (Icons.link_off_rounded, l10n.safetySeller3),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(l10n.safetyTitle)),
      body: ListView(
        padding: const EdgeInsets.all(DaryobSpacing.page),
        children: [
          Text(l10n.safetyIntro, style: context.text.bodyLarge),
          const SizedBox(height: DaryobSpacing.xl),
          Text(l10n.safetyForBuyers, style: context.text.titleMedium),
          for (final (icon, text) in buyer) _Tip(icon: icon, text: text),
          const SizedBox(height: DaryobSpacing.xl),
          Text(l10n.safetyForSellers, style: context.text.titleMedium),
          for (final (icon, text) in seller) _Tip(icon: icon, text: text),
          const SizedBox(height: DaryobSpacing.xl),
          Text(l10n.safetyReport, style: context.text.bodyMedium),
        ],
      ),
    );
  }
}

class _Tip extends StatelessWidget {
  const _Tip({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: DaryobSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: context.palette.limeSoft,
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 20),
          ),
          const SizedBox(width: DaryobSpacing.md),
          Expanded(child: Text(text, style: context.text.bodyMedium)),
        ],
      ),
    );
  }
}
