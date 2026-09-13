'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import styles from '../../admin.module.css';
import own from './detail.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card, SectionHeading } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ButtonLink } from '@/components/ui/Button';
import { Avatar } from '@/components/ui/Avatar';
import { Tabs } from '@/components/ui/Tabs';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconUser, IconExternal, IconShield } from '@/components/ui/Icon';
import { ApiFailure, get } from '@/lib/api';
import { money, shortDate, longDate, timeAgo } from '@/lib/format';
import { CONTRACT_STATUS, PROJECT_STATUS, countryName, roleLabel, statusLabel } from '@/lib/labels';
import {
  accountStatusLabel,
  accountTone,
  authEventLabel,
  identityStatusLabel,
  identityTone,
  paymentDirection,
  paymentStatusLabel,
} from '@/lib/admin';
import { AdminActions } from '@/components/admin/AdminActions';
import { IdentityPanel } from '@/components/admin/IdentityPanel';
import type {
  AdminPayment,
  AdminSecurity,
  AdminUser,
  AdminUserProjects,
  AuditRow,
  DeveloperProfile,
  ModerationReport,
  PortfolioCard,
} from '@/lib/types';

const TABS = [
  { key: 'overview', label: 'Обзор' },
  { key: 'profile', label: 'Профиль' },
  { key: 'portfolio', label: 'Портфолио' },
  { key: 'projects', label: 'Проекты' },
  { key: 'payments', label: 'Платежи' },
  { key: 'identity', label: 'Личность' },
  { key: 'security', label: 'Безопасность' },
  { key: 'reports', label: 'Жалобы' },
  { key: 'history', label: 'История' },
];

