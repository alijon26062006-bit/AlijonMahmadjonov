import 'dart:async';

import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../data.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final hits = kProducts.where((p) => p.hit).toList();
    final recommended = [...kProducts]..sort((a, b) => b.rating.compareTo(a.rating));
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: CustomScrollView(
        slivers: [
          const SliverToBoxAdapter(child: _Header()),
          const SliverToBoxAdapter(child: _PromoCarousel()),
          SliverToBoxAdapter(
            child: SectionHeader('Категории', action: 'Все', onAction: () => appNav.openCatalog()),
          ),
          const SliverToBoxAdapter(child: _CategoriesRow()),
          SliverToBoxAdapter(
            child: SectionHeader('Хиты продаж 🔥', action: 'Смотреть все', onAction: () => appNav.openCatalog()),
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
  const _Header();

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
    final name = ShopScope.of(context).name;
    return Container(
      padding: EdgeInsets.fromLTRB(20, top + 14, 20, 22),
      decoration: const BoxDecoration(
        gradient: kHeaderGradient,
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(30)),
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
                      '$_greeting${name.isEmpty ? '' : ', ${name.split(' ').first}'} 👋',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Color(0xDDFFFFFF), fontSize: 14.5),
                    ),
                    const Text(
                      'Витрина',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.w900,
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
              onTap: () => appNav.openCatalog(focusSearch: true),
              child: SizedBox(
                height: 52,
                child: Row(
                  children: [
                    const SizedBox(width: 16),
                    Icon(Icons.search_rounded, color: c.muted),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Искать среди ${kProducts.length} товаров',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: c.muted, fontSize: 15.5),
                      ),
                    ),
                    Container(
                      width: 38,
                      height: 38,
                      margin: const EdgeInsets.only(right: 7),
                      decoration: BoxDecoration(color: kViolet, borderRadius: BorderRadius.circular(11)),
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

class _Promo {
  const _Promo(this.kicker, this.title, this.button, this.emoji, this.colors, this.onTap);

  final String kicker;
  final String title;
  final String button;
  final String emoji;
  final List<Color> colors;
  final void Function(BuildContext) onTap;
}

final _promos = <_Promo>[
  _Promo('Чёрная пятница', '−50% на\nэлектронику', 'Успеть купить', '🎧', const [
    kViolet,
    Color(0xFFB620E0),
    kPink,
  ], (_) => appNav.openCatalog(category: 'electronics')),
  _Promo('Новинки сезона', 'Осенняя\nколлекция', 'Смотреть', '🧥', const [
    Color(0xFFFF6A3D),
    Color(0xFFFF3D7F),
  ], (_) => appNav.openCatalog(category: 'clothes')),
  _Promo('Промокод', 'VITRINA20 —\nскидка 20%', 'Скопировать', '🎁', const [Color(0xFF00A99D), Color(0xFF2F80ED)], (
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
                  color: i == _page ? kViolet : c.muted.withValues(alpha: .35),
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
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: promo.colors, begin: Alignment.centerLeft, end: Alignment.centerRight),
          ),
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
                  right: 10,
                  bottom: 4,
                  child: Transform.rotate(
                    angle: -.17,
                    child: Text(
                      promo.emoji,
                      style: const TextStyle(
                        fontSize: 88,
                        shadows: [Shadow(color: Color(0x40000000), blurRadius: 18, offset: Offset(0, 12))],
                      ),
                    ),
                  ),
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
                            fontWeight: FontWeight.w900,
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
          return _CategoryTile(category: cat, colors: c);
        },
      ),
    );
  }
}

class _CategoryTile extends StatelessWidget {
  const _CategoryTile({required this.category, required this.colors});

  final Category category;
  final AppColors colors;

  @override
  Widget build(BuildContext context) {
    final bg = colors.dark ? Color.lerp(category.tint.first, colors.surface, .74)! : category.tint.first;
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: () => appNav.openCatalog(category: category.id),
      child: SizedBox(
        width: 68,
        child: Column(
          children: [
            Container(
              width: 62,
              height: 62,
              alignment: Alignment.center,
              decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
              child: Text(category.emoji, style: const TextStyle(fontSize: 29)),
            ),
            const SizedBox(height: 7),
            Text(
              category.name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: colors.text),
            ),
          ],
        ),
      ),
    );
  }
}
