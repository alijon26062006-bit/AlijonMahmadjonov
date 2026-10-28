import React from 'react';
import {AbsoluteFill, interpolate} from 'remotion';
import {
  Background,
  Brand,
  ChapterTag,
  Cursor,
  Desktop,
  Explainer,
  Highlight,
  Keycap,
  Typed,
  typedNow,
  useRamp,
  useSec,
  WindowFrame,
} from '../components/common';
import {ACT_X, actY, BODY, CodeLine, ED_X, RUN_BTN, SIDE_X, VSCodeWindow, VX, VY} from '../components/vscode';
import {fonts, theme} from '../theme';
import {BrowserScene, InstallerScene, IntroScene, PlanScene, ProgressScene, PyLogo, SceneData, TerminalScene} from './scenes';

const n = (ev: SceneData['ev'], k: string) => ev[k] as number;
const tp = (ev: SceneData['ev'], k: string) => ev[k] as Typed;
const has = (ev: SceneData['ev'], k: string) => ev[k] !== undefined;

const Title: React.FC<{children: React.ReactNode; top?: number}> = ({children, top = 150}) => {
  const r = useRamp();
  const k = r(0.15, 0.5);
  return (
    <div style={{position: 'absolute', top, width: '100%', textAlign: 'center', fontFamily: fonts.display, fontWeight: 800, fontSize: 64, color: theme.text, opacity: k, translate: `0 ${(1 - k) * 20}px`}}>
      {children}
    </div>
  );
};

const Card: React.FC<{k: number; style?: React.CSSProperties; children: React.ReactNode}> = ({k, style, children}) => (
  <div
    style={{
      borderRadius: 24,
      background: `linear-gradient(160deg, ${theme.surface2}, ${theme.surface})`,
      border: `1.5px solid ${theme.border}`,
      boxShadow: '0 30px 80px rgba(0,0,0,0.35)',
      opacity: k,
      translate: `0 ${(1 - k) * 40}px`,
      ...style,
    }}
  >
    {children}
  </div>
);

const Arrow: React.FC<{k: number; x: number; y: number; w?: number}> = ({k, x, y, w = 120}) => (
  <svg width={w} height={40} style={{position: 'absolute', left: x, top: y, opacity: k}}>
    <line x1={0} y1={20} x2={(w - 14) * k} y2={20} stroke={theme.accent2} strokeWidth={5} strokeLinecap="round" />
    {k > 0.9 ? <path d={`M${w - 22} 8 L${w - 4} 20 L${w - 22} 32`} fill="none" stroke={theme.accent2} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" /> : null}
  </svg>
);

const term: React.CSSProperties = {fontFamily: fonts.mono, fontSize: 32, color: '#D6DEEB', lineHeight: 1.6, whiteSpace: 'pre'};
const PROMPT = 'C:\\Users\\User>';
const Blink: React.FC = () => {
  const sec = useSec();
  return Math.floor(sec * 2) % 2 === 0 ? <span style={{background: '#D6DEEB'}}> </span> : <span> </span>;
};

// ================================================================ что устанавливаем
export const WhatScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const ev = d.ev;
  const ver = r(n(ev, 'ver'), 0.6);
  const a = r(n(ev, 'lang'), 0.5) * (1 - ver);
  const b = r(n(ev, 'interp'), 0.5) * (1 - ver);
  const c = r(n(ev, 'flow'), 0.5) * (1 - ver);
  return (
    <AbsoluteFill>
      <Background />
      <ChapterTag title="Что мы устанавливаем" />
      <div style={{position: 'absolute', top: 360, left: 150, opacity: a}}>
        <Card k={1} style={{width: 420, height: 300, padding: 34}}>
          <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 26, color: theme.muted}}>main.py</div>
          <div style={{marginTop: 24, fontFamily: fonts.mono, fontSize: 30, lineHeight: 1.7, color: '#D4D4D4'}}>
            <div>
              <span style={{color: '#DCDCAA'}}>print</span>(<span style={{color: '#CE9178'}}>"Привет!"</span>)
            </div>
            <div style={{color: '#6A9955'}}># ваш код</div>
          </div>
          <div style={{marginTop: 20, fontFamily: fonts.body, fontWeight: 700, fontSize: 26, color: theme.accent}}>Язык Python</div>
        </Card>
      </div>
      <Arrow k={b} x={600} y={490} />
      <div style={{position: 'absolute', top: 360, left: 750, opacity: b}}>
        <Card k={1} style={{width: 420, height: 300, padding: 34, border: `2px solid ${theme.accent2}`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20}}>
          <svg width="110" height="110" viewBox="0 0 24 24" fill="none" stroke={theme.accent2} strokeWidth="1.5" style={{rotate: `${r(n(ev, 'flow'), 6, (x) => x) * 360}deg`}}>
            <path d="M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M4.9 19.1L7 17 M17 7l2.1-2.1" />
          </svg>
          <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 32, color: theme.text}}>Интерпретатор</div>
        </Card>
      </div>
      <Arrow k={c} x={1200} y={490} />
      <div style={{position: 'absolute', top: 360, left: 1350, opacity: c}}>
        <Card k={1} style={{width: 420, height: 300, padding: 34, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 20}}>
          <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 26, color: theme.muted}}>Результат</div>
          <div style={{fontFamily: fonts.mono, fontSize: 40, color: theme.green, fontWeight: 700}}>Привет!</div>
        </Card>
      </div>
      <Explainer show={n(ev, 'interp') + 0.3} hide={n(ev, 'ver') - 0.3} term="Интерпретатор" text="Программа, которая читает ваш код строчка за строчкой и выполняет его." x={660} y={720} w={600} />
      {ver > 0 ? (
        <div style={{position: 'absolute', top: 330, width: '100%', display: 'flex', justifyContent: 'center', gap: 40, opacity: ver}}>
          {['3.11', '3.12', '3.13'].map((v, i) => {
            const newest = i === 2;
            const hl = newest ? r(n(ev, 'ver_new'), 0.5) : 0;
            return (
              <Card key={v} k={r(n(ev, 'ver') + i * 0.25, 0.5)} style={{width: 340, height: 300, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, border: `2px solid ${hl > 0.5 ? theme.green : theme.border}`, scale: 1 + hl * 0.06}}>
                <div style={{fontFamily: fonts.body, fontWeight: 700, fontSize: 28, color: theme.muted}}>Python</div>
                <div style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 84, color: newest ? theme.green : theme.text}}>{v}</div>
                <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 26, color: theme.green, opacity: hl}}>самая новая</div>
              </Card>
            );
          })}
        </div>
      ) : null}
      {ver > 0 ? (
        <div style={{position: 'absolute', top: 720, width: '100%', textAlign: 'center', fontFamily: fonts.body, fontWeight: 700, fontSize: 36, color: theme.text, opacity: r(n(ev, 'ver_new'), 0.6)}}>
          Берите последнюю версию — всё из курса будет работать
        </div>
      ) : null}
      <Brand />
    </AbsoluteFill>
  );
};

