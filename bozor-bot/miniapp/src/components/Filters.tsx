/** Фильтры каталога, генерируемые из схемы категории.
    Компонент фильтра выбирается по типу поля: range / multiselect / checkbox. */
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { FieldOut, SchemaOut } from '../api/types';

type Values = Record<string, string>;

export function useSchema(slug?: string) {
  return useQuery<SchemaOut>({
    queryKey: ['schema', slug],
    queryFn: () => api(`/api/categories/${slug}/schema`),
    enabled: Boolean(slug),
    staleTime: 5 * 60_000,
  });
}

export function countActive(schema: SchemaOut | undefined, values: Values): number {
  if (!schema) return 0;
  let n = 0;
  for (const f of schema.fields) {
    if (f.filter === 'none') continue;
    if (f.filter === 'range') {
      if (values[`${f.key}_min`] || values[`${f.key}_max`]) n += 1;
    } else if (values[f.key]) n += 1;
  }
  if (values.price_min || values.price_max) n += 1;
  return n;
}

function MultiSelect({ f, values, set }: { f: FieldOut; values: Values; set: (k: string, v: string) => void }) {
  const selected = new Set((values[f.key] || '').split(',').filter(Boolean));
  const toggle = (v: string) => {
    const next = new Set(selected);
    next.has(v) ? next.delete(v) : next.add(v);
    set(f.key, [...next].join(','));
  };
  const options = f.options ?? [];
  if (!options.length) return null;
  return (
    <div className="field">
      <span className="field-label">{f.label}</span>
      <div className="chips">
        {options.map(([v, label]) => (
          <button key={v} type="button"
                  className={`chip ${selected.has(v) ? 'on' : ''}`}
                  onClick={() => toggle(v)}>
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Range({ f, values, set }: { f: FieldOut; values: Values; set: (k: string, v: string) => void }) {
  return (
    <div className="field">
      <span className="field-label">{f.label}{f.unit ? `, ${f.unit}` : ''}</span>
      <div className="range-row">
        <input inputMode="numeric" placeholder="от"
               value={values[`${f.key}_min`] || ''}
               onChange={(e) => set(`${f.key}_min`, e.target.value)} />
        <input inputMode="numeric" placeholder="до"
               value={values[`${f.key}_max`] || ''}
               onChange={(e) => set(`${f.key}_max`, e.target.value)} />
      </div>
    </div>
  );
}

function Checkbox({ f, values, set }: { f: FieldOut; values: Values; set: (k: string, v: string) => void }) {
  const on = values[f.key] === 'true';
  return (
    <button type="button" className={`chip ${on ? 'on' : ''}`}
            style={{ marginRight: 8, marginBottom: 8 }}
            onClick={() => set(f.key, on ? '' : 'true')}>
      {f.label}
    </button>
  );
}

export function FilterFields({ schema, values, set }: {
  schema: SchemaOut; values: Values; set: (k: string, v: string) => void;
}) {
  const fields = schema.fields.filter((f) => f.filter !== 'none');
  const checkboxes = fields.filter((f) => f.filter === 'checkbox');
  const rest = fields.filter((f) => f.filter !== 'checkbox');
  return (
    <>
      <div className="field">
        <span className="field-label">Цена, $</span>
        <div className="range-row">
          <input inputMode="numeric" placeholder="от"
                 value={values.price_min || ''}
                 onChange={(e) => set('price_min', e.target.value)} />
          <input inputMode="numeric" placeholder="до"
                 value={values.price_max || ''}
                 onChange={(e) => set('price_max', e.target.value)} />
        </div>
      </div>
      {rest.map((f) => {
        if (f.key === 'price') return null;
        if (f.filter === 'range') return <Range key={f.key} f={f} values={values} set={set} />;
        return <MultiSelect key={f.key} f={f} values={values} set={set} />;
      })}
      {checkboxes.length > 0 && (
        <div className="field">
          <span className="field-label">Дополнительно</span>
          <div>
            {checkboxes.map((f) => <Checkbox key={f.key} f={f} values={values} set={set} />)}
          </div>
        </div>
      )}
    </>
  );
}

export function FilterSheet({ schema, values, set, onClose, onReset, total, hasMore }: {
  schema: SchemaOut; values: Values;
  set: (k: string, v: string) => void;
  onClose: () => void; onReset: () => void;
  total?: number;
  /** есть ли ещё страницы — тогда показываем «N+», а не точное число */
  hasMore?: boolean;
}) {
  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grabber" />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
          <b style={{ fontSize: 'var(--fs-lg)' }}>Фильтры</b>
          <button className="btn-ghost" onClick={onReset}>Сбросить</button>
        </div>
        <FilterFields schema={schema} values={values} set={set} />
        <button className="btn btn-primary btn-block" onClick={onClose}>
          {typeof total === 'number'
            ? (total === 0 ? 'Ничего не найдено' : `Показать ${total}${hasMore ? '+' : ''}`)
            : 'Показать'}
        </button>
      </div>
    </div>
  );
}
