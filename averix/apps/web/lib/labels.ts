// Коды API → подписи для людей. Внутри системы роли и статусы остаются
// английскими идентификаторами; здесь — единственное место, где они
// получают русские имена.

export const ROLE_LABEL: Record<string, string> = {
  client: 'Заказчик',
  developer: 'Исполнитель',
  admin: 'Администратор',
  moderator: 'Модератор',
};

export function roleLabel(role: string | undefined): string {
  return role ? ROLE_LABEL[role] ?? role : '';
}

export const PROJECT_STATUS: Record<string, string> = {
  draft: 'Черновик',
  pending_review: 'На проверке',
  open: 'Открыт',
  in_progress: 'В работе',
  completed: 'Завершён',
  cancelled: 'Отменён',
  closed: 'Закрыт',
  expired: 'Истёк',
};

export const CONTRACT_STATUS: Record<string, string> = {
  pending: 'Ожидает',
  active: 'В работе',
  in_progress: 'В работе',
  completed: 'Завершён',
  cancelled: 'Отменён',
  disputed: 'Спор',
  paused: 'На паузе',
};

export const MILESTONE_STATUS: Record<string, string> = {
  pending: 'Ожидает',
  funded: 'Оплачен в резерв',
  in_progress: 'В работе',
  submitted: 'Сдан на проверку',
  revision_requested: 'На доработке',
  approved: 'Принят',
  released: 'Выплачен',
  disputed: 'Спор',
  cancelled: 'Отменён',
};

export const PROPOSAL_STATUS: Record<string, string> = {
  submitted: 'Отправлен',
  shortlisted: 'В шорт-листе',
  accepted: 'Принят',
  declined: 'Отклонён',
  withdrawn: 'Отозван',
  expired: 'Истёк',
};

export const SERVICE_STATUS: Record<string, string> = {
  draft: 'Черновик',
  active: 'Опубликована',
  paused: 'На паузе',
  archived: 'В архиве',
};

export const PAYMENT_STATUS: Record<string, string> = {
  pending: 'Ожидает подтверждения',
  awaiting_confirmation: 'Ожидает подтверждения',
  confirmed: 'Подтверждён',
  completed: 'Проведён',
  failed: 'Не прошёл',
  refunded: 'Возвращён',
  rejected: 'Отклонён',
  cancelled: 'Отменён',
};

export const AVAILABILITY: Record<string, string> = {
  available: 'Свободен',
  limited: 'Ограниченно',
  booked: 'Занят',
  unavailable: 'Недоступен',
};

export const EXPERIENCE: Record<string, string> = {
  any: 'Любой уровень',
  junior: 'Начинающий',
  mid: 'Уверенный',
  senior: 'Опытный',
  lead: 'Эксперт',
};

export const SKILL_LEVEL: Record<string, string> = {
  familiar: 'Знаком',
  working: 'Рабочий уровень',
  strong: 'Уверенно',
  expert: 'Эксперт',
};

export const PROFICIENCY: Record<string, string> = {
  basic: 'Базовый',
  conversational: 'Разговорный',
  fluent: 'Свободный',
  native: 'Родной',
};

export const STARTS: Record<string, string> = {
  immediately: 'Сразу',
  within_week: 'В течение недели',
  within_month: 'В течение месяца',
  flexible: 'Гибко',
};

export const BUDGET_TYPE: Record<string, string> = {
  fixed: 'Фиксированная сумма',
  range: 'Диапазон',
  hourly: 'Почасовая',
};

export const VISIBILITY: Record<string, string> = {
  public: 'Открытый — виден всем исполнителям',
  invite_only: 'Только по приглашению',
  private: 'Скрытый',
};

export const COMPANY_SIZE: Record<string, string> = {
  solo: 'Только я',
  '2-10': '2–10 человек',
  '11-50': '11–50 человек',
  '51-200': '51–200 человек',
  '200+': 'Больше 200',
};

export const REPORT_REASON: Record<string, string> = {
  spam: 'Спам или реклама',
  off_platform_payment: 'Предлагает оплату мимо платформы',
  contact_details: 'Контакты в открытом тексте',
  scam: 'Мошенничество',
  harassment: 'Оскорбления или угрозы',
  copyright: 'Чужая работа выдана за свою',
  inappropriate: 'Неприемлемый контент',
  fake_profile: 'Поддельный профиль',
  other: 'Другое',
};

export const SECTORS: { slug: string; name: string; hint: string }[] = [
  { slug: 'design', name: 'Дизайн', hint: 'Логотипы, сайты, иллюстрации, презентации' },
  { slug: 'it', name: 'Разработка и IT', hint: 'Сайты, боты, приложения, интеграции' },
  { slug: 'texts', name: 'Тексты и переводы', hint: 'Статьи, лендинги, редактура, перевод' },
  { slug: 'seo', name: 'SEO и трафик', hint: 'Продвижение, контекст, аудит' },
  { slug: 'smm', name: 'SMM и маркетинг', hint: 'Соцсети, таргет, стратегия' },
  { slug: 'media', name: 'Аудио и видео', hint: 'Монтаж, озвучка, музыка, фото' },
  { slug: 'business', name: 'Бизнес и жизнь', hint: 'Бухгалтерия, юристы, ассистенты' },
  { slug: 'education', name: 'Обучение', hint: 'Репетиторы, курсы, консультации' },
];

export function statusLabel(table: Record<string, string>, code: string | undefined): string {
  if (!code) return '';
  return table[code] ?? code.replace(/_/g, ' ');
}

/** Название страны по коду — через встроенный словарь браузера. */
export function countryName(code: string | undefined): string {
  if (!code) return '';
  try {
    return new Intl.DisplayNames(['ru'], { type: 'region' }).of(code.toUpperCase()) ?? code;
  } catch {
    return code;
  }
}

export const CURRENCIES = ['RUB', 'USD', 'EUR', 'UZS', 'KZT'];
