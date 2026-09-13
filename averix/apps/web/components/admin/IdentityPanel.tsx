'use client';

import { useCallback, useEffect, useState } from 'react';
import styles from '@/app/(app)/admin/admin.module.css';
import own from './identity.module.css';
import { Card, SectionHeading } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input, Textarea } from '@/components/ui/Field';
import { EmptyState } from '@/components/ui/EmptyState';
import { SkeletonList } from '@/components/ui/Skeleton';
import { IconLock, IconShield } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { longDate, timeAgo } from '@/lib/format';
import { countryName } from '@/lib/labels';
import { identityStatusLabel, identityTone } from '@/lib/admin';
import { DocumentViewer } from './DocumentViewer';
import type {
  IdentityAccessEntry,
  IdentityCase,
  IdentityReviewAction,
  ResubmitReason,
} from '@/lib/types';

type Gate = 'loading' | 'no-permission' | 'locked' | 'open' | 'none';

/**
 * The identity tab.
 *
 * Three doors, in this order: the named permission, a password typed again,
 * and then a ticket per image that lives two minutes. Hiding the tab would not
 * be security — every one of those checks is made by the API as well; this is
 * the part that explains to the person what is being asked and why.
 */
export function IdentityPanel({
  userID,
  fullName,
  roles,
  onChanged,
}: {
  userID: string;
  fullName: string;
  roles: string[];
  onChanged: () => void;
}) {
  const [gate, setGate] = useState<Gate>('loading');
  const [item, setItem] = useState<IdentityCase | null>(null);
  const [password, setPassword] = useState('');
  const [unlockError, setUnlockError] = useState('');
  const [busy, setBusy] = useState(false);
  const [unlockedUntil, setUnlockedUntil] = useState('');

  const load = useCallback(async () => {
    setGate('loading');
    try {
      const data = await get<IdentityCase>(`/admin/identity/users/${userID}`);
      setItem(data);
      setGate('open');
    } catch (failure) {
      if (!(failure instanceof ApiFailure)) {
        setGate('no-permission');
        return;
      }
      if (failure.status === 404) {
        setItem(null);
        setGate('none');
        return;
      }
      if (failure.code === 'reauthentication_required' || failure.code === 'identity_locked') {
        setGate('locked');
        return;
      }
      setGate(failure.status === 403 ? 'no-permission' : 'locked');
    }
  }, [userID]);

  useEffect(() => {
    void load();
  }, [load]);

  async function unlock(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setUnlockError('');
    try {
      const result = await post<{ unlocked_until: string }>('/admin/identity/unlock', { password });
      setUnlockedUntil(result.unlocked_until);
      setPassword('');
      await load();
    } catch (failure) {
      setUnlockError(
        failure instanceof ApiFailure ? failure.fields.password || failure.message : 'Не получилось.',
      );
    } finally {
      setBusy(false);
    }
  }

  // У заказчика проверки нет вовсе — и это не пустая вкладка, а правило.
  if (!roles.includes('developer')) {
    return (
      <EmptyState
        icon={<IconShield size={20} />}
        title="Заказчику проверка не нужна"
        description={`${fullName} — заказчик: он платит, а не получает оплату. Документы у него не запрашиваются, и завести дело на этот аккаунт нельзя ни отсюда, ни запросом к API.`}
      />
    );
  }

  if (gate === 'loading') return <SkeletonList count={2} />;

  if (gate === 'no-permission') {
    return (
      <EmptyState
        icon={<IconShield size={20} />}
        title="Документы вам не открыты"
        description="Нужно именное разрешение identity_verification.view. Роль администратора его не даёт: его выдаёт другой администратор конкретному сотруднику, и каждый просмотр записывается."
      />
    );
  }

  if (gate === 'locked') {
    return (
      <Card>
        <SectionHeading title="Введите пароль ещё раз" />
        <p className="av-small av-muted">
          Открытая вкладка в чужих руках не должна показывать паспорт. Пароль действует десять минут, потом
          понадобится снова.
        </p>
        <form className="av-stack-sm" onSubmit={unlock} style={{ marginTop: 'var(--av-space-3)' }}>
          <Input
            label="Ваш пароль"
            type="password"
            autoComplete="current-password"
            value={password}
            error={unlockError || undefined}
            onChange={(event) => setPassword(event.target.value)}
          />
          <div>
            <Button type="submit" loading={busy} disabled={password.length === 0} icon={<IconLock size={16} />}>
              Открыть доступ
            </Button>
          </div>
        </form>
      </Card>
    );
  }

  if (gate === 'none' || !item) {
    return (
      <EmptyState
        icon={<IconShield size={20} />}
        title="Проверка не начиналась"
        description={`${fullName} ещё не отправлял документы. Пока они не проверены, он не может откликаться на заказы, публиковать услуги и получать оплату.`}
      />
    );
  }

  return (
    <div className="av-stack">
      {unlockedUntil ? (
        <p className="av-xs av-faint">Доступ открыт до {longDate(unlockedUntil)}.</p>
      ) : null}
      <CaseCard item={item} />
      <Documents item={item} />
      <Decision
        item={item}
        onDecided={(next) => {
          setItem(next);
          onChanged();
        }}
      />
      <History caseID={item.id} />
      <AccessLog userID={userID} />
    </div>
  );
}

