// Py·Достон — генераторы графики: иконки, значки, маскот Пайко, радар навыков, каталог достижений
const ICONS = {
  flame:'<path d="M12 2.5c.6 3.6 4.8 5.4 4.8 10.3A4.8 4.8 0 0 1 7.2 13c0-2.4 1.4-3.6 2.2-5.3.8 1.2 1.3 2.4 1.2 3.6 1.3-1.8 1.8-4.6 1.4-8.8z"/>',
  mountain:'<path d="M2 20 9 7.5l4 6.5 2.5-3.5L22 20z"/><path d="M7.4 10.3 9 11.5l1.4-1.6"/>',
  bug:'<rect x="8" y="7" width="8" height="12" rx="4"/><path d="M12 10v9M8 11H4.5M19.5 11H16M8 15.5H4.5M19.5 15.5H16M9.5 7.5 8 4.5M14.5 7.5 16 4.5"/>',
  lamp:'<path d="M3 14.5c2.5 0 4-2.5 9-2.5 4.2 0 5.5 1.5 7.5 1.5l2-2.5M3 14.5c1.5 2.5 4.5 3.5 9 3.5s6.5-1.5 7.5-4.5M12 12V9.5M10 9.5h4M9 21h6"/>',
  heart:'<path d="M12 20s-7.5-4.6-7.5-10.2A4.2 4.2 0 0 1 12 7.4a4.2 4.2 0 0 1 7.5 2.4C19.5 15.4 12 20 12 20z"/>',
  gear:'<circle cx="12" cy="12" r="3.5"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
  search:'<circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5.5 5.5"/>',
  branch:'<circle cx="6" cy="5" r="2.2"/><circle cx="6" cy="19" r="2.2"/><circle cx="18" cy="7" r="2.2"/><path d="M6 7.2v9.6M18 9.2c0 5-8 3.5-11 7.6"/>',
  city:'<path d="M3 21V11l5-2.5V21M8 21V5l7-2.5V21M15 21V9l6 2v10M2 21h20M11 8h1M11 12h1M11 16h1"/>',
  robot:'<rect x="5" y="8" width="14" height="11" rx="3"/><path d="M12 8V5M9.5 12.5v.5M14.5 12.5v.5M9 16h6"/><circle cx="12" cy="4" r="1"/>',
  star:'<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
  crown:'<path d="M3 18.5h18M4 16 3 7l5 4 4-6 4 6 5-4-1 9z"/>',
  shield:'<path d="M12 3 4.5 6v6c0 4.5 3.2 7.6 7.5 9 4.3-1.4 7.5-4.5 7.5-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  rocket:'<path d="M12 3c3.5 2.5 5 6 4.5 10l-2 2.5h-5l-2-2.5C7 9 8.5 5.5 12 3z"/><circle cx="12" cy="9.5" r="1.8"/><path d="M9.5 15.5 7 19M14.5 15.5 17 19M12 16v5"/>',
  scroll:'<path d="M8 3.5h10.5a2 2 0 0 1 2 2V7H16M8 3.5a2 2 0 0 0-2 2V18a2.5 2.5 0 0 0 2.5 2.5h8A2.5 2.5 0 0 0 19 18V7M8 3.5A2 2 0 0 1 10 5.5V18a2.5 2.5 0 0 1-1.5 2.5M12.5 10h3.5M12.5 14h3.5"/>',
  chat:'<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9.5h8M8 12.5h5"/>',
  clock:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/>',
  key:'<circle cx="8" cy="12" r="4"/><path d="M12 12h9M18 12v3M21 12v2"/>',
  sun:'<circle cx="12" cy="14.5" r="4"/><path d="M12 4.5v3M4.5 8l2 2M19.5 8l-2 2M2 19h20"/>',
  infinity:'<path d="M8 8.5c-2 0-3.5 1.6-3.5 3.5S6 15.5 8 15.5c3.5 0 4.5-7 8-7 2 0 3.5 1.6 3.5 3.5s-1.5 3.5-3.5 3.5c-3.5 0-4.5-7-8-7z"/>',
  team:'<circle cx="8" cy="8" r="3"/><circle cx="16.5" cy="9" r="2.5"/><path d="M2.5 19.5c.5-3.5 2.8-5.5 5.5-5.5s5 2 5.5 5.5M14.5 14c2.8-.4 5.7 1.2 6.7 5"/>',
  swords:'<path d="M4 4l9.5 9.5M4 4h4.5M4 4v4.5M20 4l-9.5 9.5M20 4h-4.5M20 4v4.5M6.5 13.5l4 4M17.5 13.5l-4 4M8.5 15.5 5 19M15.5 15.5 19 19"/>',
  egg:'<path d="M12 3c3.6 0 6.5 5.4 6.5 10a6.5 6.5 0 0 1-13 0C5.5 8.4 8.4 3 12 3z"/><path d="M7.5 12l2.2 1.6 2.3-2.1 2.3 2.1 2.2-1.6"/>',
  book:'<path d="M4 5.5C6.5 4 9.5 4 12 6c2.5-2 5.5-2 8-.5V19c-2.5-1.5-5.5-1.5-8 .5-2.5-2-5.5-2-8-.5zM12 6v13.5"/>',
  flask:'<path d="M9.5 3h5M10.5 3v6L5 18.5A1.6 1.6 0 0 0 6.4 21h11.2a1.6 1.6 0 0 0 1.4-2.5L13.5 9V3M7.5 15h9"/>',
  db:'<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
  gift:'<rect x="4" y="9" width="16" height="11" rx="1.5"/><path d="M3 9h18M12 9v11M12 9c-1-3-5-4.5-5.5-2.5S10 9 12 9zm0 0c1-3 5-4.5 5.5-2.5S14 9 12 9z"/>',
  target:'<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8"/>',
  bell:'<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5h4"/>',
  mail:'<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="m4 7 8 6 8-6"/>',
  cal:'<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8.5 3v4M15.5 3v4M8 14h2M14 14h2M8 17h2"/>',
  coin:'<circle cx="12" cy="12" r="8.5"/><path d="M12 6.5v11M14.5 9.3c0-1-1-1.8-2.5-1.8s-2.5.7-2.5 1.8 1 1.6 2.5 1.8 2.5.8 2.5 1.8-1 1.8-2.5 1.8-2.5-.7-2.5-1.8"/>',
  gem:'<path d="M6 4h12l3 5-9 11L3 9z"/><path d="M3 9h18M9 4 7.5 9 12 20 16.5 9 15 4"/>',
  snake:'<path d="M17 5.5c-1.3-1.5-4-1.8-5.6-.3-2.5 2.3.3 5.4 2.7 6.6 2.8 1.4 3.2 4.6 1 6.4-2 1.6-5.4 1.2-7.6-1"/><circle cx="16" cy="5.6" r=".7"/>',
  moon:'<path d="M19 14.5A7.5 7.5 0 1 1 9.5 5a6 6 0 0 0 9.5 9.5z"/>',
  terminal:'<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="m7 9.5 3 2.5-3 2.5M12.5 15H17"/>',
  check:'<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  bolt:'<path d="M13 2.5 5 13.5h6l-1 8 8-11h-6z"/>',
  map:'<path d="M3.5 6.5 9 4l6 2.5L20.5 4v13.5L15 20l-6-2.5-5.5 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
  trophy:'<path d="M7.5 4h9v5a4.5 4.5 0 0 1-9 0zM7.5 6H4.5c0 2.5 1.2 4 3.3 4.3M16.5 6h3c0 2.5-1.2 4-3.3 4.3M12 13.5V17M8.5 20.5h7"/>',
  echo:'<path d="M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M18 3v4h-4M6 21v-4h4"/>',
  chart:'<path d="M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-6"/>',
  radar:'<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 7.5l4 3-1.5 5h-5L8 10.5z"/>',
  lock:'<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
  ship:'<path d="M12 3c2.5 2 3.5 5 3.5 8.5L12 20l-3.5-8.5C8.5 8 9.5 5 12 3z"/><path d="M8.5 13 5 16v3l4-2M15.5 13l3.5 3v3l-4-2"/>',
  camel:'<path d="M3 20v-6c0-2 1.5-3 3-3 1 0 1.5-2 3-2s2 2 3 2 1.5-3 3-3 2 2 2.5 3.5c.5 1.5 2.5 1.5 2.5 3.5V20M7 20v-4M16 20v-4M18 11.5l1.5-3 2 .5"/>',
  plane:'<path d="M2.5 12.5 21 4l-5 16-4.5-6.5z"/><path d="M11.5 13.5 21 4"/>',
  code:'<path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
  pen:'<path d="M4 20l1-4.5L16 4.5a2.1 2.1 0 0 1 3 3L8 18.5zM14 7l3 3"/>',
  sprout:'<path d="M12 21v-9M12 12c0-4-3-6-7.5-6 0 4.5 3 6 7.5 6zm0 0c0-3 2.5-5.5 7.5-5.5 0 4-3 5.5-7.5 5.5z"/>',
  play:'<circle cx="12" cy="12" r="8.5"/><path d="m10 8.5 5.5 3.5-5.5 3.5z"/>',
  home:'<path d="M3.5 11 12 4l8.5 7M6 9.5V20h12V9.5"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 20.5c1-4 4-6 8-6s7 2 8 6"/>',
  shop:'<path d="M4 9h16l-1.5 11h-13zM8.5 9V7a3.5 3.5 0 0 1 7 0v2"/>',
};
function icon(name, color='currentColor', size=22, sw=1.8){
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]||''}</svg>`;
}

const RAR = {
  common:{a:'#4F7461',b:'#17251D',rim:'#B9CFC2',lt:'#E3F1E8',name:'Обычное',tj:'Оддӣ'},
  rare:{a:'#2462A3',b:'#0C1E33',rim:'#5BB0FF',lt:'#D8ECFF',name:'Редкое',tj:'Нодир'},
  epic:{a:'#6A35B8',b:'#1C0E33',rim:'#C08CFF',lt:'#F0E2FF',name:'Эпическое',tj:'Ҳамосавӣ'},
  leg:{a:'#B57A12',b:'#2C1C04',rim:'#FFCB5C',lt:'#FFF2CF',name:'Легендарное',tj:'Афсонавӣ'},
};
let _bid = 0;
function badge(spec, size=72){
  const r = RAR[spec.r]||RAR.common, id='bg'+(++_bid);
  let shape='', extra='';
  if(spec.r==='common'){
    shape=`<circle cx="50" cy="50" r="38" fill="url(#${id})" stroke="${r.rim}" stroke-width="3.5"/>`;
  } else if(spec.r==='rare'){
    shape=`<path d="M50 9 85.5 29.5v41L50 91 14.5 70.5v-41z" fill="url(#${id})" stroke="${r.rim}" stroke-width="3.5" stroke-linejoin="round"/>`;
  } else if(spec.r==='epic'){
    extra=`<path d="M14 40 3 30l4 24 12 6zM86 40l11-10-4 24-12 6z" fill="${r.rim}" opacity=".55"/>`;
    shape=`<path d="M50 7 83 19v30c0 21-14 35-33 44C31 84 17 70 17 49V19z" fill="url(#${id})" stroke="${r.rim}" stroke-width="3.5" stroke-linejoin="round"/>`;
  } else {
    let rays=''; for(let i=0;i<16;i++){const a=i*Math.PI/8, a2=a+Math.PI/16, a3=a-Math.PI/16;
      rays+=`M${50+47*Math.cos(a)} ${50+47*Math.sin(a)}L${50+36*Math.cos(a2)} ${50+36*Math.sin(a2)}L${50+36*Math.cos(a3)} ${50+36*Math.sin(a3)}Z`;}
    extra=`<circle cx="50" cy="50" r="49" fill="${r.rim}" opacity=".12"/><path d="${rays}" fill="${r.rim}" opacity=".9"/>`;
    shape=`<circle cx="50" cy="50" r="36" fill="url(#${id})" stroke="${r.rim}" stroke-width="3.5"/><path d="M41 12l4.5 5 4.5-7 4.5 7 4.5-5-1.5 9H42.5z" fill="${r.rim}" stroke="#2C1C04" stroke-width="1"/>`;
  }
  let glyph;
  if(spec.i){ const sc=spec.r==='epic'?1.55:1.6, off=50-12*sc, oy=spec.r==='epic'?off-2:off;
    glyph=`<g transform="translate(${off} ${oy}) scale(${sc})" fill="none" stroke="${r.lt}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICONS[spec.i]}</g>`;
  } else { const t=spec.g||'?', fs=t.length<=2?30:t.length<=3?24:t.length<=4?19:t.length<=5?16:13;
    glyph=`<text x="50" y="${spec.r==='epic'?48:51}" text-anchor="middle" dominant-baseline="central" font-family="JetBrains Mono" font-weight="800" font-size="${fs}" fill="${r.lt}">${t}</text>`;
  }
  const inner = spec.r==='common'?`<circle cx="50" cy="50" r="30" fill="none" stroke="${r.rim}" stroke-opacity=".35" stroke-dasharray="2 4"/>`:'';
  const secret = spec.s?`<g transform="translate(70 70)"><circle r="11" fill="#0B110E" stroke="${r.rim}" stroke-width="2"/><text y="1" text-anchor="middle" dominant-baseline="central" font-family="Inter" font-weight="800" font-size="13" fill="${r.rim}">?</text></g>`:'';
  return `<svg viewBox="0 0 100 100" width="${size}" height="${size}"><defs><radialGradient id="${id}" cx="35%" cy="25%" r="85%"><stop offset="0" stop-color="${r.a}"/><stop offset="1" stop-color="${r.b}"/></radialGradient></defs>${extra}${shape}${inner}${glyph}${secret}</svg>`;
}

