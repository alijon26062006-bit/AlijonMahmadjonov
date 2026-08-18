/** Управление магазином: товары, размеры, фотографии, заказы, сводка. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, fmtPrice, photoUrl } from '../api/client';
import type {
  AdminProduct, BannerOut, CategorySchema, Group, OrderOut, ShopConfig,
} from '../api/types';
import { Icon } from '../components/icons';
import { Empty, ORDER_BADGE, useAuth } from '../components/ui';

type Tab = 'orders' | 'products' | 'new' | 'banners' | 'settings';

const STATUS_LABEL: Record<string, string> = {
  new: 'Новый', confirmed: 'Подтвердить', paid: 'Оплачен',
  shipped: 'Отправлен', done: 'Получен', canceled: 'Отменить',
};

export default function AdminPage({ cfg }: { cfg?: ShopConfig }) {
    const user = useAuth();
  const [tab, setTab] = useState<Tab>('orders');

  const { data: summary } = useQuery<any>({
    queryKey: ['summary'], queryFn: () => api('/api/admin/summary'),
    enabled: Boolean(user?.is_admin),
  });

  if (!user) return <Empty icon="sliders-horizontal" title="Нужен вход"
                           action={{ label: 'Войти', to: '/login' }} />;
  if (!user.is_admin) return <Empty icon="sliders-horizontal" title="Раздел закрыт"
                                    note="Управление доступно владельцу магазина" />;

  return (
    <div className="page fade-in">
      <h1 >Управление</h1>

      {summary && (
        <div className="stat-row">
          <Stat label="Новые заказы" value={summary.orders.new} tone="amber" />
          <Stat label="В работе" value={summary.orders.in_work} tone="blue" />
          <Stat label="Товаров" value={summary.products.active} tone="green" />
          <Stat label="На складе" value={summary.products.units} tone="gray" />
        </div>
      )}

      {summary?.low_stock?.length > 0 && (
        <div className="notice" style={{ marginTop: 12 }}>
          <b>Заканчивается</b>
          {summary.low_stock.slice(0, 5).map((l: any, i: number) => (
            <p key={i}>{l.title} — {[l.size, l.color].filter(Boolean).join(' ')}:
              {' '}{l.stock} шт.</p>
          ))}
        </div>
      )}

      <div className="chips" style={{ margin: '16px 0' }}>
        {([['orders', 'Заказы'], ['products', 'Товары'],
           ['new', 'Добавить товар'],
           ['banners', 'Баннеры'],
           ['settings', 'Настройки']] as [Tab, string][]).map(([id, label]) => (
          <button key={id} className={`chip ${tab === id ? 'active' : ''}`}
                  onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === 'orders' && <Orders />}
      {tab === 'products' && <Products />}
      {tab === 'new' && <NewProduct cfg={cfg} onDone={() => setTab('products')} />}
      {tab === 'banners' && <Banners />}
      {tab === 'settings' && <Settings />}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`stat stat-${tone}`}>
      <div className="stat-value">{value ?? 0}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/* ─────────────────────────── Заказы ─────────────────────────── */

