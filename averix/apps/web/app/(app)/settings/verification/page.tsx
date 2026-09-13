'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import styles from './verification.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card, SectionHeading } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { ApiFailure, get, post, upload } from '@/lib/api';
import { fileSize, longDate } from '@/lib/format';
import { identityStatusLabel, identityTone } from '@/lib/admin';
import type { IdentityCase, IdentityOptions } from '@/lib/types';

// Страны, которые площадка обслуживает в первую очередь. Список открытый:
// поле принимает любой код, просто эти четыре не надо искать.
const COUNTRIES = [
  { code: 'RU', label: 'Россия' },
  { code: 'UZ', label: 'Узбекистан' },
  { code: 'KZ', label: 'Казахстан' },
  { code: 'BY', label: 'Беларусь' },
  { code: 'KG', label: 'Киргизия' },
  { code: 'TJ', label: 'Таджикистан' },
  { code: 'AM', label: 'Армения' },
  { code: 'GE', label: 'Грузия' },
];

export default function VerificationPage() {
  const [item, setItem] = useState<IdentityCase | null>(null);
  const [options, setOptions] = useState<IdentityOptions | null>(null);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({ documentType: '', countryCode: '' });

  const load = useCallback(async () => {
    try {
      setItem(await get<IdentityCase>('/account/identity'));
    } catch {
      setItem(null);
    }
  }, []);

  useEffect(() => {
    void load();
    get<IdentityOptions>('/account/identity/options')
      .then(setOptions)
      .catch(() => setOptions(null));
  }, [load]);

  // Дело создаётся, только когда выбрано и то и другое: сохранять половину
  // формы — значит показать человеку красную надпись про страну ровно в тот
  // момент, когда он выбрал документ и до страны ещё не дошёл.
  async function saveDetails(documentType: string, countryCode: string) {
    setDraft({ documentType, countryCode });
    if (!documentType || !countryCode) return;
    setBusy(true);
    setError('');
    setOk('');
    try {
      setItem(await post<IdentityCase>('/account/identity', {
        document_type: documentType,
        country_code: countryCode,
      }));
    } catch (failure) {
      setError(failure instanceof ApiFailure ? Object.values(failure.fields)[0] || failure.message : 'Не получилось.');
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    setBusy(true);
    setError('');
    setOk('');
    try {
      setItem(await post<IdentityCase>('/account/identity/submit'));
      setOk('Документы отправлены. Обычно проверка занимает до суток.');
    } catch (failure) {
      setError(failure instanceof ApiFailure ? Object.values(failure.fields)[0] || failure.message : 'Не получилось.');
    } finally {
      setBusy(false);
    }
  }

  if (!options) {
    return (
      <>
        <TopBar back="/settings" title="Проверка личности" />
        <div className="av-page av-stack">
          <Skeleton height={160} />
        </div>
      </>
    );
  }

  const status = item?.status ?? 'none';
  const editable = status === 'none' || status === 'draft' || status === 'resubmit_requested' || status === 'rejected';
  const chosenType = item?.document_type || draft.documentType;
  const needsBack = options.document_types.find((type) => type.key === chosenType)?.needs_back ?? false;

  const kinds: { key: string; label: string }[] = [
    { key: 'front', label: 'Лицевая сторона' },
    ...(needsBack ? [{ key: 'back', label: 'Оборотная сторона' }] : []),
    options.selfie_with_document
      ? { key: 'selfie_with_document', label: 'Селфи с документом в руках' }
      : { key: 'selfie', label: 'Селфи' },
  ];

  return (
    <>
      <TopBar back="/settings" title="Проверка личности" />
      <div className="av-page av-stack">
        <Card>
          <SectionHeading
            title="Зачем это нужно"
            action={
              <Badge tone={identityTone(status)} size="sm">
                {item?.status_label || identityStatusLabel(status)}
              </Badge>
            }
          />
          <p className="av-small av-muted">
            Подтверждённая личность — это значок на профиле и доверие заказчика. Изображения видит только
            сотрудник с отдельным разрешением, каждый просмотр записывается, а после решения снимки
            удаляются: у площадки остаётся результат проверки, а не ваш паспорт.
          </p>
        </Card>

        {error ? <p className={styles.alert}>{error}</p> : null}
        {ok ? <p className={styles.ok}>{ok}</p> : null}

        {status === 'approved' ? (
          <Card>
            <p className="av-small">
              Личность подтверждена {item?.reviewed_at ? longDate(item.reviewed_at) : ''}.
              {item?.retention_expires_at
                ? ` Изображения будут удалены ${longDate(item.retention_expires_at)}.`
                : ''}
            </p>
          </Card>
        ) : null}

        {status === 'submitted' || status === 'under_review' ? (
          <Card>
            <p className="av-small">
              Документы у проверяющего. Пока идёт проверка, менять их нельзя — если вы ошиблись, дождитесь
              ответа: вам скажут, что именно переснять.
            </p>
          </Card>
        ) : null}

        {item?.resubmit && item.resubmit.length > 0 ? (
          <Card>
            <SectionHeading title="Что нужно переснять" />
            <ul className={styles.list}>
              {item.resubmit.map((reason) => (
                <li key={reason.key}>{reason.label}</li>
              ))}
            </ul>
            {item.decision_reason ? <p className="av-small av-muted">{item.decision_reason}</p> : null}
          </Card>
        ) : null}

        {status === 'rejected' && item?.decision_reason ? (
          <Card>
            <SectionHeading title="Почему отказано" />
            <p className="av-small">{item.decision_reason}</p>
            <p className="av-xs av-faint">Можно загрузить документы заново и отправить ещё раз.</p>
          </Card>
        ) : null}

        <Card>
          <SectionHeading title="Документ" />
          <div className={styles.form}>
            <Select
              label="Что вы покажете"
              value={item?.document_type || draft.documentType}
              disabled={!editable || busy}
              onChange={(event) =>
                void saveDetails(event.target.value, item?.country_code || draft.countryCode)
              }
            >
              <option value="">Выберите документ</option>
              {options.document_types.map((type) => (
                <option key={type.key} value={type.key}>
                  {type.label}
                </option>
              ))}
            </Select>
            <Select
              label="Страна выдачи"
              value={item?.country_code || draft.countryCode}
              disabled={!editable || busy}
              hint="Страна, которая выдала документ."
              onChange={(event) =>
                void saveDetails(item?.document_type || draft.documentType, event.target.value)
              }
            >
              <option value="">Выберите страну</option>
              {COUNTRIES.map((country) => (
                <option key={country.code} value={country.code}>
                  {country.label}
                </option>
              ))}
            </Select>
          </div>
        </Card>

        {item && item.document_type ? (
          <Card>
            <SectionHeading title="Снимки" />
            <p className="av-small av-muted">
              Снимайте при ровном свете, целиком, без бликов. Не больше {fileSize(options.max_bytes)} на файл,
              JPEG, PNG или WebP.
            </p>
            <div className={styles.slots}>
              {kinds.map((kind) => (
                <Slot
                  key={kind.key}
                  kind={kind.key}
                  label={kind.label}
                  uploaded={item.documents.some((doc) => doc.kind === kind.key && !doc.deleted_at)}
                  disabled={!editable}
                  onDone={(next) => setItem(next)}
                  onError={setError}
                />
              ))}
            </div>
          </Card>
        ) : null}

        {editable && item ? (
          <Card>
            <SectionHeading title="Отправить на проверку" />
            {item.missing.length > 0 ? (
              <p className="av-small av-muted">Ещё не хватает: {item.missing.join(', ')}.</p>
            ) : (
              <p className="av-small av-muted">Всё на месте. После отправки менять снимки будет нельзя.</p>
            )}
            <div style={{ marginTop: 'var(--av-space-3)' }}>
              <Button loading={busy} disabled={item.missing.length > 0} onClick={() => void submit()}>
                Отправить
              </Button>
            </div>
          </Card>
        ) : null}
      </div>
    </>
  );
}

function Slot({
  kind,
  label,
  uploaded,
  disabled,
  onDone,
  onError,
}: {
  kind: string;
  label: string;
  uploaded: boolean;
  disabled: boolean;
  onDone: (next: IdentityCase) => void;
  onError: (message: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function send(file: File) {
    setBusy(true);
    onError('');
    try {
      const form = new FormData();
      form.set('kind', kind);
      form.set('file', file);
      onDone(await upload<IdentityCase>('/account/identity/documents', form));
    } catch (failure) {
      onError(
        failure instanceof ApiFailure ? Object.values(failure.fields)[0] || failure.message : 'Файл не принят.',
      );
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  }

  return (
    <div className={styles.slot}>
      <p className="av-small av-strong">{label}</p>
      <p className="av-xs av-faint">{uploaded ? 'Загружено' : 'Пока пусто'}</p>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void send(file);
        }}
      />
      <Button
        variant="secondary"
        size="sm"
        loading={busy}
        disabled={disabled}
        onClick={() => input.current?.click()}
      >
        {uploaded ? 'Заменить' : 'Загрузить'}
      </Button>
    </div>
  );
}