function CaseCard({ item }: { item: IdentityCase }) {
  return (
    <Card>
      <SectionHeading
        title="Дело о проверке"
        action={
          <Badge tone={identityTone(item.status)} size="sm">
            {item.status_label || identityStatusLabel(item.status)}
          </Badge>
        }
      />
      <div className={own.pairs}>
        <Pair label="Тип документа" value={item.document_label ?? '—'} />
        <Pair label="Страна выдачи" value={countryName(item.country_code) || '—'} />
        <Pair label="Отправлено" value={item.submitted_at ? longDate(item.submitted_at) : '—'} />
        <Pair label="Решение" value={item.reviewed_at ? longDate(item.reviewed_at) : '—'} />
        <Pair label="Кто решал" value={item.reviewer_name || '—'} />
        <Pair
          label="Изображения удалятся"
          value={item.retention_expires_at ? longDate(item.retention_expires_at) : 'после решения'}
        />
      </div>
      {item.decision_reason ? (
        <p className="av-small" style={{ marginTop: 'var(--av-space-3)' }}>
          <span className="av-strong">Обоснование: </span>
          {item.decision_reason}
        </p>
      ) : null}
      {item.missing.length > 0 ? (
        <p className="av-small av-muted" style={{ marginTop: 'var(--av-space-2)' }}>
          Не хватает: {item.missing.join(', ')}
        </p>
      ) : null}
      <p className={own.note}>
        Ни номер документа, ни дата рождения здесь не показываются: они нужны для сверки с профилем, а не
        для чтения глазами. Сверяйте имя на изображении с именем в профиле.
      </p>
    </Card>
  );
}

function Pair({ label, value }: { label: string; value: string }) {
  return (
    <div className={own.pair}>
      <span className={own.pairLabel}>{label}</span>
      <span className={own.pairValue}>{value}</span>
    </div>
  );
}

function Documents({ item }: { item: IdentityCase }) {
  const [viewing, setViewing] = useState<number | null>(null);
  const alive = item.documents.filter((doc) => !doc.deleted_at);

  return (
    <Card>
      <SectionHeading title="Изображения" count={alive.length} />
      {alive.length === 0 ? (
        <p className="av-small av-muted">
          Изображений нет: либо человек их ещё не загрузил, либо срок хранения прошёл и они удалены. Решение
          по делу при этом сохранилось.
        </p>
      ) : (
        <div className={own.docs}>
          {alive.map((doc, index) => (
            <button key={doc.id} type="button" className={own.doc} onClick={() => setViewing(index)}>
              <span className="av-small av-strong">{doc.kind_label}</span>
              <span className="av-xs av-faint">
                {doc.width && doc.height ? `${doc.width}×${doc.height}` : doc.mime} · загружено{' '}
                {timeAgo(doc.created_at)}
              </span>
              <span className={own.open}>Открыть</span>
            </button>
          ))}
        </div>
      )}
      <p className={own.note}>
        Каждое открытие записывается в журнал доступа вместе с причиной, которую вы укажете. Ссылка на
        изображение живёт две минуты и не работает ни у кого другого — пересылать её бессмысленно.
      </p>

      {viewing !== null ? (
        <DocumentViewer
          documents={alive}
          index={viewing}
          onIndex={setViewing}
          onClose={() => setViewing(null)}
        />
      ) : null}
    </Card>
  );
}

