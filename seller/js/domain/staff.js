import { ROLES } from '../config.js';
import { auth } from '../services/storage.js';
import { S } from '../state.js';

// Кто сейчас вошёл: владелец магазина, сотрудник или посторонний номер (null)
export function role() {
  if (!S || !auth.phone) return null;
  if (S.shop.owner === auth.phone) return 'owner';
  return S.staff.find(x => x.phone === auth.phone)?.role || null;
}
export const can = view => { const r = role(); return r === 'owner' || (!!r && ROLES[r].views.includes(view)); };
export const me = () => S.staff.find(x => x.phone === auth.phone);