// ================================================================ что такое командная строка
export const CmdWhatScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const sec = useSec();
  const ev = d.ev;
  const mouse = r(n(ev, 'mouse'), 0.6);
  const text = r(n(ev, 'text'), 0.6);
  const demo = tp(ev, 'type:demo');
  const out = sec >= n(ev, 'demo_out');
  const uses = r(n(ev, 'uses'), 0.6);
  const top = interpolate(uses, [0, 1], [0, -90]);
  return (
    <AbsoluteFill>
      <Background />
      <ChapterTag title="Что такое командная строка" />
      <div style={{position: 'absolute', top: 210 + top, left: 150, width: 760, opacity: mouse}}>
        <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 34, color: theme.muted, marginBottom: 20}}>Обычно: мышкой</div>
        <Card k={1} style={{height: 420, position: 'relative', overflow: 'hidden'}}>
          <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(135deg, #22356B, #3A2A6B)'}} />
          {['Документы', 'Фото', 'Музыка', 'Игры'].map((nm, i) => (
            <div key={nm} style={{position: 'absolute', left: 60 + i * 170, top: 120, width: 120, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14}}>
              <div style={{width: 90, height: 70, borderRadius: 10, background: i === 1 && sec > n(ev, 'mouse') + 1.6 ? '#F6D365' : '#F2C14E', boxShadow: i === 1 && sec > n(ev, 'mouse') + 1.6 ? '0 0 0 5px rgba(255,255,255,0.4)' : 'none'}} />
              <div style={{fontFamily: fonts.body, fontWeight: 700, fontSize: 22, color: '#fff'}}>{nm}</div>
            </div>
          ))}
          <Cursor path={[{t: 0, x: 600, y: 360}, {t: n(ev, 'mouse') + 0.4, x: 600, y: 360}, {t: n(ev, 'mouse') + 1.4, x: 300, y: 170}]} clicks={[n(ev, 'mouse') + 1.6]} appear={n(ev, 'mouse')} />
        </Card>
      </div>
      <div style={{position: 'absolute', top: 210 + top, left: 1010, width: 760, opacity: text}}>
        <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 34, color: theme.accent2, marginBottom: 20}}>Командная строка: текстом</div>
        <Card k={1} style={{height: 420, background: '#0B0E14', padding: '30px 36px', border: `2px solid ${theme.accent2}`}}>
          <div style={term}>
            <span style={{color: theme.accent2}}>{PROMPT}</span> {typedNow(demo, sec)}
            {!out ? <Blink /> : null}
          </div>
          {out
            ? ['Документы', 'Фото', 'Музыка', 'Игры'].map((nm) => (
                <div key={nm} style={{...term, color: '#9FB0C8'}}>
                  {'  <DIR>   '}
                  {nm}
                </div>
              ))
            : null}
        </Card>
      </div>
      <Explainer show={n(ev, 'text') + 0.4} hide={n(ev, 'uses') - 0.2} term="Командная строка" text="Окно, где мы управляем компьютером текстом: пишем команду, нажимаем Enter — компьютер выполняет." x={560} y={730} w={800} />
      {uses > 0 ? (
        <div style={{position: 'absolute', top: 760, width: '100%', display: 'flex', justifyContent: 'center', gap: 30}}>
          {['Запуск программ', 'Установка библиотек', 'Проверка версий'].map((u, i) => (
            <div key={u} style={{padding: '22px 36px', borderRadius: 999, background: 'rgba(34,211,238,0.10)', border: `2px solid ${theme.accent2}`, fontFamily: fonts.body, fontWeight: 800, fontSize: 32, color: theme.text, opacity: r(n(ev, 'uses') + 0.5 + i * 0.6, 0.5)}}>
              {u}
            </div>
          ))}
        </div>
      ) : null}
      {has(ev, 'calm') ? (
        <div style={{position: 'absolute', top: 900, width: '100%', textAlign: 'center', fontFamily: fonts.body, fontWeight: 800, fontSize: 34, color: theme.green, opacity: r(n(ev, 'calm'), 0.6)}}>
          Не бойтесь: случайно сломать компьютер в ней очень сложно
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ================================================================ как открыть командную строку
const WayBadge: React.FC<{ev: SceneData['ev']}> = ({ev}) => {
  const sec = useSec();
  const cur = sec >= n(ev, 'way3') ? 3 : sec >= n(ev, 'way2') ? 2 : 1;
  const titles = ['', 'Через меню «Пуск»', 'Клавиши Win + R', 'Через папку'];
  return (
    <div style={{position: 'absolute', top: 130, width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 24, zIndex: 30}}>
      {[1, 2, 3].map((i) => (
        <div key={i} style={{width: 64, height: 64, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: fonts.display, fontWeight: 800, fontSize: 30, background: i === cur ? theme.accent : 'rgba(255,255,255,0.06)', color: i === cur ? '#fff' : theme.muted, border: `2px solid ${i === cur ? theme.accent : theme.border}`}}>
          {i}
        </div>
      ))}
      <div style={{marginLeft: 20, fontFamily: fonts.display, fontWeight: 800, fontSize: 44, color: theme.text}}>Способ {cur}: {titles[cur]}</div>
    </div>
  );
};

export const CmdOpenScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const sec = useSec();
  const ev = d.ev;
  const w2 = n(ev, 'way2');
  const w3 = n(ev, 'way3');
  const part = sec < w2 ? 1 : sec < w3 ? 2 : 3;
  // способ 1: меню «Пуск»
  const startK = r(n(ev, 'start_open'), 0.4);
  const startQ = typedNow(tp(ev, 'type:start'), sec);
  const picked = sec >= n(ev, 'start_pick');
  // способ 2: Win + R
  const runK = r(n(ev, 'run_open'), 0.4);
  const runQ = typedNow(tp(ev, 'type:run'), sec);
  const runDone = sec >= n(ev, 'run_enter') + 0.3;
  // способ 3: проводник
  const folderK = r(n(ev, 'folder_open'), 0.4);
  const addrSel = sec >= n(ev, 'addr_click');
  const addrQ = typedNow(tp(ev, 'type:addr'), sec);
  const addrDone = sec >= n(ev, 'addr_enter') + 0.3;
  return (
    <AbsoluteFill>
      <Desktop dim={0.45} />
      <WayBadge ev={ev} />
      {part === 1 ? (
        <>
          <div style={{position: 'absolute', left: 560, top: 250, width: 800, height: 700, borderRadius: 18, background: 'rgba(24,30,44,0.96)', border: '1px solid #33405A', boxShadow: '0 30px 90px rgba(0,0,0,0.6)', opacity: startK, translate: `0 ${(1 - startK) * 80}px`, padding: 36, fontFamily: fonts.body}}>
            <div style={{height: 64, borderRadius: 32, background: '#0F1420', border: `2px solid ${startQ ? theme.accent : '#33405A'}`, display: 'flex', alignItems: 'center', padding: '0 28px', fontSize: 30, color: theme.text, gap: 16}}>
              <span style={{color: theme.muted}}>⌕</span>
              {startQ || <span style={{color: theme.muted}}>Поиск</span>}
            </div>
            {startQ.length === 3 ? (
              <div style={{marginTop: 30}}>
                <div style={{fontSize: 24, fontWeight: 700, color: theme.muted, marginBottom: 14}}>Лучшее соответствие</div>
                <div style={{display: 'flex', alignItems: 'center', gap: 24, padding: 22, borderRadius: 14, background: picked ? 'rgba(76,141,255,0.35)' : 'rgba(76,141,255,0.15)', border: `2px solid ${theme.accent}`}}>
                  <div style={{width: 70, height: 70, borderRadius: 12, background: '#0C0C0C', border: '1px solid #444', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: fonts.mono, fontWeight: 700, fontSize: 26, color: '#fff'}}>{'>_'}</div>
                  <div>
                    <div style={{fontSize: 34, fontWeight: 800, color: '#fff'}}>Командная строка</div>
                    <div style={{fontSize: 24, fontWeight: 600, color: theme.muted}}>Приложение</div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
          <Cursor path={[{t: 0, x: 1200, y: 700}, {t: n(ev, 'start_open') - 0.9, x: 1200, y: 700}, {t: n(ev, 'start_open'), x: 840, y: 1048}, {t: n(ev, 'start_pick') - 0.9, x: 840, y: 1048}, {t: n(ev, 'start_pick'), x: 900, y: 480}]} clicks={[n(ev, 'start_open'), n(ev, 'start_pick')]} />
        </>
      ) : null}
      {part === 2 ? (
        <>
          <div style={{position: 'absolute', top: 330, width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 40, opacity: r(n(ev, 'keys') - 0.3, 0.4) * (1 - r(n(ev, 'run_open'), 0.4))}}>
            <Keycap label="Win" press={n(ev, 'keys')} w={220} />
            <span style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 64, color: theme.muted}}>+</span>
            <Keycap label="R" press={n(ev, 'keys') + 0.1} />
          </div>
          <div style={{position: 'absolute', left: 560, top: 400, opacity: runK, scale: interpolate(runK, [0, 1], [0.95, 1])}}>
            <WindowFrame x={0} y={0} w={800} h={360} title="Выполнить">
              <div style={{position: 'absolute', inset: 0, background: '#F3F4F6', padding: 34, fontFamily: fonts.body, color: '#1F2633'}}>
                <div style={{fontSize: 24, fontWeight: 600, color: '#4A5568', lineHeight: 1.4}}>Введите имя программы, папки или документа, и Windows откроет их.</div>
                <div style={{marginTop: 30, display: 'flex', alignItems: 'center', gap: 20, fontSize: 26, fontWeight: 700}}>
                  Открыть:
                  <div style={{flex: 1, height: 56, border: `2px solid ${theme.accent}`, background: '#fff', borderRadius: 6, display: 'flex', alignItems: 'center', padding: '0 16px', fontFamily: fonts.mono, fontSize: 28}}>{runQ}</div>
                </div>
                <div style={{position: 'absolute', right: 34, bottom: 30, display: 'flex', gap: 16}}>
                  <div style={{padding: '10px 34px', borderRadius: 6, background: sec >= n(ev, 'run_enter') ? '#2F5FC4' : theme.accent, color: '#fff', fontWeight: 800, fontSize: 22}}>OK</div>
                  <div style={{padding: '10px 26px', borderRadius: 6, background: '#E2E8F0', fontWeight: 700, fontSize: 22}}>Отмена</div>
                </div>
              </div>
            </WindowFrame>
          </div>
          {runDone ? <MiniCmd path="C:\Users\User>" show={n(ev, 'run_enter') + 0.3} /> : null}
        </>
      ) : null}
      {part === 3 ? (
        <>
          <div style={{opacity: folderK}}>
            <WindowFrame x={300} y={240} w={1320} h={700} title="Документы">
              <div style={{position: 'absolute', inset: 0, background: '#1B2130', fontFamily: fonts.body}}>
                <div style={{height: 64, display: 'flex', alignItems: 'center', gap: 20, padding: '0 24px', background: '#20283A'}}>
                  <span style={{color: theme.muted, fontSize: 26}}>← →</span>
                  <div style={{flex: 1, height: 44, borderRadius: 8, background: addrSel ? '#0F1420' : '#283248', border: `2px solid ${addrSel ? theme.accent : 'transparent'}`, display: 'flex', alignItems: 'center', padding: '0 18px', fontSize: 24, fontWeight: 600, color: theme.text}}>
                    {!addrSel ? 'Этот компьютер › Документы' : addrQ ? <span style={{fontFamily: fonts.mono}}>{addrQ}</span> : <span style={{background: 'rgba(76,141,255,0.6)', padding: '0 6px'}}>C:\Users\User\Documents</span>}
                  </div>
                </div>
                <div style={{display: 'flex', gap: 50, padding: 50}}>
                  {['Проекты', 'Учёба', 'Отчёт.docx', 'Фото'].map((nm, i) => (
                    <div key={nm} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14}}>
                      <div style={{width: 110, height: 86, borderRadius: 10, background: i === 2 ? '#4C8DFF' : '#F2C14E'}} />
                      <div style={{fontSize: 22, fontWeight: 700, color: theme.text}}>{nm}</div>
                    </div>
                  ))}
                </div>
              </div>
            </WindowFrame>
          </div>
          <Cursor path={[{t: 0, x: 1300, y: 760}, {t: n(ev, 'addr_click') - 0.9, x: 1300, y: 760}, {t: n(ev, 'addr_click'), x: 900, y: 316}]} clicks={[n(ev, 'addr_click')]} appear={n(ev, 'folder_open')} />
          {addrDone ? <MiniCmd path="C:\Users\User\Documents>" show={n(ev, 'addr_enter') + 0.3} /> : null}
        </>
      ) : null}
      <ChapterTag title="Как открыть командную строку" />
    </AbsoluteFill>
  );
};

