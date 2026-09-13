'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './settings.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Field';
import { Tabs } from '@/components/ui/Tabs';
import { Skeleton } from '@/components/ui/Skeleton';
import { ApiFailure, del, get, list, post, put, patch } from '@/lib/api';
import { timeAgo } from '@/lib/format';
import { roleLabel } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type {
  AccountSettings,
  AuthSession,
  GitHubStatus,
  NotificationPreference,
  NotificationPreferenceGroup,
} from '@/lib/types';

const TABS = [
  { key: 'account', label: 'Аккаунт' },
  { key: 'security', label: 'Безопасность' },
  { key: 'notifications', label: 'Уведомления' },
  { key: 'integrations', label: 'Интеграции' },
];

export default function SettingsPage() {
  const router = useRouter();
  const { session, refresh, signOut, switchRole } = useSession();
  const [tab, setTab] = useState('account');
  const [account, setAccount] = useState<AccountSettings | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash === '#notifications') setTab('notifications');
    if (typeof window !== 'undefined' && window.location.hash === '#roles') setTab('account');
  }, []);

  const load = useCallback(() => {
    get<AccountSettings>('/account')
      .then(setAccount)
      .catch(() => undefined);
  }, []);

  useEffect(() => load(), [load]);

  return (
    <>
      <TopBar title="Настройки" />
      <div className={`av-page av-stack ${styles.shell}`}>
        <Tabs items={TABS} active={tab} onChange={setTab} ariaLabel="Разделы настроек" />

        {!account ? (
          <Skeleton height={220} />
        ) : tab === 'account' ? (
          <>
            <AccountCard account={account} onSaved={(next) => setAccount(next)} />
            <RolesCard
              account={account}
              onAdded={async () => {
                await refresh();
                load();
              }}
              onSwitch={async (role) => {
                await switchRole(role);
                router.push(role === 'client' ? '/dashboard' : '/feed');
              }}
            />
            <DangerCard
              onDone={async () => {
                await signOut();
                router.replace('/');
              }}
            />
          </>
        ) : tab === 'security' ? (
          <>
            <EmailCard account={account} onChanged={load} />
            <PasswordCard />
            <SessionsCard />
          </>
        ) : tab === 'notifications' ? (
          <NotificationsCard />
        ) : (
          <IntegrationsCard isDeveloper={session?.roles.includes('developer') ?? false} />
        )}
      </div>
    </>
  );
}

function AccountCard({ account, onSaved }: { account: AccountSettings; onSaved: (next: AccountSettings) => void }) {
  const [form, setForm] = useState({
    full_name: account.full_name,
    headline: account.headline ?? '',
    timezone: account.timezone,
    locale: account.locale,
    country_code: account.country_code ?? '',
    city: account.city ?? '',
  });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Профиль аккаунта</h2>
      <div className="av-stack">
        {message ? (
          <p className={styles.alert} role="alert">
            {message}
          </p>
        ) : null}
        {saved ? <p className={styles.ok}>Сохранено.</p> : null}

        <Input label="Имя пользователя" value={`@${account.username}`} disabled readOnly hint="Имя пользователя изменить нельзя — на него ссылаются ваши работы и отзывы." />
        <Input
          label="Имя и фамилия"
          value={form.full_name}
          error={fields.full_name}
          onChange={(event) => setForm({ ...form, full_name: event.target.value })}
        />
        <Input
          label="Краткое описание"
          optional
          value={form.headline}
          error={fields.headline}
          onChange={(event) => setForm({ ...form, headline: event.target.value })}
        />
        <div className="av-row">
          <Input
            label="Код страны"
            optional
            maxLength={2}
            value={form.country_code}
            error={fields.country_code}
            onChange={(event) => setForm({ ...form, country_code: event.target.value.toUpperCase() })}
          />
          <Input
            label="Город"
            optional
            value={form.city}
            error={fields.city}
            onChange={(event) => setForm({ ...form, city: event.target.value })}
          />
        </div>
        <Input
          label="Часовой пояс"
          value={form.timezone}
          error={fields.timezone}
          onChange={(event) => setForm({ ...form, timezone: event.target.value })}
        />
        <Select label="Язык интерфейса" value={form.locale} onChange={(event) => setForm({ ...form, locale: event.target.value })}>
          <option value="ru">Русский</option>
          <option value="uz">Oʻzbekcha</option>
          <option value="en">English</option>
        </Select>

        <Button
          loading={busy}
          onClick={async () => {
            setBusy(true);
            setFields({});
            setMessage('');
            setSaved(false);
            try {
              onSaved(await patch<AccountSettings>('/account', form));
              setSaved(true);
            } catch (error) {
              if (error instanceof ApiFailure) {
                setFields(error.fields);
                setMessage(Object.keys(error.fields).length ? '' : error.message);
              } else {
                setMessage('Не удалось сохранить.');
              }
            } finally {
              setBusy(false);
            }
          }}
        >
          Сохранить
        </Button>
      </div>
    </Card>
  );
}