export default function AdminUserPage() {
  const params = useParams<{ id: string }>();
  const userID = String(params?.id ?? '');
  const [user, setUser] = useState<AdminUser | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('overview');

  const load = useCallback(async () => {
    try {
      setUser(await get<AdminUser>(`/admin/users/${userID}`));
      setError('');
    } catch (failure) {
      setError(
        failure instanceof ApiFailure && failure.status === 403
          ? 'Нет права users.view. Его выдаёт администратор поимённо.'
          : 'Не получилось открыть карточку.',
      );
    }
  }, [userID]);

  useEffect(() => {
    if (userID) void load();
  }, [userID, load]);

  if (error) {
    return (
      <>
        <TopBar back="/admin/users" title="Пользователь" />
        <div className={`av-page ${styles.shell}`}>
          <EmptyState icon={<IconShield size={20} />} title="Доступ закрыт" description={error} />
        </div>
      </>
    );
  }

  if (!user) {
    return (
      <>
        <TopBar back="/admin/users" title="Пользователь" />
        <div className={`av-page ${styles.shell}`}>
          <SkeletonList count={3} />
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar back="/admin/users" title={user.full_name} />
      <div className={`av-page av-stack ${styles.shell}`}>
        <Card>
          <div className={own.header}>
            <Avatar src={user.photo_url} name={user.full_name} size={64} verified={user.identity_verified} />
            <div className={`av-grow ${own.headerText}`}>
              <p className="av-strong">
                {user.full_name} <span className="av-faint">@{user.username}</span>
              </p>
              <p className="av-small av-muted">{user.email}</p>
              {user.phone ? <p className="av-small av-muted">{user.phone}</p> : null}
              <p className="av-xs av-faint">
                {user.reference} · зарегистрирован {longDate(user.created_at)}
                {user.last_seen_at ? ` · заходил ${timeAgo(user.last_seen_at)}` : ''}
              </p>
              <div className={own.badges}>
                {user.roles.map((role) => (
                  <Badge key={role} tone="brand" size="sm">
                    {roleLabel(role)}
                  </Badge>
                ))}
                <Badge tone={accountTone(user.status)} size="sm">
                  {accountStatusLabel(user.status)}
                </Badge>
                <Badge tone={identityTone(user.identity_status)} size="sm">
                  {identityStatusLabel(user.identity_status)}
                </Badge>
                <Badge tone={user.email_verified ? 'success' : 'warning'} size="sm">
                  {user.email_verified ? 'Почта подтверждена' : 'Почта не подтверждена'}
                </Badge>
              </div>
            </div>
          </div>
          {user.suspended_reason ? (
            <p className={styles.alert} style={{ marginTop: 'var(--av-space-4)' }}>
              {accountStatusLabel(user.status)}: {user.suspended_reason}
              {user.suspended_until ? ` (до ${shortDate(user.suspended_until)})` : ''}
            </p>
          ) : null}
        </Card>

        <Tabs items={TABS} active={tab} onChange={setTab} ariaLabel="Разделы карточки" />

        {tab === 'overview' ? <Overview user={user} onChanged={load} /> : null}
        {tab === 'profile' ? <Profile user={user} /> : null}
        {tab === 'portfolio' ? <Portfolio username={user.username} /> : null}
        {tab === 'projects' ? <Projects userID={userID} /> : null}
        {tab === 'payments' ? <Payments userID={userID} /> : null}
        {tab === 'identity' ? (
          <IdentityPanel userID={userID} fullName={user.full_name} roles={user.roles} onChanged={load} />
        ) : null}
        {tab === 'security' ? <Security userID={userID} /> : null}
        {tab === 'reports' ? <Reports userID={userID} /> : null}
        {tab === 'history' ? <History userID={userID} /> : null}
      </div>
    </>
  );
}

function Overview({ user, onChanged }: { user: AdminUser; onChanged: () => void }) {
  return (
    <div className="av-stack">
      <Card>
        <div className={styles.tiles}>
          <Fact label="Заказов размещено" value={user.projects_posted ?? 0} />
          <Fact label="Открыто сейчас" value={user.projects_open ?? 0} />
          <Fact label="Сделок всего" value={user.contracts_total ?? 0} />
          <Fact label="В работе" value={user.contracts_active ?? 0} />
          <Fact label="Завершено" value={user.contracts_completed ?? 0} />
          <Fact label="Споров" value={user.disputes ?? 0} />
          <Fact label="Жалоб на него" value={user.reports_against ?? 0} />
          <Fact label="Жалоб от него" value={user.reports_filed ?? 0} />
          <Fact label="Предупреждений" value={user.warnings ?? 0} />
          <Fact label="Активных сеансов" value={user.active_sessions ?? 0} />
        </div>
      </Card>
      <AdminActions user={user} onChanged={onChanged} />
    </div>
  );
}

function Fact({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.tile}>
      <span className={styles.tileLabel}>{label}</span>
      <span className={styles.tileValue}>{value}</span>
    </div>
  );
}

function Pair({ label, value }: { label: string; value: string }) {
  return (
    <div className={own.pair}>
      <span className={own.pairLabel}>{label}</span>
      <span className={own.pairValue}>{value || '—'}</span>
    </div>
  );
}

function Profile({ user }: { user: AdminUser }) {
  const isFreelancer = user.roles.includes('developer');
  return (
    <Card>
      <SectionHeading title="Учётные данные" />
      <div className={own.pairs}>
        <Pair label="Полное имя" value={user.full_name} />
        <Pair label="Логин" value={`@${user.username}`} />
        <Pair label="Почта" value={user.email} />
        <Pair label="Телефон" value={user.phone ?? ''} />
        <Pair label="Страна" value={countryName(user.country_code)} />
        <Pair label="Город" value={user.city ?? ''} />
        <Pair label="Часовой пояс" value={user.timezone ?? ''} />
        <Pair label="Язык интерфейса" value={user.locale ?? ''} />
        <Pair label="Профессиональный статус" value={user.professional_status ?? ''} />
        <Pair label="GitHub" value={user.github_connected ? 'Подключён' : 'Не подключён'} />
        <Pair label="Последний вход" value={user.last_login_at ? longDate(user.last_login_at) : ''} />
        <Pair label="Пароль менялся" value={user.password_changed_at ? longDate(user.password_changed_at) : ''} />
      </div>
      <p className={own.note} style={{ marginTop: 'var(--av-space-4)' }}>
        Номер документа, его изображения и платёжные реквизиты здесь не показываются — они живут только во
        вкладке «Личность», за отдельным правом и повторным вводом пароля.
      </p>
      <div className="av-row" style={{ marginTop: 'var(--av-space-4)' }}>
        {isFreelancer ? (
          <ButtonLink
            href={`/developers/${user.username}`}
            variant="secondary"
            size="sm"
            icon={<IconExternal size={16} />}
          >
            Открыть публичный профиль
          </ButtonLink>
        ) : (
          <p className={own.note}>У заказчика нет публичной страницы: его профиль видят только исполнители в сделке.</p>
        )}
      </div>
    </Card>
  );
}