const MiniCmd: React.FC<{path: string; show: number}> = ({path, show}) => (
  <WindowFrame x={460} y={330} w={1000} h={420} title="Командная строка" appear={show}>
    <div style={{position: 'absolute', inset: 0, background: '#0B0E14', padding: '28px 34px'}}>
      <div style={{...term, color: '#6B7A93'}}>Microsoft Windows [Version 10.0]</div>
      <div style={{...term, marginTop: 20}}>
        <span style={{color: theme.accent2}}>{path}</span>
        <Blink />
      </div>
    </div>
  </WindowFrame>
);

// ================================================================ интерактивный режим
export const ReplScene: React.FC<{d: SceneData}> = ({d}) => {
  const sec = useSec();
  const ev = d.ev;
  const py = tp(ev, 'type:py');
  const sum = tp(ev, 'type:sum');
  const hello = tp(ev, 'type:hello');
  const ex = tp(ev, 'type:exit');
  const inRepl = sec >= n(ev, 'py_enter');
  const rows: React.ReactNode[] = [];
  rows.push(
    <div key="p0" style={term}>
      <span style={{color: theme.accent2}}>{PROMPT}</span>
      {typedNow(py, sec)}
      {!inRepl ? <Blink /> : null}
    </div>,
  );
  if (inRepl) {
    rows.push(
      <div key="b" style={{...term, color: '#9FB0C8', fontSize: 26}}>
        Python 3.13.0 (64-bit) on win32{'\n'}Type "help" for more information.
      </div>,
    );
    const line = (key: string, t: Typed, outAt: number, out: string) => {
      if (sec < t.t - 0.6) return;
      rows.push(
        <div key={key} style={term}>
          <span style={{color: theme.green}}>{'>>> '}</span>
          {typedNow(t, sec)}
          {sec < outAt && sec < t.times[t.times.length - 1] + 0.4 ? <Blink /> : null}
        </div>,
      );
      if (sec >= outAt && out)
        rows.push(
          <div key={key + 'o'} style={{...term, color: theme.text, fontWeight: 700}}>
            {out}
          </div>,
        );
    };
    line('s', sum, n(ev, 'sum_out'), '4');
    line('h', hello, n(ev, 'hello_out'), 'Привет');
    line('e', ex, n(ev, 'exit_out'), '');
    if (sec >= n(ev, 'exit_out'))
      rows.push(
        <div key="back" style={term}>
          <span style={{color: theme.accent2}}>{PROMPT}</span>
          <Blink />
        </div>,
      );
    else if (sec < sum.t - 0.6)
      rows.push(
        <div key="pr" style={term}>
          <span style={{color: theme.green}}>{'>>> '}</span>
          <Blink />
        </div>,
      );
  }
  return (
    <AbsoluteFill>
      <Desktop dim={0.2} />
      <WindowFrame x={200} y={110} w={1050} h={860} title="Командная строка">
        <div style={{position: 'absolute', inset: 0, background: '#0B0E14', padding: '30px 40px', overflow: 'hidden'}}>{rows}</div>
      </WindowFrame>
      <Highlight show={n(ev, 'prompt')} hide={n(ev, 'repl_card') + 3} x={232} y={310} w={92} h={56} label="три стрелочки" labelPos="right" color={theme.green} />
      <Explainer show={n(ev, 'repl_card')} hide={tp(ev, 'type:sum').t - 0.5} term="Интерактивный режим" text="Пишем строку кода — Python сразу её выполняет. Удобно для быстрых проверок." x={1290} y={240} w={560} />
      <Explainer show={n(ev, 'exit_out') + 0.4} label="СОВЕТ" color={theme.green} term="exit() — выход" text="Настоящие программы пишем в файлах, а этот режим — для быстрых экспериментов." x={1290} y={500} w={560} />
      <ChapterTag title="Интерактивный режим Python" />
    </AbsoluteFill>
  );
};