// Маскот Пайко — питон-дракончик. stage: 0 яйцо, 1 малыш, 2 золотой, 3 с крыльями, 4 Дракон кода
function payko(stage=1, size=120, mood='happy'){
  const id='pk'+(++_bid);
  if(stage===0){
    return `<svg viewBox="0 0 120 120" width="${size}" height="${size}"><defs><radialGradient id="${id}" cx="40%" cy="30%" r="80%"><stop offset="0" stop-color="#E9FFF1"/><stop offset=".55" stop-color="#9FE8B9"/><stop offset="1" stop-color="#2E8B57"/></radialGradient></defs>
    <ellipse cx="60" cy="108" rx="30" ry="6" fill="#000" opacity=".35"/>
    <path d="M60 12c20 0 34 30 34 55a34 34 0 0 1-68 0c0-25 14-55 34-55z" fill="url(#${id})" stroke="#1E6B42" stroke-width="2"/>
    <circle cx="48" cy="44" r="6" fill="#FFC24A" opacity=".85"/><circle cx="74" cy="62" r="8" fill="#FFC24A" opacity=".8"/><circle cx="52" cy="82" r="5" fill="#FFC24A" opacity=".8"/><circle cx="76" cy="36" r="3.5" fill="#FFC24A" opacity=".8"/>
    <path d="M36 60l8 5 6-7 7 8 6-6 7 7 6-5 8 4" fill="none" stroke="#0F3B24" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M46 26c3-4 7-6 10-6" stroke="#fff" stroke-width="3" stroke-linecap="round" fill="none" opacity=".8"/></svg>`;
  }
  const gold = stage===2||stage===4;
  const c1 = stage===4?'#FFD36B':gold?'#FFCF5A':'#3EE07E', c2 = stage===4?'#D08A12':gold?'#D59614':'#169A4B';
  const belly = gold?'#FFF1C2':'#C9FFD9';
  const wings = stage>=3?`<path d="M44 58C26 34 8 40 6 52c10-4 16 2 18 8-8-2-14 4-12 10 8-6 18-4 24 2z" fill="${stage===4?'#7C4DFF':'#2BD96B'}" opacity=".55" stroke="${stage===4?'#B79BFF':'#9CF7C1'}" stroke-width="1.5"/><path d="M82 52c16-22 30-16 32-6-8-2-13 3-14 8 6-1 11 4 9 9-7-5-15-3-20 2z" fill="${stage===4?'#7C4DFF':'#2BD96B'}" opacity=".5" stroke="${stage===4?'#B79BFF':'#9CF7C1'}" stroke-width="1.5"/>`:'';
  const horns = stage>=2?`<path d="M62 24l-3-11 9 8zM84 24l5-10 1 12z" fill="${stage===4?'#FFF1C2':'#FFE08A'}" stroke="${c2}" stroke-width="1.5" stroke-linejoin="round"/>`:'';
  const crown = stage===4?`<path d="M63 18l4-12 6 8 5-11 4 11 6-7 1 12z" fill="#FFC24A" stroke="#7A4E05" stroke-width="1.5" stroke-linejoin="round"/><circle cx="73" cy="12" r="2" fill="#B57BFF"/>`:'';
  const eyes = mood==='sleep'
    ? `<path d="M65 41q4 3 8 0M80 41q4 3 8 0" stroke="#0A2416" stroke-width="2.5" fill="none" stroke-linecap="round"/>`
    : `<ellipse cx="68" cy="40" rx="6" ry="7" fill="#fff"/><ellipse cx="84" cy="40" rx="6" ry="7" fill="#fff"/><circle cx="69.5" cy="41.5" r="3.6" fill="#0A1A12"/><circle cx="85.5" cy="41.5" r="3.6" fill="#0A1A12"/><circle cx="70.7" cy="39.8" r="1.3" fill="#fff"/><circle cx="86.7" cy="39.8" r="1.3" fill="#fff"/>`;
  return `<svg viewBox="0 0 120 120" width="${size}" height="${size}"><defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>
  <ellipse cx="58" cy="110" rx="38" ry="6" fill="#000" opacity=".35"/>
  ${wings}
  <path d="M24 104c-14-4-12-22 6-22h30c14 0 20-8 18-20" fill="none" stroke="url(#${id})" stroke-width="20" stroke-linecap="round"/>
  <path d="M26 100c-6-2-5-10 4-10h30c10 0 16-6 16-14" fill="none" stroke="${belly}" stroke-width="5" stroke-linecap="round" opacity=".8" stroke-dasharray="6 4"/>
  <path d="M10 98c-6 0-8 6-4 8" stroke="url(#${id})" stroke-width="8" stroke-linecap="round" fill="none"/>
  ${horns}
  <ellipse cx="76" cy="44" rx="25" ry="21" fill="url(#${id})"/>
  ${crown}
  <ellipse cx="78" cy="55" rx="15" ry="8" fill="${belly}" opacity=".55"/>
  ${eyes}
  <circle cx="62" cy="51" r="3.5" fill="#FF8FB1" opacity=".7"/><circle cx="92" cy="51" r="3.5" fill="#FF8FB1" opacity=".7"/>
  <path d="M72 53q5 4 10 0" stroke="#0A2416" stroke-width="2.3" fill="none" stroke-linecap="round"/>
  ${stage===1?'<path d="M77 57v5l-2 3M77 62l2 3" stroke="#FF6B8B" stroke-width="1.6" fill="none" stroke-linecap="round"/>':''}
  </svg>`;
}

