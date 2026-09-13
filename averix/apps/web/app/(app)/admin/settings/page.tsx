'use client';

import { useCallback, useEffect, useState } from 'react';
import styles from '../admin.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { Tabs } from '@/components/ui/Tabs';
import { Skeleton } from '@/components/ui/Skeleton';
import { ApiFailure, get, put } from '@/lib/api';
import type { AdminSetting, FeatureFlag, MatchingWeights } from '@/lib/types';

const TABS = [
  { key: 'settings', label: 'Параметры' },
  { key: 'payments', label: 'Реквизиты' },
  { key: 'flags', label: 'Функции' },
  { key: 'weights', label: 'Подбор' },
];

const GROUP_LABEL: Record<string, string> = {
  money: 'Деньги',
  limits: 'Ограничения',
  marketplace: 'Площадка',
  platform: 'Платформа',
  manual_payments: 'Реквизиты для переводов',
};

export default function PlatformSettingsPage() {
  const [tab, setTab] = useState('settings');

  return (
    <>
      <TopBar back="/admin" title="Настройки платформы" />
      <div className={`av-page av-stack ${styles.shell}`}>
        <Tabs items={TABS} active={tab} onChange={setTab} ariaLabel="Разделы настроек платформы" />
        {tab === 'settings' ? <SettingsList exclude="manual_payments" /> : null}
        {tab === 'payments' ? <SettingsList only="manual_payments" /> : null}
        {tab === 'flags' ? <Flags /> : null}
        {tab === 'weights' ? <Weights /> : null}
      </div>
    </>
  );
}