// ================================================================ редактор кода
export const EditorScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const ev = d.ev;
  const np = r(n(ev, 'notepad'), 0.5);
  const ed = r(n(ev, 'editor'), 0.5);
  const feats = [
    {k: 'feat1', t: 'Подсветка кода цветом'},
    {k: 'feat2', t: 'Подсказки и поиск ошибок'},
    {k: 'feat3', t: 'Запуск одной кнопкой ▶'},
  ];
  const vs = r(n(ev, 'vscode'), 0.6);
  return (
    <AbsoluteFill>
      <Background />
      <ChapterTag title="Редактор кода" />
      <div style={{position: 'absolute', left: 120, top: 200, opacity: np * (1 - vs * 0.6)}}>
        <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 32, color: theme.muted, marginBottom: 16}}>Блокнот</div>
        <div style={{width: 760, height: 380, borderRadius: 14, background: '#F7F8FA', padding: 30, fontFamily: '"Courier New", monospace', fontSize: 30, color: '#222', lineHeight: 1.6}}>
          name = input("Имя: "){'\n'}
          <br />
          print("Привет,", name){'\n'}
          <br />
          prnt(name)
        </div>
      </div>
      <div style={{position: 'absolute', left: 1040, top: 200, opacity: ed}}>
        <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 32, color: theme.accent2, marginBottom: 16}}>Редактор кода</div>
        <div style={{width: 760, height: 380, borderRadius: 14, background: '#1E1E24', border: `2px solid ${theme.accent2}`, paddingTop: 24}}>
          <CodeLine n={1} text={'name = input("Имя: ")'} />
          <CodeLine n={2} text={'print("Привет,", name)'} />
          <div style={{position: 'relative'}}>
            <CodeLine n={3} text={'prnt(name)'} />
            <div style={{position: 'absolute', left: 94, bottom: 4, width: 74, height: 4, background: `repeating-linear-gradient(90deg, ${theme.red} 0 6px, transparent 6px 10px)`, opacity: r(n(ev, 'feat2'), 0.4)}} />
          </div>
        </div>
      </div>
      <div style={{position: 'absolute', top: 690, width: '100%', display: 'flex', justifyContent: 'center', gap: 30}}>
        {feats.map((f) => (
          <div key={f.k} style={{padding: '20px 34px', borderRadius: 999, background: 'rgba(34,211,238,0.10)', border: `2px solid ${theme.accent2}`, fontFamily: fonts.body, fontWeight: 800, fontSize: 30, color: theme.text, opacity: r(n(ev, f.k), 0.5), translate: `0 ${(1 - r(n(ev, f.k), 0.5)) * 30}px`}}>
            {f.t}
          </div>
        ))}
      </div>
      <div style={{position: 'absolute', top: 840, width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 26, opacity: vs, scale: interpolate(vs, [0, 1], [0.9, 1])}}>
        <div style={{width: 84, height: 84, borderRadius: 20, background: '#2F80ED', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: fonts.mono, fontWeight: 800, fontSize: 34, color: '#fff'}}>{'<>'}</div>
        <div style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 56, color: theme.text}}>VS Code</div>
        <div style={{fontFamily: fonts.body, fontWeight: 700, fontSize: 32, color: theme.green}}>бесплатный · миллионы программистов</div>
      </div>
    </AbsoluteFill>
  );
};

