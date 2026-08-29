/* ============================================================
   AVERIX
   Замер страницы, переключатель языка, меню, форма.
   Зависимостей нет.
   ============================================================ */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ============================================================
     Язык: русский в разметке, таджикский — словарём.
     Русские строки берём из самой страницы, поэтому без JS
     сайт остаётся полностью читаемым.
     ============================================================ */
  var TG = {
    'skip': 'Гузаштан ба мундариҷа',

    'nav.who': 'Дар бораи ман',
    'nav.services': 'Хизматрасонӣ',
    'nav.process': 'Раванди кор',
    'nav.contact': 'Дархост',

    'hero.eyebrow': 'IT-студия · Душанбе · аз соли 2023',
    'hero.h1': 'Сомонаҳое, ки бо <em>даст</em> сохта мешаванд, на бо конструктор',
    'hero.sub': 'Ҳар лоиҳа аз сифр барои вазифаи мушаххаси тиҷорат навишта мешавад. ' +
                'Барои ҳамин он дар як лаҳза бор мешавад, на дар панҷ сония, ва баъдтар ' +
                'онро рушд додан мумкин аст, на партофтан.',
    'cta.discuss': 'Муҳокимаи лоиҳа',
    'cta.process': 'Кор чӣ тавр меравад',
    'cta.calc': 'Гирифтани ҳисоб',

    'stats.years': 'сол',
    'stats.years.note': 'ҳар рӯз код менависам',
    'stats.active': 'лоиҳа айни замон дар кор',
    'stats.happy': 'мизоҷон корро қабул карданд',

    'who.label': 'Кӣ месозад',
    'who.h2': 'Номи ман <em>Алиҷон</em>',
    'who.role': 'асосгузори AVERIX · веб-барномасоз · Душанбе',
    'who.open': 'Барои лоиҳаҳои нав кушодаам',
    'who.p1': 'Ман 19-солаам, ва се соли он ҳар рӯз код менависам. Аз Python ва ботҳо ' +
              'сар кардам, ҳоло сомона месозам: аз яксаҳифагӣ то корпоративӣ.',
    'who.p2': 'Ман шаблон намегирам ва логотипи шуморо ба он намекашам. Ҳар лоиҳа аз сифр ' +
              'сохта мешавад — ин тӯлонитар аст, вале сомона зуд бор мешавад, онро рушд ' +
              'додан мумкин аст ва он аз аввалин ислоҳ вайрон намешавад.',
    'who.p3': 'Рӯирост кор мекунам: агар вазифа аз имконияти ман берун бошад ё мӯҳлат ' +
              'воқеӣ набошад — дар аввалин сӯҳбат мегӯям, на баъди пешпардохт.',

    'services.label': 'Хизматрасонӣ',
    'services.h2': 'Мо чӣ мекунем',
    'services.lede': 'Се самт. Боқимондаро алоҳида муҳокима мекунем — ва рӯирост мегӯем, мегирем ё не.',

    'svc1.h': 'Лендинг барои вазифа',
    'svc1.p': 'Як саҳифа бо як мақсад: дархост, занг, сабт. Сохтор аз рӯи маҳсулот ва ' +
              'эродҳои мизоҷони шумо сохта мешавад.',
    'svc1.l1': 'Прототип ва матн',
    'svc1.l2': 'Дизайн мувофиқи бренди шумо',
    'svc1.l3': 'Шакли дархост ба Telegram',
    'svc1.l4': 'Мутобиқшавӣ ба телефон',

    'svc2.h': 'Сомонаи пурра',
    'svc2.p': 'Сомонаи бисёрсаҳифаи ширкат: хизматрасонӣ, дар бораи мо, тамос, блог. ' +
              'Сохтори равшан ва навигатсияи муқаррарӣ.',
    'svc2.l1': 'То 8 саҳифа',
    'svc2.l2': 'Панел барои ислоҳи матн',
    'svc2.l3': 'SEO-разметка ва микромаълумот',
    'svc2.l4': 'Пайвасти домен ва SSL',

    'svc3.h': 'Дастгирӣ ва такмил',
    'svc3.p': 'Сомона ҳаст, вале суст аст, дар телефон вайрон мешавад ё касе нест, ки ' +
              'навсозӣ кунад — ба хизматрасонӣ мегирем.',
    'svc3.l1': 'Тезонидани боркунӣ',
    'svc3.l2': 'Ислоҳи вёрстка дар мобилӣ',
    'svc3.l3': 'Бахшҳо ва блокҳои нав',
    'svc3.l4': 'Кӯчонидан ба хостинги дигар',

    'price.h': 'Нарх аз чӣ иборат аст',
    'price.p': 'Прайси ягона нест: лендинг аз панҷ блок ва сомона бо каталог — кори гуногун. ' +
               'Вале мо ҳамеша аз рӯи ҳамон чизҳо ҳисоб мекунем, ва ҳисобро шумо пеш аз оғоз мебинед.',
    'price.a.h': 'Ҳаҷм',
    'price.a.p': 'Чанд саҳифа ва блоки нотакрор. Зарбкунандаи асосӣ.',
    'price.b.h': 'Функсияҳо',
    'price.b.p': 'Шакл — содда. Каталог, кабинет, пардохт — кори алоҳида.',
    'price.c.h': 'Мазмун',
    'price.c.p': 'Матн ва акс ҳаст — зудтар. Мо менависем — тӯлонитар.',
    'price.foot': 'Нависед, ки чӣ лозим аст — дар давоми рӯз ҳисоб аз рӯи ин се банд ва ' +
                  'мӯҳлатро мефиристем. Ройгон ва ӯҳдадорӣ надорад.',

    'process.label': 'Раванд',
    'process.h2': 'Кор чӣ тавр меравад',
    'process.lede': 'Чор қадам. Пас аз ҳар яке шумо натиҷаро мебинед ва қарор мекунед, пеш ' +
                    'меравем ё не. Пардохт — аз рӯи марҳилаҳо, на пешакӣ барои ҳама.',

    'step1.h': 'Вазифаро таҳлил мекунем',
    'step1.p': 'Дар Telegram менависем ё занг мезанем. Муайян мекунем, мизоҷи шумо кист, ' +
               'вай дар сомона чӣ бояд кунад ва ҳоло чӣ ба ӯ халал мерасонад.',
    'step1.out': '→ рӯйхати саҳифаҳо ва блокҳо',
    'step2.h': 'Прототип ва матн',
    'step2.p': 'Нақшаи саҳифаро месозем: чӣ пас аз чӣ меояд ва ҳар блок кадом корро мекунад. ' +
               'Матнро якҷоя менависем — шумо маҳсулотро медонед, мо тарзи пешниҳодашро.',
    'step2.out': '→ сохтори мувофиқашуда пеш аз дизайн',
    'step3.h': 'Дизайн ва васл',
    'step3.p': 'Макетро мувофиқи бренди шумо мекашем, нишон медиҳем, ислоҳ мекунем. Баъд ' +
               'вёрстка: аввал телефон, баъд десктоп. Дар дастгоҳҳои воқеӣ месанҷем.',
    'step3.out': '→ сомонаи корӣ дар суроғаи санҷишӣ',
    'step4.h': 'Оғоз ва супоридан',
    'step4.p': 'Домен ва SSL-ро пайваст мекунем, аналитика мегузорем, шаклҳоро месанҷем. ' +
               'Ҳамаи дастрасӣ ва кодро месупорем — сомона пурра аз они шумост.',
    'step4.out': '→ сомона дар кор, дастрасӣ дар шумо',

    'final.label': 'Саволҳо ва дархост',
    'final.h2': 'Нависед, ки чӣ лозим аст',

    'faq1.q': 'Чанд ислоҳ ба кор дохил мешавад?',
    'faq1.a': 'Ислоҳҳо дар доираи сохтори мувофиқашуда — чанде ки лозим бошад. Алоҳида ' +
              'танҳо тағйири худи вазифа ҳисоб мешавад: масалан, ба ҷои лендинг мағоза. ' +
              'Дар ин бора фавран огоҳ мекунем, на дар ҳисобнома.',
    'faq2.q': 'Барои оғоз аз ман чӣ лозим аст?',
    'faq2.a': 'Ҳадди ақал: бо чӣ машғулед ва меҳмони сомона чӣ бояд кунад. Боқимондаро — ' +
              'матн, акс, сохтор — бо саволҳо дар марҳилаи аввал муайян мекунем. Логотип ва ' +
              'брендбук барои оғоз лозим нест.',
    'faq3.q': 'Ин чӣ қадар вақт мегирад?',
    'faq3.a': 'Мӯҳлатро пас аз таҳлили вазифа ҳамроҳи ҳисоб мегӯем. Он аз ҳаҷм ва аз он ' +
              'вобаста аст, ки ҷавобу маводҳо аз ҷониби шумо чӣ қадар зуд меоянд — одатан ' +
              'таъхири асосӣ ҳамин аст, на худи васл.',
    'faq4.q': 'Агар кор бас кунем, сомона дар ман мемонад?',
    'faq4.a': 'Бале. Домен ба номи шумо ба қайд гирифта мешавад, код ва ҳамаи дастрасиро ' +
              'пас аз оғоз месупорем. Ҳеҷ вобастагӣ ба хостинг ё аккаунтҳои мо нест.',
    'faq5.q': 'Танҳо дар Душанбе кор мекунед?',
    'faq5.a': 'Не. Тамоми кор дар мукотиба ва зангҳо мегузарад, барои ҳамин шаҳр муҳим нест. ' +
              'Танҳо мо аз ин ҷоем, ва дар Душанбе метавонем рӯ ба рӯ вохӯрем, агар қулайтар бошад.',

    'form.name': 'Шуморо чӣ хел муроҷиат кунем',
    'form.name.ph': 'Масалан, Фаррух',
    'form.contact': 'Telegram ё телефон',
    'form.contact.hint': 'ҳисобро ба куҷо фиристем',
    'form.task': 'Чӣ кор кардан лозим аст',
    'form.task.ph': 'Ду ҷумла: бо чӣ машғулед ва сомона чӣ бояд кунад',
    'form.submit': 'Ба Telegram фиристодан',
    'form.note': 'дархост ҳамчун паёми тайёр кушода мешавад — танҳо «Фиристодан»-ро пахш кунед',

    'foot.about': 'Студия аз Душанбе. Сомонаҳо ва лендингҳо, ки бо даст барои вазифаи тиҷорат сохта мешаванд.',
    'foot.services': 'Хизматрасонӣ',
    'foot.studio': 'Студия',
    'foot.contact': 'Тамос',
    'foot.faq': 'Саволҳо',
    'foot.city': 'Душанбе, Тоҷикистон',

    /* ---- разделы студии: проекты, кейсы, команда, вакансии ---- */
    'nav.projects': 'Лоиҳаҳо',
    'nav.team': 'Студия',
    'nav.careers': 'Ҷойҳои корӣ',
    'crumb.home': 'Асосӣ',
    'cta.projects': 'Дидани лоиҳаҳо',
    'work.label': 'Лоиҳаҳои интихобшуда',
    'work.h2': 'Корҳое, ки муносибати моро беҳтар нишон медиҳанд',
    'work.more': 'Дидани кейс',
    'work.all': 'Ҳамаи лоиҳаҳо →',
    'stat.years': 'сол дар барномасозӣ',
    'stat.active': 'лоиҳаи фаъол',
    'stat.accepted': 'кор аз ҷониби фармоишгар қабул шуд',
    'svc4.h': 'Automation',
    'svc4.p': 'Автоматизатсияи равандҳои такрорӣ ва вазифаҳои дохилии тиҷорат.',
    'svc4.l1': 'Ҷамъоварӣ ва таҳлили маълумот',
    'svc4.l2': 'Ҳисоботҳо аз рӯи ҷадвал',
    'svc4.l3': 'Пайвасти хизматрасониҳо бо ҳам',
    'svc4.l4': 'Огоҳиномаҳо ба мессенҷерҳо',
    'svc5.h': 'AI Integration',
    'svc5.p': 'Ҷойгир кардани AI дар сомонаҳо, хизматрасониҳо ва Telegram-ботҳо — дар ҷое, ки вазифаро ҳал мекунад.',
    'svc5.l1': 'Коркарди матн ва аризаҳо',
    'svc5.l2': 'Ҷустуҷӯ аз рӯи маълумоти худӣ',
    'svc5.l3': 'Ёрдамчӣ дар бот',
    'svc5.l4': 'Таҳлили ҳуҷҷатҳо',
    'services.note': 'Вазифаҳои берун аз ин самтҳоро низ муҳокима мекунам — нависед, ва ман рӯирост мегӯям, мегирам ё не.',
    'step5.h': 'Оғоз',
    'step5.p': 'Доменро ва SSL-ро пайваст мекунам, таҳлилро мегузорам, формаҳоро дар кор месанҷам.',
    'step5.out': '→ маҳсулот дар кор, дастрасиҳо дар дасти шумо',
    'step6.h': 'Рушд',
    'step6.p': 'Дар сурати зарурат такмил ва васеъ кардани маҳсулотро идома медиҳам.',
    'step6.out': '→ дастгирӣ бо мувофиқа',
    'about.label': 'Дар бораи студия',
    'about.idea': 'Дар асос принсипи содда: <em>ғоя → сохтан → натиҷа</em>.',
    'about.idea.t': 'Вазифаро мефаҳмем ва муайян мекунем, ки аслан чӣ бояд сохта шавад',
    'about.dev.t': 'Тарҳрезӣ мекунем, месозем ва дар дастгоҳҳои воқеӣ месанҷем',
    'about.res.t': 'Оғоз мекунем ва ҳамаи дастрасиҳову рамзи ибтидоиро месупорем',
    'form.type': 'Чӣ лозим аст',
    'form.budget': 'Буҷа',
    'form.budget.ph': 'ҳатмӣ нест',
    'projects.h1': 'Лоиҳаҳо',
    'projects.lede': 'Дар ин ҷо танҳо он чизе ҳаст, ки воқеан сохта ва ба кор андохта шудааст. Ҳар кейс — бо вазифа, ҳал ва натиҷа.',
    'projects.all': 'Ҳама',
    'projects.empty.t': 'ҲОЛО ХОЛӢ',
    'projects.empty.p': 'Дар ин бахш ҳанӯз кори нашршуда нест. Дертар назар кунед — ё нависед, лоиҳаи шуморо муҳокима мекунем.',
    'case.stack': 'Технологияҳо',
    'case.live': 'Сомона',
    'case.open': 'Кушодан',
    'case.code': 'Рамзи ибтидоӣ',
    'case.task': 'Вазифа',
    'case.solution': 'Ҳалли масъала',
    'case.features': 'Дар дохил чӣ ҳаст',
    'case.result': 'Натиҷа',
    'case.next': 'ЛОИҲАИ ОЯНДА',
    'team.label': 'Дар бораи студия',
    'team.h1': 'AVERIX — ин студия аст, на биржаи фрилансерон',
    'team.people.label': 'Кӣ кор мекунад',
    'team.people.h2': 'Одамон',
    'team.founder.name': 'Алиҷон Маҳмадҷонов',
    'team.founder.role': 'муассис · веб-барномасоз',
    'team.founder.bio': 'Ҳоло тамоми корро худам мекунам: дизайн, вёрстка, backend ва оғоз дар сервер. Ин аз нишон додани шӯъбаи хаёлии даҳнафара ростқавлтар аст — шумо ҳамеша медонед, ки барои лоиҳаи шумо кӣ ҷавобгар аст.',
    'team.grow': 'Студия меафзояд — ҷойҳои кушода дар саҳифаи <a href="/careers">Ҷойҳои корӣ</a>.',
    'team.rules.label': 'Чӣ тавр кор мекунем',
    'team.rules.h2': 'Се қоида, ки аз онҳо намегардем',
    'team.rule1.h': 'Пеш аз кор мегӯем, на баъд',
    'team.rule1.p': 'Агар вазифа аз тавон берун бошад ё мӯҳлат воқеӣ набошад — дар сӯҳбати аввал мегӯем, на баъди пешпардохт.',
    'team.rule2.h': 'Рамзи ибтидоӣ дар дасти шумо мемонад',
    'team.rule2.p': 'Репозиторий, домен ва сервер ба номи шумо расмӣ мешаванд. Ҳеҷ вобастагии «то абад» ба мо нест.',
    'team.rule3.h': 'Бе қолабҳо',
    'team.rule3.p': 'Ҳар лоиҳа аз сифр сохта мешавад: дертар, вале зуд бор мешавад ва такмилро тоб меорад.',
    'jobs.label': 'Кор дар студия',
    'jobs.h1': 'Ҷойҳои корӣ',
    'jobs.req': 'Чӣ муҳим аст',
    'jobs.apply': 'Ариза додан',
    'jobs.empty.t': 'ҶОЙҲОИ КОРӢ КУШОДА НЕСТ',
    'jobs.empty.p': 'Айни замон мо касеро ҷустуҷӯ намекунем. Аммо агар шумо дар кори мо қавӣ бошед — ариза фиристед: ҳангоми пайдо шудани вазифа тамос мегирем.',
    'jobs.form.label': 'Ариза',
    'jobs.form.h2': 'Дар бораи худ нақл кунед',
    'jobs.form.lede': 'Ба ҳар касе, ки аз рӯи кор навиштааст, ҷавоб медиҳем. Резюме ҳатмӣ нест — истинод ба корҳои кардаатон муҳимтар аст.',
    'jobs.f.vacancy': 'Ҷойи корӣ',
    'jobs.f.any': 'Бе вобастагӣ ба ҷойи корӣ',
    'jobs.f.name': 'Ном',
    'jobs.f.tg': 'Telegram ё почта',
    'jobs.f.email': 'Почта',
    'jobs.f.country': 'Шаҳр ё кишвар',
    'jobs.f.direction': 'Самт',
    'jobs.f.direction.ph': 'frontend, backend, дизайн…',
    'jobs.f.exp': 'Таҷриба',
    'jobs.f.exp.ph': 'масалан, 2 сол таҷрибаи тиҷоратӣ',
    'jobs.f.skills': 'Технологияҳо',
    'jobs.f.portfolio': 'Портфолио',
    'jobs.f.github': 'GitHub',
    'jobs.f.msg': 'Дар бораи худ',
    'jobs.f.msg.ph': 'Чӣ кор кардаед, бо чӣ машғул шудан мехоҳед, чанд вақт ҷудо карда метавонед',
    'jobs.f.submit': 'Фиристодани ариза',
    'jobs.f.note': 'Маълумотро танҳо студия мебинад. Ба касе намедиҳем ва нашр намекунем.',
    'thanks.req.k': 'ДАРХОСТ ҚАБУЛ ШУД',
    'thanks.req.h': 'Раҳмат, дархости шумо расид',
    'thanks.req.p': 'Дар давоми рӯз ҷавоб медиҳам. Агар таъҷилӣ бошад — мустақиман ба Telegram нависед, ин зудтар аст.',
    'thanks.job.k': 'АРИЗА ҚАБУЛ ШУД',
    'thanks.job.h': 'Раҳмат, аризаи шумо расид',
    'thanks.job.p': 'Бо диққат мебинем ва ба Telegram ё почта менависем. Агар чанд рӯз ҷавоб набошад — ин рад нест, танҳо навбат ба навбат дида мебароем.',
    'thanks.home': 'Ба саҳифаи асосӣ',
    'nf.code': 'ХАТОГИИ 404',
    'nf.h': 'Чунин саҳифа нест',
    'nf.p': 'Шояд онро нест кардаанд ё дар суроға хато бошад. Истинодро санҷед — ё лоиҳаҳоро бинед.',

    /* ---- freelance ---- */
    'nav.freelance': 'Freelance',
    'foot.role': 'Digital Development Studio',
    'foot.work': 'Корҳо',
    'fl.label': 'Базаи мутахассисон',
    'fl.h1': 'Бо AVERIX кор кун',
    'fl.cta': 'Мутахассис шудан',
    'fl.how.label': 'Ин чӣ тавр кор мекунад',
    'fl.how.h2': 'На ҷойи корӣ, балки база барои вазифаҳо',
    'fl.how.lede': 'Даста ва фриланс чизҳои гуногунанд. Дар даста доимӣ кор мекунанд, мутахассисонро аз база бошад ба вазифаҳои мушаххас даъват мекунем, вақте онҳо пайдо мешаванд.',
    'fl.s1.h': 'Шумо анкета мемонед',
    'fl.s1.p': 'Ихтисос, технологияҳо, истинод ба корҳо. Ҳар қадар мушаххастар — ҳамон қадар эҳтимоли бештар, ки дар лаҳзаи лозимӣ шуморо ба ёд орем.',
    'fl.s2.h': 'Мо мебинем ва ҷавоб медиҳем',
    'fl.s2.p': 'Анкета ба базаи студия меафтад, на ба сомона: мо касеро бе пурсиш нашр намекунем. Ҷавоб ба Telegram ё почта меояд.',
    'fl.s3.h': 'Вазифа пайдо шуд — менависем',
    'fl.s3.p': 'Вазифа, мӯҳлат ва пардохт то оғоз муҳокима мешаванд. Кабул карда, шумо дар кабинети шахсӣ кор мекунед: ҳамон ҷо натиҷаро месупоред ва ислоҳҳоро мебинед.',
    'fl.honest': 'Ростқавлона: ҷараёни вазифаҳо дар студия ҳоло калон нест ва мо фавран пас аз анкета корро ваъда намедиҳем. Ваъда медиҳем танҳо он ки анкетаро одам мебинад.',
    'fl.form.label': 'Анкета',
    'fl.form.h2': 'Мутахассис шудан',
    'fl.form.lede': 'Ҳатмӣ танҳо ном, тамос, технологияҳо ва ду калима дар бораи худ. Боқимондаро пур кунед, агар ин дар бораи шумо бошад.',
    'fl.f.name': 'Ном',
    'fl.f.tg': 'Telegram ё почта',
    'fl.f.email': 'Почта',
    'fl.f.country': 'Кишвар',
    'fl.f.city': 'Шаҳр',
    'fl.f.spec': 'Ихтисос',
    'fl.f.skills': 'Технологияҳо',
    'fl.f.years': 'Соли таҷриба',
    'fl.f.exp': 'Дар куҷо кор кардаед',
    'fl.f.about': 'Дар бораи худ',
    'fl.f.about.ph': 'Чӣ кор кардаед, кадом вазифаҳо маъқуланд, чанд вақт ҷудо карда метавонед',
    'fl.f.portfolio': 'Портфолио',
    'fl.f.github': 'GitHub',
    'fl.f.rate': 'Нархнома',
    'fl.f.rate.ph': 'ҳатмӣ нест',
    'fl.f.rate.type': 'Навъи нархнома',
    'fl.f.avail': 'Бандӣ ҳоло',
    'fl.f.submit': 'Фиристодани анкета',
    'thanks.fl.k': 'АНКЕТА ҚАБУЛ ШУД',
    'thanks.fl.h': 'Раҳмат, анкета дар мост',
    'thanks.fl.p': 'Он ба базаи студия афтод, на ба сомона — мо шуморо бе пурсиш нашр намекунем. Вақте вазифаи мувофиқ пайдо шавад, менависем.'
  };

  var RU = {};   /* заполняется со страницы при загрузке */
  var langButtons = document.querySelectorAll('.lang button');

  document.querySelectorAll('[data-i18n]').forEach(function (el) {
    RU[el.dataset.i18n] = el.innerHTML;
  });
  document.querySelectorAll('[data-i18n-ph]').forEach(function (el) {
    RU[el.dataset.i18nPh] = el.placeholder;
  });

  function setLang(code) {
    var dict = code === 'tg' ? TG : RU;

    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var v = dict[el.dataset.i18n];
      if (v !== undefined) el.innerHTML = v;
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(function (el) {
      var v = dict[el.dataset.i18nPh];
      if (v !== undefined) el.placeholder = v;
    });

    document.documentElement.lang = code === 'tg' ? 'tg' : 'ru';
    langButtons.forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.lang === code));
    });
    movePill(code);
  }

  /* Язык нужен и серверу: заголовки, тексты проектов и вакансий приходят
     из базы, а не из разметки, — их словарь на странице подменить нельзя. */
  function readLang() {
    var m = document.cookie.match(/(?:^|;\s*)averix-lang=(ru|tg)/);
    if (m) return m[1];
    try { return localStorage.getItem('averix-lang') || 'ru'; } catch (e) { return 'ru'; }
  }

  function rememberLang(code) {
    var bits = 'averix-lang=' + code + ';path=/;max-age=31536000;SameSite=Lax';
    if (location.protocol === 'https:') bits += ';Secure';
    document.cookie = bits;
    try { localStorage.setItem('averix-lang', code); } catch (e) {}
  }

  var serverRendered = document.body.hasAttribute('data-server-i18n');

  langButtons.forEach(function (b) {
    b.addEventListener('click', function () {
      var code = b.dataset.lang === 'tg' ? 'tg' : 'ru';
      if (code === readLang() && code === document.documentElement.lang) return;
      rememberLang(code);
      /* На серверных страницах перезагружаем: иначе названия проектов
         и настройки останутся на прежнем языке — это выглядит как сбой. */
      if (serverRendered) { location.reload(); return; }
      setLang(code);
    });
  });

  if (readLang() === 'tg') setLang('tg');

  /* стартовое положение бегунка и пересчёт при смене размера шрифта/окна */
  movePill(document.documentElement.lang === 'tg' ? 'tg' : 'ru');
  window.addEventListener('resize', function () {
    movePill(document.documentElement.lang === 'tg' ? 'tg' : 'ru');
  });

  /* ============================================================
     Шапка и меню
     ============================================================ */
  var nav = document.getElementById('nav');
  var ticking = false;

  window.addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      if (nav) nav.classList.toggle('stuck', window.scrollY > 8);
      ticking = false;
    });
  }, { passive: true });

  var burger = document.getElementById('burger');
  var menu = document.getElementById('menu');
  var backdrop = document.getElementById('backdrop');

  function openMenu() {
    menu.classList.add('open');
    backdrop.hidden = false;
    /* следующий кадр — иначе переход прозрачности не проиграется */
    requestAnimationFrame(function () { backdrop.classList.add('open'); });
    burger.setAttribute('aria-expanded', 'true');
    burger.setAttribute('aria-label', 'Закрыть меню');
    document.body.style.overflow = 'hidden';
    var first = menu.querySelector('a');
    if (first) first.focus();
  }

  function closeMenu(returnFocus) {
    menu.classList.remove('open');
    backdrop.classList.remove('open');
    backdrop.hidden = true;
    burger.setAttribute('aria-expanded', 'false');
    burger.setAttribute('aria-label', 'Открыть меню');
    document.body.style.overflow = '';
    if (returnFocus) burger.focus();
  }

  if (burger && menu && backdrop) {
    burger.addEventListener('click', function () {
      if (menu.classList.contains('open')) closeMenu(true);
      else openMenu();
    });
    backdrop.addEventListener('click', function () { closeMenu(true); });
    menu.addEventListener('click', function (e) {
      if (e.target.closest('a')) closeMenu(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.classList.contains('open')) closeMenu(true);
    });
    /* панель живёт только на узких экранах — на широких закрываем принудительно */
    window.addEventListener('resize', function () {
      if (window.innerWidth > 900 && menu.classList.contains('open')) closeMenu(false);
    });
  }

  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  /* ============================================================
     Появление блоков
     ============================================================ */
  var items = document.querySelectorAll('.r');

  if (reduced || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(items, function (el) { el.classList.add('in'); });
    document.querySelectorAll('[data-count]').forEach(countUp);
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          entry.target.querySelectorAll('[data-count]').forEach(countUp);
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    Array.prototype.forEach.call(items, function (el) { io.observe(el); });
  }


  /* ============================================================
     Бегунок переключателя языка
     ============================================================ */
  function movePill(code) {
    /* элемент ищем внутри функции: setLang вызывается раньше,
       чем выполнится присваивание на верхнем уровне */
    var pill = document.getElementById('lang-pill');
    if (!pill) return;
    var btn = document.querySelector('.lang button[data-lang="' + code + '"]');
    var first = document.querySelector('.lang button');
    if (!btn || !first) return;
    pill.style.width = btn.offsetWidth + 'px';
    pill.style.transform = 'translateX(' + (btn.offsetLeft - first.offsetLeft) + 'px)';
  }

  /* ============================================================
     Цифры набегают, когда блок появляется на экране
     ============================================================ */
  function countUp(el) {
    var target = parseInt(el.dataset.count, 10);
    if (reduced || !target) { el.textContent = target; return; }
    var start = null;
    var dur = 900;
    el.textContent = '0';
    function tick(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / dur, 1);
      /* замедление к концу — цифра «приезжает», а не щёлкает */
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  /* ============================================================
     Блик под курсором на стеклянных карточках
     ============================================================ */
  if (window.matchMedia('(hover: hover)').matches && !reduced) {
    document.querySelectorAll('.card').forEach(function (card) {
      var pending = false, mx = 0, my = 0;
      card.addEventListener('mousemove', function (e) {
        var rect = card.getBoundingClientRect();
        mx = e.clientX - rect.left;
        my = e.clientY - rect.top;
        if (pending) return;
        pending = true;
        requestAnimationFrame(function () {
          card.style.setProperty('--mx', mx + 'px');
          card.style.setProperty('--my', my + 'px');
          pending = false;
        });
      });
    });
  }

  /* ============================================================
     Вопросы раскрываются плавно
     Анимируем сам <details>, а не его содержимое: у закрытого
     <details> тело остаётся выложенным на полную высоту и просто
     обрезается, поэтому анимация по телу шла бы вхолостую.
     Движение прерываемое: повторный клик разворачивает его,
     а не ждёт окончания.
     ============================================================ */
  document.querySelectorAll('.faq details').forEach(function (d) {
    var summary = d.querySelector('summary');
    var body = d.querySelector('.faq-body');
    var closedH = d.getBoundingClientRect().height;   /* меряем до первого клика */
    var running = null;

    summary.addEventListener('click', function (e) {
      if (reduced) return;                 /* оставляем родное поведение */
      e.preventDefault();
      if (running) running.cancel();

      var startH = d.getBoundingClientRect().height;
      var opening = !d.open;

      if (opening) d.open = true;
      d.style.height = 'auto';
      var openH = d.getBoundingClientRect().height;
      d.style.height = startH + 'px';

      var endH = opening ? openH : closedH;

      running = d.animate(
        [{ height: startH + 'px' }, { height: endH + 'px' }],
        { duration: opening ? 340 : 250, easing: 'cubic-bezier(.22,.7,.28,1)' }
      );
      body.animate(
        [{ opacity: opening ? 0 : 1 }, { opacity: opening ? 1 : 0 }],
        { duration: opening ? 280 : 180, easing: 'ease-out', fill: 'none' }
      );

      running.onfinish = function () {
        running = null;
        d.style.height = '';
        if (!opening) d.open = false;
      };
    });
  });

  /* ============================================================
     Отклик на конкретную вакансию
     Кнопка у вакансии ведёт к форме — заодно подставляем вакансию,
     чтобы человек не искал её в списке заново.
     ============================================================ */
  var vacancySelect = document.getElementById('j-vacancy');
  if (vacancySelect) {
    document.querySelectorAll('[data-vacancy]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        vacancySelect.value = btn.dataset.vacancy;
      });
    });
  }

  /* ============================================================
     Проверка форм до отправки
     Форма уходит на сервер обычным POST — без JS она тоже работает.
     Здесь мы только подсказываем раньше, чем перезагрузится страница.
     ============================================================ */
  var MESSAGES = {
    ru: {
      empty: 'Заполните это поле',
      short: 'Напишите чуть подробнее — хотя бы пару фраз'
    },
    tg: {
      empty: 'Ин майдонро пур кунед',
      short: 'Каме муфассалтар нависед — ақаллан ду ҷумла'
    }
  };

  function fieldError(input, message) {
    var box = input.parentNode.querySelector('.err.js-err');
    if (!box) {
      box = document.createElement('p');
      box.className = 'err js-err';
      box.setAttribute('role', 'alert');
      input.parentNode.appendChild(box);
    }
    box.textContent = message;
    input.setAttribute('aria-invalid', 'true');
  }

  function fieldOk(input) {
    var box = input.parentNode.querySelector('.err.js-err');
    if (box) box.remove();
    input.removeAttribute('aria-invalid');
  }

  document.querySelectorAll('form.form').forEach(function (form) {
    var required = form.querySelectorAll('[required]');

    required.forEach(function (input) {
      input.addEventListener('blur', function () {
        if (input.value.trim()) fieldOk(input);
      });
    });

    form.addEventListener('submit', function (e) {
      var texts = MESSAGES[document.documentElement.lang === 'tg' ? 'tg' : 'ru'];
      var firstBad = null;

      required.forEach(function (input) {
        var value = input.value.trim();
        /* у длинных полей минимум осмысленной длины совпадает с серверным */
        var tooShort = input.tagName === 'TEXTAREA' && value.length < 10;
        if (!value) {
          fieldError(input, texts.empty);
          if (!firstBad) firstBad = input;
        } else if (tooShort) {
          fieldError(input, texts.short);
          if (!firstBad) firstBad = input;
        } else {
          fieldOk(input);
        }
      });

      if (firstBad) {
        e.preventDefault();
        firstBad.focus();
        return;
      }

      /* Повторное нажатие создало бы вторую такую же заявку. Гасим
         кнопку не сразу: если отключить её прямо в обработчике, Chrome
         считает отправителя недоступным и вовсе не отправляет форму. */
      var submit = form.querySelector('button[type="submit"]');
      if (submit) {
        setTimeout(function () { submit.disabled = true; }, 0);
        setTimeout(function () { submit.disabled = false; }, 6000);
      }
    });
  });
})();