function Portfolio({ username }: { username: string }) {
  const [items, setItems] = useState<PortfolioCard[] | null>(null);
  const [profile, setProfile] = useState<DeveloperProfile | null>(null);

  useEffect(() => {
    get<PortfolioCard[]>(`/developers/${username}/portfolio`)
      .then(setItems)
      .catch(() => setItems([]));
    get<DeveloperProfile>(`/developers/${username}`)
      .then(setProfile)
      .catch(() => setProfile(null));
  }, [username]);

  if (items === null) return <SkeletonList count={3} />;
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<IconUser size={20} />}
        title="Портфолио пустое"
        description={profile ? 'Человек ещё ничего не опубликовал.' : 'У этого аккаунта нет профиля исполнителя.'}
      />
    );
  }

  return (
    <Card>
      <SectionHeading
        title="Работы"
        count={items.length}
        action={
          <Link href={`/developers/${username}`} className="av-small">
            Открыть профиль
          </Link>
        }
      />
      {items.map((item) => (
        <div key={item.id} className={own.listRow}>
          <div className="av-grow">
            <p className="av-strong">{item.title}</p>
            {item.excerpt ? <p className={styles.excerpt}>{item.excerpt}</p> : null}
            <p className="av-xs av-faint">
              {item.kind === 'commercial' ? 'Коммерческий проект' : 'Личный проект'}
              {item.completed_on ? ` · ${shortDate(item.completed_on)}` : ''}
            </p>
          </div>
          {item.is_featured ? (
            <Badge tone="brand" size="sm">
              В витрине
            </Badge>
          ) : null}
        </div>
      ))}
    </Card>
  );
}

