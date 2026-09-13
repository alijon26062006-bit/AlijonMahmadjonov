// Words the admin panel uses about an account.
//
// One place, because a status shown as «Заблокирован» on one screen and
// «Приостановлен» on the next is how a support person suspends the wrong
// person: приостановка снимается сама по сроку, блокировка — нет.

type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info' | 'verified';

export function accountStatusLabel(status?: string): string {
  switch (status) {
    case 'active':
      return 'Активен';
    case 'pending':
      return 'Не подтверждён';
    case 'suspended':
      return 'Приостановлен';
    case 'banned':
      return 'Заблокирован';
    case 'deactivated':
      return 'Деактивирован';
    default:
      return status ?? '—';
  }
}

export function accountTone(status?: string): Tone {
  switch (status) {
    case 'active':
      return 'success';
    case 'suspended':
      return 'warning';
    case 'banned':
      return 'danger';
    default:
      return 'neutral';
  }
}

export function identityStatusLabel(status?: string): string {
  switch (status) {
    case 'draft':
      return 'Документы не отправлены';
    case 'submitted':
      return 'Ждёт проверки';
    case 'under_review':
      return 'На проверке';
    case 'resubmit_requested':
      return 'Просят переснять';
    case 'approved':
      return 'Личность подтверждена';
    case 'rejected':
      return 'Отказано';
    case 'suspended':
      return 'Проверка приостановлена';
    case 'expired':
      return 'Проверка истекла';
    case 'none':
    case undefined:
    case '':
      return 'Проверка не начиналась';
    default:
      return status;
  }
}

export function identityTone(status?: string): Tone {
  switch (status) {
    case 'approved':
      return 'verified';
    case 'submitted':
    case 'under_review':
      return 'info';
    case 'resubmit_requested':
      return 'warning';
    case 'rejected':
    case 'suspended':
      return 'danger';
    default:
      return 'neutral';
  }
}

/** Что за движение денег: одно слово вместо кода направления. */
export function paymentDirection(direction: string): string {
  switch (direction) {
    case 'charge':
      return 'Оплата';
    case 'payout':
      return 'Выплата';
    case 'refund':
      return 'Возврат';
    default:
      return direction;
  }
}

export function paymentStatusLabel(status: string): string {
  switch (status) {
    case 'created':
      return 'Создан';
    case 'requires_action':
      return 'Ждёт действия';
    case 'processing':
      return 'В обработке';
    case 'held':
      return 'На удержании';
    case 'succeeded':
      return 'Проведён';
    case 'failed':
      return 'Не прошёл';
    case 'cancelled':
      return 'Отменён';
    case 'refunded':
      return 'Возвращён';
    case 'partially_refunded':
      return 'Возвращён частично';
    default:
      return status;
  }
}

/** Строка журнала входов: действие человеческими словами. */
export function authEventLabel(action: string): string {
  switch (action) {
    case 'auth.login':
    case 'login':
      return 'Вход';
    case 'auth.login_failed':
      return 'Неудачный вход';
    case 'auth.logout':
      return 'Выход';
    case 'auth.password_changed':
      return 'Смена пароля';
    case 'auth.password_reset_requested':
      return 'Запрос на сброс пароля';
    case 'auth.password_reset':
      return 'Сброс пароля';
    case 'auth.email_verified':
      return 'Подтверждение почты';
    case 'auth.role_switched':
      return 'Смена роли';
    default:
      return action;
  }
}
