/**
 * Шаблоны сцен для уроков (урок 2 и дальше). Каждая сцена получает данные из
 * src/data/<ep>.json: kind, params (из сценария), события ev и реплики.
 */
import React from 'react';
import {AbsoluteFill, interpolate} from 'remotion';
import {Background, Brand, ChapterTag, Cursor, Explainer, Typed, typedNow, useRamp, useSec} from '../components/common';
import {CodeLine, ED_X, RUN_BTN, VSCodeWindow, VY} from '../components/vscode';
import {fonts, theme} from '../theme';

export type LessonScene = {
  id: string;
  kind: string;
  params: Record<string, any>;
  start: number;
  dur: number;
  lines: {start: number; dur: number; text: string}[];
  ev: Record<string, number | Typed>;
};
type P = {d: LessonScene; brand: string};

const ev = (d: LessonScene, k: string) => d.ev[k] as number;
const has = (d: LessonScene, k: string | null | undefined) => !!k && d.ev[k] !== undefined;

const Card: React.FC<{k: number; style?: React.CSSProperties; children: React.ReactNode}> = ({k, style, children}) => (
  <div
    style={{
      borderRadius: 26,
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

const Title: React.FC<{children: React.ReactNode; top?: number}> = ({children, top = 150}) => {
  const r = useRamp();
  const k = r(0.15, 0.5);
  return (
    <div style={{position: 'absolute', top, width: '100%', textAlign: 'center', fontFamily: fonts.display, fontWeight: 800, fontSize: 64, color: theme.text, opacity: k, translate: `0 ${(1 - k) * 20}px`}}>
      {children}
    </div>
  );
};

/** Карточки-пояснения, которые показываются по событиям: [ключ, ключ_скрытия|null, термин, текст]. */
const Explains: React.FC<{d: LessonScene; x?: number; y?: number; w?: number}> = ({d, x = 1220, y = 220, w = 520}) => (
  <>
    {(d.params.explain || []).map((e: any[]) => {
      const [k, hideK, term, text] = e.length === 4 ? e : [e[0], null, e[1], e[2]];
      if (!has(d, k)) return null;
      return <Explainer key={k} show={ev(d, k)} hide={has(d, hideK) ? ev(d, hideK) - 0.2 : 1e9} term={term} text={text} x={x} y={y} w={w} />;
    })}
  </>
);

// ================================================================ заставка урока
export const TitleKind: React.FC<P> = ({d, brand}) => {
  const r = useRamp();
  const p = d.params;
  const pop = r(ev(d, 'title') + 0.2, 0.7);
  const sub = r(ev(d, 'subtitle'), 0.7);
  const chipsOn = (p.chips || []).some((c: string[]) => has(d, c[0]) && 0 < 1);
  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', translate: `0 ${chipsOn ? -60 : 0}px`}}>
        <div style={{opacity: r(0.1, 0.5), fontFamily: fonts.body, fontWeight: 800, fontSize: 30, letterSpacing: 6, color: theme.accent2, padding: '12px 28px', borderRadius: 999, border: '2px solid rgba(34,211,238,0.5)', background: 'rgba(34,211,238,0.08)'}}>
          {p.top.toUpperCase()}
        </div>
        <div style={{marginTop: 34, fontFamily: fonts.display, fontWeight: 800, fontSize: 190, lineHeight: 1, color: theme.text, opacity: pop, scale: interpolate(pop, [0, 1], [0.8, 1]), textShadow: '0 20px 80px rgba(76,141,255,0.45)'}}>
          {p.big}
        </div>
        <div style={{marginTop: 40, fontFamily: fonts.body, fontWeight: 700, fontSize: 64, color: theme.accent, opacity: sub, translate: `0 ${(1 - sub) * 30}px`}}>{p.sub}</div>
        <div style={{marginTop: 70, display: 'flex', gap: 26}}>
          {(p.chips || []).map((c: string[]) => {
            const k = has(d, c[0]) ? r(ev(d, c[0]), 0.5) : 0;
            return (
              <div key={c[0]} style={{padding: '18px 34px', borderRadius: 999, background: 'rgba(76,141,255,0.12)', border: `2px solid ${theme.accent}`, fontFamily: fonts.body, fontWeight: 800, fontSize: 32, color: theme.text, opacity: k, translate: `0 ${(1 - k) * 30}px`}}>
                {c[1]}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
      <Brand text={brand} />
    </AbsoluteFill>
  );
};

// ================================================================ карточки-понятия
export const CardsKind: React.FC<P> = ({d, brand}) => {
  const r = useRamp();
  const p = d.params;
  return (
    <AbsoluteFill>
      <Background />
      <Title>{p.title}</Title>
      <div style={{position: 'absolute', top: 330, left: 130, right: 130, display: 'flex', gap: 44}}>
        {p.cards.map((c: string[], i: number) => {
          const k = r(ev(d, c[0]), 0.6);
          return (
            <Card key={c[0]} k={k} style={{flex: 1, height: 420, padding: 46, display: 'flex', flexDirection: 'column', gap: 24, border: `1.5px solid ${k > 0.5 ? 'rgba(34,211,238,0.45)' : theme.border}`}}>
              <div style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 72, color: 'rgba(255,255,255,0.08)'}}>0{i + 1}</div>
              <div style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 46, color: theme.text}}>{c[1]}</div>
              <div style={{fontFamily: fonts.body, fontWeight: 600, fontSize: 32, color: '#C9D2E3', lineHeight: 1.4, whiteSpace: 'pre-line'}}>{c[2]}</div>
            </Card>
          );
        })}
      </div>
      <Explains d={d} x={560} y={790} w={800} />
      <Brand text={brand} />
    </AbsoluteFill>
  );
};

// ================================================================ разбор строки кода
export const SyntaxKind: React.FC<P> = ({d, brand}) => {
  const r = useRamp();
  const sec = useSec();
  const p = d.params;
  const code: string = p.code;
  const CW = 96 * 0.6;
  const x0 = 960 - (CW * code.length) / 2;
  const y0 = 470;
  const parts: any[] = p.parts;
  const active = parts.filter((pt) => has(d, pt[0]) && sec >= ev(d, pt[0]));
  const current = active.length ? active[active.length - 1][0] : null;
  return (
    <AbsoluteFill>
      <Background />
      <Title>{p.title}</Title>
      {parts.map(([k, s, e, label, side]) => {
        if (!has(d, k)) return null;
        const kk = r(ev(d, k), 0.4);
        if (kk <= 0) return null;
        const cur = k === current;
        const col = cur ? theme.accent2 : '#5D7A99';
        const bx0 = x0 + s * CW - 8;
        const bx1 = x0 + e * CW + 8;
        const down = side === 'down';
        return (
          <React.Fragment key={k}>
            <div style={{position: 'absolute', left: bx0, top: y0 - 12, width: bx1 - bx0, height: 140, borderRadius: 16, background: cur ? 'rgba(34,211,238,0.12)' : 'rgba(255,255,255,0.03)', border: `2px solid ${col}`, opacity: kk}} />
            <div style={{position: 'absolute', left: (bx0 + bx1) / 2 - 300, width: 600, textAlign: 'center', top: down ? y0 + 160 : y0 - 90, fontFamily: fonts.body, fontWeight: 800, fontSize: 36, color: col, opacity: kk, translate: `0 ${(1 - kk) * (down ? 15 : -15)}px`}}>
              {down ? '↑ ' : ''}
              {label}
              {down ? '' : ' ↓'}
            </div>
          </React.Fragment>
        );
      })}
      <div style={{position: 'absolute', left: x0, top: y0, opacity: r(0.3, 0.5)}}>
        <CodeBig text={code} />
      </div>
      <Explains d={d} x={560} y={800} w={800} />
      <Brand text={brand} />
    </AbsoluteFill>
  );
};

const CodeBig: React.FC<{text: string}> = ({text}) => (
  <div style={{transform: 'scale(3.2)', transformOrigin: '0 0', width: 'max-content'}}>
    <CodeLine n={0} text={text} noNum />
  </div>
);

// ================================================================ код в VS Code: печать, запуск, вывод
const CMD = 'PS C:\\Users\\User\\Desktop\\python_course> python main.py';

export const CodeKind: React.FC<P> = ({d}) => {
  const sec = useSec();
  const r = useRamp();
  const p = d.params;
  const code: string[] = p.code;
  const runs = Object.keys(d.ev)
    .filter((k) => k.startsWith('run'))
    .sort((a, b) => ev(d, a) - ev(d, b));
  const firstRun = runs.length ? ev(d, runs[0]) : 1e9;
  const panelHeight = p.panel || 300;
  // строки кода: набранные к этому моменту
  let typingLine = -1;
  // правки: [номер строки, новый текст]; событие retype:i допечатывает конец новой строки
  const edits: Record<number, string> = Object.fromEntries((p.edits || []).map((e: [number, string]) => [e[0], e[1]]));
  const shown = code.map((line, i) => {
    const rt = d.ev[`retype:${i}`] as Typed | undefined;
    if (rt && edits[i] !== undefined && sec >= rt.t) {
      if (sec < rt.times[rt.times.length - 1] + 0.2) typingLine = i;
      return edits[i].slice(0, edits[i].length - rt.text.length) + typedNow(rt, sec);
    }
    const t = d.ev[`type:${i}`] as Typed | undefined;
    if (!t) return line;
    if (sec < t.t) return null;
    if (sec < t.times[t.times.length - 1] + 0.2) typingLine = i;
    return typedNow(t, sec);
  });
  const blink = Math.floor(sec * 2) % 2 === 0;
  const editor = (
    <div style={{paddingTop: 20}}>
      {shown.map((txt, i) => (txt === null ? null : <CodeLine key={i} n={i + 1} text={txt + (i === typingLine && blink ? '|' : '')} />))}
    </div>
  );
  // вывод в терминале
  const rows: {text: string; kind: 'cmd' | 'out' | 'err'}[] = [];
  runs.forEach((rk) => {
    if (sec < ev(d, rk)) return;
    rows.push({text: CMD, kind: 'cmd'});
    (p.out || []).forEach((o: string[]) => {
      const grp = o[2] || 'run';
      if (grp === rk && has(d, o[0]) && sec >= ev(d, o[0])) rows.push({text: o[1], kind: o[3] === 'err' ? 'err' : 'out'});
    });
  });
  const maxRows = Math.floor((panelHeight - 60) / 35);
  const panel = (
    <>
      {rows.slice(-maxRows).map((row, i) => (
        <div key={i} style={{color: row.kind === 'cmd' ? '#8E98AA' : row.kind === 'err' ? '#FF8A8A' : '#fff', fontSize: row.kind === 'out' ? 24 : row.kind === 'err' ? 21 : 19, fontWeight: row.kind === 'cmd' ? 400 : 700, whiteSpace: 'pre', minHeight: 35}}>
          {row.text}
        </div>
      ))}
    </>
  );
  // курсор мыши: подходит к ▶ перед каждым запуском
  const rest = {x: 1250, y: 640};
  const path = [{t: 0, ...rest}];
  runs.forEach((rk) => {
    const t = ev(d, rk);
    path.push({t: t - 0.9, ...rest}, {t, x: RUN_BTN.x, y: RUN_BTN.y}, {t: t + 0.6, x: RUN_BTN.x, y: RUN_BTN.y}, {t: t + 1.4, ...rest});
  });
  path.sort((a, b) => a.t - b.t);
  const sidebar = (
    <div style={{padding: '0 20px', fontSize: 20, color: '#E1E6EF'}}>
      <div style={{fontWeight: 800, letterSpacing: 1}}>⌄ PYTHON_COURSE</div>
      <div style={{marginTop: 10, marginLeft: 20, display: 'flex', alignItems: 'center', gap: 10, padding: '4px 8px', borderRadius: 4, background: '#2A3040'}}>
        <span style={{color: '#F2C94C', fontFamily: fonts.mono, fontSize: 15}}>py</span>
        <span style={{fontFamily: fonts.mono}}>main.py</span>
      </div>
    </div>
  );
  const runHl = runs.some((rk) => sec >= ev(d, rk) - 0.3 && sec < ev(d, rk) + 0.3);
  return (
    <AbsoluteFill>
      <Background />
      <VSCodeWindow sidebar={sidebar} tabs={[{name: 'main.py'}]} editor={editor} panel={panel} panelK={r(firstRun, 0.5)} panelHeight={panelHeight} runHl={runHl} />
      {runs.length ? <Cursor path={path} clicks={runs.map((rk) => ev(d, rk))} appear={firstRun - 1.2} /> : null}
      {/* explainAt: [сдвиг от левого края редактора, сдвиг от верха окна, ширина] — когда строки кода длинные */}
      <Explains d={d} x={ED_X + (p.explainAt?.[0] ?? 650)} y={VY + (p.explainAt?.[1] ?? 120)} w={p.explainAt?.[2] ?? 560} />
      {p.chapter ? <ChapterTag step={p.chapter[0]} title={p.chapter[1]} /> : null}
    </AbsoluteFill>
  );
};

// ================================================================ переменные — коробки в памяти
// ops: [ключ, 'new' | 'set' | 'print', имя коробки, значение (для print — что на экране), строка кода, тип]
const valColor = (v: string) => (/^["']/.test(v) ? '#CE9178' : '#B5CEA8');
const BOX_W = 400;
const BOX_GAP = 70;

export const MemoryKind: React.FC<P> = ({d, brand}) => {
  const r = useRamp();
  const sec = useSec();
  const p = d.params;
  const ops = (p.ops as any[])
    .filter((o) => has(d, o[0]))
    .map((o) => ({k: o[0] as string, t: ev(d, o[0]), op: o[1] as string, box: o[2] as string, value: o[3] as string, code: o[4] as string | undefined, type: o[5] as string | undefined}))
    .sort((a, b) => a.t - b.t);
  const past = ops.filter((o) => o.t <= sec);
  const code = [...past].reverse().find((o) => o.code);
  const prints = past.filter((o) => o.op === 'print');
  const names: string[] = p.boxes;
  const x0 = 960 - (names.length * BOX_W + (names.length - 1) * BOX_GAP) / 2;
  const center: React.CSSProperties = {position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: fonts.mono, fontWeight: 700, fontSize: 60};
  return (
    <AbsoluteFill>
      <Background />
      <Title top={110}>{p.title}</Title>
      {code ? (
        <div key={code.k} style={{position: 'absolute', top: 240, width: '100%', display: 'flex', justifyContent: 'center', opacity: r(code.t, 0.35)}}>
          <div style={{padding: '10px 30px', borderRadius: 14, background: '#0B0E14', border: `1.5px solid ${theme.border}`, scale: 1.6}}>
            <CodeLine n={0} text={code.code!} noNum />
          </div>
        </div>
      ) : null}
      {names.map((name, i) => {
        const mine = ops.filter((o) => o.box === name && o.op !== 'print');
        const done = mine.filter((o) => o.t <= sec);
        if (!done.length) return null;
        const cur = done[done.length - 1];
        const prev = done.length > 1 ? done[done.length - 2] : null;
        const appear = r(mine[0].t, 0.5);
        const kIn = r(cur.t, 0.7);
        const reading = prints.some((o) => o.box === name && sec < o.t + 1.4);
        const col = reading ? theme.accent2 : theme.accent;
        return (
          <div key={name} style={{position: 'absolute', left: x0 + i * (BOX_W + BOX_GAP), top: 370, width: BOX_W, opacity: appear, translate: `0 ${(1 - appear) * 40}px`}}>
            <div style={{display: 'inline-block', marginLeft: 26, padding: '8px 24px', borderRadius: '12px 12px 0 0', background: col, fontFamily: fonts.mono, fontWeight: 700, fontSize: 34, color: '#0B0F17'}}>{name}</div>
            <div style={{position: 'relative', height: 240, borderRadius: 24, overflow: 'hidden', border: `3px solid ${col}`, background: 'linear-gradient(160deg, rgba(76,141,255,0.10), rgba(15,20,32,0.9))', boxShadow: reading ? '0 0 70px rgba(34,211,238,0.45)' : '0 30px 80px rgba(0,0,0,0.35)'}}>
              {prev && kIn < 1 ? (
                <div style={{...center, color: valColor(prev.value), opacity: 1 - kIn, translate: `${kIn * 260}px ${kIn * 60}px`, rotate: `${kIn * 25}deg`}}>{prev.value}</div>
              ) : null}
              <div style={{...center, color: valColor(cur.value), opacity: kIn, translate: `0 ${(1 - kIn) * -150}px`}}>{cur.value}</div>
            </div>
            {cur.type ? (
              <div style={{marginTop: 16, display: 'flex', justifyContent: 'center', opacity: kIn}}>
                <div style={{padding: '8px 22px', borderRadius: 999, background: 'rgba(34,211,238,0.12)', border: `2px solid ${theme.accent2}`, fontFamily: fonts.body, fontWeight: 800, fontSize: 26, color: theme.text}}>
                  {cur.type}
                </div>
              </div>
            ) : null}
          </div>
        );
      })}
      {prints.length ? (
        <div style={{position: 'absolute', left: 160, top: 760, width: 700, padding: '20px 30px', borderRadius: 18, background: '#0B0E14', border: `1.5px solid ${theme.border}`, opacity: r(prints[0].t, 0.4)}}>
          <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 20, letterSpacing: 3, color: theme.muted}}>ЭКРАН (ВЫВОД print)</div>
          {prints.slice(-3).map((o) => (
            <div key={o.k} style={{marginTop: 8, fontFamily: fonts.mono, fontSize: 36, fontWeight: 700, color: '#fff', opacity: r(o.t + 0.3, 0.4)}}>
              {o.value}
            </div>
          ))}
        </div>
      ) : null}
      <Explains d={d} x={1000} y={790} w={760} />
      {p.chapter ? <ChapterTag step={p.chapter[0]} title={p.chapter[1]} /> : null}
      <Brand text={brand} />
    </AbsoluteFill>
  );
};

// ================================================================ ошибки
export const ErrorsKind: React.FC<P> = ({d, brand}) => {
  const r = useRamp();
  const p = d.params;
  return (
    <AbsoluteFill>
      <Background />
      <Title top={120}>{p.title}</Title>
      <div style={{position: 'absolute', top: 260, left: 100, right: 100, display: 'flex', gap: 34}}>
        {p.items.map(([k, fk, bad, err, good, tip]: any[], i: number) => {
          const kk = has(d, k) ? r(ev(d, k), 0.5) : 0;
          const fix = has(d, fk) ? r(ev(d, fk), 0.5) : 0;
          return (
            <Card key={k} k={kk} style={{flex: 1, height: 560, padding: 34, display: 'flex', flexDirection: 'column', gap: 18}}>
              <div style={{fontFamily: fonts.display, fontWeight: 800, fontSize: 30, color: theme.muted}}>Ошибка {i + 1}</div>
              <div style={{fontFamily: fonts.mono, fontSize: 30, color: theme.red, padding: '14px 18px', borderRadius: 10, background: 'rgba(255,107,107,0.10)', border: `1.5px solid ${theme.red}`}}>{bad}</div>
              <div style={{fontFamily: fonts.mono, fontSize: 21, color: '#FF9C9C', lineHeight: 1.5, padding: '12px 16px', borderRadius: 10, background: '#0B0E14'}}>
                {err.map((ln: string, j: number) => (
                  <div key={j} style={{color: j === 0 ? '#8E98AA' : '#FF9C9C', fontWeight: j === err.length - 1 || j === 1 ? 700 : 400}}>
                    {ln}
                  </div>
                ))}
              </div>
              <div style={{marginTop: 'auto', opacity: fix}}>
                <div style={{fontFamily: fonts.mono, fontSize: 30, color: theme.green, padding: '14px 18px', borderRadius: 10, background: 'rgba(52,211,153,0.10)', border: `1.5px solid ${theme.green}`}}>{good}</div>
                <div style={{marginTop: 14, fontFamily: fonts.body, fontWeight: 800, fontSize: 30, color: theme.text}}>✓ {tip}</div>
              </div>
            </Card>
          );
        })}
      </div>
      <Explains d={d} x={560} y={845} w={800} />
      <Brand text={brand} />
    </AbsoluteFill>
  );
};

// ================================================================ итоги
export const RecapKind: React.FC<P> = ({d, brand}) => {
  const r = useRamp();
  const p = d.params;
  return (
    <AbsoluteFill>
      <Background />
      <Title top={150}>{p.title}</Title>
      <div style={{position: 'absolute', top: 320, left: 300, right: 300, display: 'flex', flexDirection: 'column', gap: 32}}>
        {p.items.map(([k, t]: string[]) => {
          const kk = r(ev(d, k), 0.5);
          return (
            <div key={k} style={{display: 'flex', alignItems: 'center', gap: 30, opacity: kk, translate: `${(1 - kk) * -40}px 0`}}>
              <div style={{width: 70, height: 70, flexShrink: 0, borderRadius: '50%', background: theme.green, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0B0F17', fontSize: 40, fontWeight: 900, scale: interpolate(kk, [0, 1], [0.5, 1])}}>✓</div>
              <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 44, color: theme.text}}>{t}</div>
            </div>
          );
        })}
      </div>
      <Brand text={brand} />
    </AbsoluteFill>
  );
};

// ================================================================ домашка и анонс
export const FinalKind: React.FC<P> = ({d, brand}) => {
  const r = useRamp();
  const p = d.params;
  const hw = r(ev(d, 'hw'), 0.6);
  const nx = r(ev(d, 'next'), 0.6);
  const sb = r(ev(d, 'sub'), 0.6);
  return (
    <AbsoluteFill>
      <Background />
      <div style={{position: 'absolute', top: 150, left: 200, right: 200}}>
        <Card k={hw} style={{padding: '44px 54px', border: `2px solid ${theme.accent2}`}}>
          <div style={{fontFamily: fonts.body, fontWeight: 800, fontSize: 24, letterSpacing: 3, color: theme.accent2}}>ДОМАШНЕЕ ЗАДАНИЕ</div>
          <div style={{marginTop: 18, fontFamily: fonts.body, fontWeight: 700, fontSize: 40, color: theme.text, lineHeight: 1.35}}>{p.hw}</div>
          <div style={{marginTop: 26}}>
            <CodeLine n={1} text={p.code} />
          </div>
        </Card>
      </div>
      <div style={{position: 'absolute', top: 640, width: '100%', textAlign: 'center', opacity: nx, translate: `0 ${(1 - nx) * 20}px`}}>
        <div style={{fontFamily: fonts.body, fontWeight: 700, fontSize: 34, color: theme.muted}}>Следующий урок</div>
        <div style={{marginTop: 10, fontFamily: fonts.display, fontWeight: 800, fontSize: 70, color: theme.text}}>{p.next}</div>
      </div>
      <div style={{position: 'absolute', top: 880, width: '100%', display: 'flex', justifyContent: 'center', opacity: sb, scale: interpolate(sb, [0, 1], [0.85, 1])}}>
        <div style={{padding: '22px 60px', borderRadius: 999, background: theme.red, fontFamily: fonts.body, fontWeight: 800, fontSize: 38, color: '#fff', boxShadow: '0 20px 60px rgba(255,107,107,0.35)'}}>Подписаться на канал</div>
      </div>
      <Brand text={brand} />
    </AbsoluteFill>
  );
};

export const KINDS: Record<string, React.FC<P>> = {
  title: TitleKind,
  cards: CardsKind,
  syntax: SyntaxKind,
  code: CodeKind,
  memory: MemoryKind,
  errors: ErrorsKind,
  recap: RecapKind,
  final: FinalKind,
};