// Существа Бестиария ошибок
function creature(color='#FF6B6B', v=0, size=64, tamed=true){
  const body=`<path d="M18 74C12 42 28 16 50 16s38 26 32 58q-7-6-13 0-6 6-12 0-7-6-14 0-6 6-12 0-7-6-13 0z" fill="${color}" ${tamed?'':'opacity=".35"'}/>`;
  const shade=`<path d="M30 30c6-8 14-10 20-10" stroke="#fff" stroke-opacity=".45" stroke-width="4" fill="none" stroke-linecap="round"/>`;
  let feat='', eyes;
  if(v===1) feat=`<path d="M30 24l-6-14 14 8zM70 24l6-14-14 8z" fill="${color}"/>`;
  if(v===2) feat=`<path d="M50 16V4" stroke="${color}" stroke-width="3"/><circle cx="50" cy="4" r="4" fill="#FFE08A"/>`;
  if(v===4) feat=`<path d="M78 40l14-6-6 12zM22 40 8 34l6 12z" fill="${color}"/>`;
  if(v===3) eyes=`<circle cx="50" cy="42" r="12" fill="#fff"/><circle cx="52" cy="44" r="6" fill="#0A1A12"/><circle cx="54" cy="41" r="2" fill="#fff"/>`;
  else eyes=`<circle cx="40" cy="42" r="8" fill="#fff"/><circle cx="62" cy="42" r="${v===5?5:8}" fill="#fff"/><circle cx="42" cy="44" r="4" fill="#0A1A12"/><circle cx="63" cy="44" r="${v===5?2.5:4}" fill="#0A1A12"/>`;
  const mouth = v===4?`<path d="M38 58l4-4 4 4 4-4 4 4 4-4 4 4" stroke="#0A1A12" stroke-width="2.5" fill="none" stroke-linejoin="round"/>`:`<path d="M42 57q8 6 16 0" stroke="#0A1A12" stroke-width="2.5" fill="none" stroke-linecap="round"/>`;
  return `<svg viewBox="0 0 100 90" width="${size}" height="${size*0.9}"><ellipse cx="50" cy="84" rx="28" ry="4" fill="#000" opacity=".35"/>${feat}${body}${shade}${eyes}${mouth}</svg>`;
}

