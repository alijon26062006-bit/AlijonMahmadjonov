import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Background, Brand, ChapterTag, Cursor, Desktop, EASE, Explainer, Highlight, useRamp, useSec, WindowFrame} from '../components/common';
import {fonts, theme} from '../theme';

type Typed = {t: number; text: string; times: number[]};
export type SceneData = {
  id: string;
  start: number;
  dur: number;
  lines: {start: number; dur: number; text: string}[];
  ev: Record<string, number | Typed>;
};

const n = (ev: SceneData['ev'], k: string) => ev[k] as number;
const typedText = (tp: Typed, sec: number) => tp.text.slice(0, tp.times.filter((t) => t <= sec).length);

// ---------------------------------------------------------------- заставка
const IntroTitle: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame: frame - 0.3 * fps, fps, config: {damping: 14, stiffness: 120}});
  const sub = r(n(d.ev, 'subtitle'), 0.7);
  const glyphs = ['print()', '>>>', '{ }', 'def', 'if', '[ ]', 'for', '#'];
  return (
    <AbsoluteFill>
      <Background />
      {glyphs.map((g, i) => (
        <div
          key={g}
          style={{
            position: 'absolute',
            left: 160 + ((i * 233) % 1600),
            top: 140 + ((i * 397) % 760),
            fontFamily: fonts.mono,
            fontSize: 34 + (i % 3) * 10,
            color: theme.accent,
            opacity: 0.1 + (i % 2) * 0.06,
            translate: `0 ${Math.sin(frame / 40 + i) * 14}px`,
          }}
        >
          {g}
        </div>
      ))}
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
        <div
          style={{
            opacity: r(0.1, 0.5),
            translate: `0 ${(1 - r(0.1, 0.5)) * 20}px`,
            fontFamily: fonts.body,
            fontWeight: 800,
            fontSize: 30,
            letterSpacing: 6,
            color: theme.accent2,
            padding: '12px 28px',
            borderRadius: 999,
            border: `2px solid rgba(34,211,238,0.5)`,
            background: 'rgba(34,211,238,0.08)',
          }}
        >
          PYTHON С НУЛЯ
        </div>
        <div
          style={{
            marginTop: 34,
            fontFamily: fonts.display,
            fontWeight: 800,
            fontSize: 190,
            lineHeight: 1,
            color: theme.text,
            scale: interpolate(pop, [0, 1], [0.7, 1]),
            opacity: Math.min(1, pop * 1.5),
            textShadow: '0 20px 80px rgba(76,141,255,0.45)',
          }}
        >
          Урок 1
        </div>
        <div
          style={{
            marginTop: 40,
            fontFamily: fonts.body,
            fontWeight: 700,
            fontSize: 58,
            color: theme.text,
            opacity: sub,
            translate: `0 ${(1 - sub) * 30}px`,
          }}
        >
          Установка <span style={{color: theme.accent}}>Python</span> и{' '}
          <span style={{color: theme.accent2}}>VS Code</span>
        </div>
        <div
          style={{
            marginTop: 26,
            height: 6,
            width: 520 * r(n(d.ev, 'subtitle') + 0.3, 0.8),
            borderRadius: 3,
            background: `linear-gradient(90deg, ${theme.accent}, ${theme.accent2})`,
          }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const WHY = [
  {k: 'u1', title: 'Телеграм-боты', icon: 'M3 11l18-8-6 18-3-7-9-3z'},
  {k: 'u2', title: 'Сайты', icon: 'M3 5h18v14H3z M3 9h18'},
  {k: 'u3', title: 'Таблицы и отчёты', icon: 'M4 4h16v16H4z M4 10h16 M4 15h16 M10 4v16'},
  {k: 'u4', title: 'Искусственный интеллект', icon: 'M9 3v3 M15 3v3 M9 18v3 M15 18v3 M3 9h3 M3 15h3 M18 9h3 M18 15h3 M6 6h12v12H6z M10 10h4v4h-4z'},
];

export const IntroScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const why = d.ev.why === undefined ? 1e9 : n(d.ev, 'why');
  const out = r(why - 0.2, 0.5);
  const inn = r(why + 0.2, 0.6);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{opacity: 1 - out}}>
        <IntroTitle d={d} />
      </AbsoluteFill>
      {inn > 0 ? (
        <AbsoluteFill style={{opacity: inn}}>
          <Background />
          <div style={{position: 'absolute', top: 170, width: '100%', textAlign: 'center', fontFamily: fonts.display, fontWeight: 800, fontSize: 80, color: theme.text}}>
            Почему <span style={{color: theme.accent}}>Python</span>?
          </div>
          <div style={{position: 'absolute', top: 300, width: '100%', textAlign: 'center', fontFamily: fonts.body, fontWeight: 700, fontSize: 34, color: theme.muted}}>
            Один из самых популярных языков в мире
          </div>
          <div style={{position: 'absolute', top: 430, left: 140, right: 140, display: 'flex', gap: 36}}>
            {WHY.map((w) => {
              const k = r(n(d.ev, w.k), 0.5);
              return (
                <div key={w.k} style={{flex: 1, height: 300, borderRadius: 26, background: `linear-gradient(160deg, ${theme.surface2}, ${theme.surface})`, border: `1.5px solid ${theme.border}`, opacity: k, translate: `0 ${(1 - k) * 50}px`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 30}}>
                  <svg width="90" height="90" viewBox="0 0 24 24" fill="none" stroke={theme.accent2} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round">
                    <path d={w.icon} />
                  </svg>
                  <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 34, color: theme.text, textAlign: 'center', padding: '0 20px'}}>{w.title}</div>
                </div>
              );
            })}
          </div>
          <div style={{position: 'absolute', top: 800, width: '100%', textAlign: 'center', fontFamily: fonts.body, fontWeight: 700, fontSize: 36, color: theme.green, opacity: r(n(d.ev, 'u4') + 1.5, 0.6)}}>
            Простой синтаксис — удобно начинать
          </div>
          <Brand />
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- план
const PlanIcon: React.FC<{kind: string}> = ({kind}) => {
  const c = theme.accent2;
  if (kind === 'download')
    return (
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round">
        <path d="M12 3v12M7 10l5 5 5-5M4 20h16" />
      </svg>
    );
  if (kind === 'install')
    return (
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinejoin="round">
        <path d="M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M12 11v10" />
      </svg>
    );
  return (
    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round">
      <path d="M8 6l-6 6 6 6M16 6l6 6-6 6M14 4l-4 16" />
    </svg>
  );
};

export const PlanScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const cards = [
    {k: 'card1', icon: 'download', title: 'Скачать Python', desc: 'с официального сайта python.org'},
    {k: 'card2', icon: 'install', title: 'Установить', desc: 'и проверить в командной строке'},
    {k: 'card3', icon: 'code', title: 'VS Code', desc: 'редактор и первая программа'},
  ];
  return (
    <AbsoluteFill>
      <Background />
      <ChapterTag title="План урока" />
      <div
        style={{
          position: 'absolute',
          top: 200,
          width: '100%',
          textAlign: 'center',
          fontFamily: fonts.display,
          fontWeight: 800,
          fontSize: 76,
          color: theme.text,
          opacity: r(0.1, 0.5),
        }}
      >
        Что сделаем сегодня
      </div>
      <div style={{position: 'absolute', top: 400, left: 150, right: 150, display: 'flex', gap: 48}}>
        {cards.map((c, i) => {
          const k = r(n(d.ev, c.k), 0.6);
          return (
            <div
              key={c.k}
              style={{
                flex: 1,
                height: 420,
                borderRadius: 28,
                background: `linear-gradient(160deg, ${theme.surface2}, ${theme.surface})`,
                border: `1.5px solid ${k > 0.5 ? 'rgba(34,211,238,0.45)' : theme.border}`,
                boxShadow: '0 30px 80px rgba(0,0,0,0.35)',
                padding: 48,
                opacity: k,
                translate: `0 ${(1 - k) * 60}px`,
                display: 'flex',
                flexDirection: 'column',
                gap: 22,
              }}
            >
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                <PlanIcon kind={c.icon} />
                <span style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 72, color: 'rgba(255,255,255,0.08)'}}>
                  0{i + 1}
                </span>
              </div>
              <div style={{fontFamily: fonts.display, fontWeight: 700, fontSize: 44, color: theme.text, marginTop: 30}}>
                {c.title}
              </div>
              <div style={{fontFamily: fonts.body, fontWeight: 600, fontSize: 30, color: theme.muted, lineHeight: 1.35}}>
                {c.desc}
              </div>
            </div>
          );
        })}
      </div>
      <Brand />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- браузер
