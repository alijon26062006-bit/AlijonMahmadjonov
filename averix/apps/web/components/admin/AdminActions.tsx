'use client';

import { useEffect, useState } from 'react';
import styles from '@/app/(app)/admin/admin.module.css';
import { Card, SectionHeading } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input, Select, Textarea } from '@/components/ui/Field';
import { ApiFailure, del, get, post, put } from '@/lib/api';
import { longDate } from '@/lib/format';
import { roleLabel } from '@/lib/labels';
import type { AdminGrantable, AdminUser } from '@/lib/types';

/**
 * Everything an administrator can do to an account, with the consequence
 * spelled out before the click rather than after it.
 *
 * Приостановка и блокировка — разные вещи, поэтому и кнопки разные: первая
 * снимается сама по сроку, вторая не снимается, пока её не снимут.
 */
export function AdminActions({ user, onChanged }: { user: AdminUser; onChanged: () => void }) {
  const [reason, setReason] = useState('');
  const [days, setDays] = useState('7');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [confirming, setConfirming] = useState('');

  const [grantable, setGrantable] = useState<AdminGrantable[]>([]);
  const [permission, setPermission] = useState('');
  const [note, setNote] = useState('');

  const staff = user.roles.includes('admin') || user.roles.includes('moderator');

  useEffect(() => {
    if (!staff) return;
    get<AdminGrantable[]>('/admin/permissions')
      .then(setGrantable)
      .catch(() => setGrantable([]));
  }, [staff]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError('');
    setOk('');
    try {
      await action();
      setOk(success);
      setConfirming('');
      onChanged();
    } catch (failure) {
      setError(
        failure instanceof ApiFailure
          ? failure.fields.reason || failure.fields.permission || failure.message
          : 'Не получилось.',
      );
    } finally {
      setBusy(false);
    }
  }

  const shortReason = reason.trim().length < 10;

  return (
    <div className="av-stack">
      <Card>
        <SectionHeading title="Действия с аккаунтом" />
        {error ? <p className={styles.alert}>{error}</p> : null}
        {ok ? <p className={styles.ok}>{ok}</p> : null}

        <Textarea
          label="Причина"
          hint="Не меньше 10 символов. Человек увидит её в уведомлении, а вы — в журнале."
          rows={3}
          max={1000}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
        <Input
          label="Приостановить на дней"
          inputMode="numeric"
          hint="0 — до снятия вручную."
          value={days}
          onChange={(event) => setDays(event.target.value)}
        />

        <div className="av-row av-wrap" style={{ marginTop: 'var(--av-space-3)' }}>
          <Button
            variant="secondary"
            size="sm"
            loading={busy}
            disabled={shortReason}
            onClick={() => run(() => post(`/admin/users/${user.id}/warn`, { reason: reason.trim() }), 'Предупреждение отправлено.')}
          >
            Предупредить
          </Button>
          <Button
            variant="danger"
            size="sm"
            loading={busy}
            disabled={shortReason}
            onClick={() =>
              run(
                () => post(`/admin/users/${user.id}/suspend`, { reason: reason.trim(), days: Number(days) || 0 }),
                'Аккаунт приостановлен, сеансы завершены.',
              )
            }
          >
            Приостановить
          </Button>
          {user.status === 'suspended' ? (
            <Button
              variant="secondary"
              size="sm"
              loading={busy}
              onClick={() => run(() => post(`/admin/users/${user.id}/unsuspend`), 'Приостановка снята.')}
            >
              Снять приостановку
            </Button>
          ) : null}
          {user.status === 'banned' ? (
            <Button
              variant="secondary"
              size="sm"
              loading={busy}
              onClick={() => run(() => post(`/admin/users/${user.id}/unblock`, { reason: reason.trim() }), 'Блокировка снята.')}
            >
              Разблокировать
            </Button>
          ) : confirming === 'block' ? (
            <>
              <Button
                variant="danger"
                size="sm"
                loading={busy}
                disabled={shortReason}
                onClick={() =>
                  run(() => post(`/admin/users/${user.id}/block`, { reason: reason.trim() }), 'Аккаунт заблокирован.')
                }
              >
                Да, заблокировать навсегда
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirming('')}>
                Отмена
              </Button>
            </>
          ) : (
            <Button variant="danger" size="sm" disabled={shortReason} onClick={() => setConfirming('block')}>
              Заблокировать
            </Button>
          )}
        </div>
        {confirming === 'block' ? (
          <p className={styles.alert} style={{ marginTop: 'var(--av-space-3)' }}>
            Блокировка не снимается сама. Человек не сможет войти, его заказы и услуги перестанут
            показываться, а активные сделки останутся у второй стороны без исполнителя.
          </p>
        ) : null}
      </Card>

      <Card>
        <SectionHeading title="Роли" />
        <div className="av-row av-wrap">
          {(['moderator', 'admin'] as const).map((role) =>
            user.roles.includes(role) ? (
              <Button
                key={role}
                variant="ghost"
                size="sm"
                loading={busy}
                onClick={() => run(() => del(`/admin/users/${user.id}/roles/${role}`), `Роль снята: ${roleLabel(role)}`)}
              >
                Снять роль: {roleLabel(role)}
              </Button>
            ) : (
              <Button
                key={role}
                variant="secondary"
                size="sm"
                loading={busy}
                onClick={() => run(() => post(`/admin/users/${user.id}/roles`, { role }), `Роль выдана: ${roleLabel(role)}`)}
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
                () => put(`/admin/users/${user.id}/identity`, { verified: !user.identity_verified }),
                user.identity_verified ? 'Отметка о проверке снята.' : 'Отметка о проверке поставлена.',
              )
            }
          >
            {user.identity_verified ? 'Снять отметку о проверке' : 'Отметить личность проверенной'}
          </Button>
        </div>
        <p className="av-xs av-faint" style={{ marginTop: 'var(--av-space-2)' }}>
          Отметка вручную — на крайний случай: обычный путь к ней лежит через вкладку «Личность», где
          решение принимается по документам и остаётся в истории дела.
        </p>
      </Card>

      {staff ? (
        <Card>
          <SectionHeading title="Именные разрешения" />
          <p className="av-small av-muted">
            Роль не даёт доступ к документам: право на них выдаётся конкретному сотруднику и отзывается так
            же — сразу, без ожидания выхода из аккаунта.
          </p>

          {user.grants && user.grants.length > 0 ? (
            <div className="av-stack-sm" style={{ marginTop: 'var(--av-space-3)' }}>
              {user.grants.map((grant) => (
                <div key={grant.permission} className={styles.row}>
                  <div className="av-grow">
                    <p className="av-small av-strong">{grant.label}</p>
                    <p className="av-xs av-faint">
                      выдал {grant.granted_by_name || 'неизвестно кто'} · {longDate(grant.granted_at)}
                      {grant.note ? ` · ${grant.note}` : ''}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={busy}
                    onClick={() =>
                      run(
                        () => del(`/admin/users/${user.id}/permissions/${grant.permission}`),
                        'Разрешение отозвано.',
                      )
                    }
                  >
                    Отозвать
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="av-small av-muted" style={{ marginTop: 'var(--av-space-3)' }}>
              Именных разрешений нет.
            </p>
          )}

          <div className="av-stack-sm" style={{ marginTop: 'var(--av-space-4)' }}>
            <Select
              label="Выдать разрешение"
              value={permission}
              onChange={(event) => setPermission(event.target.value)}
            >
              <option value="">Выберите</option>
              {grantable
                .filter((item) => !(user.grants ?? []).some((grant) => grant.permission === item.permission))
                .map((item) => (
                  <option key={item.permission} value={item.permission}>
                    {item.label}
                  </option>
                ))}
            </Select>
            <Input
              label="Зачем"
              placeholder="Например: смена в поддержке до конца месяца"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <div>
              <Button
                size="sm"
                loading={busy}
                disabled={!permission}
                onClick={() =>
                  run(async () => {
                    await post(`/admin/users/${user.id}/permissions`, { permission, note: note.trim() });
                    setPermission('');
                    setNote('');
                  }, 'Разрешение выдано.')
                }
              >
                Выдать
              </Button>
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          <SectionHeading title="Именные разрешения" />
          <p className="av-small av-muted">
            Разрешения выдаются только сотрудникам. У этого аккаунта нет роли модератора или
            администратора.
          </p>
          <div className="av-row av-wrap" style={{ marginTop: 'var(--av-space-2)' }}>
            <Badge tone="neutral" size="sm">
              {user.roles.map(roleLabel).join(', ')}
            </Badge>
          </div>
        </Card>
      )}
    </div>
  );
}