// ================================================================ установка VS Code
export const VsInstallScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const sec = useSec();
  const ev = d.ev;
  const wiz = sec >= n(ev, 'wizard');
  const tasks = sec >= n(ev, 'tasks');
  const installing = sec >= n(ev, 'install');
  const done = sec >= n(ev, 'done') + 1.2;
  const prog = r(n(ev, 'install') + 0.2, Math.max(0.5, n(ev, 'done') + 1.0 - n(ev, 'install')), (x) => x);
  const checks = [
    {k: 'chk1', t: 'Создать значок на рабочем столе'},
    {k: 'chk2', t: 'Добавить «Открыть с помощью Code» в меню файла'},
    {k: 'chk3', t: 'Добавить «Открыть с помощью Code» в меню папки'},
    {k: 'chk4', t: 'Добавить в PATH', key: true},
  ];
  const btn = {x: 1380, y: 885};
  const path = !wiz
    ? [{t: 0, x: 1300, y: 750}, {t: n(ev, 'click_dl') - 0.9, x: 1300, y: 750}, {t: n(ev, 'click_dl'), x: 560, y: 560}]
    : !tasks
      ? [{t: 0, x: 900, y: 700}, {t: n(ev, 'accept') - 0.6, x: 900, y: 700}, {t: n(ev, 'accept'), x: 436, y: 637}]
      : [
          {t: 0, x: 900, y: 700},
          ...checks.map((c, i) => ({t: n(ev, c.k), x: 436, y: 344 + i * 66})),
          {t: n(ev, 'next') - 0.1, x: btn.x, y: btn.y},
          {t: n(ev, 'install'), x: btn.x, y: btn.y},
        ];
  const clicks = [n(ev, 'click_dl'), n(ev, 'accept'), ...checks.map((c) => n(ev, c.k) + 0.05), n(ev, 'next'), n(ev, 'install')];
  return (
    <AbsoluteFill>
      <Desktop dim={wiz ? 0.35 : 0} />
      {!wiz ? (
        <WindowFrame x={210} y={110} w={1500} h={850} title="Visual Studio Code — Download" appear={n(ev, 'site')}>
          <div style={{position: 'absolute', inset: 0, background: '#141821', fontFamily: fonts.body}}>
            <div style={{height: 60, background: '#161D2B', display: 'flex', alignItems: 'center', padding: '0 24px', gap: 20}}>
              <span style={{color: theme.muted, fontSize: 26}}>← → ⟳</span>
              <div style={{flex: 1, height: 40, borderRadius: 20, background: '#0C111B', display: 'flex', alignItems: 'center', padding: '0 20px', fontSize: 22, fontWeight: 600, color: theme.text}}>
                <span style={{color: theme.green, marginRight: 10}}>🔒</span>https://code.visualstudio.com
              </div>
            </div>
            <div style={{padding: '80px 120px'}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 20}}>
                <div style={{width: 64, height: 64, borderRadius: 14, background: '#2F80ED', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: fonts.mono, fontWeight: 800, fontSize: 26, color: '#fff'}}>{'<>'}</div>
                <span style={{fontWeight: 800, fontSize: 40, color: '#fff'}}>Visual Studio Code</span>
              </div>
              <div style={{marginTop: 50, fontWeight: 800, fontSize: 60, color: '#fff', width: 800, lineHeight: 1.15}}>Бесплатный редактор кода</div>
              <div style={{marginTop: 60, width: 460, height: 86, borderRadius: 14, background: sec >= n(ev, 'click_dl') ? '#2B6FD6' : '#2F80ED', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 30, color: '#fff'}}>
                Download for Windows
              </div>
            </div>
          </div>
        </WindowFrame>
      ) : (
        <WindowFrame x={360} y={150} w={1200} h={800} title="Установка — Visual Studio Code" light appear={n(ev, 'wizard')}>
          <div style={{position: 'absolute', inset: 0, background: '#F7F8FA', padding: '40px 60px', fontFamily: fonts.body, color: '#1F2633'}}>
            {!tasks ? (
              <>
                <div style={{fontWeight: 800, fontSize: 36}}>Лицензионное соглашение</div>
                <div style={{marginTop: 24, height: 280, borderRadius: 8, border: '1px solid #CBD2DC', background: '#fff', padding: 24, fontSize: 20, color: '#4A5568', lineHeight: 1.5}}>
                  Пожалуйста, прочитайте следующее лицензионное соглашение. Вы должны принять условия этого соглашения, прежде чем продолжить установку…
                </div>
                <div style={{marginTop: 40, display: 'flex', alignItems: 'center', gap: 16, fontSize: 26, fontWeight: 700}}>
                  <div style={{width: 30, height: 30, borderRadius: '50%', border: `3px solid ${theme.accent}`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                    {sec >= n(ev, 'accept') ? <div style={{width: 14, height: 14, borderRadius: '50%', background: theme.accent}} /> : null}
                  </div>
                  Я принимаю условия соглашения
                </div>
              </>
            ) : !installing ? (
              <>
                <div style={{fontWeight: 800, fontSize: 36}}>Выберите дополнительные задачи</div>
                <div style={{marginTop: 50, display: 'flex', flexDirection: 'column', gap: 34}}>
                  {checks.map((c) => {
                    const on = sec >= n(ev, c.k) + 0.05;
                    return (
                      <div key={c.k} style={{display: 'flex', alignItems: 'center', gap: 20, fontSize: 26, fontWeight: c.key ? 800 : 600}}>
                        <div style={{width: 32, height: 32, borderRadius: 6, border: `2.5px solid ${on ? theme.accent : '#7A8699'}`, background: on ? theme.accent : '#fff', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, fontSize: 22, boxShadow: c.key && on ? '0 0 0 6px rgba(52,211,153,0.4)' : 'none'}}>{on ? '✓' : ''}</div>
                        {c.t}
                      </div>
                    );
                  })}
                </div>
              </>
            ) : !done ? (
              <>
                <div style={{fontWeight: 800, fontSize: 36}}>Установка…</div>
                <div style={{marginTop: 80, height: 26, borderRadius: 13, background: '#E2E8F0', overflow: 'hidden'}}>
                  <div style={{height: 26, width: `${prog * 100}%`, background: `linear-gradient(90deg, ${theme.accent}, ${theme.accent2})`}} />
                </div>
              </>
            ) : (
              <>
                <div style={{fontWeight: 800, fontSize: 40}}>Установка завершена</div>
                <div style={{marginTop: 50, width: 120, height: 120, borderRadius: '50%', background: theme.green, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 70, fontWeight: 900}}>✓</div>
              </>
            )}
            {!done ? (
              <div style={{position: 'absolute', right: 60, bottom: 40, display: 'flex', gap: 16}}>
                <div style={{padding: '14px 40px', borderRadius: 8, background: theme.accent, color: '#fff', fontWeight: 800, fontSize: 24}}>{tasks && !installing ? 'Далее (Next)' : installing ? 'Установить' : 'Далее'}</div>
              </div>
            ) : null}
          </div>
        </WindowFrame>
      )}
      <Cursor path={path} clicks={clicks} />
      {wiz && tasks && !installing ? (
        <Highlight show={n(ev, 'chk4')} hide={n(ev, 'next')} x={408} y={532} w={330} h={48} label="обязательно!" labelPos="right" color={theme.green} />
      ) : null}
      <ChapterTag step="ШАГ 4" title="Устанавливаем VS Code" />
    </AbsoluteFill>
  );
};