function RolesCard({
  account,
  onAdded,
  onSwitch,
}: {
  account: AccountSettings;
  onAdded: () => void;
  onSwitch: (role: 'client' | 'developer') => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const missing = (['client', 'developer'] as const).filter((role) => !account.roles.includes(role));

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Роли</h2>
      <div className="av-stack-sm">
        <div className="av-row av-wrap">
          {account.roles.map((role) => (
            <Badge key={role} tone="brand" size="sm">
              {roleLabel(role)}
            </Badge>
          ))}
        </div>
        <p className="av-small av-muted">
          Один аккаунт может и заказывать, и выполнять работу. Стороны не смешиваются: у каждой свой
          интерфейс, свои сделки и свои деньги.
        </p>
        {error ? <p className={styles.alert}>{error}</p> : null}
        <div className="av-row av-wrap">
          {missing.map((role) => (
            <Button
              key={role}
              variant="secondary"
              loading={busy}
              onClick={async () => {
                setBusy(true);
                setError('');
                try {
                  await post('/auth/role/add', { role });
                  onAdded();
                  onSwitch(role);
                } catch (failure) {
                  setError(failure instanceof ApiFailure ? failure.message : 'Не получилось добавить роль.');
                } finally {
                  setBusy(false);
                }
              }}
            >
              Стать: {roleLabel(role)}
            </Button>
          ))}
          {account.roles.includes('developer') ? (
            <ButtonLink href="/onboarding" variant="ghost">
              Анкета исполнителя
            </ButtonLink>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function EmailCard({ account, onChanged }: { account: AccountSettings; onChanged: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [ok, setOk] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Электронная почта</h2>
      <div className="av-stack">
        <div className="av-row-between">
          <span>{account.email}</span>
          {account.email_verified ? (
            <Badge tone="success" size="sm">
              Подтверждена
            </Badge>
          ) : (
            <Badge tone="warning" size="sm">
              Не подтверждена
            </Badge>
          )}
        </div>

        {!account.email_verified ? (
          <Button
            variant="secondary"
            size="sm"
            loading={busy}
            onClick={async () => {
              setBusy(true);
              setOk('');
              setMessage('');
              try {
                await post('/auth/email/resend');
                setOk('Письмо отправлено. Проверьте почту.');
              } catch (error) {
                setMessage(error instanceof ApiFailure ? error.message : 'Не удалось отправить письмо.');
              } finally {
                setBusy(false);
              }
            }}
          >
            Отправить письмо ещё раз
          </Button>
        ) : null}

        {account.pending_email ? (
          <p className={styles.notice}>
            Ждём подтверждения нового адреса: {account.pending_email}. Пока не подтвердите, вход
            остаётся по старому.
          </p>
        ) : null}

        {message ? <p className={styles.alert}>{message}</p> : null}
        {ok ? <p className={styles.ok}>{ok}</p> : null}

        <Input
          label="Новый адрес"
          type="email"
          optional
          value={email}
          error={fields.new_email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input
          label="Текущий пароль"
          type="password"
          autoComplete="current-password"
          value={password}
          error={fields.password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button
          variant="secondary"
          loading={busy}
          disabled={!email.trim() || !password}
          onClick={async () => {
            setBusy(true);
            setMessage('');
            setOk('');
            setFields({});
            try {
              await post('/account/email', { new_email: email.trim(), password });
              setOk('Мы отправили письмо на новый адрес. Ссылка в нём завершит смену.');
              setEmail('');
              setPassword('');
              onChanged();
            } catch (error) {
              if (error instanceof ApiFailure) {
                setFields(error.fields);
                setMessage(Object.keys(error.fields).length ? '' : error.message);
              } else {
                setMessage('Не удалось запросить смену адреса.');
              }
            } finally {
              setBusy(false);
            }
          }}
        >
          Сменить адрес
        </Button>
      </div>
    </Card>
  );
}

function PasswordCard() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Пароль</h2>
      <div className="av-stack">
        {message ? <p className={styles.alert}>{message}</p> : null}
        {ok ? <p className={styles.ok}>Пароль изменён. Другие сеансы завершены.</p> : null}
        <Input
          label="Текущий пароль"
          type="password"
          autoComplete="current-password"
          value={current}
          error={fields.current_password}
          onChange={(event) => setCurrent(event.target.value)}
        />
        <Input
          label="Новый пароль"
          type="password"
          autoComplete="new-password"
          hint="Не короче 12 символов."
          value={next}
          error={fields.new_password}
          onChange={(event) => setNext(event.target.value)}
        />
        <Button
          loading={busy}
          disabled={!current || next.length < 12}
          onClick={async () => {
            setBusy(true);
            setMessage('');
            setOk(false);
            setFields({});
            try {
              await post('/auth/password/change', { current_password: current, new_password: next });
              setOk(true);
              setCurrent('');
              setNext('');
            } catch (error) {
              if (error instanceof ApiFailure) {
                setFields(error.fields);
                setMessage(Object.keys(error.fields).length ? '' : error.message);
              } else {
                setMessage('Не удалось сменить пароль.');
              }
            } finally {
              setBusy(false);
            }
          }}
        >
          Сменить пароль
        </Button>
      </div>
    </Card>
  );
}

function SessionsCard() {
  const [sessions, setSessions] = useState<AuthSession[] | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    get<AuthSession[]>('/auth/sessions')
      .then((data) => setSessions(data ?? []))
      .catch(() => setSessions([]));
  }, []);

  useEffect(() => load(), [load]);

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Активные сеансы</h2>
      {sessions === null ? (
        <Skeleton height={80} />
      ) : (
        <div className="av-stack-sm">
          {sessions.map((item) => (
            <div key={item.id} className={styles.session}>
              <div className="av-grow">
                <p className="av-small av-strong">
                  {item.user_agent || 'Неизвестное устройство'}
                  {item.current ? ' · этот' : ''}
                </p>
                <p className="av-xs av-faint">
                  {roleLabel(item.role)} · {item.ip || 'IP скрыт'} · активен {timeAgo(item.last_used_at)}
                </p>
              </div>
              {!item.current ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    await del(`/auth/sessions/${item.id}`);
                    load();
                  }}
                >
                  Завершить
                </Button>
              ) : null}
            </div>
          ))}
          <Button
            variant="secondary"
            size="sm"
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await post('/auth/logout-everywhere');
                window.location.href = '/login';
              } finally {
                setBusy(false);
              }
            }}
          >
            Выйти на всех устройствах
          </Button>
        </div>
      )}
    </Card>
  );
}