function SettingsList({ only, exclude }: { only?: string; exclude?: string }) {
  const [rows, setRows] = useState<AdminSetting[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<string | null>(null);

  const load = useCallback(() => {
    get<AdminSetting[]>('/admin/settings')
      .then((data) => setRows(data ?? []))
      .catch(() => setRows([]));
  }, []);

  useEffect(() => load(), [load]);

  if (rows === null) return <Skeleton height={260} />;

  const visible = rows.filter((row) => (only ? row.group === only : row.group !== exclude));
  const groups = [...new Set(visible.map((row) => row.group))];

  async function save(row: AdminSetting) {
    const raw = drafts[row.key] ?? String(row.value ?? '');
    const value = row.type === 'int' ? Number(raw) : row.type === 'bool' ? raw === 'true' : raw;
    setBusy(row.key);
    setError({});
    setSaved(null);
    try {
      await put(`/admin/settings/${row.key}`, { value });
      setSaved(row.key);
      load();
    } catch (failure) {
      setError({ [row.key]: failure instanceof ApiFailure ? failure.fields.value || failure.message : 'Не получилось.' });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      {only === 'manual_payments' ? (
        <Card>
          <p className="av-small av-muted">
            Эти реквизиты видит заказчик, когда резервирует оплату этапа. Пока они пустые, оплатить
            этап нельзя — платформа честно скажет об этом вместо того, чтобы делать вид, что платёж
            прошёл.
          </p>
        </Card>
      ) : null}

      {groups.map((group) => (
        <Card key={group}>
          <h2 className="av-lg av-strong">{GROUP_LABEL[group] ?? group}</h2>
          {visible
            .filter((row) => row.group === group)
            .map((row) => (
              <div key={row.key} className={styles.settingRow}>
                <div>
                  <p className="av-strong">{row.label}</p>
                  {row.description ? <p className="av-small av-muted">{row.description}</p> : null}
                  <p className={styles.code}>{row.key}</p>
                  {error[row.key] ? <p className={styles.alert}>{error[row.key]}</p> : null}
                  {saved === row.key ? <p className={styles.ok}>Сохранено.</p> : null}
                </div>
                <div className="av-stack-sm">
                  {row.type === 'bool' ? (
                    <label className="av-row" style={{ gap: 'var(--av-space-2)', alignItems: 'center' }}>
                      <input
                        type="checkbox"
                        checked={(drafts[row.key] ?? String(row.value)) === 'true'}
                        onChange={(event) => setDrafts({ ...drafts, [row.key]: String(event.target.checked) })}
                      />
                      <span className="av-small">Включено</span>
                    </label>
                  ) : (
                    <Input
                      label="Значение"
                      inputMode={row.type === 'int' ? 'numeric' : undefined}
                      hint={row.min !== undefined || row.max !== undefined ? `от ${row.min ?? '—'} до ${row.max ?? '—'}` : undefined}
                      value={drafts[row.key] ?? String(row.value ?? '')}
                      onChange={(event) => setDrafts({ ...drafts, [row.key]: event.target.value })}
                    />
                  )}
                  <Button size="sm" loading={busy === row.key} onClick={() => void save(row)}>
                    Сохранить
                  </Button>
                </div>
              </div>
            ))}
        </Card>
      ))}
    </>
  );
}

function Flags() {
  const [flags, setFlags] = useState<FeatureFlag[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    get<FeatureFlag[]>('/admin/flags')
      .then((data) => setFlags(data ?? []))
      .catch(() => setFlags([]));
  }, []);

  useEffect(() => load(), [load]);

  if (flags === null) return <Skeleton height={180} />;

  return (
    <Card>
      <h2 className="av-lg av-strong">Функции</h2>
      {flags.length === 0 ? (
        <p className="av-muted">Ни один переключатель ещё не создан.</p>
      ) : (
        flags.map((flag) => (
          <div key={flag.key} className={styles.settingRow}>
            <div>
              <p className="av-strong">{flag.key}</p>
              {flag.description ? <p className="av-small av-muted">{flag.description}</p> : null}
            </div>
            <div className="av-stack-sm">
              <label className="av-row" style={{ gap: 'var(--av-space-2)', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={flag.enabled}
                  onChange={async (event) => {
                    setBusy(flag.key);
                    try {
                      await put(`/admin/flags/${flag.key}`, {
                        enabled: event.target.checked,
                        rollout_percent: flag.rollout_percent,
                      });
                      load();
                    } finally {
                      setBusy(null);
                    }
                  }}
                />
                <span className="av-small">{flag.enabled ? 'Включена' : 'Выключена'}</span>
              </label>
              <p className="av-xs av-faint">
                Показывается {flag.rollout_percent}% пользователей{busy === flag.key ? ' · сохраняем…' : ''}
              </p>
            </div>
          </div>
        ))
      )}
    </Card>
  );
}

const WEIGHT_LABEL: Record<string, string> = {
  technical: 'Совпадение по навыкам',
  track_record: 'История работ',
  github: 'Подтверждение из GitHub',
  availability: 'Доступность',
  platform_history: 'Поведение на платформе',
  budget_fit: 'Соответствие бюджету',
};

function Weights() {
  const [weights, setWeights] = useState<MatchingWeights | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [threshold, setThreshold] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const load = useCallback(() => {
    get<MatchingWeights>('/admin/matching/weights')
      .then((data) => {
        setWeights(data);
        setDraft(Object.fromEntries(Object.keys(WEIGHT_LABEL).map((key) => [key, String((data as never)[key] ?? 0)])));
        setThreshold(String(data.feed_threshold ?? 0));
      })
      .catch(() => setWeights(null));
  }, []);

  useEffect(() => load(), [load]);

  if (!weights) return <Skeleton height={220} />;

  const sum = Object.values(draft).reduce((total, value) => total + (Number(value) || 0), 0);

  return (
    <Card>
      <h2 className="av-lg av-strong">Веса подбора</h2>
      <div className="av-stack">
        <p className="av-small av-muted">
          Сумма всех весов должна быть ровно 1. Порог — минимальный балл совпадения, чтобы заказ попал
          в ленту «Для вас». Изменения версионируются: старые предложения сохраняют тот балл, который
          видел заказчик.
        </p>
        {error ? <p className={styles.alert}>{error}</p> : null}
        {saved ? <p className={styles.ok}>Новый набор весов сохранён и стал активным.</p> : null}

        {Object.entries(WEIGHT_LABEL).map(([key, label]) => (
          <Input
            key={key}
            label={label}
            inputMode="decimal"
            value={draft[key] ?? '0'}
            onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
          />
        ))}

        <p className={sum.toFixed(2) === '1.00' ? 'av-small' : styles.alert}>
          Сумма: {sum.toFixed(2)}
          {sum.toFixed(2) === '1.00' ? '' : ' — должна быть 1.00'}
        </p>

        <Input label="Порог ленты" inputMode="numeric" value={threshold} onChange={(event) => setThreshold(event.target.value)} />
        <Input
          label="Почему меняете"
          hint="Записывается в историю вместе с набором."
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />

        <Button
          loading={busy}
          disabled={sum.toFixed(2) !== '1.00'}
          onClick={async () => {
            setBusy(true);
            setError('');
            setSaved(false);
            try {
              await put('/admin/matching/weights', {
                ...Object.fromEntries(Object.entries(draft).map(([key, value]) => [key, Number(value) || 0])),
                feed_threshold: Number(threshold) || 0,
                note: note.trim(),
              });
              setSaved(true);
              load();
            } catch (failure) {
              setError(failure instanceof ApiFailure ? failure.fields.weights || failure.message : 'Не получилось сохранить.');
            } finally {
              setBusy(false);
            }
          }}
        >
          Сохранить набор
        </Button>
      </div>
    </Card>
  );
}
