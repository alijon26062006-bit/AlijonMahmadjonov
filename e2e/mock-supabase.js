// Мини-Supabase в браузере для тестов: таблицы в localStorage (общие для всех вкладок одного адреса),
// живые изменения — через событие storage. Повторяет логику миграций в seller/supabase/migrations — только то, что зовут приложения.
(() => {
  const K = '__mockdb', EV = '__mockdb_ev';
  const load = () => { try { return JSON.parse(localStorage.getItem(K)) || null; } catch { return null; } };
  const fresh = () => ({ t: { shops: [], shop_private: [], products: [], product_private: [], orders: [], order_private: [], reviews: [], expenses: [], couriers: [] }, users: [], sku: 100001, no: 1001, files: {}, codes: {} });
  const PK = { shops: 'id', shop_private: 'shop_id', products: 'id', product_private: 'product_id', orders: 'id', order_private: 'order_id', reviews: 'id', expenses: 'id', couriers: 'id' };
  const now = () => new Date().toISOString();
  const uuid = () => crypto.randomUUID();
  let chans = [];
  function tx(fn) {
    const db = load() || fresh(); const evs = [];
    const r = fn(db, (table, event, row) => evs.push({ table, event, new: row }));
    localStorage.setItem(K, JSON.stringify(db));
    if (evs.length) { localStorage.setItem(EV, JSON.stringify({ id: uuid(), evs })); setTimeout(() => emit(evs), 0); }
    return r;
  }
  const read = () => load() || fresh();
  function emit(evs) {
    for (const e of evs) for (const ch of chans) for (const h of ch.hs) {
      if (h.o.table !== e.table || (h.o.event !== '*' && h.o.event !== e.event)) continue;
      if (h.o.filter) { const [col, v] = h.o.filter.split('=eq.'); if (String(e.new?.[col]) !== v) continue; }
      try { h.cb({ eventType: e.event, new: e.new }); } catch (x) { console.error(x); }
    }
  }
  addEventListener('storage', e => { if (e.key === EV && e.newValue) emit(JSON.parse(e.newValue).evs); });

  function defaults(table, row, uid) {
    const r = { ...row };
    if (table === 'shops') Object.assign(r, { id: r.id || uuid(), owner_id: r.owner_id || uid, rating: 0, rating_count: 0, created_at: now(), ...row });
    if (table === 'products') r.created_at ||= now();
    if (table === 'orders') { r.id ||= uuid(); r.created_at ||= now(); r.status ||= 'new'; r.fee ??= 0; r.cancel_reason ??= ''; r.if_missing ||= 'replace'; r.customer ||= {}; r.comment ??= ''; }
    if (table === 'reviews') { r.id ||= uuid(); r.created_at ||= now(); }
    r.updated_at = now();
    return r;
  }

  class Q {
    constructor(c, table) { this.c = c; this.table = table; this.f = []; this.op = 'select'; this.one = null; this.lim = 0; this.ord = null; this.ret = false; }
    select() { if (this.op !== 'select') this.ret = true; return this; }
    insert(rows) { this.op = 'insert'; this.rows = [].concat(rows); return this; }
    upsert(rows) { this.op = 'upsert'; this.rows = [].concat(rows); return this; }
    update(p) { this.op = 'update'; this.patch = p; return this; }
    delete() { this.op = 'delete'; return this; }
    eq(k, v) { this.f.push(r => String(r[k]) === String(v)); return this; }
    in(k, vs) { this.f.push(r => vs.map(String).includes(String(r[k]))); return this; }
    gte(k, v) { this.f.push(r => r[k] >= v); return this; }
    order(k) { this.ord = k; return this; }
    limit(n) { this.lim = n; return this; }
    retry() { return this; }
    single() { this.one = 'single'; return this; }
    maybeSingle() { this.one = 'maybe'; return this; }
    run() {
      const uid = this.c._uid(), T = this.table, pk = PK[T];
      if (this.op === 'select') {
        let rows = read().t[T].filter(r => this.f.every(f => f(r)));
        if (this.ord) rows.sort((a, b) => String(a[this.ord]).localeCompare(String(b[this.ord])));
        if (this.lim) rows = rows.slice(0, this.lim);
        return this.fin(rows);
      }
      return this.fin(tx((db, ev) => {
        const tb = db.t[T]; let out = [];
        if (this.op === 'insert' || this.op === 'upsert') for (const row of this.rows) {
          const i = pk && row[pk] != null ? tb.findIndex(r => r[pk] === row[pk]) : -1;
          if (i >= 0 && this.op === 'upsert') { tb[i] = { ...tb[i], ...row, updated_at: now() }; out.push(tb[i]); ev(T, 'UPDATE', tb[i]); continue; }
          if (i >= 0) throw new Error('duplicate key');
          const r = defaults(T, row, uid);
          if (T === 'products' && r.sku == null) r.sku = db.sku++;
          if (T === 'orders' && r.no == null) r.no = db.no++;
          tb.push(r); out.push(r); ev(T, 'INSERT', r);
        }
        if (this.op === 'update') for (const r of tb) if (this.f.every(f => f(r))) { Object.assign(r, this.patch, { updated_at: now() }); out.push(r); ev(T, 'UPDATE', r); }
        if (this.op === 'delete') { db.t[T] = tb.filter(r => !this.f.every(f => f(r))); out = tb.filter(r => this.f.every(f => f(r))); out.forEach(r => ev(T, 'DELETE', r)); }
        return out;
      }));
    }
    fin(rows) {
      rows = JSON.parse(JSON.stringify(rows));
      if (this.one === 'single') return rows.length === 1 ? { data: rows[0], error: null } : { data: null, error: { message: 'not single' } };
      if (this.one === 'maybe') return { data: rows[0] || null, error: null };
      return { data: this.op === 'select' || this.ret ? rows : null, error: null };
    }
    then(ok, no) { let r; try { r = this.run(); } catch (e) { r = { data: null, error: { message: e.message } }; } return Promise.resolve(r).then(ok, no); }
  }

  const km = (a, b) => { const R = 6371, rad = d => d * Math.PI / 180, dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng); const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };

  const ACT = ['going', 'at_shop', 'picked', 'at_client'];
  function me(db, uid) { if (!uid) throw new Error('Нужно войти'); const c = db.t.couriers.find(x => x.id === uid); if (!c) throw new Error('Сначала заполните анкету курьера'); return c; }
  function job(db, o) {
    const s = db.t.shops.find(x => x.id === o.shop_id), ad = o.customer.addr || {};
    return { id: o.id, no: o.no, status: o.status, step: o.courier_status, created_at: o.created_at, taken_at: o.courier_at, picked_at: o.picked_at || null, delivered_at: o.delivered_at || null, received_at: o.received_at || null,
      ready_at: ['ready', 'done'].includes(o.status) ? null : new Date(Date.parse(o.accepted_at || o.created_at) + (o.ready_in || s.prep_min || 30) * 60000).toISOString(),
      earn: o.courier_fee, pay: o.pay, total: o.total, sum: o.sum, fee: o.fee, km: o.km, cash_taken: o.cash_taken ?? null,
      items: o.items.map(i => ({ name: i.name, qty: i.qty, actual: i.actual ?? null, unit: i.unit, variant: i.variant, missing: i.missing ?? null, sub: i.sub ?? null })),
      comment: o.comment, if_missing: o.if_missing, when_label: o.when_label, cancel_reason: o.cancel_reason, rating: o.courier_rating ?? null,
      shop: { name: s.name, phone: s.phone, address: s.address, landmark: s.landmark, lat: s.lat, lng: s.lng },
      client: { name: o.customer.name, phone: o.customer.phone, address: o.customer.address, lat: ad.lat ?? null, lng: ad.lng ?? null } };
  }
  const RPC = {
    place_order(a, uid) {
      return tx((db, ev) => {
        if (!uid) throw new Error('Нужно войти');
        const shop = db.t.shops.find(s => s.id === a.p_shop); if (!shop) throw new Error('Магазин не найден');
        let sum = 0; const items = [], costs = [];
        for (const l of a.p_items) {
          const p = db.t.products.find(x => x.id === l.pid && x.shop_id === shop.id);
          if (!p || !p.active) throw new Error('Товара больше нет в продаже: ' + l.pid);
          if (l.qty > p.stock) throw new Error(`Осталось только ${p.stock} ${p.unit} «${p.name}»`);
          const v = l.vid ? (p.data.variants || []).find(x => x.id === l.vid) : null;
          let price = v ? v.price : p.price; const opts = (p.data.options || []).filter(o => (l.opts || []).includes(o.id));
          price += opts.reduce((s, o) => s + (o.price || 0), 0);
          sum += Math.round(price * l.qty * 100) / 100;
          items.push({ pid: p.id, sku: p.sku, name: p.name, unit: p.unit, variant: v?.name || '', qty: l.qty, price, opts: opts.map(o => ({ name: o.name, price: o.price || 0 })) });
          const pp = db.t.product_private.find(x => x.product_id === p.id); costs.push(v ? pp?.variant_costs?.[v.id] ?? null : pp?.cost ?? null);
          p.stock -= l.qty; ev('products', 'UPDATE', p);
        }
        if (sum < shop.min_order) throw new Error(`Минимальный заказ — ${shop.min_order} смн`);
        // как private.delivery_quote в открытой зоне: у кого нет метки — считаем рядом с другим, иначе центр посёлка
        const C0 = { lat: 37.267, lng: 68.133 }, sp = shop.lat != null ? shop : null, ap = a.p_addr.lat != null ? a.p_addr : null;
        const from = sp || ap || C0, to = ap || sp || C0;
        const d = Math.max(0.3, Math.round(km(from, to) * 1.3 * 10) / 10), fee = d <= 2 ? 15 : d <= 5 ? 20 : 20 + Math.ceil(d - 5) * 2;
        const ad = a.p_addr, address = [ad.city, ad.street, ad.house && 'д. ' + ad.house, ad.apt && 'кв. ' + ad.apt].filter(Boolean).join(', ');
        const o = defaults('orders', { shop_id: shop.id, buyer_id: uid, source: 'app', delivery: 'courier', items, sum, fee, total: sum + fee, km: d, pay: a.p_pay,
          customer: { name: a.p_name || 'Покупатель', phone: a.p_phone, address, addr: ad }, comment: a.p_comment || '', if_missing: a.p_if_missing, when_at: a.p_when_at, when_label: a.p_when_label });
        o.no = db.no++; db.t.orders.push(o); ev('orders', 'INSERT', o);
        db.t.order_private.push({ order_id: o.id, shop_id: shop.id, costs });
        return o;
      });
    },

    // ---------- курьер (повторяет supabase/migrations/20261025000001_couriers.sql) ----------
    courier_register(a, uid) { return tx((db, ev) => { let c = db.t.couriers.find(x => x.id === uid); const v = { name: a.p_name.trim(), phone: a.p_phone, car: a.p_car, plate: (a.p_plate || '').toUpperCase(), photo: '' };
      if (c) Object.assign(c, v); else { c = { id: uid, status: 'active', online: false, lat: null, lng: null, loc_at: null, rating: 0, rating_count: 0, ...v }; db.t.couriers.push(c); } return c; }); },
    courier_online(a, uid) { return tx(db => { const c = me(db, uid); c.online = a.p_on; if (a.p_lat != null) { c.lat = a.p_lat; c.lng = a.p_lng; c.loc_at = now(); } return c; }); },
    courier_ping(a, uid) { return tx(db => { const c = me(db, uid); c.lat = a.p_lat; c.lng = a.p_lng; c.loc_at = now(); return null; }); },
    courier_feed(a, uid) {
      const db = read(), c = me(db, uid);
      return db.t.orders.filter(o => o.source === 'app' && !o.courier_id && ['accepted', 'ready'].includes(o.status)).map(o => {
        const s = db.t.shops.find(x => x.id === o.shop_id), ad = o.customer.addr || {};
        return { id: o.id, no: o.no, status: o.status, created_at: o.created_at, shop: s.name, shop_address: s.address, shop_lat: s.lat, shop_lng: s.lng,
          to_shop: c.lat != null && s.lat != null ? Math.max(0.1, Math.round(km(c, s) * 1.3 * 10) / 10) : null, km: o.km, earn: o.fee, pay: o.pay, cash: o.pay === 'cash' ? o.total : null,
          items: o.items.length, ready_at: o.status === 'ready' ? null : new Date(Date.parse(o.accepted_at || o.created_at) + (o.ready_in || s.prep_min || 30) * 60000).toISOString(),
          area: [ad.city, ad.street].filter(Boolean).join(', '), to_lat: ad.lat ?? null, to_lng: ad.lng ?? null };
      });
    },
    courier_take(a, uid) {
      return tx((db, ev) => {
        const c = me(db, uid);
        if (db.t.orders.some(o => o.courier_id === uid && ACT.includes(o.courier_status) && o.status !== 'cancelled')) throw new Error('Сначала доставьте текущий заказ');
        const o = db.t.orders.find(x => x.id === a.p_order && !x.courier_id && ['accepted', 'ready'].includes(x.status)); if (!o) throw new Error('Этот заказ уже взял другой курьер');
        Object.assign(o, { courier_id: uid, courier_status: 'going', courier_at: now(), courier_fee: o.fee, updated_at: now(),
          courier: { name: c.name, phone: c.phone, car: c.car, plate: c.plate, photo: '', rating: c.rating, rating_count: c.rating_count } });
        db.codes[o.id] = String(Math.floor(Math.random() * 10000)).padStart(4, '0'); ev('orders', 'UPDATE', o);
        return job(db, o);
      });
    },
    courier_jobs(a, uid) { const db = read(); me(db, uid); return db.t.orders.filter(o => o.courier_id === uid).sort((x, y) => String(y.courier_at).localeCompare(String(x.courier_at))).map(o => job(db, o)); },
    courier_step(a, uid) {
      return tx((db, ev) => {
        me(db, uid); const o = db.t.orders.find(x => x.id === a.p_order && x.courier_id === uid); if (!o) throw new Error('Заказ не найден');
        if (o.status === 'cancelled') throw new Error('Заказ отменён: ' + (o.cancel_reason || 'без причины'));
        if (a.p_step === 'at_shop') { if (o.courier_status === 'going') o.courier_status = 'at_shop'; }
        else if (a.p_step === 'picked') { if (!['going', 'at_shop'].includes(o.courier_status)) throw new Error('Заказ уже забран'); Object.assign(o, { courier_status: 'picked', picked_at: now(), status: 'done' }); }
        else if (a.p_step === 'at_client') { if (o.courier_status === 'picked') o.courier_status = 'at_client'; }
        else if (a.p_step === 'delivered') {
          if (!['picked', 'at_client'].includes(o.courier_status)) throw new Error('Сначала заберите заказ в магазине');
          if (a.p_code !== db.codes[o.id]) throw new Error('Код не подходит. Спросите у покупателя 4 цифры из его приложения');
          Object.assign(o, { courier_status: 'delivered', delivered_at: now(), received_at: o.received_at || now(), cash_taken: o.pay === 'cash' ? o.total : null });
        } else throw new Error('Неизвестный шаг');
        o.updated_at = now(); ev('orders', 'UPDATE', o); return job(db, o);
      });
    },
    courier_release(a, uid) { return tx((db, ev) => { const o = db.t.orders.find(x => x.id === a.p_order && x.courier_id === uid && ['going', 'at_shop'].includes(x.courier_status)); if (!o) throw new Error('Заказ уже забран — отказаться нельзя');
      Object.assign(o, { courier_id: null, courier: null, courier_status: null, courier_at: null, courier_fee: null, updated_at: now() }); delete db.codes[o.id]; ev('orders', 'UPDATE', o); return null; }); },
    courier_return(a, uid) { return tx((db, ev) => { const o = db.t.orders.find(x => x.id === a.p_order && x.courier_id === uid && ['picked', 'at_client'].includes(x.courier_status)); if (!o) throw new Error('Заказ не найден');
      o.courier_status = 'returned'; o.problem = { reason: 'Курьер не смог передать заказ', text: a.p_reason, ts: now(), by: 'courier' }; ev('orders', 'UPDATE', o); return job(db, o); }); },
    buyer_code(a, uid) { const db = read(), o = db.t.orders.find(x => x.id === a.p_order && x.buyer_id === uid && x.courier_id); return o ? db.codes[o.id] ?? null : null; },
    order_courier_where(a, uid) { const db = read(), o = db.t.orders.find(x => x.id === a.p_order); if (!o || !ACT.includes(o.courier_status)) return null;
      const own = db.t.shops.find(s => s.id === o.shop_id)?.owner_id === uid; if (o.buyer_id !== uid && !own) return null;
      const c = db.t.couriers.find(x => x.id === o.courier_id); return c?.loc_at ? { lat: c.lat, lng: c.lng, at: c.loc_at } : null; },
    buyer_rate_courier(a, uid) { return tx(db => { const o = db.t.orders.find(x => x.id === a.p_order && x.buyer_id === uid && x.courier_id && !x.courier_rating); if (!o) return null;
      o.courier_rating = a.p_rating; const c = db.t.couriers.find(x => x.id === o.courier_id), rs = db.t.orders.filter(x => x.courier_id === c.id && x.courier_rating).map(x => x.courier_rating);
      c.rating = Math.round(rs.reduce((s, x) => s + x, 0) / rs.length * 10) / 10; c.rating_count = rs.length; return null; }); },
    buyer_answer_sub(a, uid) { return upd(a.p_order, uid, o => { const s = o.items[a.p_n]?.sub; if (s?.status === 'wait') { s.status = a.p_yes ? 'ok' : 'no'; o.items[a.p_n].picked = false; } }); },
    buyer_cancel(a, uid) { return upd(a.p_order, uid, o => { if (o.status !== 'new') throw new Error('Магазин уже собирает заказ — отменить нельзя'); o.status = 'cancelled'; o.cancel_reason = 'Покупатель отменил заказ'; }); },
    buyer_received(a, uid) { return upd(a.p_order, uid, o => { if (!['ready', 'done'].includes(o.status)) throw new Error('Заказ ещё не передан курьеру'); o.received_at ||= now(); if (o.courier_id) { o.courier_status = 'delivered'; o.delivered_at ||= now(); if (o.pay === 'cash') o.cash_taken ??= o.total; } }); },
    buyer_problem(a, uid) { return upd(a.p_order, uid, o => { o.problem = { reason: a.p_reason, text: a.p_text, ts: now() }; }); },
    buyer_review(a, uid) {
      return tx((db, ev) => {
        const o = db.t.orders.find(x => x.id === a.p_order && x.buyer_id === uid); if (!o) throw new Error('Заказ не найден');
        if (!o.received_at) throw new Error('Оценить можно после получения заказа');
        const r = defaults('reviews', { order_id: o.id, shop_id: o.shop_id, buyer_id: uid, order_no: o.no, name: a.p_name || 'Покупатель', rating: a.p_rating, tags: a.p_tags, text: a.p_text,
          items: o.items.map(i => ({ pid: i.pid, name: i.name, like: a.p_likes?.[i.pid] ?? null })) });
        db.t.reviews.push(r); ev('reviews', 'INSERT', r); return null;
      });
    },
  };
  function upd(id, uid, fn) { return tx((db, ev) => { const o = db.t.orders.find(x => x.id === id && x.buyer_id === uid); if (!o) throw new Error('Заказ не найден'); fn(o); o.updated_at = now(); ev('orders', 'UPDATE', o); return null; }); }

  function createClient(url, key, opts) {
    const SK = opts?.auth?.storageKey || 'sb';
    const sess = () => { try { return JSON.parse(localStorage.getItem('mock-' + SK)); } catch { return null; } };
    const c = {
      _uid: () => sess()?.user?.id || null,
      auth: {
        async getSession() { return { data: { session: sess() } }; },
        async signInWithPassword({ email, password }) {
          const u = read().users.find(x => x.email === email && x.password === password);
          if (!u) return { data: {}, error: { message: 'Invalid login credentials' } };
          const s = { user: { id: u.id, email } }; localStorage.setItem('mock-' + SK, JSON.stringify(s)); return { data: s, error: null };
        },
        async signUp({ email, password }) {
          const u = tx(db => { const u = { id: uuid(), email, password }; db.users.push(u); return u; });
          const s = { user: { id: u.id, email } }; localStorage.setItem('mock-' + SK, JSON.stringify(s)); return { data: { ...s, session: s }, error: null };
        },
        async signOut() { localStorage.removeItem('mock-' + SK); return { error: null }; },
        onAuthStateChange() { return { data: { subscription: { unsubscribe() {} } } }; },
      },
      from: t => new Q(c, t),
      async rpc(name, args) { try { return { data: JSON.parse(JSON.stringify(RPC[name](args, c._uid()))), error: null }; } catch (e) { return { data: null, error: { message: e.message } }; } },
      channel(name) {
        const ch = { name, hs: [], on(_, o, cb) { this.hs.push({ o, cb }); return this; }, subscribe(cb) { chans.push(this); cb?.('SUBSCRIBED'); return this; }, unsubscribe() { chans = chans.filter(x => x !== this); return Promise.resolve('ok'); } };
        return ch;
      },
      removeChannel(ch) { return ch.unsubscribe(); },
      storage: { from: () => ({
        async upload(path) { return { data: { path }, error: null }; },
        getPublicUrl(path) { return { data: { publicUrl: 'data:image/gif;base64,R0lGODlhAQABAAAAACw=#' + path } }; },
      }) },
    };
    return c;
  }
  window.__SUPABASE_MOCK__ = { createClient };
})();
