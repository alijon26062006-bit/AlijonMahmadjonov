"""Первичное наполнение базы — меню с бумажного прайса заведения.
После запуска админка правит базу, а этот файл нужен только один раз."""

SECTIONS = [
    {
        "id": "lunch",
        "title": "Бизнес ланч",
        "note": "Суп, основное блюдо и кола",
        "layout": "cards"
    },
    {
        "id": "burgers",
        "title": "Бургеры",
        "note": "Готовим после заказа",
        "layout": "cards"
    },
    {
        "id": "pizza",
        "title": "Пицца",
        "note": "Два размера: 28 и 35 см",
        "layout": "cards"
    },
    {
        "id": "shawarma",
        "title": "Шаурма и роллы",
        "note": "",
        "layout": "cards"
    },
    {
        "id": "hotdogs",
        "title": "Хот-доги",
        "note": "",
        "layout": "cards"
    },
    {
        "id": "hot",
        "title": "Горячие блюда",
        "note": "",
        "layout": "rows"
    },
    {
        "id": "pasta",
        "title": "Паста",
        "note": "",
        "layout": "rows"
    },
    {
        "id": "sandwiches",
        "title": "Сэндвичи",
        "note": "",
        "layout": "rows"
    },
    {
        "id": "salads",
        "title": "Салаты",
        "note": "",
        "layout": "rows"
    },
    {
        "id": "soups",
        "title": "Супы",
        "note": "Крем-супы",
        "layout": "rows"
    },
    {
        "id": "breakfast",
        "title": "Завтраки",
        "note": "Питательное и сладкое утро",
        "layout": "rows"
    },
    {
        "id": "desserts",
        "title": "Десерты",
        "note": "",
        "layout": "rows"
    },
    {
        "id": "coffee",
        "title": "Кофе и чай",
        "note": "",
        "layout": "rows"
    },
    {
        "id": "cold",
        "title": "Мохито и фреш",
        "note": "",
        "layout": "rows"
    }
]

