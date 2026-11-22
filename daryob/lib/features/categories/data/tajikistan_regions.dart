import '../../../shared/models/localized_text.dart';
import '../../../shared/models/region.dart';

/// Administrative units of Tajikistan.
///
/// Phase 1 ships the five first-level units and the main cities whose
/// placement is certain. The model supports districts and settlements
/// (RegionLevel.district / settlement); the complete national list should be
/// loaded from an official source (Agency on Statistics under the President
/// of the Republic of Tajikistan) rather than typed by hand.
abstract final class RegionIds {
  static const country = 'tj';
  static const dushanbe = 'dushanbe';
  static const rrp = 'rrp';
  static const sughd = 'sughd';
  static const khatlon = 'khatlon';
  static const gbao = 'gbao';
}

const List<Region> tajikistanRegions = [
  Region(
    id: RegionIds.country,
    level: RegionLevel.country,
    name: LocalizedText(ru: 'Весь Таджикистан', tg: 'Тамоми Тоҷикистон'),
  ),

  // ── First level ──────────────────────────────────────────────────────────
  Region(
    id: RegionIds.dushanbe,
    parentId: RegionIds.country,
    level: RegionLevel.region,
    isRegionalCenter: true,
    name: LocalizedText(ru: 'Душанбе', tg: 'Душанбе'),
  ),
  Region(
    id: RegionIds.rrp,
    parentId: RegionIds.country,
    level: RegionLevel.region,
    name: LocalizedText(
      ru: 'Районы республиканского подчинения',
      tg: 'Ноҳияҳои тобеи ҷумҳурӣ',
    ),
  ),
  Region(
    id: RegionIds.sughd,
    parentId: RegionIds.country,
    level: RegionLevel.region,
    name: LocalizedText(ru: 'Согдийская область', tg: 'Вилояти Суғд'),
  ),
  Region(
    id: RegionIds.khatlon,
    parentId: RegionIds.country,
    level: RegionLevel.region,
    name: LocalizedText(ru: 'Хатлонская область', tg: 'Вилояти Хатлон'),
  ),
  Region(
    id: RegionIds.gbao,
    parentId: RegionIds.country,
    level: RegionLevel.region,
    name: LocalizedText(ru: 'ГБАО', tg: 'ВМКБ'),
  ),

  // ── Dushanbe: city districts ─────────────────────────────────────────────
  Region(
    id: 'dushanbe-sino',
    parentId: RegionIds.dushanbe,
    level: RegionLevel.district,
    name: LocalizedText(ru: 'район Сино', tg: 'ноҳияи Сино'),
  ),
  Region(
    id: 'dushanbe-firdavsi',
    parentId: RegionIds.dushanbe,
    level: RegionLevel.district,
    name: LocalizedText(ru: 'район Фирдавси', tg: 'ноҳияи Фирдавсӣ'),
  ),
  Region(
    id: 'dushanbe-somoni',
    parentId: RegionIds.dushanbe,
    level: RegionLevel.district,
    name: LocalizedText(
      ru: 'район Исмоили Сомони',
      tg: 'ноҳияи Исмоили Сомонӣ',
    ),
  ),
  Region(
    id: 'dushanbe-shohmansur',
    parentId: RegionIds.dushanbe,
    level: RegionLevel.district,
    name: LocalizedText(ru: 'район Шохмансур', tg: 'ноҳияи Шоҳмансур'),
  ),

  // ── Districts of Republican Subordination: cities ────────────────────────
  Region(
    id: 'vahdat',
    parentId: RegionIds.rrp,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Вахдат', tg: 'Ваҳдат'),
  ),
  Region(
    id: 'tursunzoda',
    parentId: RegionIds.rrp,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Турсунзаде', tg: 'Турсунзода'),
  ),
  Region(
    id: 'hisor',
    parentId: RegionIds.rrp,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Гиссар', tg: 'Ҳисор'),
  ),
  Region(
    id: 'roghun',
    parentId: RegionIds.rrp,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Рогун', tg: 'Роғун'),
  ),

  // ── Sughd ────────────────────────────────────────────────────────────────
  Region(
    id: 'khujand',
    parentId: RegionIds.sughd,
    level: RegionLevel.city,
    isRegionalCenter: true,
    name: LocalizedText(ru: 'Худжанд', tg: 'Хуҷанд'),
  ),
  Region(
    id: 'istaravshan',
    parentId: RegionIds.sughd,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Истаравшан', tg: 'Истаравшан'),
  ),
  Region(
    id: 'isfara',
    parentId: RegionIds.sughd,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Исфара', tg: 'Исфара'),
  ),
  Region(
    id: 'konibodom',
    parentId: RegionIds.sughd,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Канибадам', tg: 'Конибодом'),
  ),
  Region(
    id: 'panjakent',
    parentId: RegionIds.sughd,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Пенджикент', tg: 'Панҷакент'),
  ),
  Region(
    id: 'buston',
    parentId: RegionIds.sughd,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Бустон', tg: 'Бӯстон'),
  ),
  Region(
    id: 'guliston',
    parentId: RegionIds.sughd,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Гулистон', tg: 'Гулистон'),
  ),

  // ── Khatlon ──────────────────────────────────────────────────────────────
  Region(
    id: 'bokhtar',
    parentId: RegionIds.khatlon,
    level: RegionLevel.city,
    isRegionalCenter: true,
    name: LocalizedText(ru: 'Бохтар', tg: 'Бохтар'),
  ),
  Region(
    id: 'kulob',
    parentId: RegionIds.khatlon,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Куляб', tg: 'Кӯлоб'),
  ),
  Region(
    id: 'norak',
    parentId: RegionIds.khatlon,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Нурек', tg: 'Норак'),
  ),
  Region(
    id: 'levakant',
    parentId: RegionIds.khatlon,
    level: RegionLevel.city,
    name: LocalizedText(ru: 'Левакант', tg: 'Левакант'),
  ),

  // ── GBAO ─────────────────────────────────────────────────────────────────
  Region(
    id: 'khorugh',
    parentId: RegionIds.gbao,
    level: RegionLevel.city,
    isRegionalCenter: true,
    name: LocalizedText(ru: 'Хорог', tg: 'Хоруғ'),
  ),
];