const BX = 210;
const BY = 110;
const BW = 1500;
const BH = 850;

export const PyLogo: React.FC<{size: number}> = ({size}) => (
  <div style={{position: 'relative', width: size, height: size}}>
    <div style={{position: 'absolute', left: 0, top: 0, width: size * 0.64, height: size * 0.64, borderRadius: size * 0.2, background: '#3B77C9'}} />
    <div style={{position: 'absolute', right: 0, bottom: 0, width: size * 0.64, height: size * 0.64, borderRadius: size * 0.2, background: '#F2C94C'}} />
  </div>
);

export const BrowserScene: React.FC<{d: SceneData}> = ({d}) => {
  const sec = useSec();
  const r = useRamp();
  const ev = d.ev;
  const url = ev['type:url'] as Typed;
  const typed = typedText(url, sec);
  const loaded = sec >= n(ev, 'enter_url') + 0.5;
  const loadBar = r(n(ev, 'enter_url'), 0.5);
  const dl = r(n(ev, 'click_download') + 0.2, n(ev, 'download_done') - n(ev, 'click_download') - 0.2, (x) => x);
  const chip = r(n(ev, 'click_download') + 0.1, 0.4);
  const pressed = sec >= n(ev, 'click_download') && sec < n(ev, 'click_download') + 0.15;
  const btn = {x: BX + 120 + 210, y: 599};
  const chipC = {x: 1450, y: 375};
  const path = [
    {t: 0, x: 1250, y: 640},
    {t: n(ev, 'move_browser'), x: 1250, y: 640},
    {t: n(ev, 'move_browser') + 0.8, x: 970, y: 1048},
    {t: n(ev, 'click_address') - 0.7, x: 970, y: 1048},
    {t: n(ev, 'click_address'), x: 720, y: BY + 76},
    {t: n(ev, 'move_download'), x: 720, y: BY + 76},
    {t: n(ev, 'move_download') + 1.0, x: btn.x, y: btn.y},
    {t: n(ev, 'move_file'), x: btn.x, y: btn.y},
    {t: n(ev, 'move_file') + 0.9, x: chipC.x, y: chipC.y},
  ];
  const clicks = ['click_browser', 'click_address', 'click_download', 'click_file'].map((k) => n(ev, k));
  return (
    <AbsoluteFill>
      <Desktop />
      <WindowFrame x={BX} y={BY} w={BW} h={BH} title={loaded ? 'Welcome to Python.org' : 'Новая вкладка'} appear={n(ev, 'window')}>
        {/* адресная строка */}
        <div style={{height: 60, background: '#161D2B', display: 'flex', alignItems: 'center', padding: '0 24px', gap: 20}}>
          <span style={{color: theme.muted, fontSize: 26}}>← → ⟳</span>
          <div
            style={{
              flex: 1,
              height: 40,
              borderRadius: 20,
              background: '#0C111B',
              border: `1.5px solid ${sec >= n(ev, 'click_address') ? theme.accent : '#2A3346'}`,
              display: 'flex',
              alignItems: 'center',
              padding: '0 20px',
              fontFamily: fonts.body,
              fontWeight: 600,
              fontSize: 22,
              color: theme.text,
            }}
          >
            {loaded ? <span style={{color: theme.green, marginRight: 10}}>🔒</span> : null}
            {loaded ? 'https://www.python.org' : typed}
            {!loaded && sec >= n(ev, 'click_address') && Math.floor(sec * 2) % 2 === 0 ? (
              <span style={{width: 2, height: 24, background: theme.text, marginLeft: 2}} />
            ) : null}
          </div>
        </div>
        <div style={{height: 3, width: `${loadBar * 100}%`, background: theme.accent, opacity: loadBar < 1 ? 1 : 0}} />
        {/* страница */}
        {loaded ? (
          <div style={{position: 'absolute', top: 63, left: 0, right: 0, bottom: 0, background: '#1F2A3D'}}>
            <div style={{height: 90, background: '#162033', display: 'flex', alignItems: 'center', padding: '0 120px', gap: 22}}>
              <PyLogo size={44} />
              <span style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 40, color: '#fff'}}>python</span>
              <div style={{flex: 1}} />
              {['About', 'Downloads', 'Documentation', 'Community'].map((m) => (
                <span key={m} style={{fontFamily: fonts.body, fontWeight: 700, fontSize: 22, color: m === 'Downloads' ? theme.accent2 : '#C7D0E0', marginLeft: 34}}>
                  {m}
                </span>
              ))}
            </div>
            <div style={{position: 'absolute', left: 120, top: 170, width: 700}}>
              <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 52, color: '#fff', lineHeight: 1.15}}>
                Download the latest version for Windows
              </div>
              <div
                style={{
                  marginTop: 50,
                  width: 420,
                  height: 84,
                  borderRadius: 14,
                  background: pressed ? '#3A73D6' : theme.accent,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontFamily: fonts.body,
                  fontWeight: 800,
                  fontSize: 28,
                  color: '#fff',
                  boxShadow: sec >= n(ev, 'move_download') + 0.8 ? '0 0 0 6px rgba(76,141,255,0.3)' : 'none',
                  scale: pressed ? 0.97 : 1,
                }}
              >
                Download Python 3.13.0
              </div>
              <div style={{marginTop: 26, fontFamily: fonts.body, fontWeight: 600, fontSize: 22, color: '#9AA6BA'}}>
                Looking for Python with a different OS? Linux, macOS
              </div>
            </div>
            <div
              style={{
                position: 'absolute',
                right: 120,
                top: 170,
                width: 520,
                height: 300,
                borderRadius: 18,
                background: '#0F1626',
                border: '1px solid #2A3550',
                padding: 30,
                fontFamily: fonts.mono,
                fontSize: 24,
                color: '#C7D0E0',
                lineHeight: 1.7,
              }}
            >
              <div style={{color: '#6B7A93'}}># Python 3: Simple output</div>
              <div>
                <span style={{color: theme.accent2}}>&gt;&gt;&gt; </span>print(<span style={{color: theme.green}}>"Hello, World!"</span>)
              </div>
              <div>Hello, World!</div>
            </div>
            {/* загрузка файла */}
            <div
              style={{
                position: 'absolute',
                right: 30,
                top: 110,
                width: 420,
                padding: '18px 22px',
                borderRadius: 14,
                background: '#111827',
                border: `1.5px solid ${dl >= 1 ? theme.green : theme.border}`,
                boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
                opacity: chip,
                translate: `0 ${(1 - chip) * -20}px`,
                fontFamily: fonts.body,
              }}
            >
              <div style={{fontWeight: 700, fontSize: 21, color: '#fff'}}>python-3.13.0-amd64.exe</div>
              <div style={{marginTop: 10, height: 6, borderRadius: 3, background: '#26324A'}}>
                <div style={{height: 6, borderRadius: 3, width: `${dl * 100}%`, background: dl >= 1 ? theme.green : theme.accent}} />
              </div>
              <div style={{marginTop: 8, fontWeight: 600, fontSize: 18, color: dl >= 1 ? theme.green : theme.muted}}>
                {dl >= 1 ? 'Готово · 26,4 МБ · Открыть файл' : `${(dl * 26.4).toFixed(1)} из 26,4 МБ`}
              </div>
            </div>
          </div>
        ) : (
          <div style={{position: 'absolute', top: 63, left: 0, right: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <div style={{width: 640, height: 64, borderRadius: 32, background: '#161D2B', border: '1px solid #2A3346'}} />
          </div>
        )}
      </WindowFrame>
      <Cursor path={path} clicks={clicks} />
      {ev.warn !== undefined ? (
        <Explainer show={n(ev, 'warn')} hide={n(ev, 'move_download') - 0.3} label="ВАЖНО" color={theme.red} term="Только официальный сайт" text="Программы скачивайте только с официальных сайтов: на чужих сайтах может оказаться вирус." x={1180} y={560} w={600} />
      ) : null}
      <ChapterTag step="ШАГ 1" title="Скачиваем Python" />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- установщик
const IX = 360;
const IY = 150;
const IW = 1200;
const IH = 740;
const CHECK = {x: IX + 360, y: IY + 679}; // галочка PATH (центр квадрата)

const InstallerBody: React.FC<{checked: boolean; hlInstall: boolean; ring: number; sec: number}> = ({checked, hlInstall, ring, sec}) => (
  <div style={{position: 'absolute', inset: 0, display: 'flex', fontFamily: fonts.body, color: '#1F2633'}}>
    <div
      style={{
        width: 300,
        background: 'linear-gradient(180deg, #2F6BC9, #1D3F7A)',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        paddingBottom: 60,
      }}
    >
      <PyLogo size={130} />
    </div>
    <div style={{flex: 1, padding: '40px 46px', position: 'relative'}}>
      <div style={{fontWeight: 800, fontSize: 36}}>Install Python 3.13.0 (64-bit)</div>
      <div style={{marginTop: 14, fontWeight: 500, fontSize: 20, color: '#4A5568', lineHeight: 1.45}}>
        Select Install Now to install Python with default settings, or choose Customize to enable or disable features.
      </div>
      <div
        style={{
          marginTop: 34,
          padding: '20px 24px',
          borderRadius: 12,
          background: hlInstall ? '#DCE8FF' : 'transparent',
          border: `2px solid ${hlInstall ? theme.accent : 'transparent'}`,
        }}
      >
        <div style={{fontWeight: 800, fontSize: 30, color: '#1D4ED8'}}>→ Install Now</div>
        <div style={{marginTop: 8, fontSize: 18, color: '#4A5568'}}>C:\Users\User\AppData\Local\Programs\Python\Python313</div>
        <div style={{marginTop: 8, fontSize: 18, color: '#4A5568'}}>Includes IDLE, pip and documentation</div>
      </div>
      <div style={{marginTop: 18, padding: '0 24px', fontWeight: 800, fontSize: 28, color: '#1D4ED8'}}>→ Customize installation</div>
      <div style={{position: 'absolute', left: 46, bottom: 46, display: 'flex', flexDirection: 'column', gap: 18}}>
        {[
          {label: 'Use admin privileges when installing py.exe', on: true},
          {label: 'Add python.exe to PATH', on: checked, key: true},
        ].map((row) => (
          <div key={row.label} style={{display: 'flex', alignItems: 'center', gap: 16, fontSize: 22, fontWeight: row.key ? 800 : 600}}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 6,
                border: `2.5px solid ${row.on ? theme.accent : '#7A8699'}`,
                background: row.on ? theme.accent : '#fff',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 20,
                fontWeight: 900,
                boxShadow: row.key && ring > 0 ? `0 0 0 ${6 + Math.sin(sec * 8) * 3}px rgba(255,107,107,${0.45 * ring})` : 'none',
              }}
            >
              {row.on ? '✓' : ''}
            </div>
            {row.label}
          </div>
        ))}
      </div>
    </div>
  </div>
);