DISHES = [
    {
        "id": "lunch-wok",
        "section": "lunch",
        "name": "Ланч с воком",
        "about": "Суп, вок с курицей, 1 кола",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 75,
        "parts": []
    },
    {
        "id": "lunch-shawarma",
        "section": "lunch",
        "name": "Ланч с шаурмой",
        "about": "Суп, шаурма, фри, 1 кола",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 80,
        "parts": []
    },
    {
        "id": "lunch-sandwich",
        "section": "lunch",
        "name": "Ланч с сэндвичем",
        "about": "Суп, сэндвич с курицей, фри, 1 кола",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 87,
        "parts": []
    },
    {
        "id": "lunch-pasta",
        "section": "lunch",
        "name": "Ланч с пастой",
        "about": "Суп, паста фетучини, 1 кола",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 87,
        "parts": []
    },
    {
        "id": "lunch-french",
        "section": "lunch",
        "name": "Ланч с курицей",
        "about": "Суп, курица по-французски, 1 кола",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 90,
        "parts": []
    },
    {
        "id": "lunch-cheeseburger",
        "section": "lunch",
        "name": "Ланч с чизбургером",
        "about": "Суп, чизбургер, фри, 1 кола",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 100,
        "parts": []
    },
    {
        "id": "lunch-pizza",
        "section": "lunch",
        "name": "Ланч с пиццей",
        "about": "Суп, маленькая пицца, фри, 1 кола",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 100,
        "parts": []
    },
    {
        "id": "hamburger",
        "section": "burgers",
        "name": "Гамбургер",
        "about": "Hamburger",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 47,
        "parts": []
    },
    {
        "id": "the-burger",
        "section": "burgers",
        "name": "Зе бургер",
        "about": "The burger",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 60,
        "parts": []
    },
    {
        "id": "cheeseburger",
        "section": "burgers",
        "name": "Чизбургер",
        "about": "Cheeseburger",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 50,
        "parts": []
    },
    {
        "id": "mushroom-burger",
        "section": "burgers",
        "name": "Грибной бургер",
        "about": "Mushroom burger",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 54,
        "parts": []
    },
    {
        "id": "pizza-caesar-28",
        "section": "pizza",
        "name": "Пицца Цезарь 28 см",
        "about": "Caesar pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 57,
        "parts": []
    },
    {
        "id": "pizza-caesar-35",
        "section": "pizza",
        "name": "Пицца Цезарь 35 см",
        "about": "Caesar pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 77,
        "parts": []
    },
    {
        "id": "pizza-the-28",
        "section": "pizza",
        "name": "Зе пицца 28 см",
        "about": "The pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 57,
        "parts": []
    },
    {
        "id": "pizza-the-35",
        "section": "pizza",
        "name": "Зе пицца 35 см",
        "about": "The pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 79,
        "parts": []
    },
    {
        "id": "pizza-pepperoni-28",
        "section": "pizza",
        "name": "Пицца Пепперони 28 см",
        "about": "Pepperoni pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 59,
        "parts": []
    },
    {
        "id": "pizza-pepperoni-35",
        "section": "pizza",
        "name": "Пицца Пепперони 35 см",
        "about": "Pepperoni pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 78,
        "parts": []
    },
    {
        "id": "pizza-4cheese-28",
        "section": "pizza",
        "name": "Пицца 4 сыра 28 см",
        "about": "4 cheese pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 60,
        "parts": []
    },
    {
        "id": "pizza-4cheese-35",
        "section": "pizza",
        "name": "Пицца 4 сыра 35 см",
        "about": "4 cheese pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 80,
        "parts": []
    },
    {
        "id": "pizza-4kinds-28",
        "section": "pizza",
        "name": "4 вида пиццы 28 см",
        "about": "4 types of pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 70,
        "parts": []
    },
    {
        "id": "pizza-4kinds-35",
        "section": "pizza",
        "name": "4 вида пиццы 35 см",
        "about": "4 types of pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 90,
        "parts": []
    },
    {
        "id": "pizza-veg-28",
        "section": "pizza",
        "name": "Вегетарианская 28 см",
        "about": "Vegetarian pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 55,
        "parts": []
    },
    {
        "id": "pizza-veg-35",
        "section": "pizza",
        "name": "Вегетарианская 35 см",
        "about": "Vegetarian pizza",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 75,
        "parts": []
    },
    {
        "id": "pizza-own-28",
        "section": "pizza",
        "name": "Пицца на ваш вкус 28 см",
        "about": "Pizza to your taste",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 78,
        "parts": []
    },
    {
        "id": "pizza-own-35",
        "section": "pizza",
        "name": "Пицца на ваш вкус 35 см",
        "about": "Pizza to your taste",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 110,
        "parts": []
    },
    {
        "id": "shawarma-chicken",
        "section": "shawarma",
        "name": "Куриная шаурма",
        "about": "Chicken shawarma",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 39,
        "parts": []
    },
    {
        "id": "shawarma-cheese",
        "section": "shawarma",
        "name": "Сырная шаурма",
        "about": "Cheese shawarma",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 50,
        "parts": []
    },
    {
        "id": "roll-veg",
        "section": "shawarma",
        "name": "Овощной ролл",
        "about": "Vegetable roll",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 35,
        "parts": []
    },
    {
        "id": "hotdog-american",
        "section": "hotdogs",
        "name": "Американский хот-дог",
        "about": "American hot dog",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 20,
        "parts": []
    },
    {
        "id": "hotdog-nachos",
        "section": "hotdogs",
        "name": "Начос хот-дог",
        "about": "Nachos hot dog",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 16,
        "parts": []
    },
    {
        "id": "hotdog-classic",
        "section": "hotdogs",
        "name": "Классический хот-дог",
        "about": "Classic hot dog",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 14,
        "parts": []
    },
    {
        "id": "hotdog-chicken",
        "section": "hotdogs",
        "name": "Куриный хот-дог",
        "about": "Chicken hot dog",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 20,
        "parts": []
    },
    {
        "id": "wok-chicken",
        "section": "hot",
        "name": "Вок с курицей",
        "about": "Wok with chicken",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 48,
        "parts": []
    },
    {
        "id": "wok-beef",
        "section": "hot",
        "name": "Вок с говядиной",
        "about": "Wok with beef",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 60,
        "parts": []
    },
    {
        "id": "chicken-rice",
        "section": "hot",
        "name": "Курица с рисом",
        "about": "Chicken with rice",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 37,
        "parts": []
    },
    {
        "id": "chicken-veg",
        "section": "hot",
        "name": "Курица с овощами",
        "about": "Chicken with vegetables",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 32,
        "parts": []
    },
    {
        "id": "chicken-cutlet",
        "section": "hot",
        "name": "Котлета из курицы",
        "about": "Chicken cutlet",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 45,
        "parts": []
    },
    {
        "id": "chicken-steak",
        "section": "hot",
        "name": "Куриный стейк с рисом и греческим салатом",
        "about": "Chicken steak with rice and Greek salad",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 80,
        "parts": []
    },
    {
        "id": "chicken-potato",
        "section": "hot",
        "name": "Цыплёнок с картофелем",
        "about": "Chicken with potatoes",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 58,
        "parts": []
    },
    {
        "id": "beefsteak-puree",
        "section": "hot",
        "name": "Бифштекс с картошкой пюре",
        "about": "Beefsteak with mashed potatoes",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 68,
        "parts": []
    },
    {
        "id": "fried-rice",
        "section": "hot",
        "name": "Жареный рис с курицей",
        "about": "Fried rice with chicken",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 40,
        "parts": []
    },
    {
        "id": "chicken-thai",
        "section": "hot",
        "name": "Курица по-тайски",
        "about": "Thai-style chicken",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 48,
        "parts": []
    },
    {
        "id": "veal-cutlets",
        "section": "hot",
        "name": "Домашние котлеты из телятины",
        "about": "Homemade veal cutlets",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 51,
        "parts": []
    },
    {
        "id": "chicken-french",
        "section": "hot",
        "name": "Курица по-французски",
        "about": "French-style chicken",
        "weight": 0,
        "kcal": 0,
        "cook": "15–25 мин",
        "price": 65,
        "parts": []
    },
    {
        "id": "pasta-alfredo",
        "section": "pasta",
        "name": "Паста Альфредо",
        "about": "Alfredo pasta",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 59,
        "parts": []
    },
    {
        "id": "pasta-bolognese",
        "section": "pasta",
        "name": "Паста Болоньезе",
        "about": "Bolognese pasta",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 67,
        "parts": []
    },
    {
        "id": "pasta-fettuccine",
        "section": "pasta",
        "name": "Паста Фетучини",
        "about": "Fettuccine pasta",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 59,
        "parts": []
    },
    {
        "id": "club-sandwich",
        "section": "sandwiches",
        "name": "Клаб сэндвич с курицей",
        "about": "Chicken club sandwich",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 46,
        "parts": []
    },
    {
        "id": "sandwich-beef",
        "section": "sandwiches",
        "name": "Сэндвич с говядиной",
        "about": "Beef sandwich",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 49,
        "parts": []
    },
    {
        "id": "sandwich-cheese",
        "section": "sandwiches",
        "name": "Сэндвич с сыром",
        "about": "Cheese sandwich",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 40,
        "parts": []
    },
    {
        "id": "salad-greek",
        "section": "salads",
        "name": "Салат греческий",
        "about": "Greek salad",
        "weight": 0,
        "kcal": 0,
        "cook": "10–15 мин",
        "price": 32,
        "parts": []
    },
    {
        "id": "salad-caesar",
        "section": "salads",
        "name": "Салат Цезарь",
        "about": "Caesar salad",
        "weight": 0,
        "kcal": 0,
        "cook": "10–15 мин",
        "price": 40,
        "parts": []
    },
    {
        "id": "salad-eggplant",
        "section": "salads",
        "name": "Салат с хрустящими баклажанами",
        "about": "Salad with crispy eggplant",
        "weight": 0,
        "kcal": 0,
        "cook": "10–15 мин",
        "price": 44,
        "parts": []
    },
    {
        "id": "soup-cheese",
        "section": "soups",
        "name": "Крем-суп сырный",
        "about": "Cream of cheese soup",
        "weight": 0,
        "kcal": 0,
        "cook": "10–15 мин",
        "price": 32,
        "parts": []
    },
    {
        "id": "soup-mushroom",
        "section": "soups",
        "name": "Крем-суп грибной",
        "about": "Cream of mushroom soup",
        "weight": 0,
        "kcal": 0,
        "cook": "10–15 мин",
        "price": 29,
        "parts": []
    },
    {
        "id": "soup-corn",
        "section": "soups",
        "name": "Крем-суп кукурузный",
        "about": "Cream of corn soup",
        "weight": 0,
        "kcal": 0,
        "cook": "10–15 мин",
        "price": 31,
        "parts": []
    },
    {
        "id": "soup-lentil",
        "section": "soups",
        "name": "Крем-суп чечевичный",
        "about": "Cream of lentil soup",
        "weight": 0,
        "kcal": 0,
        "cook": "10–15 мин",
        "price": 29,
        "parts": []
    },
    {
        "id": "breakfast-bavarian",
        "section": "breakfast",
        "name": "Баварский завтрак",
        "about": "Bavarian breakfast",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 65,
        "parts": []
    },
    {
        "id": "breakfast-swiss",
        "section": "breakfast",
        "name": "Швейцарский завтрак",
        "about": "Swiss breakfast",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 63,
        "parts": []
    },
    {
        "id": "breakfast-english",
        "section": "breakfast",
        "name": "Английский завтрак",
        "about": "English breakfast",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 63,
        "parts": []
    },
    {
        "id": "omelet-cheese",
        "section": "breakfast",
        "name": "Омлет с сыром",
        "about": "Cheese omelet",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 28,
        "parts": []
    },
    {
        "id": "omelet-veg",
        "section": "breakfast",
        "name": "Омлет с овощами",
        "about": "Vegetable omelet",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 33,
        "parts": []
    },
    {
        "id": "shakshuka",
        "section": "breakfast",
        "name": "Шакшука",
        "about": "Shakshuka",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 30,
        "parts": []
    },
    {
        "id": "egg-sausage",
        "section": "breakfast",
        "name": "Яйцо с сосиской",
        "about": "Egg with sausage",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 29,
        "parts": []
    },
    {
        "id": "egg-coldcuts",
        "section": "breakfast",
        "name": "Яйцо с колбасой",
        "about": "Egg with cold cuts",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 33,
        "parts": []
    },
    {
        "id": "french-toast",
        "section": "breakfast",
        "name": "Французский тост",
        "about": "French toast",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 34,
        "parts": []
    },
    {
        "id": "syrniki",
        "section": "breakfast",
        "name": "Сырники",
        "about": "Syrniki",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 29,
        "parts": []
    },
    {
        "id": "pancakes-choco-banana",
        "section": "breakfast",
        "name": "Блинчики с шоколадом и бананом",
        "about": "Pancakes with chocolate and banana",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 25,
        "parts": []
    },
    {
        "id": "pancakes-milk",
        "section": "breakfast",
        "name": "Блинчики со сгущёнкой",
        "about": "Pancakes with condensed milk",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 23,
        "parts": []
    },
    {
        "id": "pancakes-spread",
        "section": "breakfast",
        "name": "Блинчики с шоколадной пастой",
        "about": "Pancakes with chocolate spread",
        "weight": 0,
        "kcal": 0,
        "cook": "15–20 мин",
        "price": 31,
        "parts": []
    },
    {
        "id": "cheesecake",
        "section": "desserts",
        "name": "Чизкейк",
        "about": "Cheesecake",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 33,
        "parts": []
    },
    {
        "id": "honey-cake",
        "section": "desserts",
        "name": "Медовый",
        "about": "Honey cake",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 35,
        "parts": []
    },
    {
        "id": "napoleon",
        "section": "desserts",
        "name": "Наполеон",
        "about": "Napoleon cake",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 38,
        "parts": []
    },
    {
        "id": "kotmer",
        "section": "desserts",
        "name": "Котмер",
        "about": "Kotmer",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 42,
        "parts": []
    },
    {
        "id": "espresso",
        "section": "coffee",
        "name": "Экспрессо",
        "about": "Espresso",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 13,
        "parts": []
    },
    {
        "id": "americano",
        "section": "coffee",
        "name": "Американо",
        "about": "Americano",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 19,
        "parts": []
    },
    {
        "id": "cappuccino",
        "section": "coffee",
        "name": "Капучино",
        "about": "Cappuccino",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 27,
        "parts": []
    },
    {
        "id": "latte",
        "section": "coffee",
        "name": "Латте",
        "about": "Latte",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 28,
        "parts": []
    },
    {
        "id": "flat-white",
        "section": "coffee",
        "name": "Флэт-уайт",
        "about": "Flat white",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 24,
        "parts": []
    },
    {
        "id": "tea-black",
        "section": "coffee",
        "name": "Чай чёрный",
        "about": "Black tea",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 12,
        "parts": []
    },
    {
        "id": "tea-green",
        "section": "coffee",
        "name": "Чай зелёный",
        "about": "Green tea",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 12,
        "parts": []
    },
    {
        "id": "tea-lemon",
        "section": "coffee",
        "name": "Чай с лимоном",
        "about": "Tea with lemon",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 17,
        "parts": []
    },
    {
        "id": "tea-ginger",
        "section": "coffee",
        "name": "Чай с лимоном и имбирём",
        "about": "Tea with lemon and ginger",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 21,
        "parts": []
    },
    {
        "id": "tea-fruit",
        "section": "coffee",
        "name": "Фруктовый чай",
        "about": "Fruit tea",
        "weight": 0,
        "kcal": 0,
        "cook": "10–20 мин",
        "price": 26,
        "parts": []
    },
    {
        "id": "mojito-strawberry",
        "section": "cold",
        "name": "Мохито клубничный",
        "about": "Strawberry mojito",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 23,
        "parts": []
    },
    {
        "id": "mojito-raspberry",
        "section": "cold",
        "name": "Мохито с малиной",
        "about": "Raspberry mojito",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 23,
        "parts": []
    },
    {
        "id": "mojito-iceberg",
        "section": "cold",
        "name": "Мохито айсберг",
        "about": "Iceberg mojito",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 23,
        "parts": []
    },
    {
        "id": "mojito-apple",
        "section": "cold",
        "name": "Мохито яблочный",
        "about": "Apple mojito",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 23,
        "parts": []
    },
    {
        "id": "mojito-classic",
        "section": "cold",
        "name": "Мохито классический",
        "about": "Classic mojito",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 23,
        "parts": []
    },
    {
        "id": "fresh-orange",
        "section": "cold",
        "name": "Апельсиновый фреш",
        "about": "Orange fresh juice",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 50,
        "parts": []
    },
    {
        "id": "fresh-apple",
        "section": "cold",
        "name": "Яблочный фреш",
        "about": "Apple fresh juice",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 30,
        "parts": []
    },
    {
        "id": "fresh-carrot",
        "section": "cold",
        "name": "Морковный фреш",
        "about": "Carrot fresh juice",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 30,
        "parts": []
    },
    {
        "id": "fresh-watermelon",
        "section": "cold",
        "name": "Арбузный фреш",
        "about": "Watermelon fresh juice",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 27,
        "parts": []
    },
    {
        "id": "fresh-carrot-apple",
        "section": "cold",
        "name": "Морковно-яблочный фреш",
        "about": "Carrot and apple fresh juice",
        "weight": 0,
        "kcal": 0,
        "cook": "05–20 мин",
        "price": 28,
        "parts": []
    }
]

