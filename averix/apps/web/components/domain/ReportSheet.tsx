'use client';

import { useEffect, useState } from 'react';
import { Sheet } from '@/components/ui/Sheet';
import { Button } from '@/components/ui/Button';
import { Select, Textarea } from '@/components/ui/Field';
import { ApiFailure, get, post } from '@/lib/api';

/** Жалоба на пользователя, заказ, услугу, сообщение или отзыв. */
export function ReportSheet({
  open,
  subjectType,
  subjectId,
  title,
  onClose,
}: {
  open: boolean;
  subjectType: string;
  subjectId: string;
  title?: string;
  onClose: () => void;
}) {
  const [reasons, setReasons] = useState<{ key: string; label: string }[]>([]);
  const [reason, setReason] = useState('');
  const [detail, setDetail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!open) return;
    get<{ key: string; label: string }[]>('/reports/reasons')
      .then((list) => {
        setReasons(list);
        if (!reason && list.length) setReason(list[0].key);
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function submit() {
    setBusy(true);
    setError('');
    setFields({});
    try {
      await post('/reports', { subject_type: subjectType, subject_id: subjectId, reason, detail: detail.trim() });
      setDone(true);
    } catch (failure) {
      if (failure instanceof ApiFailure) {
        setFields(failure.fields);
        setError(Object.keys(failure.fields).length ? '' : failure.message);
      } else {
        setError('Не удалось отправить жалобу.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Пожаловаться"
      description={title}
      size="sm"
      footer={
        done ? (
          <Button onClick={onClose}>Закрыть</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>
              Отмена
            </Button>
            <Button loading={busy} disabled={!reason} onClick={() => void submit()}>
              Отправить
            </Button>
          </>
        )
      }
    >
      {done ? (
        <p className="av-muted">Спасибо. Модератор посмотрит и примет решение; вы не увидите переписку по жалобе, но она не останется без ответа.</p>
      ) : (
        <div className="av-stack">
          {error ? (
            <p role="alert" style={{ color: 'var(--av-danger)' }}>
              {error}
            </p>
          ) : null}
          <Select label="Причина" value={reason} error={fields.reason} onChange={(event) => setReason(event.target.value)}>
            {reasons.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}
              </option>
            ))}
          </Select>
          <Textarea
            label="Подробности"
            optional
            max={2000}
            rows={4}
            placeholder="Что именно вас насторожило."
            value={detail}
            error={fields.detail}
            onChange={(event) => setDetail(event.target.value)}
          />
        </div>
      )}
    </Sheet>
  );
}
