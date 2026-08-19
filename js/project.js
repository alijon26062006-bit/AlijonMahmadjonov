/* ===========================================================
   Страница одного проекта: project.html?slug=имя-проекта
   Данные и помощники приходят из render.js.
   =========================================================== */

document.addEventListener('site:data', () => {
  const p = DATA.profile;
  const view = document.getElementById('projectView');
  const slug = new URLSearchParams(location.search).get('slug');
  const project = (DATA.projects.items || []).find(x => x.slug === slug);

  document.getElementById('backLabel').textContent = t(p.sections.backHome, lang);
  clear(view);

  if (!project) {
    document.title = t(p.sections.notFound, lang) + ' — ' + p.meta.name;
    view.appendChild(el('div', { class: 'empty' }, [
      icon('alert'),
      el('p', { text: t(p.sections.notFound, lang) })
    ]));
    return;
  }

  const title = t(project.title, lang);
  document.title = title + ' — ' + p.meta.name;

  const head = el('header', { class: 'project-head' });
  if (project.status) {
    head.appendChild(el('span', {
      class: 'status', text: t(p.sections.status[project.status], lang),
      attrs: { 'data-status': project.status }
    }));
  }
  head.appendChild(el('h1', { class: 'project-title', text: title }));
  if (project.summary) head.appendChild(el('p', { class: 'lead', text: t(project.summary, lang) }));

  if ((project.tags || []).length) {
    const tags = el('div', { class: 'project-tags' });
    for (const tag of project.tags) tags.appendChild(el('span', { class: 'tag', text: tag }));
    head.appendChild(tags);
  }
  view.appendChild(head);

  if (project.cover) {
    view.appendChild(el('div', { class: 'project-hero' }, [
      el('img', { attrs: { src: project.cover, alt: title, decoding: 'async' } })
    ]));
  }

  const body = el('div', { class: 'project-text' });
  for (const par of String(t(project.body, lang) || '').split(/\n{2,}/)) {
    if (par.trim()) body.appendChild(el('p', { text: par.trim() }));
  }
  if (body.childNodes.length) view.appendChild(body);

  const links = el('div', { class: 'project-links' });
  if (project.repo) {
    links.appendChild(el('a', {
      class: 'btn btn-line', attrs: { href: project.repo, target: '_blank', rel: 'noopener' }
    }, [icon('github'), el('span', { text: 'GitHub' })]));
  }
  if (project.demo) {
    links.appendChild(el('a', {
      class: 'btn btn-solid', attrs: { href: project.demo, target: '_blank', rel: 'noopener' }
    }, [icon('external'), el('span', { text: 'Demo' })]));
  }
  if (links.childNodes.length) view.appendChild(links);
});
