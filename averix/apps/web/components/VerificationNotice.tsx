'use client';

import Link from 'next/link';
import styles from './verification-notice.module.css';
import { IconShield } from '@/components/ui/Icon';
import { useSession } from '@/lib/session';

/**
 * Напоминание исполнителю, что до оплачиваемой работы осталась проверка.
 *
 * Показывается только тому, кого это касается: у заказчика проверки нет, у
 * проверенного исполнителя её уже нет. Стоит там, где человек упирается в
 * запрет — в ленте, в форме отклика, в форме услуги, — чтобы объяснение
 * пришло до отказа, а не после него.
 */
export function VerificationNotice({ where }: { where?: 'feed' | 'proposal' | 'service' }) {
  const { session } = useSession();
  if (!session || !session.roles.includes('developer') || session.identity_verified) return null;

  const what =
    where === 'proposal'
      ? 'Откликнуться можно после проверки личности.'
      : where === 'service'
        ? 'Опубликовать услугу можно после проверки личности.'
        : 'Остался один шаг до работы: проверка личности.';

  return (
    <div className={styles.notice}>
      <span className={styles.icon} aria-hidden="true">
        <IconShield size={18} />
      </span>
      <div className={styles.text}>
        <p className="av-small av-strong">{what}</p>
        <p className="av-xs">
          Площадка переводит деньги живым людям и должна знать, кому. Понадобится документ и селфи —
          пара минут, один раз.
        </p>
      </div>
      <Link href="/settings/verification" className={styles.action}>
        Пройти проверку
      </Link>
    </div>
  );
}