// Радар «Сила программиста»
const AX = ['Синтаксис','Логика','Отладка','Данные','Архитектура','Инструменты'];
function radar(vals, prev, size=240, labels=true){
  const cx=size/2, cy=size/2, R=labels?size*0.27:size*0.42, n=6;
  const pt=(i,v)=>{const a=-Math.PI/2+i*2*Math.PI/n; return [cx+R*v*Math.cos(a), cy+R*v*Math.sin(a)];};
  let g='';
  [0.25,0.5,0.75,1].forEach(k=>{g+=`<polygon points="${[...Array(n)].map((_,i)=>pt(i,k).join(',')).join(' ')}" fill="none" stroke="#2C4337" stroke-width="1"/>`;});
  for(let i=0;i<n;i++){const [x,y]=pt(i,1); g+=`<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#21322A"/>`;}
  if(prev) g+=`<polygon points="${prev.map((v,i)=>pt(i,v).join(',')).join(' ')}" fill="rgba(151,170,160,.12)" stroke="#61756A" stroke-dasharray="3 3"/>`;
  g+=`<polygon points="${vals.map((v,i)=>pt(i,v).join(',')).join(' ')}" fill="rgba(46,224,112,.22)" stroke="#2EE070" stroke-width="2"/>`;
  vals.forEach((v,i)=>{const [x,y]=pt(i,v); g+=`<circle cx="${x}" cy="${y}" r="3.2" fill="#9CF7C1"/>`;});
  if(labels) AX.forEach((l,i)=>{const [x,y]=pt(i,1.2); const anc=Math.abs(x-cx)<5?'middle':(x>cx?'start':'end'); g+=`<text x="${x}" y="${y}" text-anchor="${anc}" dominant-baseline="central" font-family="Inter" font-size="${size<200?9:11}" font-weight="600" fill="#97AAA0">${l}</text>`;});
  const pad=labels?Math.round(size*0.2):0;
  return `<svg viewBox="${-pad} 0 ${size+2*pad} ${size}" width="${size+2*pad}" height="${size}">${g}</svg>`;
}