export const InstallerScene: React.FC<{d: SceneData}> = ({d}) => {
  const sec = useSec();
  const r = useRamp();
  const ev = d.ev;
  const zoom = r(n(ev, 'zoom_in'), 0.9) * (1 - r(n(ev, 'zoom_out'), 0.9));
  const checked = sec >= n(ev, 'click_check');
  const ring = r(n(ev, 'zoom_in') + 0.4, 0.4) * (1 - r(n(ev, 'click_check'), 0.3));
  const calloutEnd = ev.path_card !== undefined ? n(ev, 'path_card') : n(ev, 'zoom_out');
  const callout = r(n(ev, 'callout'), 0.5) * (1 - r(calloutEnd, 0.4));
  const install = {x: 906, y: 452};
  const path = [
    {t: 0, x: 1400, y: 700},
    {t: n(ev, 'move_check'), x: 1400, y: 700},
    {t: n(ev, 'move_check') + 1.3, x: CHECK.x, y: CHECK.y},
    {t: n(ev, 'move_install'), x: CHECK.x, y: CHECK.y},
    {t: n(ev, 'move_install') + 0.9, x: install.x, y: install.y},
  ];
  const s = 1 + zoom * 1.2;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{scale: s, transformOrigin: `${CHECK.x + 160}px ${CHECK.y - 40}px`}}>
        <Desktop dim={0.35} />
        <WindowFrame x={IX} y={IY} w={IW} h={IH} title="Python 3.13.0 (64-bit) Setup" light>
          <InstallerBody checked={checked} hlInstall={sec >= n(ev, 'click_install')} ring={ring} sec={sec} />
        </WindowFrame>
        <Cursor path={path} clicks={[n(ev, 'click_check'), n(ev, 'click_install')]} />
      </AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          left: 1080,
          top: 530,
          padding: '26px 38px',
          borderRadius: 22,
          background: 'rgba(20,27,42,0.94)',
          border: `2px solid ${theme.red}`,
          boxShadow: '0 30px 80px rgba(0,0,0,0.5)',
          opacity: callout,
          scale: interpolate(callout, [0, 1], [0.9, 1]),
          fontFamily: fonts.body,
        }}
      >
        <div style={{fontWeight: 800, fontSize: 40, color: theme.red}}>Обязательно поставьте галочку!</div>
        <div style={{marginTop: 10, fontWeight: 600, fontSize: 28, color: theme.text}}>
          Без неё компьютер не найдёт Python
        </div>
      </div>
      {ev.path_card !== undefined ? (
        <Explainer show={n(ev, 'path_card')} hide={n(ev, 'zoom_out') + 0.2} term="PATH" text="Список папок, в которых компьютер ищет программы. С галочкой Python попадёт в этот список и будет запускаться откуда угодно." x={1200} y={380} w={620} />
      ) : null}
      <ChapterTag step="ШАГ 2" title="Устанавливаем Python" />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- прогресс установки
