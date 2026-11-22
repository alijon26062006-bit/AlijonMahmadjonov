import 'package:material_ui/material_ui.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../../core/utils/formatters.dart';
import '../models/user.dart';
import 'badges.dart';

class DaryobAvatar extends StatelessWidget {
  const DaryobAvatar({super.key, required this.initials, this.size = 48});
  final String initials;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: DaryobColors.navy,
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        initials.isEmpty ? '?' : initials,
        style: TextStyle(
          color: DaryobColors.lime,
          fontWeight: FontWeight.w800,
          fontSize: size * 0.36,
        ),
      ),
    );
  }
}

class DaryobSellerTile extends StatelessWidget {
  const DaryobSellerTile({super.key, required this.seller, this.onTap});

  final SellerSummary seller;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return InkWell(
      onTap: onTap,
      borderRadius: DaryobRadius.cardAll,
      child: Padding(
        padding: const EdgeInsets.all(DaryobSpacing.md),
        child: Row(
          children: [
            DaryobAvatar(initials: seller.initials),
            const SizedBox(width: DaryobSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          seller.name,
                          overflow: TextOverflow.ellipsis,
                          style: context.text.titleSmall,
                        ),
                      ),
                      if (seller.isVerified) ...[
                        const SizedBox(width: 4),
                        Tooltip(
                          message: l10n.verifiedSeller,
                          child: Icon(
                            Icons.verified_rounded,
                            size: 18,
                            color: context.palette.success,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    l10n.memberSince(Formatters.date(seller.memberSince)),
                    style: context.text.bodySmall,
                  ),
                  const SizedBox(height: DaryobSpacing.xs),
                  Wrap(
                    spacing: 4,
                    runSpacing: 4,
                    children: [
                      DaryobStatusBadge(
                        label: seller.isBusiness
                            ? l10n.sellerBusiness
                            : l10n.sellerPrivate,
                      ),
                      if (seller.isDemo) const DemoBadge(),
                    ],
                  ),
                ],
              ),
            ),
            if (onTap != null) const Icon(Icons.chevron_right_rounded),
          ],
        ),
      ),
    );
  }
}
