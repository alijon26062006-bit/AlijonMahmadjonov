'use client';

import { useEffect, useState } from 'react';
import styles from './admin.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { ButtonLink } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconAlert } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { money } from '@/lib/format';
import type { AdminOverview } from '@/lib/types';

const LINKS = [
  { href: '/admin/moderation', label: 'Модерация' },
  { href: '/admin/disputes', label: 'Споры' },
  { href: '/admin/payments', label: 'Платежи' },
  { href: '/admin/users', label: 'Пользователи' },
  { href: '/admin/identity', label: 'Проверка личности' },
  { href: '/admin/settings', label: 'Настройки платформы' },
  { href: '/admin/audit', label: 'Журнал действий' },
];

export default function AdminOverviewPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    get<AdminOverview>('/admin/overview')
      .then(setOverview)
      .catch(() => setFailed(true));
  }, []);

  if (failed) {
    return (
      <>
        <TopBar title="Панель" />
        <div className="av-page">
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="Раздел недоступен"
            description="Эта панель открыта администраторам и модераторам."
          />
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title="Панель" />
      <div className={`av-page av-stack ${styles.shell}`}>
        <div className={styles.nav}>
          {LINKS.map((link) => (
            <ButtonLink key={link.href} href={link.href} variant="secondary" size="sm">
              {link.label}
            </ButtonLink>
          ))}
        </div>

        {!overview ? (
          <Skeleton height={220} />
        ) : (
          <>
            {overview.attention.moderation_pending +
            overview.attention.open_reports +
            overview.attention.pending_payments +
            overview.marketplace.open_disputes >
            0 ? (
              <section className="av-stack-sm">
                <h2 className="av-lg av-strong">Требует внимания</h2>
                <div className={styles.tiles}>
                  <Tile
                    label="На модерации"
                    value={overview.attention.moderation_pending}
                    note={overview.attention.moderation_escalated ? `${overview.attention.moderation_escalated} передано выше` : 'очередь'}
                    warn={overview.attention.moderation_pending > 0}
                  />
                  <Tile label="Жалобы" value={overview.attention.open_reports} note="открытых" warn={overview.attention.open_reports > 0} />
                  <Tile label="Платежи" value={overview.attention.pending_payments} note="ждут подтверждения" warn={overview.attention.pending_payments > 0} />
                  <Tile label="Споры" value={overview.marketplace.open_disputes} note="открытых" warn={overview.marketplace.open_disputes > 0} />
                </div>
              </section>
            ) : null}

            <section className="av-stack-sm">
              <h2 className="av-lg av-strong">Люди</h2>
              <div className={styles.tiles}>
                <Tile label="Всего" value={overview.users.total} note={`+${overview.users.new_this_week} за неделю`} />
                <Tile label="Заказчики" value={overview.users.clients} note="" />
                <Tile label="Исполнители" value={overview.users.freelancers} note={`${overview.users.listed_freelancers} в каталоге`} />
                <Tile label="Заблокированы" value={overview.users.suspended} note="" />
              </div>
            </section>

            <section className="av-stack-sm">
              <h2 className="av-lg av-strong">Площадка</h2>
              <div className={styles.tiles}>
                <Tile label="Открытые заказы" value={overview.marketplace.open_projects} note="" />
                <Tile label="Услуги" value={overview.marketplace.active_services} note="опубликовано" />
                <Tile label="Сделки в работе" value={overview.marketplace.active_contracts} note="" />
                <Tile label="Завершено за месяц" value={overview.marketplace.completed_this_month} note="" />
                <Tile label="Отклики за неделю" value={overview.marketplace.proposals_this_week} note="" />
                <Tile label="Отзывы" value={overview.marketplace.published_reviews} note="опубликовано" />
              </div>
            </section>

            {overview.money?.length ? (
              <Card>
                <h2 className="av-lg av-strong">Оборот за месяц</h2>
                {overview.money.map((row) => (
                  <div key={row.currency} className={styles.row}>
                    <div>
                      <p className="av-strong">{money(row.gross_minor, row.currency)}</p>
                      <p className="av-xs av-faint">{row.contracts} завершённых сделок</p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <p className="av-small av-strong">{money(row.fee_minor, row.currency)}</p>
                      <p className="av-xs av-faint">комиссия платформы</p>
                    </div>
                  </div>
                ))}
              </Card>
            ) : null}

            <Card>
              <h2 className="av-lg av-strong">Интеграции</h2>
              <div className="av-stack-sm">
                {Object.entries(overview.integrations ?? {}).map(([key, enabled]) => (
                  <div key={key} className={styles.row}>
                    <span className="av-small">{INTEGRATION_LABEL[key] ?? key}</span>
                    <span className={enabled ? 'av-small' : 'av-small av-faint'}>
                      {enabled ? 'настроено' : 'не настроено'}
                    </span>
                  </div>
                ))}
              </div>
              <p className="av-xs av-faint">
                В чат сотрудников уходит только строка и ссылка на панель: документы туда не отправляются
                ни при какой настройке.
              </p>
              <p className="av-xs av-faint">Версия сборки: {overview.version}</p>
            </Card>
          </>
        )}
      </div>
    </>
  );
}

const INTEGRATION_LABEL: Record<string, string> = {
  email: 'Почта (SMTP)',
  push: 'Push-уведомления',
  github: 'GitHub',
  ai: 'Сервис анализа',
  payments: 'Реквизиты для переводов',
  storage: 'Хранилище файлов',
  telegram: 'Чат сотрудников (Telegram)',
};

function Tile({ label, value, note, warn }: { label: string; value: number; note: string; warn?: boolean }) {
  return (
    <div className={[styles.tile, warn ? styles.attention : ''].join(' ')}>
      <span className={styles.tileLabel}>{label}</span>
      <span className={styles.tileValue}>{value}</span>
      {note ? <span className={styles.tileNote}>{note}</span> : null}
    </div>
  );
}
