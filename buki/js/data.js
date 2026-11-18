// Учебный контент. Один набор данных обслуживает оба курса:
//   курс «en» — русскоязычный учит английский (вопросы на русском, ответы на английском);
//   курс «ru» — англоязычный учит русский (наоборот).
//
// Как добавить новый урок/юнит: допишите объект в UNITS по образцу ниже.
//   words     — слова: { id, en, ru, e } (e — эмодзи-картинка, необязательно)
//   sentences — фразы: { id, en, ru }
// Значение может быть строкой или массивом: первый вариант — эталон,
// остальные тоже принимаются как правильные ответы.
//   tip.en — подсказка для изучающих английский (пишется по-русски),
//   tip.ru — подсказка для изучающих русский (пишется по-английски).

export const UNITS = [
  {
    id: 'greet', icon: '👋', cefr: 'A1',
    title: { ru: 'Приветствия', en: 'Greetings' },
    tip: {
      en: '«Hello» — нейтральное приветствие, «Hi» — дружеское. «Thank you» вежливее, чем «thanks».',
      ru: '«Привет» is informal, «Здравствуйте» is polite. Use «спасибо» for thank you in any situation.',
    },
    words: [
      { id: 'hello', en: ['hello', 'hi'], ru: ['привет', 'здравствуйте', 'здравствуй'], e: '🙋' },
      { id: 'goodbye', en: ['goodbye', 'bye'], ru: ['до свидания', 'пока'], e: '👋' },
      { id: 'thanks', en: ['thank you', 'thanks'], ru: 'спасибо', e: '🙏' },
      { id: 'please', en: 'please', ru: 'пожалуйста', e: '🤲' },
      { id: 'yes', en: 'yes', ru: 'да', e: '✅' },
      { id: 'no', en: 'no', ru: 'нет', e: '❌' },
      { id: 'sorry', en: 'sorry', ru: ['извините', 'простите', 'прости', 'извини'], e: '😔' },
      { id: 'gmorning', en: 'good morning', ru: 'доброе утро', e: '🌅' },
    ],
    sentences: [
      { id: 'greet1', en: 'Hello, Anna!', ru: ['Привет, Анна!', 'Здравствуй, Анна!'] },
      { id: 'greet2', en: 'Thank you very much.', ru: ['Большое спасибо.', 'Спасибо большое.'] },
      { id: 'greet3', en: 'Good morning, Tom!', ru: 'Доброе утро, Том!' },
      { id: 'greet4', en: ['How are you?', 'How are you doing?'], ru: ['Как дела?', 'Как у тебя дела?'] },
      { id: 'greet5', en: ['I am fine, thanks.', 'Fine, thanks.', 'I am fine, thank you.'], ru: ['Хорошо, спасибо.', 'Всё хорошо, спасибо.'] },
      { id: 'greet6', en: 'Yes, please.', ru: 'Да, пожалуйста.' },
    ],
  },
  {
    id: 'me', icon: '🙋', cefr: 'A1',
    title: { ru: 'Я и ты', en: 'Me and you' },
    tip: {
      en: 'В английском всегда нужен глагол «to be»: I am, you are, he/she is. «Я студент» = «I am a student».',
      ru: 'Russian drops “to be” in the present: «Я студент» = “I am a student”. There are no articles (a/the).',
    },
    words: [
      { id: 'i', en: 'I', ru: 'я', e: '🙋' },
      { id: 'you', en: 'you', ru: ['ты', 'вы'], e: '👉' },
      { id: 'he', en: 'he', ru: 'он', e: '👨' },
      { id: 'she', en: 'she', ru: 'она', e: '👩' },
      { id: 'we', en: 'we', ru: 'мы', e: '👫' },
      { id: 'student', en: 'student', ru: ['студент', 'студентка'], e: '🎓' },
      { id: 'friend', en: 'friend', ru: ['друг', 'подруга'], e: '🤝' },
      { id: 'name', en: 'name', ru: 'имя', e: '🏷️' },
    ],
    sentences: [
      { id: 'me1', en: 'I am a student.', ru: ['Я студент.', 'Я студентка.'] },
      { id: 'me2', en: 'My name is Tom.', ru: 'Меня зовут Том.' },
      { id: 'me3', en: 'She is my friend.', ru: ['Она моя подруга.', 'Она мой друг.'] },
      { id: 'me4', en: 'We are friends.', ru: 'Мы друзья.' },
      { id: 'me5', en: 'What is your name?', ru: ['Как тебя зовут?', 'Как вас зовут?'] },
      { id: 'me6', en: 'He is a teacher.', ru: 'Он учитель.' },
    ],
  },
  {
    id: 'family', icon: '👨‍👩‍👧', cefr: 'A1',
    title: { ru: 'Семья', en: 'Family' },
    tip: {
      en: '«I have a brother» — «У меня есть брат». Конструкция «I have» заменяет русское «у меня есть».',
      ru: '“I have” in Russian is «У меня есть» — literally “by me there is”.',
    },
    words: [
      { id: 'mother', en: ['mother', 'mom', 'mum'], ru: ['мама', 'мать'], e: '👩‍👧' },
      { id: 'father', en: ['father', 'dad'], ru: ['папа', 'отец'], e: '👨‍👦' },
      { id: 'sister', en: 'sister', ru: 'сестра', e: '👧' },
      { id: 'brother', en: 'brother', ru: 'брат', e: '👦' },
      { id: 'familyw', en: 'family', ru: 'семья', e: '👨‍👩‍👧' },
      { id: 'son', en: 'son', ru: 'сын', e: '🧒' },
      { id: 'daughter', en: 'daughter', ru: 'дочь', e: '👱‍♀️' },
      { id: 'grandma', en: ['grandmother', 'grandma'], ru: 'бабушка', e: '👵' },
    ],
    sentences: [
      { id: 'fam1', en: 'This is my mother.', ru: ['Это моя мама.', 'Это моя мать.'] },
      { id: 'fam2', en: 'I have a brother.', ru: 'У меня есть брат.' },
      { id: 'fam3', en: ['My father is at home.', 'My dad is at home.'], ru: ['Мой папа дома.', 'Мой отец дома.'] },
      { id: 'fam4', en: 'Her sister is a doctor.', ru: 'Её сестра врач.' },
      { id: 'fam5', en: 'We are a big family.', ru: 'Мы большая семья.' },
      { id: 'fam6', en: ['Grandmother loves me.', 'Grandma loves me.'], ru: 'Бабушка любит меня.' },
    ],
  },
  {
    id: 'food', icon: '🍎', cefr: 'A1',
    title: { ru: 'Еда', en: 'Food' },
    tip: {
      en: 'Перед исчисляемым словом в единственном числе ставим «a/an»: an apple, a sandwich. С водой и молоком артикль не нужен.',
      ru: 'Russian nouns change endings: «вода» → «Я пью воду» (accusative case). Don’t worry — you’ll pick it up by ear.',
    },
    words: [
      { id: 'water', en: 'water', ru: 'вода', e: '💧' },
      { id: 'bread', en: 'bread', ru: 'хлеб', e: '🍞' },
      { id: 'apple', en: 'apple', ru: 'яблоко', e: '🍎' },
      { id: 'milk', en: 'milk', ru: 'молоко', e: '🥛' },
      { id: 'coffee', en: 'coffee', ru: 'кофе', e: '☕' },
      { id: 'tea', en: 'tea', ru: 'чай', e: '🍵' },
      { id: 'cheese', en: 'cheese', ru: 'сыр', e: '🧀' },
      { id: 'soup', en: 'soup', ru: 'суп', e: '🍲' },
    ],
    sentences: [
      { id: 'food1', en: 'I drink water.', ru: 'Я пью воду.' },
      { id: 'food2', en: 'She eats an apple.', ru: 'Она ест яблоко.' },
      { id: 'food3', en: 'Coffee with milk, please.', ru: 'Кофе с молоком, пожалуйста.' },
      { id: 'food4', en: 'I want tea.', ru: ['Я хочу чай.', 'Я хочу чаю.'] },
      { id: 'food5', en: 'The bread is fresh.', ru: 'Хлеб свежий.' },
      { id: 'food6', en: 'Do you like cheese?', ru: ['Ты любишь сыр?', 'Вы любите сыр?'] },
    ],
  },
  {
    id: 'numbers', icon: '🔢', cefr: 'A1',
    title: { ru: 'Числа', en: 'Numbers' },
    tip: {
      en: 'Во множественном числе к слову добавляется -s: one cat → two cats, one book → five books.',
      ru: 'After 2, 3, 4 Russian uses one ending («два яблока»), after 5+ another («пять книг»).',
    },
    words: [
      { id: 'one', en: 'one', ru: 'один', e: '1️⃣' },
      { id: 'two', en: 'two', ru: ['два', 'две'], e: '2️⃣' },
      { id: 'three', en: 'three', ru: 'три', e: '3️⃣' },
      { id: 'four', en: 'four', ru: 'четыре', e: '4️⃣' },
      { id: 'five', en: 'five', ru: 'пять', e: '5️⃣' },
      { id: 'six', en: 'six', ru: 'шесть', e: '6️⃣' },
      { id: 'seven', en: 'seven', ru: 'семь', e: '7️⃣' },
      { id: 'ten', en: 'ten', ru: 'десять', e: '🔟' },
    ],
    sentences: [
      { id: 'num1', en: 'I have two cats.', ru: 'У меня две кошки.' },
      { id: 'num2', en: 'Three apples, please.', ru: 'Три яблока, пожалуйста.' },
      { id: 'num3', en: ['She is seven.', 'She is seven years old.'], ru: 'Ей семь лет.' },
      { id: 'num4', en: 'One coffee and one tea.', ru: 'Один кофе и один чай.' },
      { id: 'num5', en: 'We have five books.', ru: 'У нас пять книг.' },
    ],
  },
  {
    id: 'colors', icon: '🎨', cefr: 'A1',
    title: { ru: 'Цвета', en: 'Colors' },
    tip: {
      en: 'Прилагательное в английском не меняется: a red car, red cars, a red house.',
      ru: 'Russian adjectives agree with the noun: «красный дом», «красная машина», «красное яблоко».',
    },
    words: [
      { id: 'red', en: 'red', ru: ['красный', 'красная', 'красное'], e: '🔴' },
      { id: 'blue', en: 'blue', ru: ['синий', 'голубой'], e: '🔵' },
      { id: 'green', en: 'green', ru: 'зелёный', e: '🟢' },
      { id: 'white', en: 'white', ru: 'белый', e: '⚪' },
      { id: 'black', en: 'black', ru: 'чёрный', e: '⚫' },
      { id: 'yellow', en: 'yellow', ru: 'жёлтый', e: '🟡' },
      { id: 'big', en: 'big', ru: ['большой', 'большая', 'большое'], e: '🐘' },
      { id: 'small', en: 'small', ru: ['маленький', 'маленькая', 'маленькое'], e: '🐭' },
    ],
    sentences: [
      { id: 'col1', en: 'The car is red.', ru: 'Машина красная.' },
      { id: 'col2', en: 'This is a big house.', ru: 'Это большой дом.' },
      { id: 'col3', en: 'The cat is small and black.', ru: 'Кошка маленькая и чёрная.' },
      { id: 'col4', en: 'My tea is green.', ru: 'Мой чай зелёный.' },
      { id: 'col5', en: 'I like the blue sky.', ru: ['Мне нравится синее небо.', 'Мне нравится голубое небо.'] },
    ],
  },
  {
    id: 'home', icon: '🏠', cefr: 'A1',
    title: { ru: 'Дом', en: 'Home' },
    tip: {
      en: '«The» ставится, когда понятно, о каком предмете речь: «Open the window» — то самое окно.',
      ru: '«Открой» is informal (to one friend), «Откройте» is polite or plural.',
    },
    words: [
      { id: 'house', en: 'house', ru: 'дом', e: '🏠' },
      { id: 'room', en: 'room', ru: 'комната', e: '🛋️' },
      { id: 'door', en: 'door', ru: 'дверь', e: '🚪' },
      { id: 'window', en: 'window', ru: 'окно', e: '🪟' },
      { id: 'table', en: 'table', ru: 'стол', e: '🍽️' },
      { id: 'chair', en: 'chair', ru: 'стул', e: '🪑' },
      { id: 'bed', en: 'bed', ru: 'кровать', e: '🛏️' },
      { id: 'kitchen', en: 'kitchen', ru: 'кухня', e: '🍳' },
    ],
    sentences: [
      { id: 'home1', en: 'The house is big.', ru: 'Дом большой.' },
      { id: 'home2', en: 'Open the window, please.', ru: ['Открой окно, пожалуйста.', 'Откройте окно, пожалуйста.'] },
      { id: 'home3', en: 'The kitchen is small.', ru: 'Кухня маленькая.' },
      { id: 'home4', en: 'My room is here.', ru: 'Моя комната здесь.' },
      { id: 'home5', en: 'The cat is on the bed.', ru: 'Кошка на кровати.' },
    ],
  },
  {
    id: 'city', icon: '🚌', cefr: 'A2',
    title: { ru: 'Город и поездки', en: 'City & travel' },
    tip: {
      en: 'Вопрос «где?» — «Where is ...?»: Where is the hotel? Where is the bus?',
      ru: '«Где» means “where (at)”. «Мне нужен билет» = “I need a ticket” (literally “to me is needed a ticket”).',
    },
    words: [
      { id: 'street', en: 'street', ru: 'улица', e: '🛣️' },
      { id: 'car', en: 'car', ru: 'машина', e: '🚗' },
      { id: 'bus', en: 'bus', ru: 'автобус', e: '🚌' },
      { id: 'train', en: 'train', ru: 'поезд', e: '🚆' },
      { id: 'ticket', en: 'ticket', ru: 'билет', e: '🎫' },
      { id: 'hotel', en: 'hotel', ru: ['гостиница', 'отель'], e: '🏨' },
      { id: 'left', en: 'left', ru: ['налево', 'слева'], e: '⬅️' },
      { id: 'right', en: 'right', ru: ['направо', 'справа'], e: '➡️' },
    ],
    sentences: [
      { id: 'city1', en: 'Where is the hotel?', ru: ['Где гостиница?', 'Где отель?'] },
      { id: 'city2', en: 'I need a ticket.', ru: 'Мне нужен билет.' },
      { id: 'city3', en: 'The bus is here.', ru: 'Автобус здесь.' },
      { id: 'city4', en: 'Turn left, please.', ru: ['Поверните налево, пожалуйста.', 'Поверни налево, пожалуйста.'] },
      { id: 'city5', en: 'The train is late.', ru: 'Поезд опаздывает.' },
    ],
  },
  {
    id: 'time', icon: '⏰', cefr: 'A2',
    title: { ru: 'Время', en: 'Time' },
    tip: {
      en: 'Прошедшее время глагола «to be»: I/he/she was, we/you/they were. «Вчера я был дома» = «Yesterday I was at home».',
      ru: 'Past tense in Russian depends on gender: «я был» (male), «я была» (female).',
    },
    words: [
      { id: 'day', en: 'day', ru: 'день', e: '☀️' },
      { id: 'night', en: 'night', ru: 'ночь', e: '🌙' },
      { id: 'today', en: 'today', ru: 'сегодня', e: '📅' },
      { id: 'tomorrow', en: 'tomorrow', ru: 'завтра', e: '⏭️' },
      { id: 'yesterday', en: 'yesterday', ru: 'вчера', e: '⏮️' },
      { id: 'week', en: 'week', ru: 'неделя', e: '🗓️' },
      { id: 'morning', en: 'morning', ru: 'утро', e: '🌄' },
      { id: 'evening', en: 'evening', ru: 'вечер', e: '🌆' },
    ],
    sentences: [
      { id: 'time1', en: 'See you tomorrow!', ru: 'До завтра!' },
      { id: 'time2', en: 'Today is a good day.', ru: 'Сегодня хороший день.' },
      { id: 'time3', en: 'Good night!', ru: 'Спокойной ночи!' },
      { id: 'time4', en: 'I work in the evening.', ru: 'Я работаю вечером.' },
      { id: 'time5', en: 'Yesterday I was at home.', ru: ['Вчера я был дома.', 'Вчера я была дома.'] },
    ],
  },
  {
    id: 'verbs', icon: '🏃', cefr: 'A2',
    title: { ru: 'Действия', en: 'Actions' },
    tip: {
      en: 'С he/she/it к глаголу добавляем -s: I read → she reads, I write → he writes.',
      ru: 'Russian verbs change by person: я читаю, ты читаешь, она читает.',
    },
    words: [
      { id: 'go', en: 'go', ru: ['идти', 'ходить', 'пойти'], e: '🚶' },
      { id: 'see', en: 'see', ru: 'видеть', e: '👀' },
      { id: 'want', en: 'want', ru: 'хотеть', e: '🤩' },
      { id: 'like', en: 'like', ru: ['любить', 'нравиться'], e: '❤️' },
      { id: 'read', en: 'read', ru: 'читать', e: '📖' },
      { id: 'write', en: 'write', ru: 'писать', e: '✍️' },
      { id: 'speak', en: 'speak', ru: ['говорить', 'разговаривать'], e: '🗣️' },
      { id: 'work', en: 'work', ru: 'работать', e: '💼' },
    ],
    sentences: [
      { id: 'verb1', en: 'I read a book.', ru: 'Я читаю книгу.' },
      { id: 'verb2', en: 'Do you speak English?', ru: ['Ты говоришь по-английски?', 'Вы говорите по-английски?'] },
      { id: 'verb3', en: 'I want to go home.', ru: ['Я хочу пойти домой.', 'Я хочу домой.'] },
      { id: 'verb4', en: 'She writes a letter.', ru: 'Она пишет письмо.' },
      { id: 'verb5', en: 'We see the sea.', ru: 'Мы видим море.' },
      { id: 'verb6', en: 'I like to read.', ru: 'Я люблю читать.' },
    ],
  },
];

// Курсы. target — изучаемый язык, native — язык интерфейса и подсказок.
export const COURSES = {
  en: { id: 'en', target: 'en', native: 'ru', flag: '🇬🇧', speech: 'en-US' },
  ru: { id: 'ru', target: 'ru', native: 'en', flag: '🇷🇺', speech: 'ru-RU' },
};