export const ProgressScene: React.FC<{d: SceneData}> = ({d}) => {
  const sec = useSec();
  const r = useRamp();
  const ev = d.ev;
  const succ = n(ev, 'success');
  const prog = r(n(ev, 'progress') + 0.3, succ - 0.6, (x) => x);
  const done = sec >= succ;
  const items = ['Python 3.13.0 Core Interpreter', 'Python 3.13.0 Standard Library', 'Python 3.13.0 pip Bootstrap', 'Python 3.13.0 Documentation'];
  const badge = r(succ + 0.4, 0.6);
  return (
    <AbsoluteFill>
      <Desktop dim={0.35} />
      <WindowFrame x={IX} y={IY} w={IW} h={IH} title="Python 3.13.0 (64-bit) Setup" light>
        <div style={{position: 'absolute', inset: 0, display: 'flex', fontFamily: fonts.body, color: '#1F2633'}}>
          <div style={{width: 300, background: 'linear-gradient(180deg, #2F6BC9, #1D3F7A)', display: 'flex', alignItems: 'flex-end', justifyContent: 'center', paddingBottom: 60}}>
            <PyLogo size={130} />
          </div>
          <div style={{flex: 1, padding: '40px 46px'}}>
            {!done ? (
              <>
                <div style={{fontWeight: 800, fontSize: 36}}>Setup Progress</div>
                <div style={{marginTop: 60, fontSize: 22, fontWeight: 600, color: '#4A5568'}}>Installing:</div>
                <div style={{marginTop: 8, fontSize: 24, fontWeight: 700}}>{items[Math.min(items.length - 1, Math.floor(prog * items.length))]}</div>
                <div style={{marginTop: 30, height: 24, borderRadius: 12, background: '#E2E8F0', overflow: 'hidden'}}>
                  <div style={{height: 24, width: `${prog * 100}%`, background: `linear-gradient(90deg, ${theme.accent}, ${theme.accent2})`}} />
                </div>
                <div style={{marginTop: 12, fontSize: 22, fontWeight: 700, color: '#4A5568'}}>{Math.round(prog * 100)}%</div>
              </>
            ) : (
              <div style={{opacity: r(succ, 0.4)}}>
                <div style={{fontWeight: 800, fontSize: 40}}>Setup was successful</div>
                <div style={{marginTop: 50, width: 120, height: 120, borderRadius: '50%', background: theme.green, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 70, fontWeight: 900, scale: interpolate(r(succ, 0.5), [0, 1], [0.5, 1])}}>
                  ✓
                </div>
                <div style={{marginTop: 40, fontSize: 22, fontWeight: 600, color: '#4A5568'}}>Python 3.13.0 (64-bit) is installed.</div>
              </div>
            )}
          </div>
        </div>
      </WindowFrame>
      <div
        style={{
          position: 'absolute',
          left: '50%',
          bottom: 70,
          translate: `-50% ${(1 - badge) * 30}px`,
          opacity: badge,
          padding: '18px 34px',
          borderRadius: 999,
          background: 'rgba(52,211,153,0.14)',
          border: `2px solid ${theme.green}`,
          fontFamily: fonts.body,
          fontWeight: 800,
          fontSize: 32,
          color: theme.green,
        }}
      >
        ✓ Python установлен
      </div>
      <ChapterTag step="ШАГ 2" title="Устанавливаем Python" />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- проверка в терминале
export const TerminalScene: React.FC<{d: SceneData}> = ({d}) => {
  const sec = useSec();
  const r = useRamp();
  const ev = d.ev;
  const cmd = ev['type:cmd'] as Typed;
  const typed = typedText(cmd, sec);
  const out = sec >= n(ev, 'output');
  const hl = r(n(ev, 'output') + 0.3, 0.5);
  const cursorOn = Math.floor(sec * 2) % 2 === 0;
  const line: React.CSSProperties = {fontFamily: fonts.mono, fontSize: 34, color: '#D6DEEB', lineHeight: 1.6};
  return (
    <AbsoluteFill>
      <Desktop dim={0.2} />
      <WindowFrame x={260} y={120} w={1400} h={760} title="Командная строка" appear={n(ev, 'window')}>
        <div style={{position: 'absolute', inset: 0, background: '#0B0E14', padding: '30px 40px'}}>
          <div style={{...line, color: '#6B7A93'}}>Microsoft Windows [Version 10.0]</div>
          <div style={{...line, color: '#6B7A93', marginBottom: 30}}>(c) Microsoft Corporation.</div>
          <div style={line}>
            <span style={{color: theme.accent2}}>C:\Users\User&gt;</span> {typed}
            {!out && cursorOn ? <span style={{background: '#D6DEEB', marginLeft: 2}}>&nbsp;</span> : null}
          </div>
          {out ? (
            <>
              <div style={{...line, display: 'inline-block', padding: '0 14px', margin: '6px -14px', borderRadius: 8, background: `rgba(52,211,153,${0.16 * hl})`, border: `2px solid rgba(52,211,153,${hl})`, color: theme.green, fontWeight: 700}}>
                Python 3.13.0
              </div>
              <div style={line}>
                <span style={{color: theme.accent2}}>C:\Users\User&gt;</span> {cursorOn ? <span style={{background: '#D6DEEB'}}>&nbsp;</span> : null}
              </div>
            </>
          ) : null}
        </div>
      </WindowFrame>
      <div
        style={{
          position: 'absolute',
          left: 640,
          top: 402,
          opacity: hl,
          translate: `${(1 - hl) * 30}px 0`,
          display: 'flex',
          alignItems: 'center',
          gap: 18,
          fontFamily: fonts.body,
          fontWeight: 800,
          fontSize: 36,
          color: theme.green,
        }}
      >
        <span style={{fontSize: 44}}>←</span> Python работает!
      </div>
      {ev.hl_path !== undefined ? (
        <>
          <Highlight show={n(ev, 'hl_path')} hide={n(ev, 'hl_cursor')} x={292} y={334} w={292} h={56} label="путь к папке" />
          <Highlight show={n(ev, 'hl_cursor')} hide={(ev['type:cmd'] as Typed).t} x={598} y={334} w={36} h={56} label="здесь печатаем" color={theme.green} />
          <Explainer show={n(ev, 'err_card')} label="ЕСЛИ ОШИБКА" color={theme.red} term="«python» не является командой" text="Значит, при установке не поставили галочку PATH. Запустите установщик ещё раз и отметьте её." x={1000} y={560} w={640} />
        </>
      ) : null}
      <ChapterTag step="ШАГ 3" title="Проверяем установку" />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- концовка части
export const OutroScene: React.FC<{d: SceneData}> = () => {
  const r = useRamp();
  const k = r(0.2, 0.7);
  const k2 = r(1.2, 0.7);
  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
        <div style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 110, color: theme.text, opacity: k, scale: interpolate(k, [0, 1], [0.9, 1])}}>
          Python <span style={{color: theme.green}}>установлен</span>
        </div>
        <div
          style={{
            marginTop: 50,
            display: 'flex',
            alignItems: 'center',
            gap: 22,
            fontFamily: fonts.body,
            fontWeight: 700,
            fontSize: 48,
            color: theme.muted,
            opacity: k2,
            translate: `0 ${(1 - k2) * 20}px`,
          }}
        >
          Дальше: <span style={{color: theme.accent2}}>VS Code</span>
          <span style={{color: theme.accent2, translate: `${Math.sin(r(1.2, 3) * 12) * 8}px 0`}}>→</span>
        </div>
      </AbsoluteFill>
      <Brand />
    </AbsoluteFill>
  );
};

export const SCENES: Record<string, React.FC<{d: SceneData}>> = {
  intro: IntroScene,
  plan: PlanScene,
  browser: BrowserScene,
  installer: InstallerScene,
  progress: ProgressScene,
  terminal: TerminalScene,
  outro: OutroScene,
};

export {EASE};
