// Всё, что приложение просит у телефона, — только через этот файл.
//
// Сейчас курьер работает в браузере (PWA). Когда соберём APK через Capacitor, тот же код окажется
// внутри приложения, и функции ниже сами возьмут нативные плагины, если они установлены:
//   @capacitor/geolocation, @capacitor-community/background-geolocation — место, в том числе с выключенным экраном;
//   @capacitor/haptics — вибрация; @capacitor-community/keep-awake — экран не гаснет на смене;
//   @capacitor/local-notifications — уведомление о новом заказе; @capacitor/app-launcher — навигатор и звонок;
//   @capacitor/clipboard — копирование; @capacitor/app — возврат приложения на экран.
// Экраны про это не знают: им всё равно, браузер это или APK.

const cap = () => window.Capacitor;
const plugin = name => cap()?.Plugins?.[name];
/** Работаем внутри установленного APK. */
export const isNative = () => !!cap()?.isNativePlatform?.();

const round6 = n => +(+n).toFixed(6);
const fromCoords = c => ({ lat: round6(c.latitude), lng: round6(c.longitude), acc: Math.round(c.accuracy || 0) });
const geoError = e => new Error(e?.code === 1 || /denied|permission/i.test(e?.message || '')
  ? 'Нет доступа к местоположению. Разрешите его в настройках телефона'
  : 'Не удалось определить место. Проверьте, что GPS включён');

/** Место сейчас: { lat, lng, acc }. */
export async function where() {
  const G = plugin('Geolocation');
  if (G) { try { return fromCoords((await G.getCurrentPosition({ enableHighAccuracy: true, timeout: 12000 })).coords); } catch (e) { throw geoError(e); } }
  if (!navigator.geolocation) throw new Error('Телефон не умеет определять место');
  if (!window.isSecureContext) throw new Error('Место определяется только на защищённом адресе (https)');
  return new Promise((ok, no) => navigator.geolocation.getCurrentPosition(p => ok(fromCoords(p.coords)), e => no(geoError(e)),
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 15000 }));
}

/**
 * Следить за местом: cb({ lat, lng, acc }) при каждом движении. Возвращает функцию «перестать».
 * @param {(p: { lat: number, lng: number, acc: number }) => void} cb
 * @param {(e: Error) => void} [onError]
 * @returns {() => void}
 */
export function watch(cb, onError = () => {}) {
  const BG = plugin('BackgroundGeolocation');
  if (BG) {   // в APK: место идёт и с выключенным экраном, в шторке висит «Вы на линии»
    let id = null;
    BG.addWatcher({ backgroundMessage: 'Вы на линии — приходят заказы рядом', backgroundTitle: 'Зуд Курьер', requestPermissions: true, stale: false, distanceFilter: 25 },
      (loc, err) => err ? onError(geoError(err)) : loc && cb({ lat: round6(loc.latitude), lng: round6(loc.longitude), acc: Math.round(loc.accuracy || 0) }))
      .then(w => { id = w; });
    return () => { if (id) BG.removeWatcher({ id }); };
  }
  const G = plugin('Geolocation');
  if (G) {
    let id = null;
    G.watchPosition({ enableHighAccuracy: true }, (p, err) => err ? onError(geoError(err)) : p && cb(fromCoords(p.coords))).then(w => { id = w; });
    return () => { if (id) G.clearWatch({ id }); };
  }
  if (!navigator.geolocation || !window.isSecureContext) { onError(new Error('Место недоступно: откройте приложение по https')); return () => {}; }
  const id = navigator.geolocation.watchPosition(p => cb(fromCoords(p.coords)), e => onError(geoError(e)), { enableHighAccuracy: true, maximumAge: 10000 });
  return () => navigator.geolocation.clearWatch(id);
}

/**
 * Вибрация: число — мс, массив — узор.
 * @param {number | number[]} [pattern]
 */
export function vibrate(pattern = 200) {
  const H = plugin('Haptics');
  if (H) { const total = [].concat(pattern).filter((_, i) => i % 2 === 0).reduce((s, x) => s + x, 0); H.vibrate({ duration: total }).catch(() => {}); return; }
  try { navigator.vibrate?.(pattern); } catch { /* не поддерживается */ }
}

let lock = null;
/** Не гасить экран, пока курьер на линии. */
export async function keepAwake(on) {
  const K = plugin('KeepAwake');
  if (K) { try { await (on ? K.keepAwake() : K.allowSleep()); } catch { /* нет плагина */ } return; }
  try {
    if (on && !lock && 'wakeLock' in navigator && document.visibilityState === 'visible') { lock = await navigator.wakeLock.request('screen'); lock.addEventListener('release', () => { lock = null; }); }
    if (!on && lock) { await lock.release(); lock = null; }
  } catch { lock = null; }
}

/** Открыть внешнее: навигатор, звонок, WhatsApp. В APK — системным способом, в браузере — ссылкой. */
export async function openExternal(url) {
  dispatchEvent(new CustomEvent('zud:open', { detail: url }));   // для тестов и будущей аналитики: что открыли
  const L = plugin('AppLauncher');
  if (L) { try { await L.openUrl({ url }); return true; } catch { return false; } }
  if (/^(tel|sms|yandexnavi|yandexmaps|dgis|geo|intent):/i.test(url)) { location.href = url; return true; }
  return !!window.open(url, '_blank', 'noopener');
}
export const call = phone => openExternal('tel:' + String(phone || '').replace(/[^\d+]/g, ''));

/** Скопировать текст (адрес, номер). */
export async function copy(text) {
  const C = plugin('Clipboard');
  if (C) { await C.write({ string: text }); return true; }
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

/** Уведомление, когда приложение свёрнуто. */
export async function notify(title, body) {
  const N = plugin('LocalNotifications');
  if (N) { try { await N.schedule({ notifications: [{ id: Date.now() % 2e9, title, body }] }); } catch { /* нет разрешения */ } return; }
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  try { const reg = await navigator.serviceWorker?.getRegistration(); reg ? reg.showNotification(title, { body, icon: 'img/icons/icon-192.png', vibrate: [300, 120, 300], tag: 'offer' }) : new Notification(title, { body }); } catch { /* браузер не дал */ }
}
/** Спросить разрешение на уведомления — один раз, когда курьер выходит на линию. */
export async function askNotify() {
  const N = plugin('LocalNotifications');
  if (N) { try { await N.requestPermissions(); } catch { /* отказался */ } return; }
  if ('Notification' in window && Notification.permission === 'default') { try { await Notification.requestPermission(); } catch { /* отказался */ } }
}

/** Приложение снова на экране (вернулись из навигатора, разблокировали телефон). */
export function onResume(cb) {
  const A = plugin('App');
  if (A) A.addListener('appStateChange', s => s.isActive && cb());
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') cb(); });
}