function Orders() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<{ items: OrderOut[] }>({
    queryKey: ['admin-orders'], queryFn: () => api('/api/admin/orders'),
  });
  const [tracking, setTracking] = useState<Record<number, string>>({});

  const move = useMutation({
    mutationFn: ({ id, status, track }: { id: number; status: string; track?: string }) =>
      api(`/api/admin/orders/${id}/status`, {
        method: 'POST',
        body: JSON.stringify({ status, tracking: track || null }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-orders'] });
      qc.invalidateQueries({ queryKey: ['summary'] });
    },
  });

  if (isLoading) return <div className="skeleton" style={{ height: 160 }} />;
  const items = data?.items ?? [];
  if (!items.length) return <Empty icon="package" title="Заказов пока нет" />;

  return (
    <div>
      {items.map((o) => (
        <div key={o.public_id} className="order-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <b>№{o.number}</b>
            <span className={`badge ${ORDER_BADGE[o.status] ?? 'badge-gray'}`}>
              {o.status_label}
            </span>
            <span style={{ marginLeft: 'auto', fontWeight: 800 }}>
              {fmtPrice(o.total)}
            </span>
          </div>
          <div className="subtitle" style={{ marginTop: 6 }}>
            {o.items.map((i) => `${i.title} · ${i.variant} × ${i.qty}`).join('; ')}
          </div>
          <div className="subtitle" style={{ marginTop: 4 }}>
            {o.customer_name} · <a href={`tel:${o.phone}`}>{o.phone}</a>
          </div>
          <div className="subtitle">
            {o.delivery_label}{o.city ? ` · ${o.city}` : ''}
            {o.address ? `, ${o.address}` : ''}
          </div>
          {o.comment && <div className="subtitle">💬 {o.comment}</div>}

          {o.next_statuses.includes('shipped') && (
            <input className="input" placeholder="Трек-номер" style={{ marginTop: 8 }}
                   value={tracking[o.id] ?? ''}
                   onChange={(e) => setTracking({ ...tracking, [o.id]: e.target.value })} />
          )}
          {o.next_statuses.length > 0 && (
            <div className="chips" style={{ marginTop: 10 }}>
              {o.next_statuses.map((s) => (
                <button key={s}
                        className={`chip ${s === 'canceled' ? '' : 'active'}`}
                        onClick={() => move.mutate({ id: o.id, status: s,
                                                     track: tracking[o.id] })}>
                  {STATUS_LABEL[s] ?? s}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ─────────────────────────── Товары ─────────────────────────── */

function Products() {
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const { data, isLoading } = useQuery<{ items: AdminProduct[] }>({
    queryKey: ['admin-products', q],
    queryFn: () => api(`/api/admin/products?q=${encodeURIComponent(q)}`),
  });

  const hide = useMutation({
    mutationFn: ({ id, hidden }: { id: string; hidden: boolean }) =>
      api(`/api/admin/products/${id}/visibility?hidden=${hidden}`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-products'] }),
  });
  const drop = useMutation({
    mutationFn: (id: string) => api(`/api/admin/products/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-products'] }),
  });

  if (isLoading) return <div className="skeleton" style={{ height: 160 }} />;
  const items = data?.items ?? [];

  return (
    <div>
      <input className="input" placeholder="Поиск по названию или бренду" value={q}
             onChange={(e) => setQ(e.target.value)} style={{ marginBottom: 12 }} />
      {items.length === 0 && <Empty icon="store" title="Товаров нет"
                                    note="Добавьте первый на вкладке рядом" />}
      {items.map((p) => (
        <div key={p.id} className="order-card">
          <div style={{ display: 'flex', gap: 10 }}>
            <div className="line-photo">
              {p.photo ? <img src={photoUrl(p.photo)} alt="" />
                : <div className="line-noimg"><Icon name="image" size={20} /></div>}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <b>{p.title}</b>
              <div className="subtitle">
                {p.brand ?? '—'} · {fmtPrice(p.price)} · остаток {p.in_stock}
              </div>
              <div className="subtitle">
                {STATUS_TEXT[p.status] ?? p.status}
                {p.sales_count > 0 ? ` · продано ${p.sales_count}` : ''}
              </div>
            </div>
          </div>
          <div className="chips" style={{ marginTop: 10 }}>
            <button className="chip" onClick={() => setOpen(open === p.id ? null : p.id)}>
              Размеры и остатки
            </button>
            <button className="chip"
                    onClick={() => hide.mutate({ id: p.id, hidden: p.status !== 'hidden' })}>
              {p.status === 'hidden' ? 'Показать' : 'Скрыть'}
            </button>
            <button className="chip"
                    onClick={() => { if (confirm(`Удалить «${p.title}»?`)) drop.mutate(p.id); }}>
              Удалить
            </button>
          </div>
          {open === p.id && <VariantEditor product={p} />}
        </div>
      ))}
    </div>
  );
}

const STATUS_TEXT: Record<string, string> = {
  active: 'В продаже', draft: 'Черновик — нужны фото и размеры',
  hidden: 'Скрыт', out: 'Закончился',
};

function VariantEditor({ product }: { product: AdminProduct }) {
  const qc = useQueryClient();
  const [rows, setRows] = useState(
    product.variants.length
      ? product.variants.map((v) => ({ ...v }))
      : [{ id: 0, size: '', color: '', price: 0, stock: 0, sku: null }]);
  const [msg, setMsg] = useState('');

  const save = useMutation({
    mutationFn: () => api(`/api/admin/products/${product.id}/variants`, {
      method: 'PUT',
      body: JSON.stringify({
        variants: rows.map((r) => ({
          size: r.size, color: r.color,
          price: Number(r.price) || 0, stock: Number(r.stock) || 0,
        })),
      }),
    }),
    onSuccess: () => {
      setMsg('Сохранено');
      qc.invalidateQueries({ queryKey: ['admin-products'] });
      qc.invalidateQueries({ queryKey: ['summary'] });
    },
    onError: (e: unknown) => setMsg((e as { message?: string }).message
      ?? 'Не удалось сохранить'),
  });

  const change = (i: number, key: string, value: string) =>
    setRows(rows.map((r, n) => (n === i ? { ...r, [key]: value } : r)));

  return (
    <div style={{ marginTop: 12 }}>
      <div className="variant-head">
        <span>Размер</span><span>Цвет</span><span>Цена</span><span>Шт.</span><span />
      </div>
      {rows.map((r, i) => (
        <div key={i} className="variant-row">
          <input className="input" value={r.size} placeholder="M"
                 onChange={(e) => change(i, 'size', e.target.value)} />
          <input className="input" value={r.color} placeholder="Чёрный"
                 onChange={(e) => change(i, 'color', e.target.value)} />
          <input className="input" inputMode="numeric" value={String(r.price)}
                 onChange={(e) => change(i, 'price', e.target.value)} />
          <input className="input" inputMode="numeric" value={String(r.stock)}
                 onChange={(e) => change(i, 'stock', e.target.value)} />
          <button className="line-drop"
                  onClick={() => setRows(rows.filter((_, n) => n !== i))}>
            <Icon name="trash" size={14} />
          </button>
        </div>
      ))}
      <button className="btn btn-ghost btn-block" style={{ marginTop: 6 }}
              onClick={() => setRows([...rows, {
                id: 0, size: '', color: rows[rows.length - 1]?.color ?? '',
                price: rows[rows.length - 1]?.price ?? 0, stock: 0, sku: null }])}>
        <Icon name="plus" size={15} /> Ещё строка
      </button>
      {msg && <p className="subtitle" style={{ marginTop: 8 }}>{msg}</p>}
      <button className="btn btn-primary btn-block" style={{ marginTop: 8 }}
              disabled={save.isPending} onClick={() => { setMsg(''); save.mutate(); }}>
        {save.isPending ? 'Сохраняем…' : 'Сохранить размеры'}
      </button>
      <PhotoUploader product={product} />
      <PhotoStudio product={product} />
    </div>
  );
}

type PhotoOut = {
  id: number; position: number; url: string; original: string;
  has_processed: boolean; use_processed: boolean;
  background: string | null; processing: string; error: string | null;
  mode: string | null; check_status: string | null; check_note: string | null;
};

const PROCESSING_LABEL: Record<string, string> = {
  queued: 'В очереди', working: 'Обрабатываю', ready: 'Готово',
  review: 'Нужна проверка', failed: 'Не получилось',
};

/** Подготовка фотографий для каталога.

    Кнопка «AI обработка» не трогает оригинал: обработанная версия ложится
    рядом, и переключатель возвращает исходный снимок в любой момент. */
function PhotoStudio({ product }: { product: AdminProduct }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [bg, setBg] = useState<string>('');
  const [note, setNote] = useState('');
  const [msg, setMsg] = useState('');

  const { data } = useQuery<{
    items: PhotoOut[]; backgrounds: { key: string; title: string }[];
  }>({
    queryKey: ['photos', product.id],
    queryFn: () => api(`/api/admin/products/${product.id}/photos`),
    // пока что-то в работе — переспрашиваем, чтобы счётчик был живым
    refetchInterval: (q) => {
      const items = (q.state.data as { items?: PhotoOut[] } | undefined)?.items;
      return items?.some((p) => p.processing === 'queued'
                             || p.processing === 'working') ? 2000 : false;
    },
  });

  const items = data?.items ?? [];
  const backgrounds = data?.backgrounds ?? [];
  const ready = items.filter((p) => p.processing === 'ready').length;
  const working = items.filter((p) => p.processing === 'queued'
                                   || p.processing === 'working').length;

  const run = async (path: string, mode = 'standard') => {
    setBusy(true); setMsg('');
    try {
      await api(path, { method: 'POST',
                        body: JSON.stringify({ background: bg || null,
                                               mode, note }) });
      qc.invalidateQueries({ queryKey: ['photos', product.id] });
    } catch (e) {
      setMsg((e as Error).message || 'Не получилось');
    } finally { setBusy(false); }
  };

  const switchVersion = async (photo: PhotoOut, useProcessed: boolean) => {
    try {
      await api(`/api/admin/photos/${photo.id}/version`, {
        method: 'POST', body: JSON.stringify({ use_processed: useProcessed }),
      });
      qc.invalidateQueries({ queryKey: ['photos', product.id] });
      qc.invalidateQueries({ queryKey: ['admin-products'] });
    } catch (e) { setMsg((e as Error).message); }
  };

  if (!items.length) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <div className="row-between" style={{ marginBottom: 8 }}>
        <b style={{ fontSize: 14 }}>Фотографии каталога</b>
        {working > 0
          ? <span className="caption">Обработано {ready} из {items.length}</span>
          : ready > 0 && <span className="caption">Обработано {ready}</span>}
      </div>

      <div className="chips" style={{ marginBottom: 8 }}>
        <button className={`chip ${bg === '' ? 'active' : ''}`}
                onClick={() => setBg('')}>Фон автоматически</button>
        {backgrounds.map((b) => (
          <button key={b.key} className={`chip ${bg === b.key ? 'active' : ''}`}
                  onClick={() => setBg(b.key)}>{b.title}</button>
        ))}
      </div>

      <div className="field" style={{ marginBottom: 8 }}>
        <label>Что исправить? Необязательно</label>
        <input className="input" value={note} placeholder="рукав справа загнулся"
               onChange={(e) => setNote(e.target.value)} />
      </div>

      <div className="stack">
        <button className="btn btn-block" disabled={busy || working > 0}
                onClick={() => run(`/api/admin/products/${product.id}/photos/studio`)}>
          <Icon name="sparkles" size={16} />
          {working > 0 ? 'Обрабатываю…' : 'Сделать карточки'}
        </button>
        {/* Ретушь перерисовывает кадр, поэтому результат обязательно
            сверяется с оригиналом и сам на витрину не встаёт */}
        <button className="btn btn-block" disabled={busy || working > 0}
                onClick={() => run(`/api/admin/products/${product.id}/photos/studio`,
                                   'reshape')}>
          <Icon name="ruler" size={16} /> Исправить форму
        </button>
      </div>

      <div className="stack" style={{ marginTop: 10 }}>
        {items.map((photo) => (
          <div key={photo.id} className="row" style={{ alignItems: 'flex-start' }}>
            <img src={photoUrl(photo.url)} alt="" width={56} height={70}
                 style={{ objectFit: 'cover', borderRadius: 8,
                          background: 'var(--surface-2)' }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              {photo.has_processed ? (
                <div className="chips">
                  <button className={`chip ${!photo.use_processed ? 'active' : ''}`}
                          onClick={() => switchVersion(photo, false)}>Оригинал</button>
                  <button className={`chip ${photo.use_processed ? 'active' : ''}`}
                          onClick={() => switchVersion(photo, true)}>AI</button>
                  <button className="chip" disabled={busy}
                          onClick={() => run(`/api/admin/photos/${photo.id}/studio`,
                                             photo.mode ?? 'standard')}>
                    <Icon name="rotate-ccw" size={14} /> Переделать
                  </button>
                </div>
              ) : (
                <button className="btn" disabled={busy}
                        onClick={() => run(`/api/admin/photos/${photo.id}/studio`)}>
                  <Icon name="sparkles" size={15} /> AI обработка
                </button>
              )}
              {photo.processing !== 'none' && photo.processing !== 'ready' && (
                <p className="caption" style={{ marginTop: 4 }}>
                  {PROCESSING_LABEL[photo.processing] ?? photo.processing}
                  {photo.error ? `: ${photo.error}` : ''}
                </p>
              )}
              {photo.check_status === 'review' && (
                <p className="caption" style={{ marginTop: 4,
                                                color: 'var(--danger)' }}>
                  ⚠ {photo.check_note || 'сверка с оригиналом нашла отличия'}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
      {msg && <p className="caption" style={{ marginTop: 6 }}>{msg}</p>}
    </div>
  );
}

function PhotoUploader({ product }: { product: AdminProduct }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true); setMsg('');
    const photos: unknown[] = [];
    try {
      for (const file of Array.from(files).slice(0, 10)) {
        const fd = new FormData();
        fd.append('file', file);
        // через api(): токен живёт в одном месте, и собственная копия
        // заголовка авторизации здесь уже однажды разошлась с клиентом
        photos.push(await api('/api/uploads/photo', { method: 'POST', body: fd }));
      }
      await api(`/api/admin/products/${product.id}/photos`, {
        method: 'PUT', body: JSON.stringify({ photos }),
      });
      setMsg('Фотографии сохранены');
      qc.invalidateQueries({ queryKey: ['admin-products'] });
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ marginTop: 12 }}>
      <label className="btn btn-block">
        <Icon name="camera" size={16} />
        {busy ? 'Загружаем…' : `Фотографии (${product.photos_count})`}
        <input className="input" type="file" accept="image/*" multiple hidden disabled={busy}
               onChange={(e) => upload(e.target.files)} />
      </label>
      {msg && <p className="subtitle" style={{ marginTop: 6 }}>{msg}</p>}
    </div>
  );
}

/* ─────────────────────── Новый товар ─────────────────────── */

function NewProduct({ cfg, onDone }: { cfg?: ShopConfig; onDone: () => void }) {
  const qc = useQueryClient();
  const [category, setCategory] = useState('');
  const [form, setForm] = useState({ title: '', description: '', brand: '' });
  const [attrs, setAttrs] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState('');

  const { data: groups } = useQuery<{ groups: Group[] }>({
    queryKey: ['categories'], queryFn: () => api('/api/categories'),
  });
  const { data: schema } = useQuery<CategorySchema>({
    queryKey: ['schema', category], queryFn: () => api(`/api/categories/${category}`),
    enabled: Boolean(category),
  });

  const create = useMutation({
    mutationFn: () => api('/api/admin/products', {
      method: 'POST',
      body: JSON.stringify({ category, ...form, attrs }),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-products'] });
      setMsg('');
      onDone();
    },
    onError: (e: unknown) => setMsg((e as { message?: string }).message
      ?? 'Не удалось сохранить'),
  });

  return (
    <div>
      <div className="field">
        <span className="field-label">Раздел</span>
        <select className="select" value={category} onChange={(e) => { setCategory(e.target.value); setAttrs({}); }}>
          <option value="">Выберите раздел</option>
          {(groups?.groups ?? []).map((g) => (
            <optgroup key={g.title} label={g.title}>
              {g.categories.map((c) => (
                <option key={c.slug} value={c.slug}>{c.title}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      <div className="field">
        <span className="field-label">Название <span style={{ color: 'var(--danger)' }}>*</span></span>
        <input className="input" value={form.title} placeholder="Платье летнее в цветочек"
               onChange={(e) => setForm({ ...form, title: e.target.value })} />
      </div>
      <div className="field">
        <span className="field-label">Бренд</span>
        <input className="input" value={form.brand} placeholder="Koton"
               onChange={(e) => setForm({ ...form, brand: e.target.value })} />
      </div>
      <div className="field">
        <span className="field-label">Описание</span>
        <textarea className="textarea" rows={3} value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </div>

      {(schema?.fields ?? []).map((f) => (
        <div key={f.key} className="field">
          <span className="field-label">
            {f.label}{f.required && <span style={{ color: 'var(--danger)' }}> *</span>}
          </span>
          {f.options ? (
            <div className="chips">
              {f.options.map((o) => (
                <button key={o} className={`chip ${attrs[f.key] === o ? 'active' : ''}`}
                        onClick={() => setAttrs({ ...attrs,
                          [f.key]: attrs[f.key] === o ? '' : o })}>
                  {o}
                </button>
              ))}
            </div>
          ) : (
            <input className="input" inputMode={f.type === 'int' ? 'numeric' : undefined}
                   value={attrs[f.key] ?? ''} placeholder={f.hint ?? ''}
                   onChange={(e) => setAttrs({ ...attrs, [f.key]: e.target.value })} />
          )}
        </div>
      ))}

      {msg && <div className="field-error" style={{ marginBottom: 10 }}>{msg}</div>}
      {!cfg?.uploads_enabled && (
        <div className="notice" style={{ marginBottom: 10 }}>
          <b>Фотографии пока не загрузить</b>
          <p>Нужен приватный чат-хранилище: создайте группу, добавьте бота
            и укажите её id в STORAGE_CHAT_ID.</p>
        </div>
      )}
      <button className="btn btn-primary btn-block"
              disabled={!category || form.title.trim().length < 3 || create.isPending}
              onClick={() => create.mutate()}>
        {create.isPending ? 'Сохраняем…' : 'Создать товар'}
      </button>
      <p className="subtitle" style={{ marginTop: 8 }}>
        После создания откройте товар в списке и задайте размеры, цены и фотографии.
      </p>
    </div>
  );
}

/* ─────────────────────── Настройки ─────────────────────── */

/** Ключ стороннего сервиса. Сюда он вводится один раз, наружу больше не
    возвращается — только признак «задан» и последние четыре знака. */
function Settings() {
  const qc = useQueryClient();
  const [key, setKey] = useState('');
  const [msg, setMsg] = useState('');

  const [openaiKey, setOpenaiKey] = useState('');

  const { data } = useQuery<{
    ai_provider: string; ai_key_set: boolean; ai_key_hint: string;
    openai_key_set: boolean; openai_key_hint: string; openai_model: string;
  }>({ queryKey: ['admin-settings'], queryFn: () => api('/api/admin/settings') });

  const save = async (patch: Record<string, unknown>) => {
    try {
      await api('/api/admin/settings', { method: 'PATCH',
                                         body: JSON.stringify(patch) });
      qc.invalidateQueries({ queryKey: ['admin-settings'] });
      setMsg('Сохранено');
      setKey('');
      setOpenaiKey('');
    } catch (e) { setMsg((e as Error).message || 'Не сохранилось'); }
  };

  const provider = data?.ai_provider ?? 'local';

  return (
    <div className="stack fade-in">
      <h2>Обработка фотографий</h2>
      <p className="subtitle">
        Готовит из снимка с телефона карточку в стиле каталога: убирает стол,
        руку и стену, ставит товар по центру на нейтральный фон. Сам товар
        не меняется — это те же пиксели, что и на оригинале.
      </p>

      <div className="field">
        <label>Чем отделять товар от фона</label>
        <div className="chips">
          <button className={`chip ${provider === 'local' ? 'active' : ''}`}
                  onClick={() => save({ ai_provider: 'local' })}>
            На своём сервере
          </button>
          <button className={`chip ${provider === 'removebg' ? 'active' : ''}`}
                  onClick={() => save({ ai_provider: 'removebg' })}>
            Сторонний сервис
          </button>
        </div>
        <span className="caption">
          {provider === 'local'
            ? 'Работает без ключа и без оплаты за кадр. Первая обработка после '
              + 'перезапуска идёт дольше — сервер подгружает модель.'
            : 'Нужен ключ remove.bg. Качество на сложном фоне выше, каждый '
              + 'кадр платный.'}
        </span>
      </div>

      <div className="field">
        <label>Ключ сервиса</label>
        <input className="input" type="password" autoComplete="off"
               placeholder={data?.ai_key_set ? `Задан: ${data.ai_key_hint}`
                                             : 'Ключ ещё не задан'}
               value={key} onChange={(e) => setKey(e.target.value)} />
        <span className="caption">
          Хранится на сервере и в браузер не возвращается никогда.
        </span>
      </div>

      <button className="btn btn-primary" disabled={!key.trim()}
              onClick={() => save({ ai_api_key: key.trim() })}>
        Сохранить ключ
      </button>

      <h2 style={{ marginTop: 32 }}>Разбор фотографий</h2>
      <p className="subtitle">
        По снимку предлагает название, раздел, цвет и описание. Ничего не
        публикуется само — черновик приходит вам в бот, вы правите и
        подтверждаете.
      </p>

      <div className="field">
        <label>Ключ OpenAI</label>
        <input className="input" type="password" autoComplete="off"
               placeholder={data?.openai_key_set
                 ? `Задан: ${data.openai_key_hint}` : 'Ключ ещё не задан'}
               value={openaiKey} onChange={(e) => setOpenaiKey(e.target.value)} />
        <span className="caption">
          Берётся на platform.openai.com. Хранится на сервере, в браузер не
          возвращается. Разбор одного снимка стоит около цента.
        </span>
      </div>

      <div className="field">
        <label>Модель</label>
        <input className="input" defaultValue={data?.openai_model ?? ''}
               placeholder="gpt-4o-mini"
               onBlur={(e) => e.target.value !== data?.openai_model
                 && save({ openai_model: e.target.value })} />
      </div>

      <button className="btn btn-primary" disabled={!openaiKey.trim()}
              onClick={() => save({ openai_api_key: openaiKey.trim() })}>
        Сохранить ключ OpenAI
      </button>

      <div className="notice" style={{ marginTop: 24 }}>
        <b>Товар удобнее заводить в боте.</b> Команда <code>/add</code> или
        кнопка «Добавить товар»: прислали фотографии, ответили на пять
        вопросов — и карточка готова.
      </div>

      {msg && <div className="notice">{msg}</div>}
    </div>
  );
}

/* ─────────────────────── Баннеры ─────────────────────── */

const DAY_CHOICES = [3, 7, 14, 30, 0];

/** Баннеры на главной: своя фотография, срок показа, очередь, удаление. */
function Banners() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const { data } = useQuery<{ items: BannerOut[] }>({
    queryKey: ['admin-banners'], queryFn: () => api('/api/admin/banners'),
  });
  const items = data?.items ?? [];

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['admin-banners'] });
    qc.invalidateQueries({ queryKey: ['banners'] });
  };

  const call = async (path: string, init: RequestInit) => {
    setBusy(true); setMsg('');
    try { await api(path, init); refresh(); }
    catch (e) { setMsg((e as Error).message || 'Не получилось'); }
    finally { setBusy(false); }
  };

  const add = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true); setMsg('');
    try {
      const fd = new FormData();
      fd.append('file', files[0]);
      const photo = await api('/api/uploads/photo', { method: 'POST', body: fd });
      await api('/api/admin/banners', {
        method: 'POST',
        body: JSON.stringify({ photo, days: 14, link: '/catalog',
                               button_text: 'Смотреть' }),
      });
      refresh();
    } catch (e) {
      setMsg((e as Error).message || 'Не загрузилось');
    } finally { setBusy(false); }
  };

  const patch = (id: string, body: Record<string, unknown>) =>
    call(`/api/admin/banners/${id}`, { method: 'PATCH',
                                       body: JSON.stringify(body) });

  return (
    <div className="stack fade-in">
      <h2>Баннеры на главной</h2>
      <p className="subtitle">
        Показываются по очереди, листаются пальцем. Срок задаётся днями —
        баннер уходит с витрины сам, снимать руками не нужно.
      </p>

      <label className="btn btn-primary btn-block">
        <Icon name="image" size={16} />
        {busy ? 'Загружаю…' : 'Добавить баннер'}
        <input type="file" accept="image/*" hidden disabled={busy}
               onChange={(e) => add(e.target.files)} />
      </label>

      {items.length === 0 && (
        <div className="notice">
          Баннеров нет — главная начинается сразу с товаров. Так и надо,
          пока нет хорошей фотографии и повода.
        </div>
      )}

      {items.map((b, i) => (
        <div key={b.id} className="order-card">
          <div className="row" style={{ alignItems: 'flex-start' }}>
            <img src={photoUrl(b.photo)} alt="" width={96} height={72}
                 style={{ objectFit: 'cover', borderRadius: 8,
                          background: 'var(--surface-2)' }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="row-between">
                <b>{b.title || 'Без заголовка'}</b>
                <span className="caption">
                  {b.expired ? 'срок вышел'
                    : b.days_left === null ? 'без срока'
                    : `осталось ${b.days_left} дн.`}
                </span>
              </div>
              <div className="row" style={{ marginTop: 8, gap: 4 }}>
                <button className="btn btn-ghost btn-icon" disabled={busy || i === 0}
                        aria-label="Выше"
                        onClick={() => call(`/api/admin/banners/${b.id}/move?direction=up`,
                                            { method: 'POST' })}>↑</button>
                <button className="btn btn-ghost btn-icon"
                        disabled={busy || i === items.length - 1}
                        aria-label="Ниже"
                        onClick={() => call(`/api/admin/banners/${b.id}/move?direction=down`,
                                            { method: 'POST' })}>↓</button>
                <button className="btn" disabled={busy}
                        onClick={() => patch(b.id, { is_active: !b.is_active })}>
                  {b.is_active ? 'Скрыть' : 'Показать'}
                </button>
                <button className="btn btn-ghost btn-icon" disabled={busy}
                        aria-label="Удалить"
                        onClick={() => {
                          if (confirm('Удалить баннер?')) {
                            call(`/api/admin/banners/${b.id}`, { method: 'DELETE' });
                          }
                        }}>
                  <Icon name="trash" size={16} />
                </button>
              </div>
            </div>
          </div>

          <div className="stack" style={{ marginTop: 12 }}>
            <div className="field">
              <label className="field-label">Надпись сверху</label>
              <input className="input" defaultValue={b.eyebrow ?? ''}
                     placeholder="Новая партия"
                     onBlur={(e) => e.target.value !== (b.eyebrow ?? '')
                       && patch(b.id, { eyebrow: e.target.value })} />
            </div>
            <div className="field">
              <label className="field-label">Заголовок</label>
              <input className="input" defaultValue={b.title ?? ''}
                     placeholder="Зимние куртки"
                     onBlur={(e) => e.target.value !== (b.title ?? '')
                       && patch(b.id, { title: e.target.value })} />
            </div>
            <div className="field">
              <label className="field-label">Подпись</label>
              <input className="input" defaultValue={b.subtitle ?? ''}
                     placeholder="от 24 900 ₸"
                     onBlur={(e) => e.target.value !== (b.subtitle ?? '')
                       && patch(b.id, { subtitle: e.target.value })} />
            </div>
            <div className="field">
              <label className="field-label">Куда ведёт</label>
              <input className="input" defaultValue={b.link ?? ''}
                     placeholder="/catalog?category=women_clothes"
                     onBlur={(e) => e.target.value !== (b.link ?? '')
                       && patch(b.id, { link: e.target.value })} />
              <span className="caption">
                Ссылка на подборку, а не на главную — иначе баннер бесполезен.
              </span>
            </div>
            <div className="field">
              <label className="field-label">Сколько дней показывать</label>
              <div className="chips">
                {DAY_CHOICES.map((d) => (
                  <button key={d} className="chip" disabled={busy}
                          onClick={() => patch(b.id, { days: d })}>
                    {d === 0 ? 'Без срока' : `${d} дн.`}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      ))}

      {msg && <div className="notice notice-error">{msg}</div>}
    </div>
  );
}
