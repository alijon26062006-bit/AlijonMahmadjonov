'use client';

import { useCallback, useEffect, useState } from 'react';
import styles from './viewer.module.css';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { ApiFailure, post } from '@/lib/api';
import type { IdentityDocument, IdentityViewToken } from '@/lib/types';

const ZOOMS = [0.5, 0.75, 1, 1.5, 2, 3, 4];

/**
 * The document viewer.
 *
 * It asks for the reason before it asks for the image, because the reason is
 * what the access log is for. The ticket it gets back is good for two minutes
 * and for this reviewer only; when it runs out the image goes and the button
 * to ask for another one comes back — a viewer left open on a desk does not
 * keep showing a passport.
 *
 * There is no download button, no context menu handler and no link out: the
 * bytes are on screen while somebody is looking at them and nowhere else.
 */
export function DocumentViewer({
  documents,
  index,
  onIndex,
  onClose,
}: {
  documents: IdentityDocument[];
  index: number;
  onIndex: (next: number) => void;
  onClose: () => void;
}) {
  const doc = documents[index];
  const [reason, setReason] = useState('');
  const [ticket, setTicket] = useState<IdentityViewToken | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [zoom, setZoom] = useState(1);
  const [angle, setAngle] = useState(0);
  const [left, setLeft] = useState(0);

  // A ticket belongs to one image: moving to the next one starts again.
  useEffect(() => {
    setTicket(null);
    setError('');
    setZoom(1);
    setAngle(0);
  }, [index]);

  const request = useCallback(async () => {
    setBusy(true);
    setError('');
    try {
      setTicket(
        await post<IdentityViewToken>(`/admin/identity/documents/${doc.id}/token`, { reason: reason.trim() }),
      );
    } catch (failure) {
      setError(failure instanceof ApiFailure ? failure.message : 'Не получилось открыть изображение.');
    } finally {
      setBusy(false);
    }
  }, [doc.id, reason]);

  // The countdown is the honest thing to show: the ticket really does stop
  // working, and the image really does disappear with it.
  useEffect(() => {
    if (!ticket) return;
    const tick = () => {
      const remaining = Math.max(0, Math.round((new Date(ticket.expires_at).getTime() - Date.now()) / 1000));
      setLeft(remaining);
      if (remaining === 0) setTicket(null);
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [ticket]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight' && index < documents.length - 1) onIndex(index + 1);
      if (event.key === 'ArrowLeft' && index > 0) onIndex(index - 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [index, documents.length, onIndex, onClose]);

  function step(direction: 1 | -1) {
    const current = ZOOMS.indexOf(zoom);
    const next = Math.min(ZOOMS.length - 1, Math.max(0, (current === -1 ? 2 : current) + direction));
    setZoom(ZOOMS[next]);
  }

  return (
    <div className={styles.backdrop} role="dialog" aria-modal="true" aria-label={`Документ: ${doc.kind_label}`}>
      <div className={styles.shell}>
        <header className={styles.bar}>
          <div className="av-grow">
            <p className="av-small av-strong">{doc.kind_label}</p>
            <p className="av-xs av-faint">
              {index + 1} из {documents.length}
              {ticket ? ` · доступ закроется через ${left} с` : ''}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Закрыть
          </Button>
        </header>

        <div className={styles.stage} onContextMenu={(event) => event.preventDefault()}>
          {ticket ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={ticket.url}
              alt={doc.kind_label}
              className={styles.image}
              draggable={false}
              style={{ transform: `rotate(${angle}deg) scale(${zoom})` }}
              onError={() => {
                setTicket(null);
                setError('Доступ истёк. Запросите изображение заново.');
              }}
            />
          ) : (
            <div className={styles.gate}>
              <p className="av-small av-muted">
                Укажите, зачем вы открываете документ. Это попадёт в журнал рядом с вашим именем.
              </p>
              <Input
                label="Причина"
                placeholder="Например: сверка имени с профилем"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                error={error || undefined}
              />
              <Button loading={busy} disabled={reason.trim().length < 3} onClick={() => void request()}>
                Показать изображение
              </Button>
            </div>
          )}
        </div>

        <footer className={styles.bar}>
          <Button variant="secondary" size="sm" disabled={index === 0} onClick={() => onIndex(index - 1)}>
            Назад
          </Button>
          <div className={styles.tools}>
            <Button variant="ghost" size="sm" disabled={!ticket} onClick={() => step(-1)}>
              −
            </Button>
            <span className="av-xs av-faint">{Math.round(zoom * 100)}%</span>
            <Button variant="ghost" size="sm" disabled={!ticket} onClick={() => step(1)}>
              +
            </Button>
            <Button variant="ghost" size="sm" disabled={!ticket} onClick={() => setZoom(1)}>
              По размеру
            </Button>
            <Button variant="ghost" size="sm" disabled={!ticket} onClick={() => setAngle((a) => (a + 90) % 360)}>
              Повернуть
            </Button>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={index >= documents.length - 1}
            onClick={() => onIndex(index + 1)}
          >
            Дальше
          </Button>
        </footer>
      </div>
    </div>
  );
}