function Decision({ item, onDecided }: { item: IdentityCase; onDecided: (next: IdentityCase) => void }) {
  const [reasons, setReasons] = useState<ResubmitReason[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');

  useEffect(() => {
    get<ResubmitReason[]>('/admin/identity/reasons')
      .then(setReasons)
      .catch(() => setReasons([]));
  }, []);

  const decided = item.status === 'approved' || item.status === 'rejected';

  async function decide(action: string) {
    setBusy(true);
    setError('');
    setOk('');
    try {
      const next = await post<IdentityCase>(`/admin/identity/cases/${item.id}/decide`, {
        action,
        reason: text.trim(),
        reasons: action === 'request_resubmit' ? picked : undefined,
      });
      setOk('Решение записано, человек получил уведомление.');
      setText('');
      setPicked([]);
      onDecided(next);
    } catch (failure) {
      setError(
        failure instanceof ApiFailure
          ? failure.fields.reason || failure.fields.reasons || failure.message
          : 'Не получилось.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <SectionHeading title="Решение" />
      {error ? <p className={styles.alert}>{error}</p> : null}
      {ok ? <p className={styles.ok}>{ok}</p> : null}
      {decided ? (
        <p className="av-small av-muted">
          Решение уже принято. Его можно изменить — это тоже останется в истории дела.
        </p>
      ) : null}

      <Textarea
        label="Что вы проверили"
        hint="Не меньше 10 символов. Это увидит следующий проверяющий, а при отказе — и сам человек."
        rows={3}
        max={1000}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />

      <div className="av-stack-sm" style={{ marginTop: 'var(--av-space-3)' }}>
        <p className="av-small av-strong">Если просите переснять — отметьте, что именно не так</p>
        <div className={own.reasons}>
          {reasons.map((reason) => (
            <label key={reason.key} className={own.reason}>
              <input
                type="checkbox"
                checked={picked.includes(reason.key)}
                onChange={(event) =>
                  setPicked((current) =>
                    event.target.checked
                      ? [...current, reason.key]
                      : current.filter((key) => key !== reason.key),
                  )
                }
              />
              <span>{reason.label}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="av-row av-wrap" style={{ marginTop: 'var(--av-space-4)' }}>
        <Button size="sm" loading={busy} disabled={text.trim().length < 10} onClick={() => void decide('approve')}>
          Подтвердить личность
        </Button>
        <Button
          variant="secondary"
          size="sm"
          loading={busy}
          disabled={text.trim().length < 10 || picked.length === 0}
          onClick={() => void decide('request_resubmit')}
        >
          Попросить переснять
        </Button>
        <Button
          variant="danger"
          size="sm"
          loading={busy}
          disabled={text.trim().length < 10}
          onClick={() => void decide('reject')}
        >
          Отказать
        </Button>
        <Button
          variant="ghost"
          size="sm"
          loading={busy}
          disabled={text.trim().length < 10}
          onClick={() => void decide('suspend')}
        >
          Приостановить проверку
        </Button>
      </div>
      <p className={own.note}>
        «Переснять» не обнуляет дело: остальные изображения остаются, человеку придёт список того, что нужно
        сделать заново.
      </p>
    </Card>
  );
}

function History({ caseID }: { caseID: string }) {
  const [rows, setRows] = useState<IdentityReviewAction[] | null>(null);
  useEffect(() => {
    get<IdentityReviewAction[]>(`/admin/identity/cases/${caseID}/history`)
      .then(setRows)
      .catch(() => setRows([]));
  }, [caseID]);

  if (rows === null) return null;

  return (
    <Card>
      <SectionHeading title="История дела" />
      {rows.length === 0 ? (
        <p className="av-small av-muted">Пока ничего не решали.</p>
      ) : (
        rows.map((row) => (
          <div key={row.id} className={styles.auditRow}>
            <span className="av-strong">{actionLabel(row.action)}</span>
            <span className="av-xs av-faint">
              {row.actor_name || 'человек сам'} · {longDate(row.created_at)}
            </span>
            {row.reason ? <span className="av-xs av-muted">{row.reason}</span> : null}
          </div>
        ))
      )}
    </Card>
  );
}

function AccessLog({ userID }: { userID: string }) {
  const [rows, setRows] = useState<IdentityAccessEntry[] | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    get<IdentityAccessEntry[]>(`/admin/identity/users/${userID}/access-log?limit=50`)
      .then(setRows)
      .catch((failure) => {
        setDenied(failure instanceof ApiFailure && failure.status === 403);
        setRows([]);
      });
  }, [userID]);

  if (rows === null) return null;
  if (denied) {
    return (
      <Card>
        <SectionHeading title="Кто смотрел документы" />
        <p className="av-small av-muted">Журнал доступа требует ещё и права audit.read.</p>
      </Card>
    );
  }

  return (
    <Card>
      <SectionHeading title="Кто смотрел документы" count={rows.length} />
      {rows.length === 0 ? (
        <p className="av-small av-muted">Никто ещё не открывал.</p>
      ) : (
        rows.map((row) => (
          <div key={row.id} className={styles.auditRow}>
            <span className="av-strong">
              {row.actor_name || 'сотрудник'} — {accessLabel(row.action)}
            </span>
            <span className="av-xs av-faint">
              {longDate(row.created_at)}
              {row.ip ? ` · ${row.ip}` : ''}
            </span>
            {row.reason ? <span className="av-xs av-muted">Причина: {row.reason}</span> : null}
          </div>
        ))
      )}
    </Card>
  );
}

function actionLabel(action: string): string {
  switch (action) {
    case 'submitted':
      return 'Отправлено на проверку';
    case 'approve':
      return 'Личность подтверждена';
    case 'reject':
      return 'Отказано';
    case 'request_resubmit':
      return 'Попросили переснять';
    case 'suspend':
      return 'Проверка приостановлена';
    default:
      return action;
  }
}

function accessLabel(action: string): string {
  if (action.startsWith('view:')) {
    const kind = action.slice('view:'.length);
    const labels: Record<string, string> = {
      front: 'открыл лицевую сторону',
      back: 'открыл оборотную сторону',
      selfie: 'открыл селфи',
      selfie_with_document: 'открыл селфи с документом',
    };
    return labels[kind] ?? `открыл изображение (${kind})`;
  }
  if (action.startsWith('decide:')) {
    return `принял решение — ${actionLabel(action.slice('decide:'.length)).toLowerCase()}`;
  }
  switch (action) {
    case 'open':
      return 'открыл дело';
    case 'list':
      return 'смотрел очередь';
    case 'access_log':
      return 'читал журнал доступа';
    default:
      return action;
  }
}