// ================================================================ интерфейс VS Code и расширение
export const VsUiScene: React.FC<{d: SceneData}> = ({d}) => {
  const sec = useSec();
  const r = useRamp();
  const ev = d.ev;
  const extMode = sec >= n(ev, 'ext_click');
  const q = typedNow(tp(ev, 'type:ext'), sec);
  const installed = sec >= n(ev, 'ext_install') + 1.0;
  const installBtn = {x: SIDE_X + 255, y: BODY + 200};
  const sidebar = extMode ? (
    <div style={{padding: '0 16px'}}>
      <div style={{height: 40, borderRadius: 6, border: `1.5px solid ${q ? theme.accent : '#3A4357'}`, background: '#14161C', display: 'flex', alignItems: 'center', padding: '0 12px', fontSize: 19, color: '#E1E6EF'}}>
        {q || <span style={{color: '#6B7891'}}>Search Extensions</span>}
      </div>
      {q.length >= 6 ? (
        <div style={{marginTop: 18, display: 'flex', gap: 14, padding: 12, borderRadius: 8, background: '#2A2F3B'}}>
          <div style={{width: 54, height: 54, borderRadius: 10, background: '#3B77C9', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <PyLogo size={34} />
          </div>
          <div style={{flex: 1}}>
            <div style={{fontSize: 20, fontWeight: 800, color: '#fff'}}>Python</div>
            <div style={{fontSize: 15, color: '#9AA4B5'}}>Microsoft ✓</div>
            <div style={{marginTop: 8, display: 'inline-block', padding: '4px 14px', borderRadius: 4, background: installed ? '#2B3242' : '#2F80ED', color: '#fff', fontSize: 15, fontWeight: 700}}>
              {installed ? 'Installed' : sec >= n(ev, 'ext_install') ? 'Installing…' : 'Install'}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  ) : (
    <div style={{padding: '30px 20px', fontSize: 19, color: '#9AA4B5', lineHeight: 1.6}}>Папка не открыта.{'\n'}Откройте папку, чтобы начать.</div>
  );
  const editor = (
    <div style={{padding: '80px 90px', fontFamily: fonts.body}}>
      <div style={{fontSize: 54, fontWeight: 800, color: '#C8D0DC'}}>Visual Studio Code</div>
      <div style={{marginTop: 14, fontSize: 26, color: '#7D879A'}}>Editing evolved</div>
      <div style={{marginTop: 50, fontSize: 24, color: '#4C8DFF', lineHeight: 1.9}}>
        New File…
        <br />
        Open Folder…
      </div>
    </div>
  );
  return (
    <AbsoluteFill>
      <Background />
      <VSCodeWindow active={extMode ? 4 : 0} sidebarTitle={extMode ? 'EXTENSIONS' : 'EXPLORER'} sidebar={sidebar} editor={editor} panelK={r(n(ev, 'lbl_term'), 0.5) * (1 - r(n(ev, 'ext_card'), 0.5))} panel={<div style={{color: '#6B7891'}}>здесь будет терминал</div>} />
      <Highlight show={n(ev, 'lbl_files')} hide={n(ev, 'ext_card')} x={SIDE_X} y={BODY} w={330} h={VY + 900 - BODY} label="файлы проекта" labelPos="right" />
      <Highlight show={n(ev, 'lbl_code')} hide={n(ev, 'ext_card')} x={ED_X + 20} y={BODY + 60} w={1000} h={400} label="место для кода" />
      <Highlight show={n(ev, 'lbl_term')} hide={n(ev, 'ext_card')} x={ED_X + 10} y={VY + 900 - 250} w={1200} h={240} label="терминал" labelPos="top" color={theme.green} />
      <Highlight show={n(ev, 'lbl_bar')} hide={n(ev, 'ext_card')} x={VX + 4} y={BODY + 6} w={48} h={330} label="панели" labelPos="right" color={theme.violet} />
      <Explainer show={n(ev, 'ext_card')} hide={n(ev, 'ext_install') + 2} term="Расширение" text="Дополнение, которое добавляет редактору новые возможности. Для Python — подсветка, подсказки и запуск." x={1180} y={300} w={600} />
      <Cursor path={[{t: 0, x: 1100, y: 600}, {t: n(ev, 'ext_click') - 1, x: 1100, y: 600}, {t: n(ev, 'ext_click'), x: ACT_X, y: actY(4)}, {t: tp(ev, 'type:ext').t - 0.6, x: ACT_X, y: actY(4)}, {t: tp(ev, 'type:ext').t, x: SIDE_X + 150, y: BODY + 70}, {t: n(ev, 'ext_install') - 0.8, x: SIDE_X + 150, y: BODY + 70}, {t: n(ev, 'ext_install'), x: installBtn.x - 120, y: installBtn.y - 20}]} clicks={[n(ev, 'ext_click'), tp(ev, 'type:ext').t, n(ev, 'ext_install')]} />
      <ChapterTag step="ШАГ 5" title="Знакомимся с VS Code" />
    </AbsoluteFill>
  );
};

// ================================================================ папка и файл
export const ProjectScene: React.FC<{d: SceneData}> = ({d}) => {
  const sec = useSec();
  const r = useRamp();
  const ev = d.ev;
  const menuOpen = sec >= n(ev, 'menu_file') && sec < n(ev, 'menu_open') + 0.4;
  const opened = sec >= n(ev, 'opened');
  const fname = typedNow(tp(ev, 'type:fname'), sec);
  const fileDone = sec >= tp(ev, 'type:fname').times[tp(ev, 'type:fname').times.length - 1] + 0.4;
  const newFile = sec >= n(ev, 'new_file');
  const folderK = r(n(ev, 'folder'), 0.5) * (1 - r(n(ev, 'menu_file') - 0.6, 0.4));
  const sidebar = opened ? (
    <div style={{padding: '0 20px', fontSize: 20, color: '#E1E6EF'}}>
      <div style={{fontWeight: 800, letterSpacing: 1}}>⌄ PYTHON_COURSE</div>
      {newFile ? (
        <div style={{marginTop: 10, marginLeft: 20, display: 'flex', alignItems: 'center', gap: 10, padding: '4px 8px', borderRadius: 4, border: fileDone ? 'none' : `1.5px solid ${theme.accent}`, background: fileDone ? '#2A3040' : '#14161C'}}>
          <span style={{color: '#F2C94C', fontFamily: fonts.mono, fontSize: 15}}>py</span>
          <span style={{fontFamily: fonts.mono}}>{fname}</span>
        </div>
      ) : null}
    </div>
  ) : (
    <div style={{padding: '30px 20px', fontSize: 19, color: '#9AA4B5'}}>Папка не открыта.</div>
  );
  return (
    <AbsoluteFill>
      <Background />
      <VSCodeWindow sidebar={sidebar} tabs={fileDone ? [{name: 'main.py'}] : []} editor={fileDone ? <div style={{paddingTop: 20}}><CodeLine n={1} text="" /></div> : null} menuOpen={menuOpen} menuHl={sec >= n(ev, 'menu_open') ? 5 : -1} />
      {folderK > 0 ? (
        <div style={{position: 'absolute', inset: 0, opacity: folderK}}>
          <Desktop />
          <div style={{position: 'absolute', left: 860, top: 380, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, scale: interpolate(r(n(ev, 'folder') + 0.3, 0.5), [0, 1], [0.6, 1])}}>
            <div style={{width: 170, height: 130, borderRadius: 14, background: '#F2C14E', boxShadow: '0 20px 50px rgba(0,0,0,0.4)'}} />
            <div style={{padding: '6px 14px', borderRadius: 6, background: 'rgba(76,141,255,0.6)', fontFamily: fonts.body, fontWeight: 800, fontSize: 30, color: '#fff'}}>python_course</div>
          </div>
        </div>
      ) : null}
      <Cursor path={[{t: 0, x: 1000, y: 600}, {t: n(ev, 'menu_file') - 0.8, x: 1000, y: 600}, {t: n(ev, 'menu_file'), x: VX + 72, y: VY + 22}, {t: n(ev, 'menu_open') - 0.6, x: VX + 72, y: VY + 22}, {t: n(ev, 'menu_open'), x: VX + 200, y: VY + 40 + 8 + 5 * 37 + 18}]} clicks={[n(ev, 'menu_file'), n(ev, 'menu_open')]} appear={n(ev, 'menu_file') - 0.8} />
      <Explainer show={n(ev, 'py_card')} term=".py" text="Окончание файла. Говорит компьютеру и редактору, что внутри — код на Python." x={1180} y={420} w={560} />
      <ChapterTag step="ШАГ 6" title="Папка проекта и файл" />
    </AbsoluteFill>
  );
};

// ================================================================ первая программа
export const FirstProgScene: React.FC<{d: SceneData}> = ({d}) => {
  const sec = useSec();
  const r = useRamp();
  const ev = d.ev;
  const code = tp(ev, 'type:code');
  const typed = typedNow(code, sec);
  const saved = sec >= n(ev, 'save') + 0.3;
  const termK = r(n(ev, 'term_open'), 0.5);
  const out = sec >= n(ev, 'term_out');
  const keys = r(n(ev, 'save') - 0.2, 0.3) * (1 - r(n(ev, 'save') + 1.4, 0.3));
  const sidebar = (
    <div style={{padding: '0 20px', fontSize: 20, color: '#E1E6EF'}}>
      <div style={{fontWeight: 800, letterSpacing: 1}}>⌄ PYTHON_COURSE</div>
      <div style={{marginTop: 10, marginLeft: 20, display: 'flex', alignItems: 'center', gap: 10, padding: '4px 8px', borderRadius: 4, background: '#2A3040'}}>
        <span style={{color: '#F2C94C', fontFamily: fonts.mono, fontSize: 15}}>py</span>
        <span style={{fontFamily: fonts.mono}}>main.py</span>
      </div>
    </div>
  );
  const editor = (
    <div style={{paddingTop: 20}}>
      <CodeLine n={1} text={typed + (sec < code.times[code.times.length - 1] + 0.3 && Math.floor(sec * 2) % 2 === 0 ? '|' : '')} />
    </div>
  );
  const panel = out ? (
    <>
      <div style={{color: '#8E98AA', fontSize: 19}}>PS C:\Users\User\Desktop\python_course&gt; &amp; python main.py</div>
      <div style={{color: '#fff', fontWeight: 700, fontSize: 28}}>Привет, мир!</div>
      <div style={{color: '#8E98AA', fontSize: 19}}>PS C:\Users\User\Desktop\python_course&gt;</div>
    </>
  ) : null;
  const congrats = r(n(ev, 'congrats'), 0.6) * (1 - r(n(ev, 'term_hint'), 0.4));
  return (
    <AbsoluteFill>
      <Background />
      <VSCodeWindow sidebar={sidebar} tabs={[{name: 'main.py', dirty: typed.length > 0 && !saved}]} editor={editor} panel={panel} panelK={termK} runHl={sec >= n(ev, 'move_run') + 0.8 && sec < n(ev, 'click_run') + 0.4} />
      <Explainer show={n(ev, 'print_card')} hide={n(ev, 'save') - 0.3} term="print()" text="Команда, которая выводит текст на экран. Текст пишем в кавычках внутри скобок." x={1170} y={330} w={560} />
      <div style={{position: 'absolute', top: 420, width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 30, opacity: keys}}>
        <Keycap label="Ctrl" press={n(ev, 'save')} w={200} />
        <span style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 60, color: theme.muted}}>+</span>
        <Keycap label="S" press={n(ev, 'save') + 0.05} />
      </div>
      <Cursor path={[{t: 0, x: 1200, y: 520}, {t: n(ev, 'move_run'), x: 1200, y: 520}, {t: n(ev, 'move_run') + 0.9, x: RUN_BTN.x, y: RUN_BTN.y}]} clicks={[n(ev, 'click_run')]} appear={n(ev, 'move_run') - 0.5} />
      <Highlight show={n(ev, 'term_hint')} hide={n(ev, 'term_hint2')} x={ED_X + 18} y={VY + 900 - 196} w={720} h={36} label="VS Code запускает Python" labelPos="top" color={theme.violet} />
      <Highlight show={n(ev, 'term_hint2')} x={ED_X + 18} y={VY + 900 - 160} w={230} h={46} label="результат программы" labelPos="right" color={theme.green} />
      <div style={{position: 'absolute', top: 300, width: '100%', display: 'flex', justifyContent: 'center', opacity: congrats, scale: interpolate(congrats, [0, 1], [0.85, 1])}}>
        <div style={{padding: '30px 60px', borderRadius: 28, background: 'rgba(14,20,34,0.95)', border: `2px solid ${theme.green}`, boxShadow: '0 30px 90px rgba(0,0,0,0.6)', fontFamily: fonts.display, fontWeight: 800, fontSize: 54, color: theme.green}}>
          Первая программа работает!
        </div>
      </div>
      <ChapterTag step="ШАГ 7" title="Первая программа" />
    </AbsoluteFill>
  );
};

// ================================================================ частые ошибки
export const ErrorsScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const ev = d.ev;
  const items = [
    {k: 'e1', bad: 'Print("Привет")', err: "NameError: name 'Print' is not defined", good: 'print("Привет")', tip: 'Только маленькие буквы'},
    {k: 'e2', bad: 'print(Привет)', err: "NameError: name 'Привет' is not defined", good: 'print("Привет")', tip: 'Текст — в кавычках'},
    {k: 'e3', bad: 'main.py ●', err: 'Запускается старая версия кода', good: 'Ctrl + S', tip: 'Сохраняйте файл'},
  ];
  return (
    <AbsoluteFill>
      <Background />
      <Title top={130}>Три частые ошибки</Title>
      <div style={{position: 'absolute', top: 290, left: 110, right: 110, display: 'flex', gap: 36}}>
        {items.map((it, i) => {
          const k = r(n(ev, it.k), 0.5);
          const fix = r(n(ev, it.k) + 2.2, 0.5);
          return (
            <Card key={it.k} k={k} style={{flex: 1, height: 560, padding: 36, display: 'flex', flexDirection: 'column', gap: 22}}>
              <div style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 30, color: theme.muted}}>Ошибка {i + 1}</div>
              <div style={{fontFamily: fonts.mono, fontSize: 30, color: theme.red, padding: '14px 18px', borderRadius: 10, background: 'rgba(255,107,107,0.10)', border: `1.5px solid ${theme.red}`}}>{it.bad}</div>
              <div style={{fontFamily: fonts.mono, fontSize: 20, color: '#FF9C9C', lineHeight: 1.4}}>{it.err}</div>
              <div style={{marginTop: 'auto', opacity: fix}}>
                <div style={{fontFamily: fonts.mono, fontSize: 30, color: theme.green, padding: '14px 18px', borderRadius: 10, background: 'rgba(52,211,153,0.10)', border: `1.5px solid ${theme.green}`}}>{it.good}</div>
                <div style={{marginTop: 16, fontFamily: fonts.body, fontWeight: 800, fontSize: 30, color: theme.text}}>{it.tip}</div>
              </div>
            </Card>
          );
        })}
      </div>
      <Brand />
    </AbsoluteFill>
  );
};

