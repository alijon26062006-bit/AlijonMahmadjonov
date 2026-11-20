import 'dart:async';

import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../core/demo_data.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import 'buyer_common.dart';
import 'order_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = StoreScope.of(context);
    final catalog = s.catalog;
    final hits = catalog.where((p) => p.hit).toList();
    final recommended = [...catalog]..sort((a, b) => b.rating.compareTo(a.rating));
    final shops = s.visibleShops;
    final active = s.myOrders.where((o) => o.status.isActive).toList();
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(child: _Header(productsCount: catalog.length)),
          if (active.isNotEmpty)
            SliverToBoxAdapter(
              child: _ActiveOrderBanner(order: active.first, more: active.length - 1),
            ),
          const SliverToBoxAdapter(child: _PromoCarousel()),
          SliverToBoxAdapter(
            child: SectionHeader('Категории', action: 'Все', onAction: () => buyerNav.openCatalog()),
          ),
          const SliverToBoxAdapter(child: _CategoriesRow()),
          SliverToBoxAdapter(child: SectionHeader('Магазины', action: '${shops.length}')),
          SliverToBoxAdapter(
            child: SizedBox(
              height: 92,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: shops.length,
                separatorBuilder: (_, _) => const SizedBox(width: 10),
                itemBuilder: (_, i) => SizedBox(width: 240, child: ShopCard(shop: shops[i])),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: SectionHeader('Хиты продаж', action: 'Смотреть все', onAction: () => buyerNav.openCatalog()),
          ),
          SliverToBoxAdapter(
            child: SizedBox(
              height: 296,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: hits.length,
                separatorBuilder: (_, _) => const SizedBox(width: 12),
                itemBuilder: (_, i) => SizedBox(
                  width: 172,
                  child: ProductCard(product: hits[i], heroPrefix: 'hit'),
                ),
              ),
            ),
          ),
          const SliverToBoxAdapter(child: SectionHeader('Рекомендуем вам')),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
            sliver: SliverGrid.builder(
              gridDelegate: kProductGridDelegate,
              itemCount: recommended.length,
              itemBuilder: (_, i) => ProductCard(product: recommended[i], heroPrefix: 'rec'),
            ),
          ),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.productsCount});

  final int productsCount;

  String get _greeting {
    final h = DateTime.now().hour;
    if (h < 5) return 'Доброй ночи';
    if (h < 12) return 'Доброе утро';
    if (h < 18) return 'Добрый день';
    return 'Добрый вечер';
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final top = MediaQuery.paddingOf(context).top;
    final name = StoreScope.of(context).user?.name ?? '';
    return Container(
      padding: EdgeInsets.fromLTRB(20, top + 14, 20, 22),
      decoration: BoxDecoration(
        gradient: c.headerGradient,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(30)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '$_greeting${name.isEmpty ? '' : ', ${name.split(' ').first}'}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Color(0xDDFFFFFF), fontSize: 14.5),
                    ),
                    const Text(
                      'Витрина',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.8,
                      ),
                    ),
                  ],
                ),
              ),
              CircleButton(
                icon: Icons.notifications_none_rounded,
                background: const Color(0x2EFFFFFF),
                color: Colors.white,
                onTap: () => showSnack(context, 'Новых уведомлений нет'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Material(
            color: c.surface,
            borderRadius: BorderRadius.circular(16),
            elevation: 10,
            shadowColor: const Color(0x66280058),
            child: InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: () => buyerNav.openCatalog(focusSearch: true),
              child: SizedBox(
                height: 52,
                child: Row(
                  children: [
                    const SizedBox(width: 16),
                    Icon(Icons.search_rounded, color: c.muted),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Искать среди $productsCount товаров',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: c.muted, fontSize: 15.5),
                      ),
                    ),
                    Container(
                      width: 38,
                      height: 38,
                      margin: const EdgeInsets.only(right: 7),
                      decoration: BoxDecoration(color: c.accent, borderRadius: BorderRadius.circular(11)),
                      child: const Icon(Icons.tune_rounded, color: Colors.white, size: 20),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Плашка «Ваш заказ в пути» на главной.
class _ActiveOrderBanner extends StatelessWidget {
  const _ActiveOrderBanner({required this.order, required this.more});

  final Order order;
  final int more;

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    final shop = StoreScope.of(context).shopById(order.shopId);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: AppCard(
        padding: const EdgeInsets.all(14),
        onTap: () =>
            Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => OrderScreen(orderId: order.id))),
        child: Row(
          children: [
            Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                color: order.status.color.withValues(alpha: .14),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(order.status.icon, color: order.status.color),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Заказ №${order.id} · ${order.statusLabel}',
                    style: TextStyle(fontWeight: FontWeight.w800, color: c.text),
                  ),
                  Text(
                    '${shop?.name ?? ''}${more > 0 ? ' и ещё $more' : ''}',
                    style: TextStyle(fontSize: 13, color: c.muted),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right_rounded, color: c.muted),
          ],
        ),
      ),
    );
  }
}

