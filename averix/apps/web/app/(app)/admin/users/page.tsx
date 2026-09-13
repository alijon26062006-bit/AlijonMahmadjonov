'use client';

import { useCallback, useEffect, useState } from 'react';
import styles from '../admin.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Input, Select, Textarea } from '@/components/ui/Field';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconSearch, IconUser } from '@/components/ui/Icon';
import { ApiFailure, del, get, list, post, put } from '@/lib/api';
import { shortDate, timeAgo } from '@/lib/format';
import { roleLabel } from '@/lib/labels';
import type { AdminUser } from '@/lib/types';

export default function AdminUsersPage() {
  const [text, setText] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('');
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [total, setTotal] = useState(0);
  const [open, setOpen] = useState<AdminUser | null>(null);

  const load = useCallback(async () => {
    setUsers(null);
    const query = new URLSearchParams({ limit: '30' });
    if (text.trim()) query.set('q', text.trim());
    if (role) query.set('role', role);
    if (status) query.set('status', status);
    try {
      const response = await list<AdminUser[]>(`/admin/users?${query.toString()}`);
      setUsers(response.data ?? []);
      setTotal(Number(response.meta?.total ?? 0));
    } catch {
      setUsers([]);
    }
  }, [text, role, status]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, status]);

  return (
    <>
      <TopBar back="/admin" title="Пользователи" />
      <div className={`av-page av-stack ${styles.shell}`}>
        <Card>
          <form
            className="av-row av-wrap"
            onSubmit={(event) => {
              event.preventDefault();
              void load();
            }}
          >
            <Input
              label="Поиск"
              placeholder="Имя, @логин или почта"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
            <Select label="Роль" value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="">Любая</option>
              <option value="client">Заказчики</option>
              <option value="developer">Исполнители</option>
              <option value="moderator">Модераторы</option>
              <option value="admin">Администраторы</option>
            </Select>
            <Select label="Статус" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Любой</option>
              <option value="active">Активные</option>
              <option value="suspended">Заблокированные</option>
              <option value="deactivated">Деактивированные</option>
            </Select>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <Button type="submit" icon={<IconSearch size={16} />}>
                Найти
              </Button>
            </div>
          </form>
        </Card>

        {users === null ? (
          <SkeletonList count={4} />
        ) : users.length === 0 ? (
          <EmptyState icon={<IconUser size={20} />} title="Никого не нашли" description="Измените условия поиска." />
        ) : (
          <Card>
            <p className="av-small av-muted">Найдено: {total}</p>
            {users.map((user) => (
              <div key={user.id} className={styles.row}>
                <div className="av-grow">
                  <p className="av-strong">
                    {user.full_name} <span className="av-faint">@{user.username}</span>
                  </p>
                  <p className="av-xs av-faint">
                    {user.email} · {user.roles.map(roleLabel).join(', ')} · с {shortDate(user.created_at)}
                    {user.last_seen_at ? ` · был ${timeAgo(user.last_seen_at)}` : ''}
                  </p>
                </div>
                <div className="av-row" style={{ alignItems: 'center' }}>
                  {user.status !== 'active' ? (
                    <Badge tone={user.status === 'suspended' ? 'danger' : 'neutral'} size="sm">
                      {user.status === 'suspended' ? 'Заблокирован' : 'Деактивирован'}
                    </Badge>
                  ) : null}
                  <Button size="sm" variant="secondary" onClick={() => setOpen(user)}>
                    Открыть
                  </Button>
                </div>
              </div>
            ))}
          </Card>
        )}
      </div>

      <UserSheet
        user={open}
        onClose={() => setOpen(null)}
        onChanged={() => {
          setOpen(null);
          void load();
        }}
      />
    </>
  );
}