// Каталог достижений
const ACH = [
 // Старт и привычка
 {tj:'Салом, Ҷаҳон!',ru:'Привет, мир!',g:'>_',r:'common',c:'Запустить первую программу в онлайн-редакторе',v:'Пайко вылупляется, начало истории',a:'Яйцо трескается, из него выползает Пайко и «печатает» вывод'},
 {tj:'Хонандаи Traceback',ru:'Читатель Traceback',i:'search',r:'common',c:'5 раз исправить ошибку, ни разу не открыв подсказку',v:'Навык, который экономит часы',a:'Строка Traceback подсвечивается и превращается в значок'},
 {tj:'Шикорчии Хато',ru:'Охотник на ошибки',i:'bug',r:'rare',c:'Приручить 10 разных существ Бестиария (исправить 10 типов ошибок)',v:'Ошибки больше не пугают',a:'10 существ выбегают и выстраиваются в шеренгу'},
 {tj:'Ҳикмати Python',ru:'Мудрость Питона',g:'zen',r:'common',s:1,c:'Секрет: выполнить import this в песочнице',v:'Пасхалка для любопытных',a:'Строки «Дзена Python» падают, как зелёный дождь'},
 {tj:'Ҳалқаи Абадӣ',ru:'Вечный цикл',i:'infinity',r:'common',s:1,c:'Секрет: создать бесконечный цикл и самому остановить его',v:'Превращает панику в улыбку',a:'Значок крутится, пока ученик не нажмёт «Стоп»'},
 {tj:'Гулхани Ҳафта',ru:'Костёр недели',i:'flame',r:'common',c:'4 недели подряд выполнить свою недельную цель (уровни I–V)',v:'Привычка закреплена',a:'Костёр разгорается, искры — число недель'},
 {tj:'Бозгашти Қаҳрамон',ru:'Возвращение героя',i:'sun',r:'common',c:'Вернуться после перерыва 14+ дней и пройти урок',v:'Нет чувства вины — только радость возвращения',a:'Рассвет над картой, Пайко машет хвостом'},
 {tj:'Субҳхез',ru:'Ранняя пташка',i:'moon',r:'rare',s:1,c:'Секрет: решить 5 задач до 8:00 утра',v:'Награда за дисциплину',a:'Солнце поднимается над Памиром'},
 {tj:'Оташи Ҷовидон',ru:'Вечный огонь',i:'flame',r:'leg',c:'26 недель подряд выполнять недельную цель',v:'Полгода учебной привычки',a:'Золотое пламя на весь экран и живая рамка профиля'},
 // Блок 1–2
 {tj:'Устои Тағйирёбанда',ru:'Мастер переменных',g:'x=',r:'common',c:'100% в тестах темы «Переменные и типы»',v:'Первый кирпич в фундаменте',a:'Ящики склада подписываются и закрываются'},
 {tj:'Сардори Шартҳо',ru:'Повелитель условий',g:'if',r:'common',c:'15 задач на if/elif/else, принятых автотестами',v:'Логика под контролем',a:'Светофоры города загораются зелёным по очереди'},
 {tj:'Мири Шаҳр',ru:'Мэр города',i:'city',r:'rare',c:'Восстановить все 9 кварталов Безмолвного города (Блок 1)',v:'Первый большой рубеж',a:'Город загорается вечерними огнями'},
 {tj:'Тӯфоншикан',ru:'Укротитель шторма',i:'bolt',r:'epic',c:'Сдать итоговый экзамен Блока 1 на 90%+',v:'Доказанный фундамент Python',a:'Молния бьёт в значок, тучи рассеиваются'},
 {tj:'Кимиёгар',ru:'Алхимик',g:'def',r:'rare',c:'25 своих функций принято в Книгу рецептов',v:'Код, который можно переиспользовать',a:'Котёл бурлит, флакон с именем функции всплывает'},
 {tj:'Рецепти Такрорӣ',ru:'Переиспользователь',i:'echo',r:'rare',c:'Использовать функцию из своего Кодекса в задании другого блока',v:'Мышление настоящего разработчика',a:'Свиток из Кодекса летит в новое задание'},
 {tj:'Ҳофизи JSON',ru:'Хранитель JSON',g:'{ }',r:'common',c:'Сдать все задания по файлам и JSON',v:'Работа с реальными данными',a:'Скобки защёлкиваются вокруг кристалла'},
 // Блок 3–5
 {tj:'Боти Зинда',ru:'Живой бот',i:'robot',r:'epic',c:'Бот прошёл проверку и работает на сервере 7 дней',v:'Настоящий продукт в портфолио',a:'Антенна бота мигает, приходит /start'},
 {tj:'Аввалин Мизоҷ',ru:'Первый покупатель',i:'gift',r:'rare',c:'Реальный человек (не автор) запустил вашего бота',v:'Кто-то пользуется твоим кодом!',a:'Колокольчик лавки звенит, вылетает чек'},
 {tj:'Ҷонглёри Async',ru:'Жонглёр async',g:'await',r:'common',c:'Пройти мини-игру «Async-жонглёр» на 3 звезды',v:'Асинхронность понятна',a:'Три шарика жонглируются вокруг значка'},
 {tj:'Муҳандиси Робот',ru:'Инженер роботов',i:'gear',r:'rare',c:'Пройти Блок 4 (ООП) и собрать свою линейку роботов',v:'Код как система объектов',a:'Шестерёнки сцепляются и раскручивают значок'},
 {tj:'Ғолиби Мегабот',ru:'Победитель Мегабота',i:'trophy',r:'epic',c:'Пробить все 30 скрытых тестов босса «Мегабот»',v:'Код выдерживает строгую проверку',a:'Полоска HP босса обнуляется, Мегабот рассыпается на шестерёнки'},
 {tj:'Детективи SQL',ru:'SQL-детектив',i:'search',r:'epic',c:'Раскрыть «Дело о памирском золоте»',v:'SQL — суперсила работы с данными',a:'Нити на доске улик сходятся в одну точку'},
 {tj:'Устои JOIN',ru:'Мастер JOIN',g:'JOIN',r:'rare',c:'10 принятых запросов с JOIN',v:'Связываешь данные как профи',a:'Две таблицы-карточки сшиваются нитью'},
 // Блок 6–9
 {tj:'Соҳиби Чароғ',ru:'Хозяин лампы',i:'lamp',r:'epic',c:'AI-бот выдержал испытание «Хитрого джинна»',v:'Безопасный AI-продукт',a:'Из лампы вырывается фиолетовый дым и складывается в значок'},
 {tj:'Сухани Мухтасар',ru:'Краткость — сестра таланта',i:'code',r:'rare',c:'Войти в топ-25% «Промпт-гольфа» недели',v:'Умеешь ставить задачу ИИ',a:'Лишние слова промпта сгорают, остаётся суть'},
 {tj:'Аввалин Commit',ru:'Первый коммит',g:'git',r:'common',c:'Первый коммит в свой GitHub-репозиторий (проверка через API)',v:'Код живёт в истории',a:'На линии времени зажигается первая звезда'},
 {tj:'Сулҳҷӯ',ru:'Миротворец',i:'branch',r:'rare',c:'Самостоятельно разрешить merge-конфликт',v:'Работа в команде без страха',a:'Две ветки сливаются в одну линию'},
 {tj:'Посбони Вақт',ru:'Хранитель времени',i:'clock',r:'epic',c:'Пройти Блок 7: CI на GitHub Actions зелёный',v:'Профессиональный процесс разработки',a:'Стрелки часов отматываются, вспыхивает зелёная галочка'},
 {tj:'Капитани Ситора',ru:'Капитан звездолёта',i:'ship',r:'rare',c:'Найти 20 багов в коде, сгенерированном ИИ',v:'Ты управляешь ИИ, а не он тобой',a:'Звездолёт делает петлю вокруг значка'},
 {tj:'Тоҷири Абрешим',ru:'Купец Шёлкового пути',i:'camel',r:'epic',c:'Сдать 3 учебных заказа с оценкой 5★ от «заказчика»',v:'Готовность к реальным заказам',a:'Караван проходит по экрану, звенят колокольчики'},
 // Социальные
 {tj:'Мубориз',ru:'Боец Python',i:'swords',r:'common',c:'Победить в 10 Python-битвах',v:'Скорость и уверенность',a:'Мечи скрещиваются, искры зелёные'},
 {tj:'Устоди Меҳрубон',ru:'Добрый наставник',i:'heart',r:'rare',c:'10 ответов другим ученикам отмечены «Помогло»',v:'Объясняя — понимаешь глубже',a:'Сердце-код пульсирует, вокруг «спасибо» на 3 языках'},
 {tj:'Дастаи Тиллоӣ',ru:'Золотая команда',i:'team',r:'rare',c:'Командный квест недели выполнен на 100%',v:'Вместе сильнее',a:'Аватары команды соединяются в звезду'},
 {tj:'Устоди Бузург',ru:'Великий наставник',i:'book',r:'epic',c:'50 «Помогло» + 10 принятых код-ревью для других',v:'Статус наставника в сообществе',a:'Книга раскрывается, страницы светятся'},
 {tj:'Эхои Абадӣ',ru:'Вечное эхо',i:'echo',r:'epic',c:'Выполнить 50 Эхо-миссий (повторение пройденного)',v:'Знания, которые не забываются',a:'Волны эха расходятся по всей карте'},
 // Легенды
 {tj:'Ҷамъоварандаи Багҳо',ru:'Коллекционер Бестиария',i:'bug',r:'leg',c:'Приручить всех 25 существ Бестиария ошибок',v:'Ты видел все ошибки — и победил',a:'Все существа кланяются, золотой свет'},
 {tj:'Фотеҳи Қулла',ru:'Покоритель вершины',i:'mountain',r:'leg',c:'Защитить финальный проект на Демо-дне',v:'Готовый проект + сертификат с QR',a:'Флаг на пике Сомони, панорама гор, салют'},
 {tj:'Аждаҳои Код',ru:'Дракон кода',i:'crown',r:'leg',c:'Пройти все 11 миров курса',v:'Пайко в финальной форме — навсегда',a:'Пайко превращается в Дракона и облетает профиль'},
];
const RANK = {common:0,rare:1,epic:2,leg:3};

