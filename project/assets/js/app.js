/* =============================================================
   CineWave \u2014 Mini App front-end controller
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
    const text = await res.text();
    let json;
    try {
      json = JSON.parse(text);
    } catch (e) {
      // Surface what the server actually returned (PHP error page, stray
      // output, empty body) instead of a generic "bad json".
      const snippet = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 220);
      throw new Error('HTTP ' + res.status + ' | ' + (snippet || '(empty response)'));
    }
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
    const rating = m.rating ? `<div class="card__rating">\u2605 ${Number(m.rating).toFixed(1)}</div>` : '';
    const age = m.age_rating ? `<div class="card__age">${esc(m.age_rating)}</div>` : '';
    const sub = [m.year, catLabel(m.category)].filter(Boolean).map(esc).join(' \u2022 ');
    const progress = opts.progress != null
      ? `<div class="card__progress"><i style="width:${opts.progress}%"></i></div>` : '';
    const cls = 'card' + (opts.wide ? ' card--wide' : '');
    const poster = opts.wide
      ? (m.banner || m.backdrop || m.poster)
      : (m.thumbnail || m.poster);
    return `
      <article class="${cls}" data-id="${m.id}">
        <div class="card__poster">
          ${lazy(poster, m.title)}
          ${rating}${age}
          <button class="card__fav ${fav}" data-fav="${m.id}" aria-label="\u0412 \u0438\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0435">
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

  const catLabel = (c) => ({ movie:'\u0424\u0438\u043B\u044C\u043C', series:'\u0421\u0435\u0440\u0438\u0430\u043B', anime:'\u0410\u043D\u0438\u043C\u0435', cartoon:'\u041C\u0443\u043B\u044C\u0442\u0444\u0438\u043B\u044C\u043C' }[c] || '');

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
          ${opts.section ? `<button class="rail__more" data-section="${opts.section}">\u0412\u0441\u0435 \u203A</button>` : ''}
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
        history.length ? railHTML('history', '\uD83D\uDD52 \u041F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C \u043F\u0440\u043E\u0441\u043C\u043E\u0442\u0440', history, { progressMap }) : '',
        railHTML('new', '\uD83D\uDD25 \u041D\u043E\u0432\u0438\u043D\u043A\u0438', data.new, { wide: true, section: 'new' }),
        railHTML('popular', '\uD83C\uDFAC \u041F\u043E\u043F\u0443\u043B\u044F\u0440\u043D\u043E\u0435', data.popular, { section: 'popular' }),
        railHTML('recommended', '\u2B50 \u0420\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u0443\u0435\u043C', data.recommended, { section: 'recommended' }),
        railHTML('coming', '\uD83C\uDF9E \u0421\u043A\u043E\u0440\u043E \u0432\u044B\u0439\u0434\u0435\u0442', data.coming_soon, { section: 'coming_soon' }),
        railHTML('cinema', '\uD83C\uDF7F \u0421\u0435\u0439\u0447\u0430\u0441 \u0432 \u043A\u0438\u043D\u043E', data.in_cinema, { section: 'in_cinema' }),
        railHTML('series', '\uD83D\uDCFA \u0421\u0435\u0440\u0438\u0430\u043B\u044B', data.series, { section: 'series' }),
        railHTML('movies', '\uD83C\uDFA5 \u0424\u0438\u043B\u044C\u043C\u044B', data.movies, { section: 'movies' }),
        railHTML('anime', '\uD83C\uDF8C \u0410\u043D\u0438\u043C\u0435', data.anime, { section: 'anime' }),
        railHTML('cartoons', '\uD83D\uDC76 \u041C\u0443\u043B\u044C\u0442\u0444\u0438\u043B\u044C\u043C\u044B', data.cartoons, { section: 'cartoons' }),
        favorites.length ? railHTML('fav', '\u2764\uFE0F \u0418\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0435', favorites, { section: 'favorites' }) : '',
      ].join('');

      railsEl.innerHTML = html || emptyState('\uD83C\uDFAC', '\u041A\u0430\u0442\u0430\u043B\u043E\u0433 \u043F\u0443\u0441\u0442', '\u041A\u043E\u043D\u0442\u0435\u043D\u0442 \u043F\u043E\u044F\u0432\u0438\u0442\u0441\u044F, \u043A\u0430\u043A \u0442\u043E\u043B\u044C\u043A\u043E \u0430\u0434\u043C\u0438\u043D\u0438\u0441\u0442\u0440\u0430\u0442\u043E\u0440 \u0434\u043E\u0431\u0430\u0432\u0438\u0442 \u0444\u0438\u043B\u044C\u043C\u044B \u0447\u0435\u0440\u0435\u0437 \u0431\u043E\u0442\u0430.');
      bindLazy(railsEl);
    } catch (e) {
      railsEl.innerHTML = emptyState('\u26A0\uFE0F', '\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C', e.message);
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

  // Video background when the banner has a playable clip; the poster is used
  // as the video's poster frame so something is visible while it buffers.
  function heroMedia(b) {
    if (b.video) {
      return `<video class="hero__video" muted loop playsinline preload="none"
        ${b.image ? `poster="${esc(b.image)}"` : ''} data-src="${esc(b.video)}"></video>`;
    }
    return lazy(b.image, b.title);
  }

  // Only the visible slide plays: saves traffic and battery.
  function syncHeroVideo() {
    $$('.hero__slide').forEach((slide, idx) => {
      const v = slide.querySelector('.hero__video');
      if (!v) return;
      if (idx === heroIndex) {
        if (!v.src && v.dataset.src) v.src = v.dataset.src;
        const p = v.play();
        if (p && p.catch) p.catch(() => {});
      } else {
        v.pause();
      }
    });
  }
  function renderHero(banners) {
    const track = $('#heroTrack'), dots = $('#heroDots');
    clearInterval(heroTimer);
    if (!banners.length) { track.innerHTML = ''; dots.innerHTML = ''; return; }
    heroCount = banners.length; heroIndex = 0;

    track.innerHTML = banners.map((b, i) => {
      const meta = [
        b.rating ? `<span class="star">\u2605 ${Number(b.rating).toFixed(1)}</span>` : '',
        b.genre ? esc(b.genre) : '',
        b.year || (b.release_date ? String(b.release_date).slice(0,4) : ''),
      ].filter(Boolean).join(' \u2022 ');
      return `
        <div class="hero__slide ${i===0?'active':''}" data-hero="${i}" data-movie="${b.movie_id||''}">
          <div class="hero__bg">${heroMedia(b)}</div>
          <span class="hero__badge">\u041F\u0440\u0435\u043C\u044C\u0435\u0440\u0430</span>
          <h1 class="hero__title">${esc(b.title)}</h1>
          <div class="hero__meta">${meta}</div>
          <p class="hero__desc">${esc(b.description || '')}</p>
          <div class="hero__cta">
            <button class="btn btn--primary" data-hero-play="${b.movie_id||''}">
              <svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z"/></svg> \u041F\u043E\u0434\u0440\u043E\u0431\u043D\u0435\u0435
            </button>
            <button class="btn btn--glass" data-hero-fav="${b.movie_id||''}">\uFF0B \u0418\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0435</button>
          </div>
        </div>`;
    }).join('');
    dots.innerHTML = banners.map((_, i) => `<i class="${i===0?'active':''}"></i>`).join('');
    bindLazy(track);
    syncHeroVideo();
    heroTimer = setInterval(nextHero, 6000);
  }
  function goHero(i) {
    heroIndex = (i + heroCount) % heroCount;
    $$('.hero__slide').forEach((s, idx) => s.classList.toggle('active', idx === heroIndex));
    $$('#heroDots i').forEach((d, idx) => d.classList.toggle('active', idx === heroIndex));
    syncHeroVideo();
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
      el.innerHTML = emptyState('\u26A0\uFE0F', '\u041E\u0448\u0438\u0431\u043A\u0430', e.message);
    }
  }

  function renderDetail(m) {
    const fav = S.favIds.has(Number(m.id)) ? 'active' : '';
    const tags = [
      m.rating ? `<span class="tag tag--rating">\u2605 ${Number(m.rating).toFixed(1)}</span>` : '',
      m.year ? `<span class="tag">${esc(m.year)}</span>` : '',
      m.age_rating ? `<span class="tag">${esc(m.age_rating)}</span>` : '',
      m.duration ? `<span class="tag">${esc(m.duration)} \u043C\u0438\u043D</span>` : '',
      ...(m.genres || []).map(g => `<span class="tag">${esc(g.name)}</span>`),
    ].filter(Boolean).join('');

    const meta = [
      ['\u041A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044F', catLabel(m.category)],
      ['\u0421\u0442\u0440\u0430\u043D\u0430', m.country],
      ['\u0413\u043E\u0434', m.year],
      ['\u042F\u0437\u044B\u043A', m.language],
      ['\u0420\u0435\u0436\u0438\u0441\u0441\u0451\u0440', m.director],
      ['\u0414\u043B\u0438\u0442\u0435\u043B\u044C\u043D\u043E\u0441\u0442\u044C', m.duration ? m.duration + ' \u043C\u0438\u043D' : null],
    ].filter(([, v]) => v).map(([k, v]) =>
      `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('');

    const actors = (m.actors && m.actors.length)
      ? `<div class="section"><h3>\u0412 \u0440\u043E\u043B\u044F\u0445</h3><p>${m.actors.map(esc).join(', ')}</p></div>` : '';

    const trailer = m.trailer ? `
      <div class="section"><h3>\u0422\u0440\u0435\u0439\u043B\u0435\u0440</h3>
        <div class="trailer-wrap">${embedTrailer(m.trailer)}</div>
      </div>` : '';

    const shots = (m.screenshots && m.screenshots.length) ? `
      <div class="section"><h3>\u041A\u0430\u0434\u0440\u044B</h3>
        <div class="shots">${m.screenshots.map(s => lazy(s)).join('')}</div>
      </div>` : '';

    const similar = (m.similar && m.similar.length) ? `
      <section class="rail"><div class="rail__head"><h2 class="rail__title">\u041F\u043E\u0445\u043E\u0436\u0438\u0435</h2></div>
        <div class="rail__scroller">${m.similar.map(x => card(x)).join('')}</div>
      </section>` : '';

    $('#detailContent').innerHTML = `
      <div class="detail__hero">
        <div class="detail__bg">${detailMedia(m)}</div>
        <div class="detail__floatbar">
          <button class="back-btn" data-back>\u2039</button>
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
          ${['series', 'anime'].includes(m.category)
            ? `<button class="btn btn--primary" data-scroll="episodesSection"><svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z"/></svg> \u0421\u043C\u043E\u0442\u0440\u0435\u0442\u044C \u0441\u0435\u0440\u0438\u0438</button>`
            : `<button class="btn btn--primary" data-watch="${m.id}"><svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z"/></svg> \u0421\u043C\u043E\u0442\u0440\u0435\u0442\u044C</button>`}
          <button class="btn btn--glass" data-fav="${m.id}">
            ${fav ? '\u2764\uFE0F \u0412 \u0438\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u043C' : '\uFF0B \u0418\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0435'}
          </button>
        </div>
      </div>
      ${m.description ? `<div class="section"><h3>\u041E\u043F\u0438\u0441\u0430\u043D\u0438\u0435</h3><p>${esc(m.description)}</p></div>` : ''}
      <div class="section"><h3>\u041E \u0442\u0430\u0439\u0442\u043B\u0435</h3><dl class="meta-grid">${meta}</dl></div>
      ${actors}${trailer}${shots}
      <div id="episodesSection"></div>
      ${similar}
    `;
    bindLazy($('#detailContent'));
    if (['series', 'anime'].includes(m.category)) {
      loadEpisodes(m.id);
    }
  }

  // ---- Episodes (series / anime) ----
  async function loadEpisodes(movieId) {
    const host = $('#episodesSection');
    if (!host) return;
    try {
      const { data } = await api('episodes', { params: { movie_id: movieId } });
      if (!data || !data.length) { host.innerHTML = ''; return; }
      host.innerHTML = `<div class="section"><h3>\u0421\u0435\u0440\u0438\u0438</h3>${data.map(s => `
        <div class="season">
          <div class="season__title">\u0421\u0435\u0437\u043E\u043D ${s.season}</div>
          <div class="ep-grid">${s.episodes.map(e => `
            <button class="ep" data-episode="${e.id}" data-deep="ep_${movieId}_${s.season}_${e.episode}">
              <span class="ep__num">${e.episode}</span>
              <span class="ep__label">${e.title ? esc(e.title) : '\u0421\u0435\u0440\u0438\u044F ' + e.episode}</span>
              <svg class="ep__play" viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z"/></svg>
            </button>`).join('')}</div>
        </div>`).join('')}</div>`;
    } catch (e) { host.innerHTML = ''; }
  }

  async function watchEpisode(id) {
    haptic('medium');
    try {
      const { data } = await api('watch', { method: 'POST', body: { episode_id: Number(id) } });
      if (data.via === 'telegram' && data.delivered) {
        toast(data.message || '\u0421\u0435\u0440\u0438\u044F \u043E\u0442\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0430 \u0432 \u0447\u0430\u0442 \u0441 \u0431\u043E\u0442\u043E\u043C \u2705');
        setTimeout(() => { try { tg?.close(); } catch (e) {} }, 1400);
        return;
      }
      const link = data.watch_url;
      if (link) {
        if (tg?.openLink) tg.openLink(link, { try_instant_view: false });
        else window.open(link, '_blank');
      } else {
        toast('\u0418\u0441\u0442\u043E\u0447\u043D\u0438\u043A \u043F\u043E\u044F\u0432\u0438\u0442\u0441\u044F \u043F\u043E\u0437\u0436\u0435');
      }
    } catch (e) { toast('\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u044C'); }
  }

  // Direct video files can autoplay inline; page links (YouTube etc.) cannot.
  function isVideoFile(url) {
    if (!url) return false;
    return /\.(mp4|webm|m4v|mov)(\?|#|$)/i.test(url);
  }

  /**
   * Detail header media: when the title has a short preview clip it plays
   * automatically (muted, looping) instead of showing a static backdrop.
   */
  function detailMedia(m) {
    if (isVideoFile(m.trailer)) {
      return `<video class="detail__video" autoplay muted loop playsinline
        ${m.backdrop || m.poster ? `poster="${esc(m.backdrop || m.poster)}"` : ''}
        src="${esc(m.trailer)}"></video>`;
    }
    return lazy(m.backdrop || m.poster, m.title);
  }

  function embedTrailer(url) {
    // A real file gets a native player with sound and controls.
    if (isVideoFile(url)) {
      return `<video class="trailer-video" controls playsinline preload="metadata" src="${esc(url)}"></video>`;
    }
    const yt = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/))([\w-]{11})/);
    if (yt) return `<iframe src="https://www.youtube.com/embed/${yt[1]}" allowfullscreen allow="encrypted-media"></iframe>`;
    return `<iframe src="${esc(url)}" allowfullscreen></iframe>`;
  }

  // ---- Watch ----
  // Open a t.me deep link: the Mini App closes and the bot delivers the film.
  function openDeepLink(payload) {
    const link = `https://t.me/${window.APP.bot}?start=${payload}`;
    if (tg?.openTelegramLink) tg.openTelegramLink(link);
    else window.open(link, '_blank');
    setTimeout(() => { try { tg?.close(); } catch (e) {} }, 300);
  }

  async function watch(id) {
    haptic('medium');

    // Preferred: auto-generated per-movie link -> app closes, film arrives in the bot.
    if (window.APP.bot) {
      api('history', { method: 'POST', body: { movie_id: Number(id), progress: 0 } }).catch(() => {});
      openDeepLink(`movie_${id}`);
      return;
    }

    // Fallback (bot username not configured): server-side delivery.
    try {
      const { data } = await api('watch', { method: 'POST', body: { movie_id: Number(id) } });

      // Film delivered straight into the Telegram chat with the bot.
      if (data.via === 'telegram' && data.delivered) {
        toast(data.message || '\u0424\u0438\u043B\u044C\u043C \u043E\u0442\u043F\u0440\u0430\u0432\u043B\u0435\u043D \u0432 \u0447\u0430\u0442 \u0441 \u0431\u043E\u0442\u043E\u043C \u2705');
        setTimeout(() => { try { tg?.close(); } catch (e) {} }, 1400);
        return;
      }

      const link = data.watch_url || data.trailer;
      if (link) {
        if (tg?.openLink) tg.openLink(link, { try_instant_view: false });
        else window.open(link, '_blank');
      } else {
        toast('\u0418\u0441\u0442\u043E\u0447\u043D\u0438\u043A \u043F\u043E\u044F\u0432\u0438\u0442\u0441\u044F \u043F\u043E\u0437\u0436\u0435');
      }
    } catch (e) { toast('\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043A\u0440\u044B\u0442\u044C'); }
  }

  // ---- Favorites ----
  async function toggleFav(id) {
    id = Number(id);
    haptic('light');
    try {
      const { data } = await api('favorites', { method: 'POST', body: { movie_id: id } });
      if (data.favorited) { S.favIds.add(id); toast('\u0414\u043E\u0431\u0430\u0432\u043B\u0435\u043D\u043E \u0432 \u0438\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0435'); }
      else { S.favIds.delete(id); toast('\u0423\u0434\u0430\u043B\u0435\u043D\u043E \u0438\u0437 \u0438\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0433\u043E'); }
      syncFavUI(id);
    } catch (e) { toast('\u0412\u043E\u0439\u0434\u0438\u0442\u0435 \u0447\u0435\u0440\u0435\u0437 Telegram'); }
  }
  function syncFavUI(id) {
    const active = S.favIds.has(Number(id));
    $$(`[data-fav="${id}"]`).forEach(b => {
      b.classList.toggle('active', active);
      if (b.classList.contains('btn')) b.innerHTML = active ? '\u2764\uFE0F \u0412 \u0438\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u043C' : '\uFF0B \u0418\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0435';
    });
  }

  // ---- Catalog / section view (infinite scroll) ----
  const SECTION_TITLES = {
    new:'\uD83D\uDD25 \u041D\u043E\u0432\u0438\u043D\u043A\u0438', popular:'\uD83C\uDFAC \u041F\u043E\u043F\u0443\u043B\u044F\u0440\u043D\u043E\u0435', recommended:'\u2B50 \u0420\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u0443\u0435\u043C',
    coming_soon:'\uD83C\uDF9E \u0421\u043A\u043E\u0440\u043E \u0432\u044B\u0439\u0434\u0435\u0442', in_cinema:'\uD83C\uDF7F \u0421\u0435\u0439\u0447\u0430\u0441 \u0432 \u043A\u0438\u043D\u043E',
    series:'\uD83D\uDCFA \u0421\u0435\u0440\u0438\u0430\u043B\u044B', movies:'\uD83C\uDFA5 \u0424\u0438\u043B\u044C\u043C\u044B', anime:'\uD83C\uDF8C \u0410\u043D\u0438\u043C\u0435',
    cartoons:'\uD83D\uDC76 \u041C\u0443\u043B\u044C\u0442\u0444\u0438\u043B\u044C\u043C\u044B', favorites:'\u2764\uFE0F \u0418\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0435', history:'\uD83D\uDD52 \u0418\u0441\u0442\u043E\u0440\u0438\u044F',
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
    $('#catalogTitle').textContent = SECTION_TITLES[key] || '\u041A\u0430\u0442\u0430\u043B\u043E\u0433';
    const grid = $('#catalogGrid');
    grid.innerHTML = `<div class="rail__scroller" style="flex-wrap:wrap">${skeletonRail()}</div>`;
    S.catalog = { key, offset: 0, loading: false, done: false, params: SECTION_PARAMS[key] || {} };

    // Favorites & history are user endpoints, not paginated /movies
    if (key === 'favorites' || key === 'history') {
      try {
        const { data } = await api(key);
        grid.innerHTML = data.length
          ? data.map(m => card(m, { progress: key==='history' ? m.progress : null })).join('')
          : emptyState(key==='favorites'?'\u2764\uFE0F':'\uD83D\uDD52', '\u041F\u0443\u0441\u0442\u043E', '\u0417\u0434\u0435\u0441\u044C \u043F\u043E\u044F\u0432\u0438\u0442\u0441\u044F \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D\u043D\u043E\u0435.');
        bindLazy(grid);
        S.catalog.done = true;
      } catch (e) { grid.innerHTML = emptyState('\u26A0\uFE0F','\u041E\u0448\u0438\u0431\u043A\u0430', e.message); }
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
      if (!data.length) { c.done = true; if (!c.offset) $('#catalogGrid').innerHTML = emptyState('\uD83C\uDFAC','\u041F\u0443\u0441\u0442\u043E','\u041A\u043E\u043D\u0442\u0435\u043D\u0442 \u0441\u043A\u043E\u0440\u043E \u043F\u043E\u044F\u0432\u0438\u0442\u0441\u044F.'); }
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
    // Never leave the app on a blank screen: unknown view -> home.
    if (!$(`#view-${name}`)) name = 'home';
    // Stop any playing clip before leaving the current view.
    $$('video').forEach(v => { try { v.pause(); } catch (e) {} });
    $$('.view').forEach(v => v.classList.remove('view--active'));
    $(`#view-${name}`).classList.add('view--active');
    if (!['detail', 'catalog', 'profile'].includes(name)) {
      $$('.nav-item').forEach(n => n.classList.toggle('is-active', n.dataset.nav === name));
    }
    window.scrollTo(0, 0);
  }

  function emptyState(em, title, text) {
    return `<div class="empty"><div class="em">${em}</div><h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;
  }

  // ---- Hash deep links (from bot buttons: #series, #anime, \u2026) ----
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

  async function openProfile() {
    haptic('light');
    switchView('profile');
    const el = $('#profileContent');

    // Telegram already gives us the user \u2014 render immediately, then enrich
    // with server stats. The profile therefore opens even if the API is down.
    const tgUser = tg?.initDataUnsafe?.user || null;
    if (tgUser) {
      renderProfile({
        first_name: tgUser.first_name,
        last_name: tgUser.last_name,
        username: tgUser.username,
        photo_url: tgUser.photo_url,
        is_premium: tgUser.is_premium,
      });
    } else {
      el.innerHTML = `<div class="skeleton" style="height:220px;margin:16px;border-radius:18px"></div>`;
    }

    try {
      const { data } = await api('profile', { method: 'POST' });
      renderProfile(data);
    } catch (e) {
      if (!tgUser) {
        el.innerHTML = emptyState('\uD83D\uDC64', '\u041F\u0440\u043E\u0444\u0438\u043B\u044C \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D', '\u041E\u0442\u043A\u0440\u043E\u0439\u0442\u0435 \u043F\u0440\u0438\u043B\u043E\u0436\u0435\u043D\u0438\u0435 \u0438\u0437 Telegram, \u0447\u0442\u043E\u0431\u044B \u0443\u0432\u0438\u0434\u0435\u0442\u044C \u043F\u0440\u043E\u0444\u0438\u043B\u044C.');
      }
    }
  }

  function renderProfile(data) {
    const el = $('#profileContent');
    {
      const name = [data.first_name, data.last_name].filter(Boolean).map(esc).join(' ') || '\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u044C';
      const avatar = data.photo_url
        ? `<img src="${esc(data.photo_url)}" alt="">`
        : `<span>${(data.first_name || 'U').charAt(0).toUpperCase()}</span>`;
      el.innerHTML = `
        <div class="profile">
          <div class="profile__avatar">${avatar}</div>
          <div class="profile__name">${name}</div>
          ${data.username ? `<div class="profile__username">@${esc(data.username)}</div>` : ''}
          ${data.is_premium ? `<div class="profile__badge">\u2B50 Telegram Premium</div>` : ''}
          <div class="profile__stats">
            <button class="pstat" data-nav-section="favorites">
              <b>${data.favorites_count || 0}</b><span>\u2764\uFE0F \u0418\u0437\u0431\u0440\u0430\u043D\u043D\u043E\u0435</span>
            </button>
            <button class="pstat" data-nav-section="history">
              <b>${data.history_count || 0}</b><span>\uD83D\uDD52 \u0418\u0441\u0442\u043E\u0440\u0438\u044F</span>
            </button>
          </div>
          ${data.is_admin
            ? `<div class="profile__admin">\uD83D\uDEE0 \u0412\u044B \u0430\u0434\u043C\u0438\u043D\u0438\u0441\u0442\u0440\u0430\u0442\u043E\u0440.<br>\u0414\u043E\u0431\u0430\u0432\u043B\u0435\u043D\u0438\u0435 \u0444\u0438\u043B\u044C\u043C\u043E\u0432 \u0438 \u0441\u0435\u0440\u0438\u0439 \u2014 \u0432 \u0431\u043E\u0442\u0435: <b>/admin</b></div>`
            : ''}
        </div>`;
      bindLazy(el);
    }
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

    const epBtn = t.closest('[data-episode]');
    if (epBtn) {
      haptic('medium');
      if (window.APP.bot && epBtn.dataset.deep) { openDeepLink(epBtn.dataset.deep); return; }
      watchEpisode(epBtn.dataset.episode);
      return;
    }

    const scrollBtn = t.closest('[data-scroll]');
    if (scrollBtn) { $('#' + scrollBtn.dataset.scroll)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }

    const pstat = t.closest('[data-nav-section]');
    if (pstat) { switchView('catalog'); openSection(pstat.dataset.navSection); return; }

    const heroPlay = t.closest('[data-hero-play]');
    if (heroPlay) { const id = heroPlay.dataset.heroPlay; if (id) openDetail(id); else toast('\u0421\u043A\u043E\u0440\u043E \u0432 \u043A\u0430\u0442\u0430\u043B\u043E\u0433\u0435'); return; }
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
  $('#btnProfile').addEventListener('click', openProfile);

  // Top bar blur on scroll
  window.addEventListener('scroll', () => {
    $('#topbar').classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });

  window.addEventListener('hashchange', handleHash);

  // ---- Boot ----
  loadProfile();
  loadHome().then(handleHash);
})();
