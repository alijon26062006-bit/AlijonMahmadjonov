/** Подача с сайта: форма строится из той же схемы, что и мастер в боте.
    В Telegram подача идёт через диалог с ботом — здесь только подсказка. */
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { API, api, photoUrl } from '../api/client';
import type { Direction, FieldOut } from '../api/types';
import { useSchema } from '../components/Filters';
import { PickMap } from '../components/MapView';
import { Empty, useAuth, useTgBackButton } from '../components/ui';
import { inTelegram, tg } from '../telegram/tg';

// Раздел техники → область брендов (зеркало серверной карты)
const SECTION_AREA: Record<string, string> = {
  phones: 'phones', tablets: 'phones', laptops: 'computers', desktops: 'computers',
  tvs: 'tv_audio', audio: 'tv_audio', appliances: 'appliances',
  photo: 'electronics', consoles: 'electronics', watches: 'electronics', other: 'electronics',
};

type UploadedPhoto = {
  file_id: string; thumb_file_id: string; file_unique_id: string;
  width: number; height: number; sig: string; preview: string;
};

function useFieldOptions(f: FieldOut, values: Record<string, unknown>) {
  const dep = f.depends_on ? String(values[f.depends_on] ?? '') : '';
  const section = String(values.section ?? '');
  return useQuery<[string, string][]>({
    queryKey: ['opts', f.key, f.options_ref, dep, section],
    queryFn: async () => {
      const ref = f.options_ref ?? '';
      const [kind, area] = ref.split(':');
      if (kind === 'models') {
        const r = await api<{ items: { name: string }[] }>(
          `/api/dicts/models?brand=${encodeURIComponent(dep)}&area=${area || 'cars'}`);
        return r.items.map((m) => [m.name, m.name]);
      }
      if (kind === 'districts') {
        if (!dep) return [];
        const r = await api<{ items: { id: number; name: string }[] }>(
          `/api/dicts/districts?city_id=${dep}`);
        return r.items.map((d) => [String(d.id), d.name]);
      }
      if (kind === 'brands') {
        const realArea = area === '@section' ? (SECTION_AREA[section] ?? 'electronics') : area;
        const r = await api<{ items: { name: string }[] }>(`/api/dicts/brands?area=${realArea}`);
        return r.items.map((b) => [b.name, b.name]);
      }
      return [];
    },
    enabled: Boolean(f.options_ref) && !f.options && (!f.depends_on || Boolean(dep))
             && (f.options_ref?.includes('@section') ? Boolean(section) : true),
    staleTime: 5 * 60_000,
  });
}