function achCard(a){
  const r=RAR[a.r];
  return `<div class="ac ac-${a.r}"><div class="ac-h">${badge(a,48)}<div style="min-width:0"><div class="ac-ru">${a.ru}</div><div class="tj" style="font-size:11.5px">${a.tj}</div>
  <div style="margin-top:3px"><span class="chip ${a.r}" style="padding:2px 7px;font-size:10px">${r.name}</span>${a.s?' <span class="chip gray" style="padding:2px 7px;font-size:10px">секрет</span>':''}</div></div></div>
  <div class="ac-c">${a.c}</div><div class="ac-v"><b>Ценность:</b> ${a.v}</div><div class="ac-v"><b>Анимация:</b> ${a.a}</div></div>`;
}
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('[data-i]').forEach(el=>{el.innerHTML=icon(el.dataset.i, el.dataset.c||'currentColor', +(el.dataset.s||22), +(el.dataset.w||1.8));});
  document.querySelectorAll('[data-ach]').forEach(el=>{el.innerHTML=badge(ACH[+el.dataset.ach], +(el.dataset.s||72));});
  document.querySelectorAll('[data-badge]').forEach(el=>{el.innerHTML=badge(JSON.parse(el.dataset.badge), +(el.dataset.s||72));});
  document.querySelectorAll('[data-payko]').forEach(el=>{el.innerHTML=payko(+el.dataset.payko, +(el.dataset.s||120), el.dataset.m||'happy');});
  document.querySelectorAll('[data-cr]').forEach(el=>{const [c,v]=el.dataset.cr.split('|'); el.innerHTML=creature(c,+v,+(el.dataset.s||64),!el.dataset.wild);});
  document.querySelectorAll('[data-radar]').forEach(el=>{const d=JSON.parse(el.dataset.radar); el.innerHTML=radar(d.v,d.p,+(el.dataset.s||240),el.dataset.nol?false:true);});
  const t1=document.getElementById('ach1'), t2=document.getElementById('ach2');
  if(t1) t1.insertAdjacentHTML('afterbegin',ACH.slice(0,19).map(achCard).join(''));
  if(t2) t2.insertAdjacentHTML('afterbegin',ACH.slice(19).map(achCard).join(''));
  const pages=[...document.querySelectorAll('.page')];
  pages.forEach((p,i)=>{ if(p.dataset.nofoot) return; const f=document.createElement('div'); f.className='foot';
    f.innerHTML=`<span><b>Py·Достон</b> &nbsp;·&nbsp; игровая система mycourse.tj</span><span>${p.dataset.sec||''}</span><span>${String(i+1).padStart(2,'0')} / ${pages.length}</span>`; p.appendChild(f);});
  document.body.dataset.ready='1';
});