function NotificationsCard() {
  const [groups, setGroups] = useState<NotificationPreferenceGroup[] | null>(null);
  const [emailConfigured, setEmailConfigured] = useState(true);
  const [pushConfigured, setPushConfigured] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    list<NotificationPreferenceGroup[]>('/notifications/preferences')
      .then((response) => {
        setGroups(response.data ?? []);
        setEmailConfigured(Boolean(response.meta?.email_configured));
        setPushConfigured(Boolean(response.meta?.push_configured));
      })
      .catch(() => setGroups([]));
  }, []);

  function toggle(type: string, channel: 'in_app' | 'email' | 'push', value: boolean) {
    setGroups((current) =>
      current
        ? current.map((group) => ({
            ...group,
            preferences: group.preferences.map((preference) =>
              preference.type === type ? { ...preference, [channel]: value } : preference,
            ),
          }))
        : current,
    );
  }

  async function save() {
    if (!groups) return;
    setBusy(true);
    setSaved(false);
    const flat: NotificationPreference[] = groups.flatMap((group) => group.preferences);
    try {
      setGroups(await put<NotificationPreferenceGroup[]>('/notifications/preferences', { preferences: flat }));
      setSaved(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className={styles.sectionTitle}>Что присылать</h2>
      {groups === null ? (
        <Skeleton height={200} />
      ) : (
        <div className="av-stack">
          {!emailConfigured ? (
            <p className={styles.notice}>
              Почтовый сервер ещё не настроен администратором — письма пока не уходят. Уведомления
              внутри платформы работают.
            </p>
          ) : null}
          {!pushConfigured ? (
            <p className="av-small av-faint">
              Push-уведомления не настроены на этой площадке: ключи не заданы, и переключатель ничего
              не изменит, пока их не добавят.
            </p>
          ) : null}
          {saved ? <p className={styles.ok}>Сохранено.</p> : null}

          <div className={styles.prefTable}>
            <div className={styles.prefHead}>
              <span>Событие</span>
              <span>В сервисе</span>
              <span>Почта</span>
              <span>Push</span>
            </div>
            {groups.map((group) => (
              <div key={group.key}>
                <div className={styles.prefGroup}>{group.label}</div>
                {group.preferences.map((preference) => (
                  <div key={preference.type} className={styles.prefRow}>
                    <span>{preference.label}</span>
                    <span className={styles.cell}>
                      <input
                        type="checkbox"
                        checked={preference.in_app}
                        disabled={preference.in_app_locked}
                        title={preference.in_app_locked ? 'Это уведомление нельзя отключить' : undefined}
                        onChange={(event) => toggle(preference.type, 'in_app', event.target.checked)}
                      />
                    </span>
                    <span className={styles.cell}>
                      <input
                        type="checkbox"
                        checked={preference.email}
                        disabled={!emailConfigured}
                        onChange={(event) => toggle(preference.type, 'email', event.target.checked)}
                      />
                    </span>
                    <span className={styles.cell}>
                      <input
                        type="checkbox"
                        checked={preference.push}
                        disabled={!pushConfigured}
                        onChange={(event) => toggle(preference.type, 'push', event.target.checked)}
                      />
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>

          <Button loading={busy} onClick={() => void save()}>
            Сохранить
          </Button>
        </div>
      )}
    </Card>
  );
}

function IntegrationsCard({ isDeveloper }: { isDeveloper: boolean }) {
  const [status, setStatus] = useState<GitHubStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    if (!isDeveloper) return;
    get<GitHubStatus>('/github/status')
      .then(setStatus)
      .catch(() => setStatus(null));
  }, [isDeveloper]);

  useEffect(() => load(), [load]);

  if (!isDeveloper) {
    return (
      <Card>
        <h2 className={styles.sectionTitle}>Интеграции</h2>
        <p className="av-muted">Подключение GitHub доступно в роли исполнителя.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className={styles.sectionTitle}>GitHub</h2>
      <div className="av-stack-sm">
        {error ? <p className={styles.alert}>{error}</p> : null}
        {!status ? (
          <Skeleton height={80} />
        ) : !status.configured ? (
          <p className={styles.notice}>
            Интеграция с GitHub не настроена на этой площадке: администратор не задал ключи приложения.
            Как только их добавят, подключение появится здесь.
          </p>
        ) : status.connected ? (
          <>
            <p className="av-small">
              Подключён аккаунт <strong>@{status.account?.login}</strong>.
              {status.analysis?.status === 'completed'
                ? ' Публичные репозитории проанализированы.'
                : status.analysis?.status === 'running'
                  ? ' Идёт анализ репозиториев.'
                  : ''}
            </p>
            {status.analysis_degraded ? (
              <p className="av-small av-faint">
                Сервис анализа временно недоступен, поэтому сводка может быть неполной.
              </p>
            ) : null}
            <div className="av-row av-wrap">
              <Button
                variant="secondary"
                size="sm"
                loading={busy}
                onClick={async () => {
                  setBusy(true);
                  setError('');
                  try {
                    await post('/github/sync');
                    load();
                  } catch (failure) {
                    setError(failure instanceof ApiFailure ? failure.message : 'Не удалось запустить синхронизацию.');
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Обновить данные
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={async () => {
                  if (!window.confirm('Отключить GitHub? Подтверждение навыков по репозиториям пропадёт.')) return;
                  await del('/github/connection');
                  load();
                }}
              >
                Отключить
              </Button>
            </div>
          </>
        ) : (
          <>
            <p className="av-small av-muted">
              Подключите GitHub — AVERIX прочитает ваши публичные репозитории и подтвердит языки и
              инструменты, которыми вы действительно пользуетесь. Доля кода показывается как доля кода
              и никогда не превращается в оценку знаний.
            </p>
            <Button
              loading={busy}
              onClick={async () => {
                setBusy(true);
                setError('');
                try {
                  const started = await post<{ authorize_url: string }>('/github/connect', {
                    redirect_to: '/settings',
                  });
                  window.location.href = started.authorize_url;
                } catch (failure) {
                  setError(failure instanceof ApiFailure ? failure.message : 'Не удалось начать подключение.');
                  setBusy(false);
                }
              }}
            >
              Подключить GitHub
            </Button>
          </>
        )}
      </div>
    </Card>
  );
}

function DangerCard({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  return (
    <Card className={styles.danger}>
      <h2 className={styles.sectionTitle}>Удаление аккаунта</h2>
      <div className="av-stack-sm">
        <p className="av-small av-muted">
          Профиль скрывается из каталога, услуги уходят в архив, все сеансы завершаются. Завершённые
          сделки и отзывы остаются: они принадлежат обеим сторонам. Пока есть незакрытые сделки,
          деактивировать аккаунт нельзя.
        </p>
        {error ? <p className={styles.alert}>{error}</p> : null}
        {open ? (
          <>
            <Input
              label="Подтвердите паролем"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <div className="av-row">
              <Button variant="secondary" onClick={() => setOpen(false)}>
                Отмена
              </Button>
              <Button
                variant="danger"
                loading={busy}
                disabled={!password}
                onClick={async () => {
                  setBusy(true);
                  setError('');
                  try {
                    await post('/account/deactivate', { password });
                    onDone();
                  } catch (failure) {
                    setError(failure instanceof ApiFailure ? failure.message : 'Не удалось деактивировать аккаунт.');
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Деактивировать
              </Button>
            </div>
          </>
        ) : (
          <div>
            <Button variant="ghost" onClick={() => setOpen(true)}>
              Деактивировать аккаунт
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
