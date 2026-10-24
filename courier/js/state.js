// Что курьер хранит на телефоне: номер, анкета, смена, настройки.
// Заказы и доход живут в базе; здесь только то, что нужно, чтобы приложение открылось сразу, даже без сети.

const KEY = 'zud-courier-v1';
const fresh = () => ({
  phone: '',            // номер, по которому вошли (9 цифр)
  me: null,             // анкета из базы: имя, машина, номер, рейтинг
  online: false,        // курьер на линии
  nav: '2gis',          // навигатор для маршрута
  autoRoute: true,      // открывать маршрут сам: взял заказ — путь до магазина, забрал — до покупателя
  sound: true,          // звук нового заказа
  awake: true,          // не гасить экран на линии
  theme: 'auto',
  checked: {},          // отмеченные товары при заборе: { orderId: [номера строк] }
  waitFrom: {},         // когда начали ждать покупателя: { orderId: время }
  seenDone: [],         // какие доставки и отмены уже показали
  jobs: [],             // последние заказы — чтобы экран открылся без сети
});
export const K = (() => { try { return { ...fresh(), ...JSON.parse(localStorage.getItem(KEY)) }; } catch { return fresh(); } })();
// версия 2: 2GIS стал навигатором по умолчанию — переключаем тех, кто ещё не выбирал сам
if (!K.navV) { K.nav = '2gis'; K.navV = 2; }
export const save = () => { try { localStorage.setItem(KEY, JSON.stringify(K)); } catch { /* память переполнена */ } };
export const reset = () => { const keep = { nav: K.nav, navV: K.navV, autoRoute: K.autoRoute, sound: K.sound, awake: K.awake, theme: K.theme }; Object.assign(K, fresh(), keep); save(); };

// живое состояние (не сохраняется): лента, место, связь, что сейчас на экране
export const rt = {
  feed: [],             // свободные заказы рядом
  fresh: new Set(),     // новые в ленте — подсвечиваем
  pos: null,            // где курьер: { lat, lng, acc }
  geoErr: '',
  net: 'ok',            // ok | off — есть ли связь с базой
  busy: false,          // идёт запрос — кнопки ждут
  code: '',             // код покупателя, который вводит курьер
  period: 'day',        // доход: day | week | month
  history: null,        // доставки за 30 дней (для дохода)
  done: null,           // только что доставленный заказ — экран «+20 смн»
};

export const ACTIVE = ['going', 'at_shop', 'picked', 'at_client'];
/** Текущий заказ курьера (один за раз). */
export const activeJob = () => K.jobs.find(j => ACTIVE.includes(j.step) && j.status !== 'cancelled') || null;
/** Заказ отменили, пока курьер его вёз, — показать один раз. */
export const cancelledJob = () => K.jobs.find(j => ACTIVE.includes(j.step) && j.status === 'cancelled' && !K.seenDone.includes(j.id)) || null;