function UserSheet({ user, onClose, onChanged }: { user: AdminUser | null; onClose: () => void; onChanged: () => void }) {
  const [detail, setDetail] = useState<AdminUser | null>(null);
  const [reason, setReason] = useState('');
  const [days, setDays] = useState('7');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');

  useEffect(() => {
    if (!user) {
      setDetail(null);
      return;
    }
    setReason('');
    setError('');
    setOk('');
    get<AdminUser>(`/admin/users/${user.id}`)
      .then(setDetail)
      .catch(() => setDetail(user));
  }, [user]);

  if (!user) return null;
  const shown = detail ?? user;

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError('');
    setOk('');
    try {
      await action();
      setOk(success);
      setDetail(await get<AdminUser>(`/admin/users/${user!.id}`));
    } catch (failure) {
      setError(failure instanceof ApiFailure ? failure.fields.reason || failure.message : 'Не получилось.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title={shown.full_name}
      description={`@${shown.username} · ${shown.email}`}
      size="lg"
      footer={<Button onClick={onChanged}>Готово</Button>}
    >
      <div className="av-stack">
        {error ? <p className={styles.alert}>{error}</p> : null}
        {ok ? <p className={styles.ok}>{ok}</p> : null}

        <div className={styles.tiles}>
          <Fact label="Заказов размещено" value={shown.projects_posted ?? 0} />
          <Fact label="Сделок всего" value={shown.contracts_total ?? 0} />
          <Fact label="В работе" value={shown.contracts_active ?? 0} />
          <Fact label="Жалоб на него" value={shown.reports_against ?? 0} />
          <Fact label="Предупреждений" value={shown.warnings ?? 0} />
          <Fact label="Сеансов" value={shown.active_sessions ?? 0} />
        </div>

        <div className="av-row av-wrap">
          <Badge tone={shown.email_verified ? 'success' : 'warning'} size="sm">
            {shown.email_verified ? 'Почта подтверждена' : 'Почта не подтверждена'}
          </Badge>
          <Badge tone={shown.identity_verified ? 'verified' : 'neutral'} size="sm">
            {shown.identity_verified ? 'Личность подтверждена' : 'Личность не подтверждена'}
          </Badge>
          {shown.roles.map((role) => (
            <Badge key={role} tone="brand" size="sm">
              {roleLabel(role)}
            </Badge>
          ))}
        </div>

        {shown.suspended_reason ? (
          <p className={styles.alert}>
            Заблокирован: {shown.suspended_reason}
            {shown.suspended_until ? ` (до ${shortDate(shown.suspended_until)})` : ''}
          </p>
        ) : null}

        <div className="av-stack-sm">
          <p className="av-small av-strong">Блокировка и предупреждение</p>
          <Textarea
            label="Причина"
            hint="Не меньше 10 символов. Человек увидит её в уведомлении."
            rows={3}
            max={1000}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <Input
            label="На сколько дней"
            inputMode="numeric"
            hint="0 — до снятия вручную."
            value={days}
            onChange={(event) => setDays(event.target.value)}
          />
          <div className="av-row av-wrap">
            <Button
              variant="danger"
              size="sm"
              loading={busy}
              disabled={reason.trim().length < 10}
              onClick={() =>
                run(
                  () => post(`/admin/users/${shown.id}/suspend`, { reason: reason.trim(), days: Number(days) || 0 }),
                  'Пользователь заблокирован, сеансы завершены.',
                )
              }
            >
              Заблокировать
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={busy}
              disabled={reason.trim().length < 10}
              onClick={() => run(() => post(`/admin/users/${shown.id}/warn`, { reason: reason.trim() }), 'Предупреждение отправлено.')}
            >
              Предупредить
            </Button>
            {shown.status === 'suspended' ? (
              <Button
                variant="secondary"
                size="sm"
                loading={busy}
                onClick={() => run(() => post(`/admin/users/${shown.id}/unsuspend`), 'Блокировка снята.')}
              >
                Снять блокировку
              </Button>
            ) : null}
          </div>
        </div>

        <div className="av-stack-sm">
          <p className="av-small av-strong">Роли и проверка</p>
          <div className="av-row av-wrap">
            {(['moderator', 'admin'] as const).map((role) =>
              shown.roles.includes(role) ? (
                <Button
                  key={role}
                  variant="ghost"
                  size="sm"
                  loading={busy}
                  onClick={() => run(() => del(`/admin/users/${shown.id}/roles/${role}`), `Роль снята: ${roleLabel(role)}`)}
                >
                  Снять роль: {roleLabel(role)}
                </Button>
              ) : (
                <Button
                  key={role}
                  variant="secondary"
                  size="sm"
                  loading={busy}
                  onClick={() => run(() => post(`/admin/users/${shown.id}/roles`, { role }), `Роль выдана: ${roleLabel(role)}`)}
                >
                  Выдать роль: {roleLabel(role)}
                </Button>
              ),
            )}
            <Button
              variant="secondary"
              size="sm"
              loading={busy}
              onClick={() =>
                run(
                  () => put(`/admin/users/${shown.id}/identity`, { verified: !shown.identity_verified }),
                  shown.identity_verified ? 'Отметка о проверке снята.' : 'Личность отмечена как проверенная.',
                )
              }
            >
              {shown.identity_verified ? 'Снять отметку о проверке' : 'Подтвердить личность'}
            </Button>
          </div>
          <p className="av-xs av-faint">
            Каждое действие записывается в журнал с вашим именем. Снять у человека последнюю роль или
            заблокировать самого себя нельзя.
          </p>
        </div>
      </div>
    </Sheet>
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
