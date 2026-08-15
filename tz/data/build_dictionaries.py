#!/usr/bin/env python3
"""
Сборка справочников брендов и моделей.

Источник компактный, на выходе — готовые JSON для загрузки в базу.
Порядок внутри каждой области отражает распространённость на рынке
Таджикистана: самые частые бренды идут первыми.
"""

import json
from pathlib import Path

OUT = Path(__file__).parent

# Области применения. Схема категории указывает, из какой брать список.
AREAS = {
    "cars": "Автомобили",
    "phones": "Телефоны и планшеты",
    "computers": "Компьютеры и ноутбуки",
    "components": "Комплектующие",
    "appliances": "Бытовая техника",
    "tv_audio": "Телевизоры и аудио",
    "tools": "Инструмент и садовая техника",
    "moto_bike": "Мото и велотехника",
    "electronics": "Прочая электроника",
}

# ─────────────────────────────────────────────────────────────
# Бренды по областям. Первые в списке — самые распространённые.
# ─────────────────────────────────────────────────────────────

BRANDS: dict[str, list[str]] = {
    "cars": [
        "Toyota", "Opel", "Mercedes-Benz", "Lada (ВАЗ)", "Chevrolet", "Daewoo",
        "Hyundai", "Kia", "BMW", "Volkswagen", "Nissan", "Honda", "Mitsubishi",
        "Audi", "Ford", "Mazda", "Subaru", "Lexus", "Suzuki", "Renault",
        "Škoda", "Peugeot", "Daihatsu", "Chery", "Haval", "BYD", "Geely",
        "Changan", "JAC", "Exeed", "Jetour", "Omoda", "Lifan", "Great Wall",
        "Dongfeng", "FAW", "ГАЗ", "УАЗ", "Москвич", "ЗАЗ", "Isuzu",
        "Land Rover", "Volvo", "Porsche", "Jaguar", "Mini", "Infiniti",
        "SsangYong", "Fiat", "Citroën", "Tesla", "Genesis", "Acura",
        "Ravon", "Seat", "Cadillac", "Jeep", "Dodge", "Zeekr", "Li Auto",
    ],
    "phones": [
        "Samsung", "Apple", "Xiaomi", "Redmi", "POCO", "Infinix", "Tecno",
        "itel", "Realme", "Huawei", "Honor", "OPPO", "vivo", "Nokia",
        "Motorola", "OnePlus", "Google Pixel", "ZTE", "Nubia", "Meizu",
        "Asus", "Sony", "LG", "HTC", "Lenovo", "Alcatel", "TCL", "Nothing",
        "Blackview", "Doogee", "Ulefone", "Oukitel", "Sharp", "Micromax",
    ],
    "computers": [
        "HP", "Lenovo", "Dell", "Asus", "Acer", "Apple", "MSI", "Samsung",
        "Huawei", "Honor", "Xiaomi", "Toshiba", "Sony", "Fujitsu", "LG",
        "Microsoft", "Gigabyte", "Razer", "Chuwi", "Digma", "Packard Bell",
    ],
    "components": [
        "Intel", "AMD", "NVIDIA", "Kingston", "Samsung", "Western Digital",
        "Seagate", "Crucial", "ADATA", "Corsair", "G.Skill", "Patriot",
        "Transcend", "Netac", "Gigabyte", "MSI", "ASRock", "Asus", "Zotac",
        "Palit", "Deepcool", "Cooler Master", "Thermaltake", "be quiet!",
        "Noctua", "Arctic", "Hikvision", "Toshiba", "SanDisk",
    ],
    "appliances": [
        "Samsung", "LG", "Artel", "Bosch", "Beko", "Indesit", "Ariston",
        "Midea", "Haier", "Hisense", "Siemens", "Whirlpool", "Electrolux",
        "Zanussi", "Candy", "Gorenje", "Vestel", "Panasonic", "Philips",
        "Shivaki", "Avalon", "Roison", "Атлант", "Бирюса", "Норд",
        "Redmond", "Polaris", "Scarlett", "Vitek", "Tefal", "Moulinex",
        "Braun", "Dyson", "Xiaomi", "Ergo", "Premier",
    ],
    "tv_audio": [
        "Samsung", "LG", "Artel", "TCL", "Hisense", "Xiaomi", "Sony",
        "Philips", "Panasonic", "Haier", "Toshiba", "Sharp", "Skyworth",
        "Vestel", "Shivaki", "Yasin", "Roison", "Premier", "Avalon", "Ergo",
        "JVC", "Grundig", "JBL", "Bose", "Marshall", "Harman Kardon",
        "Sven", "Edifier", "Yamaha", "Pioneer", "Kenwood", "Denon", "Sonos",
    ],
    "tools": [
        "Bosch", "Makita", "DeWalt", "Total", "Ingco", "Metabo", "HiKOKI",
        "Milwaukee", "Ryobi", "Black+Decker", "Stanley", "Einhell",
        "Интерскол", "Зубр", "Вихрь", "Калибр", "Ресанта", "Sturm",
        "Elitech", "Deko", "Wortex", "Кратон", "Энкор", "Фиолент",
        "Stihl", "Husqvarna", "Champion", "Patriot", "Carver", "Huter",
    ],
    "moto_bike": [
        "Honda", "Yamaha", "Suzuki", "Kawasaki", "Lifan", "Zongshen",
        "Loncin", "Bajaj", "TVS", "Hero", "Racer", "Regulmoto", "Motoland",
        "CFMoto", "Voge", "Benelli", "KTM", "BMW Motorrad", "Ducati",
        "Harley-Davidson", "Минск", "Урал", "ИЖ", "Stels", "Forward",
        "Stern", "Merida", "Trek", "Giant", "Author", "Cube", "Scott",
        "Specialized", "Cannondale", "Format", "Altair", "Десна", "Аист",
    ],
    "electronics": [
        "Apple", "Samsung", "Xiaomi", "Huawei", "Honor", "JBL", "Anker",
        "Baseus", "Hoco", "Borofone", "Remax", "Ugreen", "Amazfit",
        "Garmin", "Fitbit", "Sony", "DJI", "GoPro", "Insta360", "Canon",
        "Nikon", "Fujifilm", "Panasonic", "Nintendo", "PlayStation",
        "Xbox", "Valve", "Logitech", "Razer", "HyperX", "SteelSeries",
        "A4Tech", "Defender", "Sven", "Genius",
    ],
}

