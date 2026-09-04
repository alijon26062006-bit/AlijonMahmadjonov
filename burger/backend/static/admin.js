/* Мелочи, которые делают админку сносной на телефоне:
   поиск по 94 блюдам и сворачивание разделов. Без скрипта страница тоже
   работает — просто списком, как раньше. */

const find = document.querySelector('#find');
const sections = [...document.querySelectorAll('[data-section]')];

/* Разделы сворачиваются, и выбор запоминается: у каждого свои привычные. */
const SHUT = 'admin_menu_shut';
let shut = new Set();
try { shut = new Set(JSON.parse(localStorage.getItem(SHUT) || '[]')); } catch (e) {}

sections.forEach((sec, i) => {
  const head = sec.querySelector('.sec__head');
  if (shut.has(String(i))) sec.classList.add('is-shut');
  head.setAttribute('aria-expanded', String(!sec.classList.contains('is-shut')));

  head.addEventListener('click', () => {
    const nowShut = sec.classList.toggle('is-shut');
    head.setAttribute('aria-expanded', String(!nowShut));
    nowShut ? shut.add(String(i)) : shut.delete(String(i));
    try { localStorage.setItem(SHUT, JSON.stringify([...shut])); } catch (e) {}
  });
});

/* Поиск: показываем подходящие блюда и прячем разделы, где не осталось ничего. */
if (find) {
  const rows = [...document.querySelectorAll('.list li[data-name]')];

  find.addEventListener('input', () => {
    const q = find.value.trim().toLowerCase();
    let found = 0;

    rows.forEach(li => {
      const ok = !q || li.dataset.name.includes(q);
      li.hidden = !ok;
      if (ok) found += 1;
    });

    sections.forEach(sec => {
      const has = [...sec.querySelectorAll('li[data-name]')].some(li => !li.hidden);
      sec.hidden = q ? !has : false;
      if (q) sec.classList.remove('is-shut');     // при поиске всё раскрыто
    });

    document.querySelector('#nothing').hidden = !q || found > 0;
  });
}