ZONES = [
    {
        "id": "center",
        "name": "Центр, Айни, Рудаки",
        "price": 15
    },
    {
        "id": "sino",
        "name": "Сино, Фирдавси",
        "price": 15
    },
    {
        "id": "shohmansur",
        "name": "Шохмансур, И. Сомони",
        "price": 20
    },
    {
        "id": "out",
        "name": "За городом",
        "price": None
    }
]

SETTINGS = {
    "free_from": 100, "min_order": 40,
    "delivery_time": "30–40 минут", "pickup": "ул. Айни 49",
    "phone_main": "+992939171997", "phone_extra": "+992063202020",
    "address": "ул. Айни 49, ориентир GulyaGold", "hours": "9:00 – 00:00",
}

ADDONS = []   # платных добавок заведение пока не давало

REMOVALS = [
    {"section": "burgers", "name": "Лук", "gen": "лука"},
    {"section": "burgers", "name": "Солёный огурец", "gen": "солёного огурца"},
    {"section": "burgers", "name": "Томат", "gen": "томата"},
    {"section": "burgers", "name": "Соус", "gen": "соуса"},
    {"section": "shawarma", "name": "Лук", "gen": "лука"},
    {"section": "shawarma", "name": "Острый соус", "gen": "острого соуса"},
    {"section": "hotdogs", "name": "Лук", "gen": "лука"},
    {"section": "hotdogs", "name": "Горчица", "gen": "горчицы"},
    {"section": "hotdogs", "name": "Кетчуп", "gen": "кетчупа"},
]
