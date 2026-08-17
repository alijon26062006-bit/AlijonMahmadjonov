/** Управление магазином: товары, размеры, фотографии, заказы, сводка. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, fmtPrice, photoUrl, API } from '../api/client';
import type {
  AdminProduct, CategorySchema, Group, OrderOut, ShopConfig,
} from '../api/types';
import { Icon } from '../components/icons';
import { Empty, ORDER_BADGE, useAuth, useTgBackButton } from '../components/ui';

type Tab = 'orders' | 'products' | 'new';

const STATUS_LABEL: Record<string, string> = {
  new: 'Новый', confirmed: 'Подтвердить', paid: 'Оплачен',
  shipped: 'Отправлен', done: 'Получен', canceled: 'Отменить',
};

export default function AdminPage({ cfg }: { cfg?: ShopConfig }) {
  useTgBackButton(true);
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
    <div className="section fade-in">
      <h1 className="section-title">Управление</h1>

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
           ['new', 'Добавить товар']] as [Tab, string][]).map(([id, label]) => (
          <button key={id} className={`chip ${tab === id ? 'on' : ''}`}
                  onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === 'orders' && <Orders />}
      {tab === 'products' && <Products />}
      {tab === 'new' && <NewProduct cfg={cfg} onDone={() => setTab('products')} />}
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
            <input placeholder="Трек-номер" style={{ marginTop: 8 }}
                   value={tracking[o.id] ?? ''}
                   onChange={(e) => setTracking({ ...tracking, [o.id]: e.target.value })} />
          )}
          {o.next_statuses.length > 0 && (
            <div className="chips" style={{ marginTop: 10 }}>
              {o.next_statuses.map((s) => (
                <button key={s}
                        className={`chip ${s === 'canceled' ? '' : 'on'}`}
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
      <input placeholder="Поиск по названию или бренду" value={q}
             onChange={(e) => setQ(e.target.value)} style={{ marginBottom: 12 }} />
      {items.length === 0 && <Empty icon="store" title="Товаров нет"
                                    note="Добавьте первый на вкладке рядом" />}
      {items.map((p) => (
        <div key={p.id} className="order-card">
          <div style={{ display: 'flex', gap: 10 }}>
            <div className="cart-photo">
              {p.photo ? <img src={photoUrl(p.photo)} alt="" />
                : <div className="noimg"><Icon name="image" size={20} /></div>}
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
          <input value={r.size} placeholder="M"
                 onChange={(e) => change(i, 'size', e.target.value)} />
          <input value={r.color} placeholder="Чёрный"
                 onChange={(e) => change(i, 'color', e.target.value)} />
          <input inputMode="numeric" value={String(r.price)}
                 onChange={(e) => change(i, 'price', e.target.value)} />
          <input inputMode="numeric" value={String(r.stock)}
                 onChange={(e) => change(i, 'stock', e.target.value)} />
          <button className="cart-drop"
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
        const r = await fetch(`${API}/api/uploads/photo`, {
          method: 'POST', body: fd,
          headers: authHeader(),
        });
        if (!r.ok) throw new Error((await r.json()).detail ?? 'Ошибка загрузки');
        photos.push(await r.json());
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
        <input type="file" accept="image/*" multiple hidden disabled={busy}
               onChange={(e) => upload(e.target.files)} />
      </label>
      {msg && <p className="subtitle" style={{ marginTop: 6 }}>{msg}</p>}
    </div>
  );
}

function authHeader(): Record<string, string> {
  // токен держится в модуле клиента; здесь нужен только заголовок
  const raw = localStorage.getItem('session');
  try {
    const saved = raw ? JSON.parse(raw) : null;
    return saved?.t ? { Authorization: `Bearer ${saved.t}` } : {};
  } catch {
    return {};
  }
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
        <select value={category} onChange={(e) => { setCategory(e.target.value); setAttrs({}); }}>
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
        <input value={form.title} placeholder="Платье летнее в цветочек"
               onChange={(e) => setForm({ ...form, title: e.target.value })} />
      </div>
      <div className="field">
        <span className="field-label">Бренд</span>
        <input value={form.brand} placeholder="Koton"
               onChange={(e) => setForm({ ...form, brand: e.target.value })} />
      </div>
      <div className="field">
        <span className="field-label">Описание</span>
        <textarea rows={3} value={form.description}
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
                <button key={o} className={`chip ${attrs[f.key] === o ? 'on' : ''}`}
                        onClick={() => setAttrs({ ...attrs,
                          [f.key]: attrs[f.key] === o ? '' : o })}>
                  {o}
                </button>
              ))}
            </div>
          ) : (
            <input inputMode={f.type === 'int' ? 'numeric' : undefined}
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
