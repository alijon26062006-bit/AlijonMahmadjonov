/** Строка поиска: одна на всё приложение — на главной и в каталоге.
 *  Лупа внутри поля, крестик для очистки, недавние запросы под рукой. */
import { useEffect, useRef, useState } from 'react';
import { Icon } from './icons';
import { haptic } from '../telegram/tg';

const RECENT_KEY = 'recent-searches';
const RECENT_MAX = 6;

export function recentSearches(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    return Array.isArray(raw) ? raw.filter((s) => typeof s === 'string') : [];
  } catch {
    return [];
  }
}

export function rememberSearch(q: string): void {
  const value = q.trim();
  if (value.length < 2) return;
  const next = [value, ...recentSearches().filter((s) => s !== value)]
    .slice(0, RECENT_MAX);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch { /* приватный режим — обойдёмся без истории */ }
}

export function SearchBox({ value, placeholder, onSearch, autoFocus, children }: {
  value?: string;
  placeholder?: string;
  onSearch: (q: string) => void;
  autoFocus?: boolean;
  /** кнопки справа от поля: фильтры, карта */
  children?: React.ReactNode;
}) {
  const [text, setText] = useState(value ?? '');
  const [focused, setFocused] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  // Внешнее значение меняется при переходе по ссылке с готовым запросом
  useEffect(() => { setText(value ?? ''); }, [value]);

  const submit = (q: string) => {
    rememberSearch(q);
    setFocused(false);
    input.current?.blur();
    onSearch(q.trim());
  };

  const recent = recentSearches();
  const showRecent = focused && !text && recent.length > 0;

  return (
    <div className="search-wrap">
      <div className={`search-field${focused ? ' on' : ''}`}>
        <Icon name="search" size={18} strokeWidth={2.2} />
        <input
          ref={input}
          value={text}
          placeholder={placeholder ?? 'Поиск'}
          autoFocus={autoFocus}
          enterKeyHint="search"
          onChange={(e) => setText(e.target.value)}
          onFocus={() => setFocused(true)}
          // клик по подсказке успевает пройти до закрытия списка
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          onKeyDown={(e) => { if (e.key === 'Enter') submit(text); }} />
        {text && (
          <button className="search-clear" aria-label="Очистить"
                  onClick={() => { haptic(); setText(''); onSearch(''); input.current?.focus(); }}>
            <Icon name="x" size={16} strokeWidth={2.4} />
          </button>
        )}
      </div>
      {children}

      {showRecent && (
        <div className="search-recent">
          <span className="subtitle">Вы искали</span>
          <div className="chips" style={{ marginTop: 8 }}>
            {recent.map((q) => (
              <button key={q} className="chip"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => { setText(q); submit(q); }}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