// ================================================================ итоги и домашнее задание
export const RecapScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const ev = d.ev;
  const items = [
    {k: 'r1', t: 'Скачали Python и поставили галочку PATH'},
    {k: 'r2', t: 'Открыли командную строку и проверили версию'},
    {k: 'r3', t: 'Установили VS Code и расширение Python'},
    {k: 'r4', t: 'Запустили первую программу'},
  ];
  return (
    <AbsoluteFill>
      <Background />
      <Title top={150}>Что мы сделали</Title>
      <div style={{position: 'absolute', top: 320, left: 360, right: 360, display: 'flex', flexDirection: 'column', gap: 30}}>
        {items.map((it) => {
          const k = r(n(ev, it.k), 0.5);
          return (
            <div key={it.k} style={{display: 'flex', alignItems: 'center', gap: 30, opacity: k, translate: `${(1 - k) * -40}px 0`}}>
              <div style={{width: 70, height: 70, borderRadius: '50%', background: theme.green, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0B0F17', fontSize: 40, fontWeight: 900, scale: interpolate(k, [0, 1], [0.5, 1])}}>✓</div>
              <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 44, color: theme.text}}>{it.t}</div>
            </div>
          );
        })}
      </div>
      <Brand />
    </AbsoluteFill>
  );
};