function Field({ f, values, set, error }: {
  f: FieldOut; values: Record<string, unknown>;
  set: (k: string, v: unknown) => void; error?: string;
}) {
  const dynamic = useFieldOptions(f, values);
  const options = f.options ?? dynamic.data ?? [];
  const [other, setOther] = useState(false);

  const label = (
    <span className="field-label">
      {f.label}{f.unit ? `, ${f.unit}` : ''}
      {f.required && <span style={{ color: 'var(--danger)' }}> *</span>}
    </span>
  );

  let control: JSX.Element;
  switch (f.type) {
    case 'bool':
      control = (
        <div className="chips">
          {[['true', 'Да'], ['false', 'Нет']].map(([v, l]) => (
            <button key={v} type="button"
                    className={`chip ${String(values[f.key]) === v ? 'on' : ''}`}
                    onClick={() => set(f.key, v === 'true')}>{l}</button>
          ))}
        </div>
      );
      break;
    case 'enum_one':
      control = other ? (
        <input placeholder="Свой вариант"
               value={String(values[f.key] ?? '')}
               onChange={(e) => set(f.key, e.target.value)} />
      ) : options.length <= 6 ? (
        <div className="chips">
          {options.map(([v, l]) => (
            <button key={v} type="button"
                    className={`chip ${values[f.key] === v ? 'on' : ''}`}
                    onClick={() => set(f.key, v)}>{l}</button>
          ))}
          {f.allow_other && (
            <button type="button" className="chip" onClick={() => setOther(true)}>Другое</button>
          )}
        </div>
      ) : (
        <select value={String(values[f.key] ?? '')}
                onChange={(e) => {
                  if (e.target.value === '__other__') { setOther(true); set(f.key, ''); }
                  else set(f.key, e.target.value);
                }}>
          <option value="">— выберите —</option>
          {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          {f.allow_other && <option value="__other__">Другое</option>}
        </select>
      );
      break;
    case 'enum_many': {
      const selected = new Set((values[f.key] as string[] | undefined) ?? []);
      control = (
        <div className="chips">
          {options.map(([v, l]) => (
            <button key={v} type="button"
                    className={`chip ${selected.has(v) ? 'on' : ''}`}
                    onClick={() => {
                      const next = new Set(selected);
                      next.has(v) ? next.delete(v) : next.add(v);
                      set(f.key, [...next]);
                    }}>{l}</button>
          ))}
        </div>
      );
      break;
    }
    case 'text':
      control = (
        <textarea rows={5} maxLength={f.max_len ?? 1000}
                  value={String(values[f.key] ?? '')}
                  onChange={(e) => set(f.key, e.target.value)} />
      );
      break;
    case 'money':
      control = (
        <div className="range-row">
          <input inputMode="decimal" placeholder="Сумма"
                 value={String(values[f.key] ?? '')}
                 onChange={(e) => set(f.key, e.target.value.replace(/[^\d.]/g, ''))} />
          <select style={{ width: 110, flex: 'none' }}
                  value={String(values.currency ?? 'TJS')}
                  onChange={(e) => set('currency', e.target.value)}>
            <option value="TJS">сомони</option>
            <option value="USD">$</option>
          </select>
        </div>
      );
      break;
    default: // int, decimal, string, identifier
      control = (
        <input inputMode={f.type === 'int' || f.type === 'decimal' ? 'numeric' : undefined}
               maxLength={f.max_len ?? undefined}
               value={String(values[f.key] ?? '')}
               onChange={(e) => set(f.key, e.target.value)} />
      );
  }

  return (
    <div className="field">
      {label}
      {control}
      {f.hint && !error && <div className="field-hint">{f.hint}</div>}
      {error && <div className="field-error">{error}</div>}
    </div>
  );
}

export default function PostPage() {
  useTgBackButton(true);
  const user = useAuth();
  const navigate = useNavigate();
  const [category, setCategory] = useState('');
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const { data: cats } = useQuery<{ directions: Direction[] }>({
    queryKey: ['categories'], queryFn: () => api('/api/categories'),
  });
  const { data: schema } = useSchema(category || undefined);

  const set = (k: string, v: unknown) => setValues((prev) => ({ ...prev, [k]: v }));

  const visibleFields = useMemo(() => {
    if (!schema) return [];
    return schema.fields.filter((f) => {
      if (!f.visible_if) return true;
      return Object.entries(f.visible_if).every(([k, allowed]) =>
        allowed.includes(String(values[k])));
    });
  }, [schema, values]);

  if (inTelegram) {
    return (
      <div className="section">
        <Empty icon="message-circle" title="Подача — в чате с ботом"
               note="Закройте приложение и нажмите «➕ Подать объявление» в меню бота: мастер задаст вопросы по шагам" />
        <button className="btn btn-primary btn-block" onClick={() => tg?.close()}>
          Перейти в чат с ботом
        </button>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="section">
        <Empty icon="lock" title="Сначала войдите"
               note="Подача объявлений доступна после входа через Telegram" />
        <Link to="/login" className="btn btn-primary btn-block">Войти</Link>
      </div>
    );
  }

  if (done) {
    return (
      <div className="section">
        <Empty icon="check" title="Отправлено на модерацию"
               note="Мы пришлём уведомление в Telegram, когда объявление проверят" />
        <Link to="/my" className="btn btn-primary btn-block">К моим объявлениям</Link>
      </div>
    );
  }

  const upload = async (files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files).slice(0, 10 - photos.length)) {
      const fd = new FormData();
      fd.append('file', file);
      try {
        const p = await api<Omit<UploadedPhoto, 'preview'>>(
          '/api/uploads/photo', { method: 'POST', body: fd });
        setPhotos((prev) => [...prev, { ...p, preview: URL.createObjectURL(file) }]);
        setErrors((prev) => ({ ...prev, photos: '' }));
      } catch (e) {
        // показываем причину с сервера, а не общее «не удалось»
        const msg = (e as Error).message || 'Не удалось загрузить фото';
        setErrors((prev) => ({ ...prev, photos: msg }));
      }
    }
  };

  const submit = async () => {
    if (!schema) return;
    const errs: Record<string, string> = {};
    for (const f of visibleFields) {
      if (f.type === 'photos') {
        if (!photos.length) errs.photos = 'Добавьте хотя бы одно фото';
        continue;
      }
      if (f.type === 'geo') continue;
      const v = values[f.key];
      if (f.required && (v === undefined || v === '' || v === null
          || (Array.isArray(v) && !v.length))) {
        errs[f.key] = 'Обязательное поле';
      }
    }
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setBusy(true);
    try {
      await api('/api/listings', {
        method: 'POST',
        body: JSON.stringify({
          category: schema.slug,
          values,
          photos: photos.map(({ preview, ...p }) => p),
        }),
      });
      setDone(true);
    } catch (e) {
      const err = e as Error;
      setErrors({ _global: err.message || 'Ошибка отправки' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="section fade-in" style={{ maxWidth: 640, margin: '0 auto' }}>
      <h1 className="section-title">Подать объявление</h1>

      <div className="field">
        <span className="field-label">Категория *</span>
        <select value={category}
                onChange={(e) => { setCategory(e.target.value); setValues({}); setErrors({}); }}>
          <option value="">— выберите —</option>
          {cats?.directions.map((d) => (
            <optgroup key={d.slug} label={d.title}>
              {d.categories.map((c) => (
                <option key={c.slug} value={c.slug}>{c.title}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {schema && visibleFields.map((f) => {
        if (f.type === 'photos') {
          return (
            <div className="field" key="photos">
              <span className="field-label">Фотографии * <span className="subtitle">({photos.length}/10)</span></span>
              <div className="upload-grid">
                {photos.map((p, i) => (
                  <div key={p.file_unique_id} className="upload-cell">
                    <img src={p.preview} alt="" />
                    <button className="del"
                            onClick={() => setPhotos(photos.filter((_, j) => j !== i))}>✕</button>
                  </div>
                ))}
                {photos.length < 10 && (
                  <label className="upload-add">
                    +
                    <input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden
                           onChange={(e) => upload(e.target.files)} />
                  </label>
                )}
              </div>
              {errors.photos && <div className="field-error">{errors.photos}</div>}
            </div>
          );
        }
        if (f.type === 'geo') {
          return (
            <div className="field" key="geo">
              <span className="field-label">{f.label}{f.required ? ' *' : ''}</span>
              <div className="field-hint" style={{ marginBottom: 6 }}>
                Кликните по карте, чтобы поставить точку
              </div>
              <PickMap value={values.lat != null
                         ? { lat: values.lat as number, lon: values.lon as number } : null}
                       onChange={(p) => { set('lat', p.lat); set('lon', p.lon); }} />
            </div>
          );
        }
        return <Field key={f.key} f={f} values={values} set={set} error={errors[f.key]} />;
      })}

      {schema && (
        <>
          {errors._global && <div className="field-error" style={{ marginBottom: 10 }}>{errors._global}</div>}
          <button className="btn btn-primary btn-block" disabled={busy} onClick={submit}>
            {busy ? 'Отправляем…' : 'Отправить на модерацию'}
          </button>
          <p className="field-hint" style={{ textAlign: 'center', marginTop: 10 }}>
            Объявление появится в каталоге после проверки модератором
          </p>
        </>
      )}
    </div>
  );
}
