/* =============================================================
   CineWave — Mini App front-end controller
   Vanilla ES6, Telegram WebApp SDK
   ============================================================= */
(() => {
  'use strict';

  // ---- Telegram WebApp ----
  const tg = window.Telegram?.WebApp;
  const tgInitData = tg?.initData || '';
  if (tg) {
    tg.ready();
    tg.expand();
    try { tg.setHeaderColor('#08080b'); tg.setBackgroundColor('#08080b'); } catch (e) {}
  }
  const haptic = (type = 'light') => { try { tg?.HapticFeedback?.impactOccurred(type); } catch (e) {} };

  // ---- State ----
  const S = {
    favIds: new Set(),
    genres: [],
    home: null,
    catalog: { key: null, offset: 0, loading: false, done: false, params: {} },
  };

  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));

  // ---- API ----
  async function api(route, { method = 'GET', body = null, params = {} } = {}) {
    const url = new URL(window.APP.api, location.href);
    url.searchParams.set('route', route);
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
    });
    const headers = { 'X-Telegram-Init-Data': tgInitData };
    const opts = { method, headers };
    if (body) { headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    const res = await fetch(url.toString(), opts);
    const json = await res.json().catch(() => ({ success: false, error: 'bad json' }));
    if (!json.success) throw new Error(json.error || 'request failed');
    return json;
  }

  // ---- Lazy image loading ----
  const imgObserver = new IntersectionObserver((entries, obs) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const img = e.target;
      img.src = img.dataset.src;
      img.onload = () => img.classList.add('loaded');
      obs.unobserve(img);
    });
  }, { rootMargin: '200px' });

  const lazy = (src, alt = '') =>
    `<img data-src="${esc(src || placeholder())}" alt="${esc(alt)}" loading="lazy">`;

  function placeholder() {
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450"><rect width="100%" height="100%" fill="#1c1c25"/></svg>`);
  }
  const bindLazy = (root) => $$('img[data-src]', root).forEach(i => imgObserver.observe(i));

  // ---- Toast ----
  let toastT;
  function toast(msg) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastT);
    toastT = setTimeout(() => t.classList.remove('show'), 2200);
  }

  // ---- Card template ----
  function card(m, opts = {}) {
    const fav = S.favIds.has(Number(m.id)) ? 'active' : '';
    const rating = m.rating ? `<div class="card__rating">★ ${Number(m.rating).toFixed(1)}</div>` : '';
    const age = m.age_rating ? `<div class="card__age">${esc(m.age_rating)}</div>` : '';
    const sub = [m.year, catLabel(m.category)].filter(Boolean).map(esc).join(' • ');
    const progress = opts.progress != null
      ? `<div class="card__progress"><i style="width:${opts.progress}%"></i></div>` : '';
    const cls = 'card' + (opts.wide ? ' card--wide' : '');
    const poster = opts.wide ? (m.backdrop || m.poster) : m.poster;
    return `
      <article class="${cls}" data-id="${m.id}">
        <div class="card__poster">
          ${lazy(poster, m.title)}
          ${rating}${age}
          <button class="card__fav ${fav}" data-fav="${m.id}" aria-label="В избранное">
            <svg viewBox="0 0 24 24"><path d="M12 21s-7-4.5-9.5-9A5 5 0 0112 5a5 5 0 019.5 7c-2.5 4.5-9.5 9-9.5 9z"/></svg>
          </button>
        </div>
        <div class="card__body">
          <div class="card__title">${esc(m.title)}</div>
          <div class="card__sub">${sub}</div>
          ${progress}
        </div>
      </article>`;
  }

  const catLabel = (c) => ({ movie:'Фильм', series:'Сериал', anime:'Аниме', cartoon:'Мультфильм' }[c] || '');

  function skeletonRail(wide) {
    const w = wide ? ' style="width:260px"' : '';
    const p = wide ? 'aspect-ratio:16/10' : '';
    let s = '';
    for (let i = 0; i < 6; i++) s += `
      <div class="sk-card"${w}>
        <div class="skeleton sk-poster" style="${p}"></div>
        <div class="skeleton sk-line"></div>
        <div class="skeleton sk-line short"></div>
      </div>`;
    return s;
  }

  // ---- Rails / home ----
  function railHTML(id, title, items, opts = {}) {
    if (!items || !items.length) return '';
    const cards = items.map(m => card(m, {
      wide: opts.wide,
      progress: opts.progressMap ? opts.progressMap[m.id] : null,
    })).join('');
    return `
      <section class="rail" data-rail="${id}">
        <div class="rail__head">
          <h2 class="rail__title">${title}</h2>
          ${opts.section ? `<button class="rail__more" data-section="${opts.section}">Все ›</button>` : ''}
        </div>
        <div class="rail__scroller">${cards}</div>
      </section>`;
  }

  async function loadHome() {
    const railsEl = $('#rails');
    // Skeleton hero + rails
    $('#heroTrack').innerHTML = `<div class="skeleton sk-hero"></div>`;
    railsEl.innerHTML = [1,2,3].map(() =>
      `<section class="rail"><div class="rail__head"><div class="skeleton sk-line" style="width:140px;height:18px"></div></div><div class="rail__scroller">${skeletonRail()}</div></section>`
    ).join('');

    try {
      const [{ data }, favResp] = await Promise.all([
        api('home'),
        loadFavIds(),
      ]);
      S.home = data;
      renderHero(data.banners || []);

      // History (continue watching) + favorites need auth; fetch in parallel
      let history = [], favorites = [];
      try { history = (await api('history')).data || []; } catch (e) {}
      try { favorites = (await api('favorites')).data || []; } catch (e) {}
      const progressMap = {};
      history.forEach(h => progressMap[h.id] = h.progress);

      const html = [
        history.length ? railHTML('history', '🕒 Продолжить просмотр', history, { progressMap }) : '',
        railHTML('new', '🔥 Новинки', data.new, { wide: true, section: 'new' }),
        railHTML('popular', '🎬 Популярное', data.popular, { section: 'popular' }),
        railHTML('recommended', '⭐ Рекомендуем', data.recommended, { section: 'recommended' }),
        railHTML('coming', '🎞 Скоро выйдет', data.coming_soon, { section: 'coming_soon' }),
        railHTML('cinema', '🍿 Сейчас в кино', data.in_cinema, { section: 'in_cinema' }),
        railHTML('series', '📺 Сериалы', data.series, { section: 'series' }),
        railHTML('movies', '🎥 Фильмы', data.movies, { section: 'movies' }),
        railHTML('anime', '🎌 Аниме', data.anime, { section: 'anime' }),
        railHTML('cartoons', '👶 Мультфильмы', data.cartoons, { section: 'cartoons' }),
        favorites.length ? railHTML('fav', '❤️ Избранное', favorites, { section: 'favorites' }) : '',
      ].join('');

      railsEl.innerHTML = html || emptyState('🎬', 'Каталог пуст', 'Контент появится, как только администратор добавит фильмы через бота.');
      bindLazy(railsEl);
    } catch (e) {
      railsEl.innerHTML = emptyState('⚠️', 'Не удалось загрузить', e.message);
    }
  }

  async function loadFavIds() {
    try {
      const { data } = await api('favorites');
      S.favIds = new Set((data || []).map(m => Number(m.id)));
    } catch (e) { /* unauthenticated preview */ }
  }

  // ---- Hero carousel ----
  let heroTimer, heroIndex = 0, heroCount = 0;
  function renderHero(banners) {
    const track = $('#heroTrack'), dots = $('#heroDots');
    clearInterval(heroTimer);
    if (!banners.length) { track.innerHTML = ''; dots.innerHTML = ''; return; }
    heroCount = banners.length; heroIndex = 0;

    track.innerHTML = banners.map((b, i) => {
      const meta = [
        b.rating ? `<span class="star">★ ${Number(b.rating).toFixed(1)}</span>` : '',
        b.genre ? esc(b.genre) : '',
        b.year || (b.release_date ? String(b.release_date).slice(0,4) : ''),
      ].filter(Boolean).join(' • ');
      return `
        <div class="hero__slide ${i===0?'active':''}" data-hero="${i}" data-movie="${b.movie_id||''}">
          <div class="hero__bg">${lazy(b.image, b.title)}</div>
          <span class="hero__badge">Премьера</span>
          <h1 class="hero__title">${esc(b.title)}</h1>
          <div class="hero__meta">${meta}</div>
          <p class="hero__desc">${esc(b.description || '')}</p>
          <div class="hero__cta">
            <button class="btn btn--primary" data-hero-play="${b.movie_id||''}">
              <svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z"/></svg> Подробнее
            </button>
            <button class="btn btn--glass" data-hero-fav="${b.movie_id||''}">＋ Избранное</button>
          </div>
        </div>`;
    }).join('');
    dots.innerHTML = banners.map((_, i) => `<i class="${i===0?'active':''}"></i>`).join('');
    bindLazy(track);
    heroTimer = setInterval(nextHero, 6000);
  }
  function goHero(i) {
    heroIndex = (i + heroCount) % heroCount;
    $$('.hero__slide').forEach((s, idx) => s.classList.toggle('active', idx === heroIndex));
    $$('#heroDots i').forEach((d, idx) => d.classList.toggle('active', idx === heroIndex));
  }
  const nextHero = () => goHero(heroIndex + 1);

  // ---- Detail view ----
  async function openDetail(id) {
    haptic('medium');
    switchView('detail');
    const el = $('#detailContent');
    el.innerHTML = `<div class="skeleton" style="height:60vh"></div>`;
    window.scrollTo(0, 0);
    try {
      const { data: m } = await api('movie', { params: { id } });
      renderDetail(m);
    } catch (e) {
      el.innerHTML = emptyState('⚠️', 'Ошибка', e.message);
    }
  }

  function renderDetail(m) {
    const fav = S.favIds.has(Number(m.id)) ? 'active' : '';
    const tags = [
      m.rating ? `<span class="tag tag--rating">★ ${Number(m.rating).toFixed(1)}</span>` : '',
      m.year ? `<span class="tag">${esc(m.year)}</span>` : '',
      m.age_rating ? `<span class="tag">${esc(m.age_rating)}</span>` : '',
      m.duration ? `<span class="tag">${esc(m.duration)} мин</span>` : '',
      ...(m.genres || []).map(g => `<span class="tag">${esc(g.name)}</span>`),
    ].filter(Boolean).join('');

    const meta = [
      ['Категория', catLabel(m.category)],
      ['Страна', m.country],
      ['Год', m.year],
      ['Язык', m.language],
      ['Режиссёр', m.director],
      ['Длительность', m.duration ? m.duration + ' мин' : null],
    ].filter(([, v]) => v).map(([k, v]) =>
      `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('');

    const actors = (m.actors && m.actors.length)
      ? `<div class="section"><h3>В ролях</h3><p>${m.actors.map(esc).join(', ')}</p></div>` : '';

    const trailer = m.trailer ? `
      <div class="section"><h3>Трейлер</h3>
        <div class="trailer-wrap">${embedTrailer(m.trailer)}</div>
      </div>` : '';

    const shots = (m.screenshots && m.screenshots.length) ? `
      <div class="section"><h3>Кадры</h3>
        <div class="shots">${m.screenshots.map(s => lazy(s)).join('')}</div>
      </div>` : '';

    const similar = (m.similar && m.similar.length) ? `
      <section class="rail"><div class="rail__head"><h2 class="rail__title">Похожие</h2></div>
        <div class="rail__scroller">${m.similar.map(x => card(x)).join('')}</div>
      </section>` : '';

    $('#detailContent').innerHTML = `
      <div class="detail__hero">
        <div class="detail__bg">${lazy(m.backdrop || m.poster, m.title)}</div>
        <div class="detail__floatbar">
          <button class="back-btn" data-back>‹</button>
          <button class="icon-btn ${fav}" data-fav="${m.id}" style="width:38px;height:38px">
            <svg viewBox="0 0 24 24"><path d="M12 21s-7-4.5-9.5-9A5 5 0 0112 5a5 5 0 019.5 7c-2.5 4.5-9.5 9-9.5 9z"/></svg>
          </button>
        </div>
        <div class="detail__row">
          <div class="detail__poster">${lazy(m.poster, m.title)}</div>
          <div class="detail__headmeta">
            <h1 class="detail__title">${esc(m.title)}</h1>
            <div class="detail__tags">${tags}</div>
          </div>
        </div>
        <div class="detail__cta">
          <button class="btn btn--primary" data-watch="${m.id}">
            <svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z"/></svg> Смотреть
          </button>
          <button class="btn btn--glass" data-fav="${m.id}">
            ${fav ? '❤️ В избранном' : '＋ Избранное'}
          </button>
        </div>
      </div>
      ${m.description ? `<div class="section"><h3>Описание</h3><p>${esc(m.description)}</p></div>` : ''}
      <div class="section"><h3>О тайтле</h3><dl class="meta-grid">${meta}</dl></div>
      ${actors}${trailer}${shots}${similar}
    `;
    bindLazy($('#detailContent'));
  }

  function embedTrailer(url) {
    const yt = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/))([\w-]{11})/);
    if (yt) return `<iframe src="https://www.youtube.com/embed/${yt[1]}" allowfullscreen allow="encrypted-media"></iframe>`;
    return `<iframe src="${esc(url)}" allowfullscreen></iframe>`;
  }

  // ---- Watch ----
  async function watch(id) {
    haptic('medium');
    try {
      const { data } = await api('watch', { method: 'POST', body: { movie_id: Number(id) } });
      const link = data.watch_url || data.trailer;
      if (link) {
        if (tg?.openLink) tg.openLink(link, { try_instant_view: false });
        else window.open(link, '_blank');
      } else {
        toast('Ссылка появится позже');
      }
    } catch (e) { toast('Не удалось открыть'); }
  }

  // ---- Favorites ----
  async function toggleFav(id) {
    id = Number(id);
    haptic('light');
    try {
      const { data } = await api('favorites', { method: 'POST', body: { movie_id: id } });
      if (data.favorited) { S.favIds.add(id); toast('Добавлено в избранное'); }
      else { S.favIds.delete(id); toast('Удалено из избранного'); }
      syncFavUI(id);
    } catch (e) { toast('Войдите через Telegram'); }
  }
  function syncFavUI(id) {
    const active = S.favIds.has(Number(id));
    $$(`[data-fav="${id}"]`).forEach(b => {
      b.classList.toggle('active', active);
      if (b.classList.contains('btn')) b.innerHTML = active ? '❤️ В избранном' : '＋ Избранное';
    });
  }

  // ---- Catalog / section view (infinite scroll) ----
  const SECTION_TITLES = {
    new:'🔥 Новинки', popular:'🎬 Популярное', recommended:'⭐ Рекомендуем',
    coming_soon:'🎞 Скоро выйдет', in_cinema:'🍿 Сейчас в кино',
    series:'📺 Сериалы', movies:'🎥 Фильмы', anime:'🎌 Аниме',
    cartoons:'👶 Мультфильмы', favorites:'❤️ Избранное', history:'🕒 История',
  };
  const SECTION_PARAMS = {
    new:{ flag:'new', sort:'newest' }, popular:{ flag:'popular', sort:'popular' },
    recommended:{ flag:'recommended', sort:'rating' },
    coming_soon:{ status:'coming_soon', sort:'soon' }, in_cinema:{ status:'in_cinema', sort:'rating' },
    series:{ category:'series' }, movies:{ category:'movie' },
    anime:{ category:'anime' }, cartoons:{ category:'cartoon' },
  };

  async function openSection(key) {
    switchView('catalog');
    $('#catalogTitle').textContent = SECTION_TITLES[key] || 'Каталог';
    const grid = $('#catalogGrid');
    grid.innerHTML = `<div class="rail__scroller" style="flex-wrap:wrap">${skeletonRail()}</div>`;
    S.catalog = { key, offset: 0, loading: false, done: false, params: SECTION_PARAMS[key] || {} };

    // Favorites & history are user endpoints, not paginated /movies
    if (key === 'favorites' || key === 'history') {
      try {
        const { data } = await api(key);
        grid.innerHTML = data.length
          ? data.map(m => card(m, { progress: key==='history' ? m.progress : null })).join('')
          : emptyState(key==='favorites'?'❤️':'🕒', 'Пусто', 'Здесь появится сохранённое.');
        bindLazy(grid);
        S.catalog.done = true;
      } catch (e) { grid.innerHTML = emptyState('⚠️','Ошибка', e.message); }
      return;
    }
    grid.innerHTML = '';
    loadCatalogPage();
  }

  async function loadCatalogPage() {
    const c = S.catalog;
    if (c.loading || c.done) return;
    c.loading = true;
    try {
      const { data } = await api('movies', { params: { ...c.params, limit: 18, offset: c.offset } });
      if (!data.length) { c.done = true; if (!c.offset) $('#catalogGrid').innerHTML = emptyState('🎬','Пусто','Контент скоро появится.'); }
      else {
        $('#catalogGrid').insertAdjacentHTML('beforeend', data.map(m => card(m)).join(''));
        bindLazy($('#catalogGrid'));
        c.offset += data.length;
        if (data.length < 18) c.done = true;
      }
    } catch (e) { c.done = true; }
    c.loading = false;
  }

  const catalogObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && $('#view-catalog').classList.contains('view--active')) loadCatalogPage();
  }, { rootMargin: '400px' });
  catalogObserver.observe($('#catalogSentinel'));

  // ---- Search ----
  let searchT;
  function openSearch() {
    $('#searchOverlay').classList.add('open');
    $('#searchInput').focus();
    populateFilters();
  }
  function closeSearch() { $('#searchOverlay').classList.remove('open'); }

  function populateFilters() {
    if (S.genres.length) return;
    api('genres').then(({ data }) => {
      S.genres = data;
      $('#fGenre').insertAdjacentHTML('beforeend',
        data.map(g => `<option value="${esc(g.slug)}">${esc(g.name)}</option>`).join(''));
    }).catch(() => {});
    const y = new Date().getFullYear();
    const years = [];
    for (let i = y + 1; i >= 1980; i--) years.push(`<option value="${i}">${i}</option>`);
    $('#fYear').insertAdjacentHTML('beforeend', years.join(''));
  }

  function runSearch() {
    clearTimeout(searchT);
    searchT = setTimeout(async () => {
      const params = {
        q: $('#searchInput').value.trim(),
        category: $('#fCategory').value,
        genre: $('#fGenre').value,
        year: $('#fYear').value,
        min_rating: $('#fRating').value,
        limit: 30,
      };
      if (!params.q && !params.category && !params.genre && !params.year && !params.min_rating) {
        $('#searchResults').innerHTML = ''; $('#searchEmpty').hidden = true; return;
      }
      $('#searchResults').innerHTML = `<div style="grid-column:1/-1">${skeletonRail()}</div>`;
      try {
        const { data } = await api('search', { params });
        $('#searchEmpty').hidden = data.length > 0;
        $('#searchResults').innerHTML = data.map(m => card(m)).join('');
        bindLazy($('#searchResults'));
      } catch (e) { $('#searchResults').innerHTML = ''; }
    }, 280);
  }

  // ---- Views / nav ----
  function switchView(name) {
    $$('.view').forEach(v => v.classList.remove('view--active'));
    $(`#view-${name}`)?.classList.add('view--active');
    if (name !== 'detail' && name !== 'catalog') {
      $$('.nav-item').forEach(n => n.classList.toggle('is-active', n.dataset.nav === name));
    }
    window.scrollTo(0, 0);
  }

  function emptyState(em, title, text) {
    return `<div class="empty"><div class="em">${em}</div><h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;
  }

  // ---- Hash deep links (from bot buttons: #series, #anime, …) ----
  function handleHash() {
    const h = location.hash.replace('#', '');
    if (!h) return;
    if (SECTION_TITLES[h]) openSection(h);
  }

  // ---- Profile ----
  async function loadProfile() {
    try {
      const { data } = await api('profile', { method: 'POST' });
      const initial = (data.first_name || data.username || 'U').charAt(0).toUpperCase();
      $('#avatarInitial').textContent = initial;
      if (data.photo_url) {
        $('#btnProfile').innerHTML = `<img src="${esc(data.photo_url)}" alt="">`;
      }
    } catch (e) {}
  }

  // ---- Global events (delegation) ----
  document.addEventListener('click', (ev) => {
    const t = ev.target;

    const back = t.closest('[data-back]');
    if (back) { history.length > 1 ? switchView('home') : switchView('home'); return; }

    const favBtn = t.closest('[data-fav]');
    if (favBtn) { ev.stopPropagation(); toggleFav(favBtn.dataset.fav); return; }

    const watchBtn = t.closest('[data-watch]');
    if (watchBtn) { watch(watchBtn.dataset.watch); return; }

    const heroPlay = t.closest('[data-hero-play]');
    if (heroPlay) { const id = heroPlay.dataset.heroPlay; if (id) openDetail(id); else toast('Скоро в каталоге'); return; }
    const heroFav = t.closest('[data-hero-fav]');
    if (heroFav) { const id = heroFav.dataset.heroFav; if (id) toggleFav(id); return; }

    const sectionBtn = t.closest('[data-section]');
    if (sectionBtn) { openSection(sectionBtn.dataset.section); return; }

    const c = t.closest('.card');
    if (c && c.dataset.id) { openDetail(c.dataset.id); return; }

    const nav = t.closest('.nav-item');
    if (nav) {
      const n = nav.dataset.nav;
      haptic('light');
      if (n === 'search') { openSearch(); return; }
      if (n === 'favorites') { switchView('catalog'); openSection('favorites'); return; }
      if (n === 'history') { switchView('catalog'); openSection('history'); return; }
      switchView('home');
      return;
    }
  });

  $('#btnSearch').addEventListener('click', openSearch);
  $('#btnSearchClose').addEventListener('click', closeSearch);
  $('#searchInput').addEventListener('input', runSearch);
  ['#fCategory','#fGenre','#fYear','#fRating'].forEach(s => $(s).addEventListener('change', runSearch));
  $('#btnProfile').addEventListener('click', () => { switchView('catalog'); openSection('favorites'); });

  // Top bar blur on scroll
  window.addEventListener('scroll', () => {
    $('#topbar').classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });

  window.addEventListener('hashchange', handleHash);

  // ---- Boot ----
  loadProfile();
  loadHome().then(handleHash);
})();