# ─────────────────────────────────────────────────────────────
# Модели автомобилей
# ─────────────────────────────────────────────────────────────

CAR_MODELS: dict[str, list[str]] = {
    "Toyota": [
        "Camry", "Corolla", "Yaris", "Avalon", "Crown", "Mark II", "Vitz",
        "Premio", "Allion", "Avensis", "RAV4", "C-HR", "Venza", "Highlander",
        "Land Cruiser 100", "Land Cruiser 200", "Land Cruiser 300",
        "Land Cruiser Prado", "4Runner", "Sequoia", "Fortuner", "Hilux",
        "Sienna", "Alphard", "Vellfire", "Estima", "Ipsum", "Carina",
    ],
    "Opel": [
        "Astra", "Vectra", "Corsa", "Omega", "Zafira", "Insignia", "Meriva",
        "Antara", "Mokka", "Combo", "Frontera", "Kadett", "Vita", "Signum",
    ],
    "Mercedes-Benz": [
        "A-Class", "B-Class", "C-Class", "E-Class", "S-Class", "CLA", "CLS",
        "GLA", "GLB", "GLC", "GLE", "GLS", "ML", "GL", "G-Class", "V-Class",
        "Vito", "Sprinter", "190 (W201)", "124 (W124)",
    ],
    "Lada (ВАЗ)": [
        "2101", "2102", "2103", "2104", "2105", "2106", "2107", "2108",
        "2109", "21099", "2110", "2111", "2112", "2113", "2114", "2115",
        "Niva", "Niva Travel", "Granta", "Vesta", "Kalina", "Priora",
        "Largus", "XRAY",
    ],
    "Chevrolet": [
        "Spark", "Matiz", "Nexia", "Nexia 3", "Cobalt", "Lacetti", "Gentra",
        "Aveo", "Malibu", "Epica", "Captiva", "Tracker", "Onix", "Equinox",
        "Traverse", "Tahoe", "Trailblazer", "Orlando", "Damas", "Labo",
    ],
    "Daewoo": [
        "Matiz", "Tico", "Nexia", "Damas", "Labo", "Lacetti", "Gentra",
        "Espero", "Leganza", "Magnus", "Nubira",
    ],
    "Hyundai": [
        "Accent", "Solaris", "Elantra", "Sonata", "Grandeur", "Getz", "i30",
        "i40", "Tucson", "Santa Fe", "Creta", "Palisade", "Kona", "Venue",
        "Starex", "Staria", "Porter", "Avante", "Verna",
    ],
    "Kia": [
        "Rio", "Picanto", "Cerato", "Optima", "K5", "Soul", "Sportage",
        "Sorento", "Seltos", "Carnival", "Mohave", "Telluride", "Stinger",
        "Cee'd", "Spectra", "Morning",
    ],
    "BMW": [
        "1 Series", "2 Series", "3 Series", "4 Series", "5 Series",
        "6 Series", "7 Series", "8 Series", "X1", "X2", "X3", "X4", "X5",
        "X6", "X7", "Z4", "M3", "M5", "i3", "i4", "iX", "E34", "E39",
    ],
    "Volkswagen": [
        "Golf", "Passat", "Polo", "Jetta", "Tiguan", "Touareg", "Touran",
        "Sharan", "Caddy", "Transporter", "Bora", "Vento", "Amarok", "Teramont",
    ],
    "Nissan": [
        "Almera", "Sunny", "Note", "Tiida", "Sentra", "Teana", "Altima",
        "Maxima", "Juke", "Qashqai", "X-Trail", "Murano", "Pathfinder",
        "Patrol", "Leaf", "Primera", "Bluebird",
    ],
    "Honda": [
        "Civic", "Accord", "CR-V", "HR-V", "Pilot", "Fit", "Jazz", "Odyssey",
        "Stepwgn", "Insight", "Legend", "Element",
    ],
    "Mitsubishi": [
        "Lancer", "Galant", "Outlander", "Pajero", "Pajero Sport", "ASX",
        "Montero", "Colt", "Space Wagon", "L200", "Eclipse Cross", "Delica",
    ],
    "Audi": [
        "A3", "A4", "A5", "A6", "A7", "A8", "Q3", "Q5", "Q7", "Q8",
        "TT", "80", "100", "e-tron",
    ],
    "Ford": [
        "Focus", "Mondeo", "Fiesta", "Fusion", "Escape", "Explorer", "Kuga",
        "Transit", "Ranger", "Edge", "Escort", "Sierra",
    ],
    "Mazda": [
        "Mazda 3", "Mazda 6", "Mazda 2", "CX-3", "CX-5", "CX-7", "CX-9",
        "Demio", "Axela", "Atenza", "MPV", "323", "626",
    ],
    "Subaru": [
        "Impreza", "Legacy", "Forester", "Outback", "XV", "Tribeca",
        "WRX", "BRZ", "Levorg",
    ],
    "Lexus": [
        "ES", "IS", "GS", "LS", "NX", "RX", "GX", "LX", "UX", "RC", "CT",
    ],
    "Suzuki": [
        "Swift", "Vitara", "Grand Vitara", "SX4", "Jimny", "Alto", "Baleno",
        "Wagon R", "Escudo",
    ],
    "Renault": [
        "Logan", "Sandero", "Duster", "Megane", "Clio", "Symbol", "Fluence",
        "Kaptur", "Laguna", "Scenic", "Kangoo",
    ],
    "Škoda": [
        "Octavia", "Rapid", "Fabia", "Superb", "Kodiaq", "Karoq", "Yeti", "Felicia",
    ],
    "Peugeot": ["206", "207", "301", "307", "308", "406", "407", "508", "3008", "Partner"],
    "Chery": ["Tiggo 2", "Tiggo 3", "Tiggo 4", "Tiggo 7 Pro", "Tiggo 8 Pro",
              "Arrizo 5", "Arrizo 6", "Arrizo 8", "QQ", "Amulet"],
    "Haval": ["Jolion", "F7", "F7x", "H6", "H9", "Dargo", "M6"],
    "BYD": ["Song Plus", "Han", "Qin Plus", "Tang", "Seal", "Atto 3", "Dolphin", "Seagull", "F3"],
    "Geely": ["Coolray", "Atlas", "Atlas Pro", "Emgrand", "Tugella", "Monjaro", "Okavango", "MK"],
    "Changan": ["CS35 Plus", "CS55 Plus", "CS75 Plus", "CS85", "Eado", "UNI-K", "UNI-T", "Alsvin"],
    "ГАЗ": ["Волга 24", "Волга 3110", "Волга 31105", "Газель", "Газель Next", "Соболь", "66", "53"],
    "УАЗ": ["469", "Хантер", "Патриот", "Буханка", "Пикап", "Профи"],
    "Москвич": ["412", "2140", "2141", "Святогор", "3"],
    "Daihatsu": ["Terios", "Mira", "Move", "Charade", "Sirion"],
    "Isuzu": ["Trooper", "Bighorn", "D-Max", "NPR", "Elf"],
    "Ravon": ["R2", "R3 Nexia", "R4", "Gentra", "Matiz", "Nexia 3"],
    "Volvo": ["S40", "S60", "S80", "XC60", "XC70", "XC90", "V40", "940"],
    "Land Rover": ["Range Rover", "Range Rover Sport", "Range Rover Evoque",
                   "Discovery", "Defender", "Freelander"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y"],
    "Fiat": ["Albea", "Punto", "Doblo", "Ducato", "Tipo"],
    "Citroën": ["C3", "C4", "C5", "Berlingo", "Jumper"],
    "Mini": ["Cooper", "Countryman", "Clubman"],
    "Porsche": ["Cayenne", "Macan", "Panamera", "911", "Taycan"],
    "Jaguar": ["XF", "XE", "XJ", "F-Pace"],
    "Infiniti": ["FX35", "QX56", "QX60", "QX80", "G25", "M37"],
    "SsangYong": ["Rexton", "Actyon", "Kyron", "Musso", "Korando"],
    "Genesis": ["G70", "G80", "G90", "GV70", "GV80"],
    "Acura": ["MDX", "RDX", "TL", "TSX", "ZDX"],
    "JAC": ["S3", "S5", "S7", "T6", "J7"],
    "Exeed": ["TXL", "VX", "LX", "RX"],
    "Jetour": ["X70", "X90", "Dashing", "T2"],
    "Omoda": ["C5", "S5", "C7"],
    "Lifan": ["X60", "X50", "Solano", "Smily", "Breez"],
    "Great Wall": ["Hover", "Wingle", "Poer", "Deer"],
    "Dongfeng": ["AX7", "S30", "H30", "580"],
    "FAW": ["Besturn X80", "V5", "Vita", "Oley"],
    "ЗАЗ": ["968", "1102 Таврия", "Sens", "Chance", "Vida"],
    "Seat": ["Ibiza", "Leon", "Toledo", "Ateca"],
    "Cadillac": ["Escalade", "SRX", "CTS", "XT5"],
    "Jeep": ["Grand Cherokee", "Cherokee", "Wrangler", "Compass"],
    "Dodge": ["Caravan", "Journey", "Charger", "Durango"],
    "Zeekr": ["001", "007", "X", "009"],
    "Li Auto": ["L7", "L8", "L9"],
}


def build() -> None:
    brands = []
    brand_index: dict[str, dict] = {}

    for area, names in BRANDS.items():
        for order, name in enumerate(names):
            if name in brand_index:
                # Один бренд может работать в нескольких областях:
                # Samsung — телефоны, телевизоры и бытовая техника.
                # Заводим одну запись с несколькими областями.
                brand_index[name]["areas"].append(area)
            else:
                entry = {
                    "name": name,
                    "areas": [area],
                    "popular": order < 10,
                    "sort_order": order,
                }
                brand_index[name] = entry
                brands.append(entry)

    models = []
    for brand, names in CAR_MODELS.items():
        for order, name in enumerate(names):
            models.append({
                "brand": brand,
                "name": name,
                "area": "cars",
                "sort_order": order,
            })

    brands_doc = {
        "meta": {
            "description": "Справочник брендов по областям применения",
            "region": "Таджикистан",
            "note": "Порядок отражает распространённость на рынке. "
                    "Список редактируется администратором без обновления системы.",
            "areas": AREAS,
            "total_brands": len(brands),
        },
        "brands": brands,
    }

    models_doc = {
        "meta": {
            "description": "Модели автомобилей",
            "region": "Таджикистан",
            "total_models": len(models),
            "brands_covered": len(CAR_MODELS),
        },
        "models": models,
    }

    (OUT / "brands.json").write_text(
        json.dumps(brands_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "car_models.json").write_text(
        json.dumps(models_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    multi = [b["name"] for b in brands if len(b["areas"]) > 1]

    print(f"brands.json      — {len(brands)} брендов в {len(AREAS)} областях")
    print(f"car_models.json  — {len(models)} моделей у {len(CAR_MODELS)} марок")
    print(f"\nБрендов в нескольких областях: {len(multi)}")
    print("  " + ", ".join(sorted(multi)[:12]) + " …")


if __name__ == "__main__":
    build()