function Projects({ userID }: { userID: string }) {
  const [data, setData] = useState<AdminUserProjects | null>(null);
  useEffect(() => {
    get<AdminUserProjects>(`/admin/users/${userID}/projects`)
      .then(setData)
      .catch(() => setData({ posted: [], contracts: [] }));
  }, [userID]);

  if (!data) return <SkeletonList count={3} />;

  return (
    <div className="av-stack">
      <Card>
        <SectionHeading title="Размещённые заказы" />
        {data.posted.length === 0 ? (
          <p className="av-small av-muted">Ни одного.</p>
        ) : (
          data.posted.map((project) => (
            <div key={project.id} className={own.listRow}>
              <div className="av-grow">
                <Link href={`/projects/${project.slug}`} className="av-strong">
                  {project.title}
                </Link>
                <p className="av-xs av-faint">
                  {project.reference} · {statusLabel(PROJECT_STATUS, project.status)} · откликов:{' '}
                  {project.proposals_count} · {shortDate(project.created_at)}
                </p>
              </div>
              <span className={own.amount}>{project.budget_display ?? ''}</span>
            </div>
          ))
        )}
      </Card>

      <Card>
        <SectionHeading title="Сделки" />
        {data.contracts.length === 0 ? (
          <p className="av-small av-muted">Ни одной.</p>
        ) : (
          data.contracts.map((contract) => (
            <div key={contract.id} className={own.listRow}>
              <div className="av-grow">
                <Link href={`/contracts/${contract.id}`} className="av-strong">
                  {contract.title}
                </Link>
                <p className="av-xs av-faint">
                  {contract.reference} · {roleLabel(contract.role)} · вторая сторона: {contract.counterparty} ·{' '}
                  {statusLabel(CONTRACT_STATUS, contract.status)}
                </p>
              </div>
              <span className={own.amount}>
                {contract.amount_minor !== undefined && contract.currency
                  ? money(contract.amount_minor, contract.currency)
                  : ''}
              </span>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}

function Payments({ userID }: { userID: string }) {
  const [rows, setRows] = useState<AdminPayment[] | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    get<AdminPayment[]>(`/admin/users/${userID}/payments`)
      .then(setRows)
      .catch((failure) => {
        setDenied(failure instanceof ApiFailure && failure.status === 403);
        setRows([]);
      });
  }, [userID]);

  if (rows === null) return <SkeletonList count={3} />;
  if (denied) {
    return (
      <EmptyState
        icon={<IconShield size={20} />}
        title="Платежи закрыты"
        description="Нужно право payments.view."
      />
    );
  }
  if (rows.length === 0) {
    return <EmptyState icon={<IconUser size={20} />} title="Движений денег не было" description="" />;
  }

  return (
    <Card>
      {rows.map((row) => (
        <div key={row.id} className={own.listRow}>
          <div className="av-grow">
            <p className="av-strong">
              {paymentDirection(row.direction)} · {paymentStatusLabel(row.status)}
            </p>
            <p className="av-xs av-faint">
              {row.reference}
              {row.contract_reference ? ` · сделка ${row.contract_reference}` : ''} · {row.provider} ·{' '}
              {shortDate(row.created_at)}
              {row.destination ? ` · ${row.destination}` : ''}
            </p>
            {row.refunded_minor > 0 ? (
              <p className="av-xs av-faint">Возвращено: {money(row.refunded_minor, row.currency)}</p>
            ) : null}
          </div>
          <span className={own.amount}>{money(row.amount_minor, row.currency)}</span>
        </div>
      ))}
      <p className={own.note} style={{ marginTop: 'var(--av-space-3)' }}>
        Реквизиты показываются только в замаскированном виде. Полного номера карты или счёта площадка не
        хранит вовсе.
      </p>
    </Card>
  );
}

function Security({ userID }: { userID: string }) {
  const [data, setData] = useState<AdminSecurity | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    get<AdminSecurity>(`/admin/users/${userID}/security`)
      .then(setData)
      .catch((failure) => {
        setDenied(failure instanceof ApiFailure && failure.status === 403);
        setData(null);
      });
  }, [userID]);

  if (denied) {
    return (
      <EmptyState icon={<IconShield size={20} />} title="Раздел закрыт" description="Нужно право security.view." />
    );
  }
  if (!data) return <SkeletonList count={3} />;

  return (
    <div className="av-stack">
      <Card>
        <SectionHeading title="Вход в аккаунт" />
        <div className={own.pairs}>
          <Pair
            label="Двухфакторная защита"
            value={data.two_factor === 'not_available' ? 'В продукте пока нет' : data.two_factor}
          />
          <Pair label="Пароль менялся" value={data.password_changed_at ? longDate(data.password_changed_at) : ''} />
          <Pair label="Неудачных попыток подряд" value={String(data.failed_logins)} />
          <Pair label="Заблокирован до" value={data.locked_until ? longDate(data.locked_until) : ''} />
          <Pair label="GitHub" value={data.github_connected ? data.github_login || 'Подключён' : 'Не подключён'} />
        </div>
        <p className={own.note} style={{ marginTop: 'var(--av-space-3)' }}>
          Ни пароля, ни его хеша, ни кодов подтверждения здесь нет и быть не может.
        </p>
      </Card>

      <Card>
        <SectionHeading title="Активные сеансы" />
        {data.sessions.length === 0 ? (
          <p className="av-small av-muted">Ни одного.</p>
        ) : (
          data.sessions.map((session) => (
            <div key={session.id} className={own.listRow}>
              <div className="av-grow">
                <p className="av-small av-strong">{roleLabel(session.role)}</p>
                <p className="av-xs av-faint">
                  {session.user_agent || 'Браузер не назвался'}
                  {session.ip ? ` · ${session.ip}` : ''}
                </p>
              </div>
              <span className="av-xs av-faint">{timeAgo(session.last_used_at)}</span>
            </div>
          ))
        )}
      </Card>

      <Card>
        <SectionHeading title="Последние события" />
        {data.events.length === 0 ? (
          <p className="av-small av-muted">Пусто.</p>
        ) : (
          data.events.map((event, index) => (
            <div key={`${event.created_at}-${index}`} className={own.listRow}>
              <div className="av-grow">
                <p className="av-small">
                  {authEventLabel(event.action)}
                  {event.outcome && event.outcome !== 'success' ? ` — ${event.outcome}` : ''}
                </p>
                <p className="av-xs av-faint">
                  {event.ip ? `${event.ip} · ` : ''}
                  {event.detail ?? ''}
                </p>
              </div>
              <span className="av-xs av-faint">{timeAgo(event.created_at)}</span>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}

function Reports({ userID }: { userID: string }) {
  const [rows, setRows] = useState<ModerationReport[] | null>(null);
  useEffect(() => {
    get<ModerationReport[]>(`/admin/moderation/users/${userID}/reports`)
      .then(setRows)
      .catch(() => setRows([]));
  }, [userID]);

  if (rows === null) return <SkeletonList count={3} />;
  if (rows.length === 0) {
    return <EmptyState icon={<IconUser size={20} />} title="Жалоб нет" description="Ни на него, ни от него." />;
  }

  return (
    <Card>
      {rows.map((report) => (
        <div key={report.id} className={own.listRow}>
          <div className="av-grow">
            <p className="av-small av-strong">
              {report.direction === 'filed' ? 'Пожаловался сам' : 'Жалоба на него'} · {report.reason_label}
            </p>
            {report.detail ? <p className={styles.excerpt}>{report.detail}</p> : null}
            <p className="av-xs av-faint">
              {report.preview?.title ?? report.subject_type} · {shortDate(report.created_at)}
              {report.resolution ? ` · итог: ${report.resolution}` : ''}
            </p>
          </div>
          <Badge tone={report.status === 'open' ? 'warning' : 'neutral'} size="sm">
            {report.status === 'open' ? 'Открыта' : 'Закрыта'}
          </Badge>
        </div>
      ))}
    </Card>
  );
}

function History({ userID }: { userID: string }) {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    get<AuditRow[]>(`/admin/users/${userID}/history`)
      .then(setRows)
      .catch((failure) => {
        setDenied(failure instanceof ApiFailure && failure.status === 403);
        setRows([]);
      });
  }, [userID]);

  if (rows === null) return <SkeletonList count={3} />;
  if (denied) {
    return <EmptyState icon={<IconShield size={20} />} title="Журнал закрыт" description="Нужно право audit.read." />;
  }
  if (rows.length === 0) {
    return <EmptyState icon={<IconUser size={20} />} title="Действий не было" description="" />;
  }

  return (
    <Card>
      {rows.map((row) => (
        <div key={row.id} className={styles.auditRow}>
          <span className="av-strong">{row.action}</span>
          <span className="av-xs av-faint">
            {row.actor_name || 'система'} · {longDate(row.created_at)}
            {row.ip ? ` · ${row.ip}` : ''}
          </span>
          {row.detail ? <span className="av-xs av-muted">{row.detail}</span> : null}
        </div>
      ))}
      <p className={own.note} style={{ marginTop: 'var(--av-space-3)' }}>
        Каждое действие сотрудника записано здесь: кто, что и когда. Запись из журнала не удаляется.
      </p>
    </Card>
  );
}
