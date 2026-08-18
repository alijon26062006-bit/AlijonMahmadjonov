/** Баннеры на главной.

    Несколько — листаются пальцем по очереди, порядок задаёт владелец в
    панели. Текст рисуется поверх фотографии как обычная разметка, а не
    запекается в картинку: так он остаётся резким на любом экране и
    правится без перерисовки.
*/
import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, photoUrl } from '../api/client';
import type { BannerOut } from '../api/types';

export default function Banners() {
  const [index, setIndex] = useState(0);
  const track = useRef<HTMLDivElement>(null);

  const { data } = useQuery<{ items: BannerOut[] }>({
    queryKey: ['banners'], queryFn: () => api('/api/banners'),
    staleTime: 5 * 60_000,
  });
  const items = data?.items ?? [];

  useEffect(() => {
    const el = track.current;
    if (!el) return;
    const onScroll = () => setIndex(Math.round(el.scrollLeft / (el.clientWidth || 1)));
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, [items.length]);

  if (!items.length) return null;

  return (
    <div className="banners">
      <div className="banner-track" ref={track}>
        {items.map((b) => {
          const inner = (
            <>
              <img src={photoUrl(b.photo)} alt={b.title ?? ''}
                   loading="lazy" decoding="async" />
              {(b.eyebrow || b.title || b.subtitle || b.button_text) && (
                <div className="banner-text">
                  {b.eyebrow && <span className="banner-eyebrow">{b.eyebrow}</span>}
                  {b.title && <span className="banner-title">{b.title}</span>}
                  {b.subtitle && <span className="banner-sub">{b.subtitle}</span>}
                  {b.button_text && (
                    <span className="banner-cta">{b.button_text}</span>
                  )}
                </div>
              )}
            </>
          );
          return b.link
            ? <Link key={b.id} to={b.link} className="banner">{inner}</Link>
            : <div key={b.id} className="banner">{inner}</div>;
        })}
      </div>

      {items.length > 1 && (
        <div className="dots" aria-hidden="true">
          {items.map((b, i) => <i key={b.id} className={i === index ? 'on' : ''} />)}
        </div>
      )}
    </div>
  );
}
