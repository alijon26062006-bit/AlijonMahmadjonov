/** Строка поиска с подсказками.

    В магазине с большим ассортиментом поиск — главный инструмент, поэтому
    подсказки появляются с первого символа и делятся на три группы: разделы,
    бренды и сами товары с миниатюрой. Запрос уходит через четверть секунды
    после последнего нажатия — иначе на каждую букву летит запрос.
*/
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, fmtPrice, photoUrl } from '../api/client';
import type { Card, Group } from '../api/types';
import { Icon } from './icons';

const RECENT_KEY = 'stambul.recent';
const RECENT_MAX = 6;
const DEBOUNCE = 250;

export function recentSearches(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    return Array.isArray(raw) ? raw.filter((s) => typeof s === 'string') : [];
  } catch { return []; }
}

export function rememberSearch(q: string): void {
  const value = q.trim();
  if (value.length < 2) return;
  const next = [value, ...recentSearches().filter((s) => s !== value)]
    .slice(0, RECENT_MAX);
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)); }
  catch { /* приватный режим — обойдёмся без истории */ }
}

type Suggestions = { groups: Group[]; items: Card[] };

export default function SearchBox({ initial = '', autoFocus = false }: {
  initial?: string; autoFocus?: boolean;
}) {
  const navigate = useNavigate();
  const [text, setText] = useState(initial);
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Suggestions>({ groups: [], items: [] });
  const box = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { setText(initial); }, [initial]);

  // Клик мимо закрывает подсказки. Через onBlur это работает хуже: он
  // срабатывает раньше клика по самой подсказке.
  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', away);
    return () => document.removeEventListener('mousedown', away);
  }, []);

  useEffect(() => {
    const q = text.trim();
    if (!open) return;
    if (q.length < 1) { setData({ groups: [], items: [] }); return; }
    let cancelled = false;
    const id = setTimeout(async () => {
      try {
        const [cats, found] = await Promise.all([
          api<{ groups: Group[] }>('/api/categories'),
          api<{ items: Card[] }>(`/api/products?q=${encodeURIComponent(q)}`),
        ]);
        if (cancelled) return;
        const needle = q.toLowerCase();
        const groups = cats.groups
          .map((g) => ({
            ...g,
            categories: g.categories.filter((c) =>
              c.title.toLowerCase().includes(needle)),
          }))
          .filter((g) => g.categories.length);
        setData({ groups, items: found.items.slice(0, 5) });
      } catch { /* подсказки — не повод показывать ошибку */ }
    }, DEBOUNCE);
    return () => { cancelled = true; clearTimeout(id); };
  }, [text, open]);

  const submit = (q: string) => {
    const value = q.trim();
    rememberSearch(value);
    setOpen(false);
    input.current?.blur();
    navigate(value ? `/catalog?q=${encodeURIComponent(value)}` : '/catalog');
  };

  const recent = recentSearches();
  const empty = text.trim().length === 0;
  const nothing = !empty && !data.groups.length && !data.items.length;

  return (
    <div className="searchbox" ref={box}>
      <span className="ico-left"><Icon name="search" size={18} strokeWidth={2.2} /></span>
      <input
        ref={input}
        className="input"
        value={text}
        autoFocus={autoFocus}
        enterKeyHint="search"
        placeholder="Что ищете?"
        aria-label="Поиск по магазину"
        onFocus={() => setOpen(true)}
        onChange={(e) => { setText(e.target.value); setOpen(true); }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') submit(text);
          if (e.key === 'Escape') { setOpen(false); input.current?.blur(); }
        }} />
      {text && (
        <button className="ico-clear" aria-label="Очистить"
                onClick={() => { setText(''); input.current?.focus(); }}>
          <Icon name="x" size={16} strokeWidth={2.4} />
        </button>
      )}

      {open && (
        <div className="suggest">
          {empty && recent.length > 0 && (
            <div className="suggest-group">
              <div className="suggest-head">Вы искали</div>
              {recent.map((q) => (
                <button key={q} className="suggest-item" onClick={() => submit(q)}>
                  <Icon name="rotate-ccw" size={16} />
                  <span>{q}</span>
                </button>
              ))}
            </div>
          )}

          {empty && recent.length === 0 && (
            <div className="suggest-group">
              <div className="suggest-head">Часто ищут</div>
              {['платье', 'кроссовки', 'куртка', 'постельное бельё'].map((q) => (
                <button key={q} className="suggest-item" onClick={() => submit(q)}>
                  <Icon name="search" size={16} />
                  <span>{q}</span>
                </button>
              ))}
            </div>
          )}

          {data.groups.map((g) => (
            <div className="suggest-group" key={g.title}>
              <div className="suggest-head">{g.title}</div>
              {g.categories.map((c) => (
                <button key={c.slug} className="suggest-item"
                        onClick={() => { setOpen(false); navigate(`/catalog?category=${c.slug}`); }}>
                  <Icon name="list" size={16} />
                  <span>{c.title}</span>
                </button>
              ))}
            </div>
          ))}

          {data.items.length > 0 && (
            <div className="suggest-group">
              <div className="suggest-head">Товары</div>
              {data.items.map((p) => (
                <button key={p.id} className="suggest-item"
                        onClick={() => { setOpen(false); navigate(`/p/${p.id}`); }}>
                  {p.photo
                    ? <img src={photoUrl(p.photo)} alt="" loading="lazy" />
                    : <span style={{ width: 34 }} />}
                  <span style={{ flex: 1, textAlign: 'left' }}>{p.title}</span>
                  <span className="price">{fmtPrice(p.price)}</span>
                </button>
              ))}
            </div>
          )}

          {/* Пустая выдача — не тупик: даём уйти в каталог, а не в никуда */}
          {nothing && (
            <div className="suggest-group">
              <div className="suggest-head">
                По запросу «{text.trim()}» ничего не нашлось
              </div>
              <button className="suggest-item" onClick={() => submit('')}>
                <Icon name="arrow-right" size={16} />
                <span>Смотреть весь каталог</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
