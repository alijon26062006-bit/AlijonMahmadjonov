(function(){
  // ---------- service illustrations (own drawings, no third-party logos) ----------
  var V='#7e5bff',VD='#5b3fd9',VL='#b9a9ff',VT='#efebff',TL='#2dd4bf',TD='#14a89a',INK='#1a1d24',G='#6b7280',W='#fff';
  var IMG={cards:'svc-1',wallet:'svc-2',gift:'svc-3',key:'svc-4',subs:'svc-5',phone:'svc-6'};
  var TXT={
    cards:['РЕШЕНИЕ ДЛЯ РЕСЕЛЛЕРОВ','Оптовые','подарочные карты','Сотни брендов и регионов по оптовым ценам.'],
    wallet:['РЕШЕНИЕ ДЛЯ РЕСЕЛЛЕРОВ','Пополнение','кошелька Steam','По логину, для СНГ и других регионов.'],
    gift:['РЕШЕНИЕ ДЛЯ РЕСЕЛЛЕРОВ','Оптовые','Steam гифты','Подарки игр оптом, выдача автоматическая.'],
    key:['РЕШЕНИЕ ДЛЯ РЕСЕЛЛЕРОВ','Оптовые','ключи игр','Ключи для ПК и консолей популярных платформ.'],
    subs:['РЕШЕНИЕ ДЛЯ РЕСЕЛЛЕРОВ','Оптовые','подписки','Премиум-доступ. Создано для бизнеса.'],
    phone:['РЕШЕНИЕ ДЛЯ B2B РЕСЕЛЛЕРОВ','Мобильные игры','Оптовые пополнения','Автоматизация API · Мгновенная доставка']
  };
  var BUL=[['Оптовые цены','Низкие цены и высокая маржа'],['Мгновенная доставка','Автоматическая выдача за секунды'],['API и автоматизация','Интеграция и массовые заказы'],['Надёжно и безопасно','Защита транзакций и данных']];
  var STEPS=['Выберите товар','Оплатите заказ','Получите мгновенно','Масштабируйте'];
  var FOOT=['Конкурентные цены','Глобальное покрытие','Поддержка 24/7'];
  function esc(s){return s.replace(/&/g,'&amp;')}
  function art(k){
    var t=TXT[k],s='<svg viewBox="0 0 540 360" xmlns="http://www.w3.org/2000/svg" font-family="Inter,system-ui,sans-serif"><rect width="540" height="360" rx="10" fill="#fff"/><image href="/static/redesign/img/'+IMG[k]+'.webp" x="270" y="36" width="262" height="262"/>';
    s+='<rect x="18" y="14" width="'+(t[0].length*5.6+22)+'" height="18" rx="5" fill="'+VT+'"/><text x="29" y="26.5" font-size="8" font-weight="700" fill="'+V+'">'+esc(t[0])+'</text>';
    s+='<text x="18" y="62" font-size="24" font-weight="700" fill="'+INK+'" letter-spacing="-.5">'+esc(t[1])+'</text><text x="18" y="90" font-size="24" font-weight="700" fill="'+V+'" letter-spacing="-.5">'+esc(t[2])+'</text>';
    s+='<text x="18" y="108" font-size="8.5" fill="'+G+'">'+esc(t[3])+'</text>';
    BUL.forEach(function(b,i){var y=124+i*36;
      s+='<rect x="18" y="'+y+'" width="22" height="22" rx="6" fill="'+V+'"/><circle cx="29" cy="'+(y+11)+'" r="4" fill="none" stroke="#fff" stroke-width="2"/>';
      s+='<text x="48" y="'+(y+9)+'" font-size="9.5" font-weight="700" fill="'+INK+'">'+b[0]+'</text><text x="48" y="'+(y+20)+'" font-size="7.5" fill="'+G+'">'+b[1]+'</text>';});
    s+='<rect x="14" y="270" width="242" height="44" rx="8" fill="none" stroke="#eceaf5"/>';
    STEPS.forEach(function(st,i){var x=44+i*60;
      s+='<rect x="'+(x-8)+'" y="277" width="16" height="14" rx="4" fill="'+V+'" opacity="'+(1-i*.12)+'"/><text x="'+x+'" y="305" font-size="5.2" text-anchor="middle" fill="'+INK+'" font-weight="600">'+st+'</text>';
      if(i<3)s+='<path d="M'+(x+20)+' 284h10m-3-3 3 3-3 3" fill="none" stroke="'+VL+'" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>';});
    FOOT.forEach(function(f,i){var x=24+i*176;
      s+='<circle cx="'+(x+6)+'" cy="336" r="7" fill="'+VT+'"/><circle cx="'+(x+6)+'" cy="336" r="3" fill="'+V+'"/><text x="'+(x+18)+'" y="339" font-size="8" font-weight="700" fill="'+INK+'">'+f+'</text>';});
    s+='</svg>';
    return s;
  }
  document.querySelectorAll('[data-art]').forEach(function(el){el.innerHTML=art(el.getAttribute('data-art'))});

  // ---------- burger ----------
  var burger=document.getElementById('burger'),menu=document.getElementById('menu');
  function setMenu(open){menu.hidden=!open;burger.setAttribute('aria-expanded',String(open));burger.setAttribute('aria-label',open?'Закрыть меню':'Открыть меню');burger.querySelector('use').setAttribute('href',open?'#i-close':'#i-menu')}
  burger.addEventListener('click',function(){setMenu(menu.hidden)});
  menu.addEventListener('click',function(e){if(e.target.closest('a'))setMenu(false)});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')setMenu(false)});

  // ---------- placeholder links ----------
  var toast=document.getElementById('toast'),tt;
  document.addEventListener('click',function(e){
    var a=e.target.closest('[data-soon]'); if(!a) return;
    e.preventDefault();
    toast.textContent=a.getAttribute('data-soon')||'Эта страница появится на следующем шаге';
    toast.hidden=false; clearTimeout(tt); tt=setTimeout(function(){toast.hidden=true},2600);
  });

  // ---------- to top ----------
  var tb=document.getElementById('toTop');
  function onScroll(){tb.classList.toggle('off',window.scrollY<300)}
  window.addEventListener('scroll',onScroll,{passive:true}); onScroll();
  tb.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'})});

  var still=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- hero window: rows appear one by one, window grows for buttons, loop ----------
  (function(){
    var rows=[].slice.call(document.querySelectorAll('#mockRows .mrow')),fold=document.getElementById('mockFold');
    function showAll(){rows.forEach(function(r){r.classList.add('on','done')});fold.classList.add('on')}
    if(still){showAll();return}
    var STEP=900,HOLD=9000,timers=[],running=false,visible=true;
    function at(ms,fn){timers.push(setTimeout(fn,ms))}
    function stop(){timers.forEach(clearTimeout);timers=[];running=false}
    function play(){
      stop();running=true;
      rows.forEach(function(r){r.classList.remove('on','done')});fold.classList.remove('on');
      rows.forEach(function(r,i){
        at(400+i*STEP,function(){r.classList.add('on')});
        if(i>0) at(400+i*STEP+500,function(){r.classList.add('done')});
      });
      var full=400+rows.length*STEP+300;
      at(full,function(){fold.classList.add('on')});
      at(full+HOLD,fadeOut);
    }
    function fadeOut(){            // everything fades together, then a calm pause before replay
      fold.classList.remove('on');
      rows.forEach(function(r){r.classList.remove('on','done')});
      at(1400,function(){if(visible&&!document.hidden)play();else{running=false;showAll()}});
    }
    function resume(){if(!running&&visible&&!document.hidden){stop();running=true;at(HOLD/2,fadeOut)}}
    play();
    // pause when the window is off-screen or the tab is hidden (keeps the full state on screen)
    if('IntersectionObserver' in window){
      new IntersectionObserver(function(es){visible=es[0].isIntersecting;if(!visible){stop();showAll()}else resume()},{threshold:.25}).observe(fold.closest('.mock'));
    }
    document.addEventListener('visibilitychange',function(){if(document.hidden){stop();showAll()}else resume()});
  })();

  // ---------- count-up (final values are already in the markup) ----------
  if(!still&&'IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(en){
      if(!en.isIntersecting) return; io.unobserve(en.target);
      var el=en.target,to=+el.dataset.to,dec=+(el.dataset.dec||0),suf=el.dataset.suf||'',t0=null;
      function step(t){if(!t0)t0=t;var k=Math.min(1,(t-t0)/1600);k=1-Math.pow(1-k,3);el.textContent=(to*k).toFixed(dec)+suf;if(k<1)requestAnimationFrame(step)}
      requestAnimationFrame(step);
    })},{threshold:.6});
    document.querySelectorAll('.stat b[data-to]').forEach(function(el){io.observe(el)});
  }
  // ---------- FAQ accordion ----------
  document.querySelectorAll('.faq-q').forEach(function(b){
    b.addEventListener('click',function(){
      var open=b.getAttribute('aria-expanded')==='true';
      b.setAttribute('aria-expanded',String(!open));
      document.getElementById(b.getAttribute('aria-controls')).hidden=open;
    });
  });

})();
