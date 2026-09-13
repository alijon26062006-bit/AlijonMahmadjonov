'use client';

import { useEffect, useState } from 'react';
import styles from './PreviewBrowser.module.css';
import { Button } from '@/components/ui/Button';
import {
  IconClose,
  IconExternal,
  IconLock,
  IconMonitor,
  IconPhone,
  IconRefresh,
  IconTablet,
} from '@/components/ui/Icon';
import { get } from '@/lib/api';
import type { PreviewResponse } from '@/lib/types';

/**
 * The in-app project browser.
 *
 * Clicking "Live preview" keeps the visitor inside AVERIX: this is a small
 * browser — address bar, reload, open externally, close — around a sandboxed
 * frame. Every permission on that frame is decided by the server, and the
 * component simply applies what it is given.
 *
 * When a site refuses to be framed, that refusal is honoured: the frame is not
 * rendered at all, and the visitor gets the developer's own screenshot with a
 * button that opens the real site in a new tab.
 */
export function PreviewBrowser({
  username,
  slug,
  onClose,
}: {
  username: string;
  slug: string;
  onClose: () => void;
}) {
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [device, setDevice] = useState('desktop');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    get<PreviewResponse>(`/developers/${username}/portfolio/${slug}/preview`)
      .then((data) => !cancelled && setPreview(data))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [username, slug]);

  const frame = preview?.frame;
  const allowed = frame?.verdict === 'allowed';
  const width = frame?.devices?.find((item) => item.key === device)?.width;

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Предпросмотр сайта">
      <div className={styles.window}>
        <header className={styles.chrome}>
          <button type="button" className={styles.chromeButton} onClick={onClose} aria-label="Закрыть предпросмотр">
            <IconClose size={18} />
          </button>

          <div className={styles.address}>
            <IconLock size={13} />
            <span className={styles.host}>{frame?.host ?? 'загрузка…'}</span>
          </div>

          <div className={styles.chromeActions}>
            <button
              type="button"
              className={styles.chromeButton}
              onClick={() => setReloadKey((key) => key + 1)}
              aria-label="Обновить"
              disabled={!allowed}
            >
              <IconRefresh size={17} />
            </button>
            {frame?.url ? (
              <a
                className={styles.chromeButton}
                href={frame.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                aria-label="Открыть в новой вкладке"
              >
                <IconExternal size={17} />
              </a>
            ) : null}
          </div>
        </header>

        {allowed ? (
          <div className={styles.devices}>
            {[
              { key: 'mobile', label: 'Телефон', icon: <IconPhone size={15} /> },
              { key: 'tablet', label: 'Планшет', icon: <IconTablet size={15} /> },
              { key: 'desktop', label: 'Компьютер', icon: <IconMonitor size={15} /> },
            ].map((option) => (
              <button
                key={option.key}
                type="button"
                className={[styles.device, device === option.key ? styles.deviceActive : ''].join(' ')}
                onClick={() => setDevice(option.key)}
                aria-pressed={device === option.key}
              >
                {option.icon}
                <span className={styles.deviceLabel}>{option.label}</span>
              </button>
            ))}
          </div>
        ) : null}

        <div className={styles.viewport}>
          {failed ? (
            <Unavailable
              title="Не удалось открыть предпросмотр"
              body="Что-то пошло не так на нашей стороне. Сам сайт, скорее всего, в порядке."
              url={frame?.url}
            />
          ) : !preview ? (
            <div className={styles.loading}>Загружаем предпросмотр…</div>
          ) : allowed ? (
            <div
              className={styles.frameHolder}
              style={width ? { width, maxWidth: '100%' } : undefined}
            >
              <iframe
                key={reloadKey}
                src={frame?.url}
                title={preview.project.title}
                className={styles.frame}
                // Every attribute below comes from the server's verdict. The
                // sandbox deliberately withholds allow-same-origin, so the
                // embedded page runs in an opaque origin with no access to
                // AVERIX — no cookies, no session, no parent document.
                sandbox={frame?.sandbox}
                referrerPolicy={frame?.referrer_policy as React.HTMLAttributeReferrerPolicy}
                allow={frame?.permissions_policy}
                loading="lazy"
              />
            </div>
          ) : (
            <Unavailable
              title="Предпросмотр этого сайта недоступен"
              body={
                frame?.verdict === 'unreachable'
                  ? 'Сайт сейчас не отвечает.'
                  : 'Сайт запрещает показывать себя внутри другой страницы. Это его выбор, и AVERIX его уважает.'
              }
              url={frame?.url}
              screenshot={preview.fallback?.url}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function Unavailable({
  title,
  body,
  url,
  screenshot,
}: {
  title: string;
  body: string;
  url?: string;
  screenshot?: string;
}) {
  return (
    <div className={styles.unavailable}>
      {screenshot ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={screenshot} alt="" className={styles.screenshot} />
      ) : null}
      <div className={styles.unavailableText}>
        <h3 className="av-strong">{title}</h3>
        <p className="av-small av-muted">{body}</p>
        {url ? (
          <Button
            variant="secondary"
            icon={<IconExternal size={16} />}
            onClick={() => window.open(url, '_blank', 'noopener,noreferrer')}
          >
            Открыть сайт
          </Button>
        ) : null}
      </div>
    </div>
  );
}
