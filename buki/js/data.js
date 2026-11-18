// Учебный контент «Буки». Один набор данных обслуживает все курсы:
//   en_tg — английский с объяснениями на таджикском (основной курс);
//   en_ru — английский с объяснениями на русском;
//   ru_en — русский для англоговорящих.
//
// Как добавить юнит: допишите объект в UNITS по образцу ниже.
//   words     — слова: { id, en, ru, tg, e } (e — эмодзи-картинка, необязательно)
//   sentences — фразы: { id, en, ru, tg }
// Значение может быть строкой или массивом: первый вариант — эталон,
// остальные тоже принимаются как правильный ответ.
//   tip — короткая подсказка к юниту, отдельно для каждого курса.
// Правило для таджикского: простые повседневные слова, без книжных и редких.
// Таджикские тексты нужно проверить у носителя языка перед запуском.

export const UNITS = [
  {
    id: 'greet', icon: '👋', cefr: 'A1',
    title: { ru: 'Приветствия', en: 'Greetings', tg: 'Салом ва хайр' },
    tip: {
      en_tg: '«Hello» — салом. «Hi» — ҳам салом, вале дӯстона. «Thank you» — ташаккур.',
      en_ru: '«Hello» — нейтральное приветствие, «Hi» — дружеское. «Thank you» вежливее, чем «thanks».',
      ru_en: '«Привет» is informal, «Здравствуйте» is polite. Use «спасибо» for thank you in any situation.',
    },
    words: [
      { id: 'hello', en: ['hello', 'hi'], ru: ['привет', 'здравствуйте', 'здравствуй'], tg: ['салом', 'ассалому алайкум'], e: '🙋' },
      { id: 'goodbye', en: ['goodbye', 'bye'], ru: ['до свидания', 'пока'], tg: ['хайр', 'то дидан'], e: '👋' },
      { id: 'thanks', en: ['thank you', 'thanks'], ru: 'спасибо', tg: ['ташаккур', 'раҳмат'], e: '🙏' },
      { id: 'please', en: 'please', ru: 'пожалуйста', tg: 'лутфан', e: '🤲' },
      { id: 'yes', en: 'yes', ru: 'да', tg: ['ҳа', 'бале'], e: '✅' },
      { id: 'no', en: 'no', ru: 'нет', tg: 'не', e: '❌' },
      { id: 'sorry', en: 'sorry', ru: ['извините', 'простите', 'прости', 'извини'], tg: ['бубахшед', 'бубахш'], e: '😔' },
      { id: 'gmorning', en: 'good morning', ru: 'доброе утро', tg: 'субҳ ба хайр', e: '🌅' },
    ],
    sentences: [
      { id: 'greet1', en: 'Hello, Anna!', ru: ['Привет, Анна!', 'Здравствуй, Анна!'], tg: 'Салом, Анна!' },
      { id: 'greet2', en: 'Thank you very much.', ru: ['Большое спасибо.', 'Спасибо большое.'], tg: ['Ташаккури зиёд.', 'Бисёр ташаккур.'] },
      { id: 'greet3', en: 'Good morning, Tom!', ru: 'Доброе утро, Том!', tg: 'Субҳ ба хайр, Том!' },
      { id: 'greet4', en: ['How are you?', 'How are you doing?'], ru: ['Как дела?', 'Как у тебя дела?'], tg: ['Аҳволат чӣ хел?', 'Аҳволи шумо чӣ хел?', 'Чӣ хелӣ?'] },
      { id: 'greet5', en: ['I am fine, thanks.', 'Fine, thanks.', 'I am fine, thank you.'], ru: ['Хорошо, спасибо.', 'Всё хорошо, спасибо.'], tg: ['Хуб, ташаккур.', 'Ман хуб, ташаккур.'] },
      { id: 'greet6', en: 'Yes, please.', ru: 'Да, пожалуйста.', tg: ['Ҳа, лутфан.', 'Бале, лутфан.'] },
    ],
  },
  {
    id: 'me', icon: '🙋', cefr: 'A1',
    title: { ru: 'Я и ты', en: 'Me and you', tg: 'Ман ва ту' },
    tip: {
      en_tg: 'Дар англисӣ «am / is / are» ҳамеша лозим: I am, you are, he is. «Ман донишҷӯ ҳастам» = «I am a student».',
      en_ru: 'В английском всегда нужен глагол «to be»: I am, you are, he/she is. «Я студент» = «I am a student».',
      ru_en: 'Russian drops “to be” in the present: «Я студент» = “I am a student”. There are no articles (a/the).',
    },
    words: [
      { id: 'i', en: 'I', ru: 'я', tg: 'ман', e: '🙋' },
      { id: 'you', en: 'you', ru: ['ты', 'вы'], tg: ['ту', 'шумо'], e: '👉' },
      { id: 'he', en: 'he', ru: 'он', tg: ['ӯ (мард)', 'ӯ', 'вай'], e: '👨' },
      { id: 'she', en: 'she', ru: 'она', tg: ['ӯ (зан)', 'ӯ', 'вай'], e: '👩' },
      { id: 'we', en: 'we', ru: 'мы', tg: 'мо', e: '👫' },
      { id: 'student', en: 'student', ru: ['студент', 'студентка'], tg: ['донишҷӯ', 'толибилм'], e: '🎓' },
      { id: 'friend', en: 'friend', ru: ['друг', 'подруга'], tg: 'дӯст', e: '🤝' },
      { id: 'name', en: 'name', ru: 'имя', tg: 'ном', e: '🏷️' },
    ],
    sentences: [
      { id: 'me1', en: 'I am a student.', ru: ['Я студент.', 'Я студентка.'], tg: ['Ман донишҷӯ ҳастам.', 'Ман донишҷӯям.'] },
      { id: 'me2', en: 'My name is Tom.', ru: 'Меня зовут Том.', tg: ['Номи ман Том аст.', 'Номам Том.'] },
      { id: 'me3', en: 'She is my friend.', ru: ['Она моя подруга.', 'Она мой друг.'], tg: ['Ӯ дӯсти ман аст.', 'Вай дӯсти ман аст.'] },
      { id: 'me4', en: 'We are friends.', ru: 'Мы друзья.', tg: ['Мо дӯст ҳастем.', 'Мо дӯстем.'] },
      { id: 'me5', en: 'What is your name?', ru: ['Как тебя зовут?', 'Как вас зовут?'], tg: ['Номи ту чист?', 'Номи шумо чист?', 'Номат чист?'] },
      { id: 'me6', en: 'He is a teacher.', ru: 'Он учитель.', tg: ['Ӯ муаллим аст.', 'Вай муаллим аст.'] },
    ],
  },
  {
    id: 'family', icon: '👨‍👩‍👧', cefr: 'A1',
    title: { ru: 'Семья', en: 'Family', tg: 'Оила' },
    tip: {
      en_tg: '«I have a brother» = «Ман бародар дорам». «I have» — «ман дорам».',
      en_ru: '«I have a brother» — «У меня есть брат». Конструкция «I have» заменяет русское «у меня есть».',
      ru_en: '“I have” in Russian is «У меня есть» — literally “by me there is”.',
    },
    words: [
      { id: 'mother', en: ['mother', 'mom', 'mum'], ru: ['мама', 'мать'], tg: ['модар', 'оча'], e: '👩‍👧' },
      { id: 'father', en: ['father', 'dad'], ru: ['папа', 'отец'], tg: ['падар', 'дада', 'ота'], e: '👨‍👦' },
      { id: 'sister', en: 'sister', ru: 'сестра', tg: 'хоҳар', e: '👧' },
      { id: 'brother', en: 'brother', ru: 'брат', tg: ['бародар', 'ака', 'додар'], e: '👦' },
      { id: 'familyw', en: 'family', ru: 'семья', tg: 'оила', e: '👨‍👩‍👧' },
      { id: 'son', en: 'son', ru: 'сын', tg: 'писар', e: '🧒' },
      { id: 'daughter', en: 'daughter', ru: 'дочь', tg: 'духтар', e: '👱‍♀️' },
      { id: 'grandma', en: ['grandmother', 'grandma'], ru: 'бабушка', tg: ['бибӣ', 'модаркалон'], e: '👵' },
    ],
    sentences: [
      { id: 'fam1', en: 'This is my mother.', ru: ['Это моя мама.', 'Это моя мать.'], tg: ['Ин модари ман аст.', 'Ин очаи ман аст.'] },
      { id: 'fam2', en: 'I have a brother.', ru: 'У меня есть брат.', tg: ['Ман бародар дорам.', 'Ман як бародар дорам.'] },
      { id: 'fam3', en: ['My father is at home.', 'My dad is at home.'], ru: ['Мой папа дома.', 'Мой отец дома.'], tg: ['Падари ман дар хона аст.', 'Падарам дар хона аст.', 'Дадаам дар хона аст.'] },
      { id: 'fam4', en: 'Her sister is a doctor.', ru: 'Её сестра врач.', tg: ['Хоҳари ӯ духтур аст.', 'Хоҳари вай духтур аст.'] },
      { id: 'fam5', en: 'We are a big family.', ru: 'Мы большая семья.', tg: ['Мо оилаи калон ҳастем.', 'Мо оилаи калонем.'] },
      { id: 'fam6', en: ['Grandmother loves me.', 'Grandma loves me.'], ru: 'Бабушка любит меня.', tg: ['Бибӣ маро дӯст медорад.', 'Модаркалон маро дӯст медорад.'] },
    ],
  },
  {
    id: 'food', icon: '🍎', cefr: 'A1',
    title: { ru: 'Еда', en: 'Food', tg: 'Хӯрок' },
    tip: {
      en_tg: 'Пеш аз чизе, ки шумурдан мумкин, «a» ё «an» мегузорем: an apple, a cup. Пеш аз «water» ва «milk» — не.',
      en_ru: 'Перед исчисляемым словом в единственном числе ставим «a/an»: an apple, a sandwich. С водой и молоком артикль не нужен.',
      ru_en: 'Russian nouns change endings: «вода» → «Я пью воду» (accusative case). Don’t worry — you’ll pick it up by ear.',
    },
    words: [
      { id: 'water', en: 'water', ru: 'вода', tg: 'об', e: '💧' },
      { id: 'bread', en: 'bread', ru: 'хлеб', tg: 'нон', e: '🍞' },
      { id: 'apple', en: 'apple', ru: 'яблоко', tg: 'себ', e: '🍎' },
      { id: 'milk', en: 'milk', ru: 'молоко', tg: 'шир', e: '🥛' },
      { id: 'coffee', en: 'coffee', ru: 'кофе', tg: 'қаҳва', e: '☕' },
      { id: 'tea', en: 'tea', ru: 'чай', tg: 'чой', e: '🍵' },
      { id: 'cheese', en: 'cheese', ru: 'сыр', tg: 'панир', e: '🧀' },
      { id: 'soup', en: 'soup', ru: 'суп', tg: 'шӯрбо', e: '🍲' },
    ],
    sentences: [
      { id: 'food1', en: 'I drink water.', ru: 'Я пью воду.', tg: 'Ман об менӯшам.' },
      { id: 'food2', en: 'She eats an apple.', ru: 'Она ест яблоко.', tg: ['Ӯ себ мехӯрад.', 'Вай себ мехӯрад.'] },
      { id: 'food3', en: 'Coffee with milk, please.', ru: 'Кофе с молоком, пожалуйста.', tg: ['Қаҳва бо шир, лутфан.', 'Лутфан, қаҳва бо шир.'] },
      { id: 'food4', en: 'I want tea.', ru: ['Я хочу чай.', 'Я хочу чаю.'], tg: ['Ман чой мехоҳам.', 'Чой мехоҳам.'] },
      { id: 'food5', en: 'The bread is fresh.', ru: 'Хлеб свежий.', tg: ['Нон тоза аст.', 'Нон нав аст.'] },
      { id: 'food6', en: 'Do you like cheese?', ru: ['Ты любишь сыр?', 'Вы любите сыр?'], tg: ['Ту панирро дӯст медорӣ?', 'Шумо панирро дӯст медоред?'] },
    ],
  },
  {
    id: 'numbers', icon: '🔢', cefr: 'A1',
    title: { ru: 'Числа', en: 'Numbers', tg: 'Рақамҳо' },
    tip: {
      en_tg: 'Агар чиз зиёда аз як бошад, ба охири калима «-s» илова мекунем: one cat → two cats.',
      en_ru: 'Во множественном числе к слову добавляется -s: one cat → two cats, one book → five books.',
      ru_en: 'After 2, 3, 4 Russian uses one ending («два яблока»), after 5+ another («пять книг»).',
    },
    words: [
      { id: 'one', en: 'one', ru: 'один', tg: 'як', e: '1️⃣' },
      { id: 'two', en: 'two', ru: ['два', 'две'], tg: 'ду', e: '2️⃣' },
      { id: 'three', en: 'three', ru: 'три', tg: 'се', e: '3️⃣' },
      { id: 'four', en: 'four', ru: 'четыре', tg: 'чор', e: '4️⃣' },
      { id: 'five', en: 'five', ru: 'пять', tg: 'панҷ', e: '5️⃣' },
      { id: 'six', en: 'six', ru: 'шесть', tg: 'шаш', e: '6️⃣' },
      { id: 'seven', en: 'seven', ru: 'семь', tg: 'ҳафт', e: '7️⃣' },
      { id: 'ten', en: 'ten', ru: 'десять', tg: 'даҳ', e: '🔟' },
    ],
    sentences: [
      { id: 'num1', en: 'I have two cats.', ru: 'У меня две кошки.', tg: 'Ман ду гурба дорам.' },
      { id: 'num2', en: 'Three apples, please.', ru: 'Три яблока, пожалуйста.', tg: ['Се себ, лутфан.', 'Се дона себ, лутфан.'] },
      { id: 'num3', en: ['She is seven.', 'She is seven years old.'], ru: 'Ей семь лет.', tg: ['Ӯ ҳафтсола аст.', 'Вай ҳафтсола аст.'] },
      { id: 'num4', en: 'One coffee and one tea.', ru: 'Один кофе и один чай.', tg: 'Як қаҳва ва як чой.' },
      { id: 'num5', en: 'We have five books.', ru: 'У нас пять книг.', tg: 'Мо панҷ китоб дорем.' },
    ],
  },
  {
    id: 'colors', icon: '🎨', cefr: 'A1',
    title: { ru: 'Цвета', en: 'Colors', tg: 'Рангҳо' },
    tip: {
      en_tg: 'Ранг пеш аз калима меояд: a red car — мошини сурх. Ранг дигар намешавад: red cars.',
      en_ru: 'Прилагательное в английском не меняется: a red car, red cars, a red house.',
      ru_en: 'Russian adjectives agree with the noun: «красный дом», «красная машина», «красное яблоко».',
    },
    words: [
      { id: 'red', en: 'red', ru: ['красный', 'красная', 'красное'], tg: 'сурх', e: '🔴' },
      { id: 'blue', en: 'blue', ru: ['синий', 'голубой'], tg: ['кабуд', 'осмонӣ'], e: '🔵' },
      { id: 'green', en: 'green', ru: 'зелёный', tg: 'сабз', e: '🟢' },
      { id: 'white', en: 'white', ru: 'белый', tg: 'сафед', e: '⚪' },
      { id: 'black', en: 'black', ru: 'чёрный', tg: 'сиёҳ', e: '⚫' },
      { id: 'yellow', en: 'yellow', ru: 'жёлтый', tg: 'зард', e: '🟡' },
      { id: 'big', en: 'big', ru: ['большой', 'большая', 'большое'], tg: 'калон', e: '🐘' },
      { id: 'small', en: 'small', ru: ['маленький', 'маленькая', 'маленькое'], tg: ['хурд', 'майда'], e: '🐭' },
    ],
    sentences: [
      { id: 'col1', en: 'The car is red.', ru: 'Машина красная.', tg: 'Мошин сурх аст.' },
      { id: 'col2', en: 'This is a big house.', ru: 'Это большой дом.', tg: 'Ин хонаи калон аст.' },
      { id: 'col3', en: 'The cat is small and black.', ru: 'Кошка маленькая и чёрная.', tg: 'Гурба хурд ва сиёҳ аст.' },
      { id: 'col4', en: 'My tea is green.', ru: 'Мой чай зелёный.', tg: ['Чойи ман сабз аст.', 'Чоям сабз аст.'] },
      { id: 'col5', en: 'I like the blue sky.', ru: ['Мне нравится синее небо.', 'Мне нравится голубое небо.'], tg: ['Ба ман осмони кабуд маъқул аст.', 'Ман осмони кабудро дӯст медорам.'] },
    ],
  },
  {
    id: 'home', icon: '🏠', cefr: 'A1',
    title: { ru: 'Дом', en: 'Home', tg: 'Хона' },
    tip: {
      en_tg: '«The» — вақте ки маълум аст, кадом чиз: «Open the window» — ҳамон тиреза.',
      en_ru: '«The» ставится, когда понятно, о каком предмете речь: «Open the window» — то самое окно.',
      ru_en: '«Открой» is informal (to one friend), «Откройте» is polite or plural.',
    },
    words: [
      { id: 'house', en: 'house', ru: 'дом', tg: ['хона', 'ҳавлӣ'], e: '🏠' },
      { id: 'room', en: 'room', ru: 'комната', tg: ['ҳуҷра', 'утоқ'], e: '🛋️' },
      { id: 'door', en: 'door', ru: 'дверь', tg: 'дар', e: '🚪' },
      { id: 'window', en: 'window', ru: 'окно', tg: 'тиреза', e: '🪟' },
      { id: 'table', en: 'table', ru: 'стол', tg: 'миз', e: '🍽️' },
      { id: 'chair', en: 'chair', ru: 'стул', tg: 'курсӣ', e: '🪑' },
      { id: 'bed', en: 'bed', ru: 'кровать', tg: ['кат', 'бистар'], e: '🛏️' },
      { id: 'kitchen', en: 'kitchen', ru: 'кухня', tg: 'ошхона', e: '🍳' },
    ],
    sentences: [
      { id: 'home1', en: 'The house is big.', ru: 'Дом большой.', tg: 'Хона калон аст.' },
      { id: 'home2', en: 'Open the window, please.', ru: ['Открой окно, пожалуйста.', 'Откройте окно, пожалуйста.'], tg: ['Тирезаро кушо, лутфан.', 'Лутфан, тирезаро кушо.', 'Лутфан, тирезаро кушоед.'] },
      { id: 'home3', en: 'The kitchen is small.', ru: 'Кухня маленькая.', tg: 'Ошхона хурд аст.' },
      { id: 'home4', en: 'My room is here.', ru: 'Моя комната здесь.', tg: ['Ҳуҷраи ман ин ҷо аст.', 'Ҳуҷраи ман дар ин ҷо аст.', 'Утоқи ман ин ҷо аст.'] },
      { id: 'home5', en: 'The cat is on the bed.', ru: 'Кошка на кровати.', tg: ['Гурба дар болои кат аст.', 'Гурба дар рӯи кат аст.'] },
    ],
  },
  {
    id: 'city', icon: '🚌', cefr: 'A2',
    title: { ru: 'Город и поездки', en: 'City & travel', tg: 'Шаҳр ва сафар' },
    tip: {
      en_tg: '«Where is …?» — «… куҷост?». Where is the bus? — Автобус куҷост?',
      en_ru: 'Вопрос «где?» — «Where is ...?»: Where is the hotel? Where is the bus?',
      ru_en: '«Где» means “where (at)”. «Мне нужен билет» = “I need a ticket” (literally “to me is needed a ticket”).',
    },
    words: [
      { id: 'street', en: 'street', ru: 'улица', tg: 'кӯча', e: '🛣️' },
      { id: 'car', en: 'car', ru: 'машина', tg: 'мошин', e: '🚗' },
      { id: 'bus', en: 'bus', ru: 'автобус', tg: 'автобус', e: '🚌' },
      { id: 'train', en: 'train', ru: 'поезд', tg: ['қатора', 'поезд'], e: '🚆' },
      { id: 'ticket', en: 'ticket', ru: 'билет', tg: ['чипта', 'билет'], e: '🎫' },
      { id: 'hotel', en: 'hotel', ru: ['гостиница', 'отель'], tg: ['меҳмонхона', 'отел'], e: '🏨' },
      { id: 'left', en: 'left', ru: ['налево', 'слева'], tg: ['ба чап', 'чап'], e: '⬅️' },
      { id: 'right', en: 'right', ru: ['направо', 'справа'], tg: ['ба рост', 'рост'], e: '➡️' },
    ],
    sentences: [
      { id: 'city1', en: 'Where is the hotel?', ru: ['Где гостиница?', 'Где отель?'], tg: ['Меҳмонхона куҷост?', 'Меҳмонхона дар куҷост?'] },
      { id: 'city2', en: 'I need a ticket.', ru: 'Мне нужен билет.', tg: ['Ба ман чипта лозим аст.', 'Ба ман билет лозим аст.'] },
      { id: 'city3', en: 'The bus is here.', ru: 'Автобус здесь.', tg: ['Автобус ин ҷо аст.', 'Автобус дар ин ҷо аст.'] },
      { id: 'city4', en: 'Turn left, please.', ru: ['Поверните налево, пожалуйста.', 'Поверни налево, пожалуйста.'], tg: ['Лутфан, ба чап гардед.', 'Ба чап гардед, лутфан.'] },
      { id: 'city5', en: 'The train is late.', ru: 'Поезд опаздывает.', tg: ['Қатора дер мекунад.', 'Поезд дер мекунад.'] },
    ],
  },
  {
    id: 'time', icon: '⏰', cefr: 'A2',
    title: { ru: 'Время', en: 'Time', tg: 'Вақт' },
    tip: {
      en_tg: 'Барои гузашта: I / he / she was, we / you / they were. «Ман дар хона будам» = «I was at home».',
      en_ru: 'Прошедшее время глагола «to be»: I/he/she was, we/you/they were. «Вчера я был дома» = «Yesterday I was at home».',
      ru_en: 'Past tense in Russian depends on gender: «я был» (male), «я была» (female).',
    },
    words: [
      { id: 'day', en: 'day', ru: 'день', tg: 'рӯз', e: '☀️' },
      { id: 'night', en: 'night', ru: 'ночь', tg: 'шаб', e: '🌙' },
      { id: 'today', en: 'today', ru: 'сегодня', tg: 'имрӯз', e: '📅' },
      { id: 'tomorrow', en: 'tomorrow', ru: 'завтра', tg: ['фардо', 'пагоҳ'], e: '⏭️' },
      { id: 'yesterday', en: 'yesterday', ru: 'вчера', tg: ['дирӯз', 'дина'], e: '⏮️' },
      { id: 'week', en: 'week', ru: 'неделя', tg: 'ҳафта', e: '🗓️' },
      { id: 'morning', en: 'morning', ru: 'утро', tg: ['субҳ', 'саҳар'], e: '🌄' },
      { id: 'evening', en: 'evening', ru: 'вечер', tg: ['бегоҳ', 'шом'], e: '🌆' },
    ],
    sentences: [
      { id: 'time1', en: 'See you tomorrow!', ru: 'До завтра!', tg: ['То фардо!', 'То пагоҳ!'] },
      { id: 'time2', en: 'Today is a good day.', ru: 'Сегодня хороший день.', tg: 'Имрӯз рӯзи хуб аст.' },
      { id: 'time3', en: 'Good night!', ru: 'Спокойной ночи!', tg: 'Шаб ба хайр!' },
      { id: 'time4', en: 'I work in the evening.', ru: 'Я работаю вечером.', tg: ['Ман бегоҳ кор мекунам.', 'Ман бегоҳӣ кор мекунам.'] },
      { id: 'time5', en: 'Yesterday I was at home.', ru: ['Вчера я был дома.', 'Вчера я была дома.'], tg: ['Дирӯз ман дар хона будам.', 'Ман дирӯз дар хона будам.'] },
    ],
  },
  {
    id: 'verbs', icon: '🏃', cefr: 'A2',
    title: { ru: 'Действия', en: 'Actions', tg: 'Амалҳо' },
    tip: {
      en_tg: 'Бо «he» ва «she» ба охири феъл «-s» илова мекунем: I read → she reads.',
      en_ru: 'С he/she/it к глаголу добавляем -s: I read → she reads, I write → he writes.',
      ru_en: 'Russian verbs change by person: я читаю, ты читаешь, она читает.',
    },
    words: [
      { id: 'go', en: 'go', ru: ['идти', 'ходить', 'пойти'], tg: 'рафтан', e: '🚶' },
      { id: 'see', en: 'see', ru: 'видеть', tg: 'дидан', e: '👀' },
      { id: 'want', en: 'want', ru: 'хотеть', tg: 'хостан', e: '🤩' },
      { id: 'like', en: 'like', ru: ['любить', 'нравиться'], tg: ['дӯст доштан', 'писанд кардан'], e: '❤️' },
      { id: 'read', en: 'read', ru: 'читать', tg: 'хондан', e: '📖' },
      { id: 'write', en: 'write', ru: 'писать', tg: 'навиштан', e: '✍️' },
      { id: 'speak', en: 'speak', ru: ['говорить', 'разговаривать'], tg: ['гап задан', 'гуфтан'], e: '🗣️' },
      { id: 'work', en: 'work', ru: 'работать', tg: 'кор кардан', e: '💼' },
    ],
    sentences: [
      { id: 'verb1', en: 'I read a book.', ru: 'Я читаю книгу.', tg: 'Ман китоб мехонам.' },
      { id: 'verb2', en: 'Do you speak English?', ru: ['Ты говоришь по-английски?', 'Вы говорите по-английски?'], tg: ['Ту англисӣ гап мезанӣ?', 'Шумо англисӣ гап мезанед?'] },
      { id: 'verb3', en: 'I want to go home.', ru: ['Я хочу пойти домой.', 'Я хочу домой.'], tg: ['Ман мехоҳам ба хона равам.', 'Ман ба хона рафтан мехоҳам.'] },
      { id: 'verb4', en: 'She writes a letter.', ru: 'Она пишет письмо.', tg: ['Ӯ мактуб менависад.', 'Вай мактуб менависад.'] },
      { id: 'verb5', en: 'We see the sea.', ru: 'Мы видим море.', tg: 'Мо баҳрро мебинем.' },
      { id: 'verb6', en: 'I like to read.', ru: 'Я люблю читать.', tg: ['Ман хонданро дӯст медорам.', 'Ба ман хондан маъқул аст.'] },
    ],
  },
];

// Курсы. target — изучаемый язык, native — язык интерфейса, подсказок и переводов.
export const COURSES = {
  en_tg: { id: 'en_tg', target: 'en', native: 'tg', flag: '🇹🇯', speech: 'en-US' },
  en_ru: { id: 'en_ru', target: 'en', native: 'ru', flag: '🇷🇺', speech: 'en-US' },
  ru_en: { id: 'ru_en', target: 'ru', native: 'en', flag: '🇬🇧', speech: 'ru-RU' },
};