// Техническая реализация функций: [название, как работает, действия, хранение, анти-накрутка, когда награда, триггеры, сложность 1-5, этап]
const FEAT = [
 ['XP, уровни, ранги','Сервер начисляет XP по таблице стоимости; уровень и ранг — функция от суммы XP','видео (по реальному просмотру), тест, код прошёл тесты, ДЗ принято, эхо, босс','xp_ledger · game_profile(xp, level, rank)','XP только за первый успех (уникальный ключ события), всё проверяет сервер','сразу после события','«+40 XP» всплывает; повышение уровня — полноэкранно',2,1],
 ['Танга и магазин','Танга ≈ XP ÷ 5 + награды квестов; покупка — атомарная транзакция','все события с XP, квесты, покупки','wallet_tx · shop_items · inventory','баланс считается только из журнала; лимиты на товары','сразу; покупка — мгновенно','монеты летят в кошелёк; «Куплено»',2,1],
 ['Миссия дня','В 00:00 по часовому поясу ученика собирается из текущего урока + 1 эхо','события курса, закрывающие шаги','daily_missions(date, steps jsonb, done_at)','шаг закрывается только реальным событием курса','когда закрыты все шаги','кольцо прогресса; «Находка дня»',2,1],
 ['Гулхан (недельная серия)','Цель 2–6 дней; день засчитан при ≥ 1 событии с XP','любое событие с XP','streak_weeks(goal, days_done, freeze_used)','считаются только события с XP; «масло» из инвентаря','итог недели: вс 23:59 по TZ ученика','костёр разгорается; итог недели в Telegram',2,1],
 ['Достижения','Правила — данные (JSON): условие и порог; проверка после каждого события','все события','achievements(rule, rarity, secret) · user_achievements(tier, share_token)','выдача идемпотентна; % владельцев считается по базе','в момент выполнения условия','анимация по редкости; карточка для сторис',3,1],
 ['Пайко','Стадия = число пройденных блоков; реплики из шаблонов по контексту дня','завершение блока, события дня','game_profile(payko_stage, skin)','ускорить нельзя — только прохождение блоков','при завершении блока','эволюция; реплики на главной',2,1],
 ['Бестиарий ошибок','Код-раннер возвращает тип исключения; если следующий запуск без этой ошибки и без готового решения — существо приручено','запуск кода с ошибкой → успешный запуск','bestiary(error_type, first_seen, tamed_at)','1 раз на тип; только в учебных задачах; не засчитывается после показа решения','при исправлении','существо выбегает; «Новое существо!»',3,1],
 ['Радар навыков','Каждое задание помечено навыками с весами','код прошёл тесты, результат теста','skills(user, skill, value) · task_skill_tags','только первые успехи; нормализация по сложности','после события; итог дня','«Сегодня: +3 Отладка»',2,2],
 ['Кодекс','Принятое решение копируется в личную библиотеку с тегами','код прошёл тесты, ДЗ принято','codex_items(task_id, code, tags)','только принятые решения','сразу','«Свиток #65 добавлен»',2,2],
 ['Эхо-миссии','Интервалы 1–3–7–21 день (система Лейтнера)','ответ на эхо-задачу','echo_schedule(topic, box, due_at)','XP только в день, когда эхо «созрело»; без повторов той же задачи','при верном ответе','значок эха на карте',3,2],
 ['Мини-игры','HTML5-модули с банком заданий, ответы проверяет сервер','игра завершена (счёт, время)','minigame_runs(score, duration)','3 игры с XP в день; минимальное время; серверная проверка','после игры','1–3 звезды',4,2],
 ['Боссы блоков','Экзамен или проект со скрытыми тестами; HP = доля непройденных тестов','отправка решения, пройденные тесты','boss_attempts(tests_passed, best)','скрытые тесты; антиплагиат по AST; награда один раз','при 100% или пороге экзамена','полоска HP; эпическая анимация',3,2],
 ['Лиги','Группы по 20–30 по активности прошлой недели; очки с убывающей отдачей','события с XP за неделю','league_members(week, points) · Redis sorted set','убывающая отдача, лимиты, поиск аномалий','воскресенье вечером','итоги лиги, повышение',3,2],
 ['Командные квесты','Общая цель недели; вклад одного ограничен сверху','события участников','teams · team_quests(progress)','потолок вклада, защита от фейковых аккаунтов','при достижении цели','флаг команды на карте',3,2],
 ['Помощь и карма','«Помогло» ставит автор вопроса; ревью ДЗ по рубрике','отметка «Помогло», принятое ревью','help_votes(from, to, post) · mentor_karma','1 голос на пост, недельный лимит, поиск взаимных «ферм», выборочная проверка','после отметки','«Спасибо» + карма',3,2],
 ['Проверка ботов и GitHub','Платформа даёт одноразовый код боту / читает репозиторий через API','бот ответил кодом, коммит, CI зелёный','integrations(bot, repo) · verifications','одноразовые коды, проверка владельца, повторная проверка через 7 дней','после успешной проверки','«Живой бот», «Хранитель времени»',4,2],
 ['Python-битвы','Подбор по рангу, одна задача; асинхронно — против записи «призрака»','решение битвы (время, тесты)','battles · battle_runs(replay)','серверное время, одинаковые задачи, ограничение вставки кода','по завершении','экран VS, победа',4,3],
 ['AI-испытания','Набор проверочных диалогов к AI-боту ученика, оценка по рубрике','испытание пройдено','ai_runs(transcript, score)','фиксированный набор атак, лимит запусков, бюджет токенов','при прохождении','эпическая анимация «Хозяин лампы»',5,3],
];
function featRow(f){
  const dots=[1,2,3,4,5].map(i=>`<i class="${i<=f[7]?'on':''}"></i>`).join('');
  const ph={1:'<span class="chip">1 · запуск</span>',2:'<span class="chip rare">2 · расширение</span>',3:'<span class="chip epic">3 · будущее</span>'}[f[8]];
  const dc=f[7]>=5?'red':f[7]>=4?'warn':'';
  return `<tr><td><b style="font-size:12px">${f[0]}</b><div style="margin-top:4px">${ph}</div></td><td>${f[1]}</td><td class="muted">${f[2]}</td><td class="mono" style="font-size:10.4px;color:#B9D9C6">${f[3]}</td><td>${f[4]}</td><td class="muted">${f[5]}</td><td class="muted">${f[6]}</td><td><span class="dots ${dc}">${dots}</span></td></tr>`;
}
document.addEventListener('DOMContentLoaded',()=>{
  const head=`<thead><tr><th style="width:150px">Функция</th><th style="width:230px">Как работает</th><th style="width:180px">Учитываемые действия</th><th style="width:190px">Что хранить в БД</th><th style="width:220px">Защита от накрутки</th><th style="width:120px">Когда награда</th><th style="width:170px">Анимации и уведомления</th><th>Сложн.</th></tr></thead>`;
  const a=document.getElementById('feat1'), b=document.getElementById('feat2');
  if(a) a.innerHTML=head+'<tbody>'+FEAT.slice(0,9).map(featRow).join('')+'</tbody>';
  if(b) b.innerHTML=head+'<tbody>'+FEAT.slice(9).map(featRow).join('')+'</tbody>';
});