export const FinalScene: React.FC<{d: SceneData}> = ({d}) => {
  const r = useRamp();
  const ev = d.ev;
  const hw = r(n(ev, 'hw'), 0.6);
  const nx = r(n(ev, 'next'), 0.6);
  const sb = r(n(ev, 'sub'), 0.6);
  return (
    <AbsoluteFill>
      <Background />
      <div style={{position: 'absolute', top: 150, left: 200, right: 200, opacity: hw}}>
        <Card k={1} style={{padding: '44px 54px', border: `2px solid ${theme.accent2}`}}>
          <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 24, letterSpacing: 3, color: theme.accent2}}>ДОМАШНЕЕ ЗАДАНИЕ</div>
          <div style={{marginTop: 18, fontFamily: fonts.body, fontWeight: 700, fontSize: 40, color: theme.text, lineHeight: 1.35}}>
            Поменяйте текст в кавычках на своё имя и запустите программу ещё раз
          </div>
          <div style={{marginTop: 26, fontFamily: fonts.mono, fontSize: 34}}>
            <span style={{color: '#DCDCAA'}}>print</span>
            <span style={{color: '#D4D4D4'}}>(</span>
            <span style={{color: '#CE9178'}}>"Привет, я Алиджон!"</span>
            <span style={{color: '#D4D4D4'}}>)</span>
          </div>
        </Card>
      </div>
      <div style={{position: 'absolute', top: 620, width: '100%', textAlign: 'center', opacity: nx, translate: `0 ${(1 - nx) * 20}px`}}>
        <div style={{fontFamily: fonts.body, fontWeight: 700, fontSize: 34, color: theme.muted}}>Следующий урок</div>
        <div style={{marginTop: 10, fontFamily: fonts.display, fontWeight: 800, fontSize: 64, color: theme.text}}>
          Команда <span style={{color: theme.accent}}>print()</span> подробно
        </div>
      </div>
      <div style={{position: 'absolute', top: 860, width: '100%', display: 'flex', justifyContent: 'center', opacity: sb, scale: interpolate(sb, [0, 1], [0.85, 1])}}>
        <div style={{padding: '22px 60px', borderRadius: 999, background: theme.red, fontFamily: fonts.body, fontWeight: 800, fontSize: 38, color: '#fff', boxShadow: '0 20px 60px rgba(255,107,107,0.35)'}}>Подписаться на канал</div>
      </div>
      <Brand />
    </AbsoluteFill>
  );
};

export const LESSON_SCENES: Record<string, React.FC<{d: SceneData}>> = {
  intro: IntroScene,
  plan: PlanScene,
  what: WhatScene,
  browser: BrowserScene,
  installer: InstallerScene,
  progress: ProgressScene,
  cmdwhat: CmdWhatScene,
  cmdopen: CmdOpenScene,
  terminal: TerminalScene,
  repl: ReplScene,
  editor: EditorScene,
  vsinstall: VsInstallScene,
  vsui: VsUiScene,
  project: ProjectScene,
  firstprog: FirstProgScene,
  errors: ErrorsScene,
  recap: RecapScene,
  outro: FinalScene,
};