class _Promo {
  const _Promo(this.kicker, this.title, this.button, this.image, this.colors, this.onTap);

  final String kicker;
  final String title;
  final String button;
  final String image;
  final List<Color> colors;
  final void Function(BuildContext) onTap;
}

final _promos = <_Promo>[
  _Promo('Чёрная пятница', '−30% на\nэлектронику', 'Успеть купить', 'headphones', const [
    Color(0xFF7B2FF7),
    Color(0xFFB620E0),
    Color(0xFFF107A3),
  ], (_) => buyerNav.openCatalog(category: 'electronics')),
  _Promo('Новинки сезона', 'Осенняя\nколлекция', 'Смотреть', 'coat', const [
    Color(0xFFFF6A3D),
    Color(0xFFFF3D7F),
  ], (_) => buyerNav.openCatalog(category: 'clothes')),
  _Promo('Промокод', 'VITRINA20 —\nскидка 20%', 'Скопировать', 'gift', const [Color(0xFF00A99D), Color(0xFF2F80ED)], (
    context,
  ) {
    Clipboard.setData(const ClipboardData(text: 'VITRINA20'));
    showSnack(context, 'Промокод VITRINA20 скопирован — введите его в корзине');
  }),
];

class _PromoCarousel extends StatefulWidget {
  const _PromoCarousel();

  @override
  State<_PromoCarousel> createState() => _PromoCarouselState();
}

class _PromoCarouselState extends State<_PromoCarousel> {
  final _controller = PageController();
  Timer? _timer;
  int _page = 0;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (!_controller.hasClients) return;
      _controller.animateToPage(
        (_page + 1) % _promos.length,
        duration: const Duration(milliseconds: 600),
        curve: Curves.easeOutCubic,
      );
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return Column(
      children: [
        const SizedBox(height: 18),
        SizedBox(
          height: 152,
          child: PageView.builder(
            controller: _controller,
            itemCount: _promos.length,
            onPageChanged: (i) => setState(() => _page = i),
            itemBuilder: (context, i) => Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: _PromoCard(promo: _promos[i]),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (var i = 0; i < _promos.length; i++)
              AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                margin: const EdgeInsets.symmetric(horizontal: 2.5),
                width: i == _page ? 18 : 6,
                height: 6,
                decoration: BoxDecoration(
                  color: i == _page ? c.accent : c.muted.withValues(alpha: .35),
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _PromoCard extends StatelessWidget {
  const _PromoCard({required this.promo});

  final _Promo promo;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(22),
      child: Material(
        child: Ink(
          decoration: BoxDecoration(gradient: LinearGradient(colors: promo.colors)),
          child: InkWell(
            onTap: () => promo.onTap(context),
            child: Stack(
              children: [
                Positioned(
                  right: -30,
                  top: -40,
                  child: Container(
                    width: 190,
                    height: 190,
                    decoration: const BoxDecoration(color: Color(0x24FFFFFF), shape: BoxShape.circle),
                  ),
                ),
                Positioned(
                  right: 6,
                  bottom: 6,
                  width: 116,
                  height: 116,
                  child: Transform.rotate(angle: -.12, child: AppImage(promo.image)),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 18, 120, 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        promo.kicker.toUpperCase(),
                        style: const TextStyle(
                          color: Color(0xD9FFFFFF),
                          fontSize: 11.5,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1.2,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Expanded(
                        child: Text(
                          promo.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 24,
                            height: 1.08,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.5,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(99)),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Flexible(
                              child: Text(
                                promo.button,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(color: promo.colors.first, fontWeight: FontWeight.w800, fontSize: 13),
                              ),
                            ),
                            const SizedBox(width: 4),
                            Icon(Icons.arrow_forward_rounded, size: 15, color: promo.colors.first),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CategoriesRow extends StatelessWidget {
  const _CategoriesRow();

  @override
  Widget build(BuildContext context) {
    final c = AppColors.of(context);
    return SizedBox(
      height: 96,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: kCategories.length,
        separatorBuilder: (_, _) => const SizedBox(width: 10),
        itemBuilder: (context, i) {
          final cat = kCategories[i];
          return InkWell(
            borderRadius: BorderRadius.circular(20),
            onTap: () => buyerNav.openCatalog(category: cat.id),
            child: SizedBox(
              width: 68,
              child: Column(
                children: [
                  Container(
                    width: 62,
                    height: 62,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: tintFor(context, cat.id).first,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    padding: const EdgeInsets.all(11),
                    child: AppImage(cat.image),
                  ),
                  const SizedBox(height: 7),
                  Text(
                    cat.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: c.text),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
