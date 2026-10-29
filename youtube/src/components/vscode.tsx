import React from 'react';
import {interpolate} from 'remotion';
import {fonts, theme} from '../theme';
import {useRamp} from './common';

// Окно редактора на экране 1920×1080
export const VX = 160;
export const VY = 100;
export const VW = 1600;
export const VH = 900;
export const BODY = VY + 44; // верх рабочей области (под строкой меню)
export const ACT_X = VX + 28; // центр значков на левой полоске
export const actY = (i: number) => BODY + 34 + i * 62; // 0 файлы, 1 поиск, 2 git, 3 запуск, 4 расширения
export const SIDE_X = VX + 56;
export const SIDE_W = 330;
export const ED_X = SIDE_X + SIDE_W;
export const RUN_BTN = {x: VX + VW - 46, y: BODY + 21};
export const PANEL_H = 250;

const ActIcon: React.FC<{i: number; active: boolean}> = ({i, active}) => {
  const c = active ? '#E8EDF5' : '#6B7891';
  const paths = [
    'M6 3h8l4 4v14H6z M14 3v4h4', // файлы
    'M10 4a6 6 0 1 1 0 12a6 6 0 0 1 0-12 M15 15l5 5', // поиск
    'M7 4v16 M7 8c6 0 10 2 10 8 M17 4v4', // git
    'M7 5l12 7-12 7z', // запуск
    'M4 4h7v7H4z M13 13h7v7h-7z M4 13h7v7H4z M14.5 3.5l5 5-5 5-5-5z', // расширения
  ];
  return (
    <div style={{position: 'absolute', left: VX, top: actY(i) - 24, width: 56, height: 48, display: 'flex', alignItems: 'center', justifyContent: 'center', borderLeft: active ? '3px solid #4C8DFF' : '3px solid transparent'}}>
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round">
        <path d={paths[i]} />
      </svg>
    </div>
  );
};

export const Menu: React.FC<{open: boolean; hl?: number}> = ({open, hl = -1}) => {
  if (!open) return null;
  const items = ['New Text File', 'New File...', 'New Window', '—', 'Open File...', 'Open Folder...', 'Open Recent', '—', 'Save', 'Save As...'];
  return (
    <div style={{position: 'absolute', left: VX + 60, top: VY + 40, width: 330, padding: '8px 0', borderRadius: 10, background: '#252B38', border: '1px solid #3A4357', boxShadow: '0 20px 60px rgba(0,0,0,0.5)', zIndex: 30, fontFamily: fonts.body, fontSize: 21, color: '#D5DCE8'}}>
      {items.map((it, i) =>
        it === '—' ? (
          <div key={i} style={{height: 1, background: '#3A4357', margin: '6px 0'}} />
        ) : (
          <div key={i} style={{padding: '7px 22px', background: i === hl ? '#2F5FC4' : 'transparent', color: i === hl ? '#fff' : '#D5DCE8'}}>
            {it}
          </div>
        ),
      )}
    </div>
  );
};

/** Окно VS Code. Содержимое боковой панели, редактора и терминала передаётся снаружи. */
export const VSCodeWindow: React.FC<{
  active?: number;
  sidebarTitle?: string;
  sidebar?: React.ReactNode;
  tabs?: {name: string; dirty?: boolean}[];
  editor?: React.ReactNode;
  panel?: React.ReactNode;
  panelK?: number;
  menuOpen?: boolean;
  menuHl?: number;
  appear?: number;
  runHl?: boolean;
  panelHeight?: number;
}> = ({active = 0, sidebarTitle = 'EXPLORER', sidebar, tabs = [], editor, panel, panelK = 0, menuOpen = false, menuHl, appear = 0, runHl = false, panelHeight = PANEL_H}) => {
  const r = useRamp();
  const k = r(appear, 0.45);
  const panelH = panelHeight * panelK;
  return (
    <div style={{position: 'absolute', inset: 0, opacity: k, scale: interpolate(k, [0, 1], [0.96, 1])}}>
      <div style={{position: 'absolute', left: VX, top: VY, width: VW, height: VH, borderRadius: 14, overflow: 'hidden', background: '#1E1E24', boxShadow: '0 40px 120px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08)'}}>
        {/* строка меню */}
        <div style={{height: 44, background: '#181A20', display: 'flex', alignItems: 'center', padding: '0 18px', gap: 26, fontFamily: fonts.body, fontWeight: 600, fontSize: 19, color: '#B8C1D1'}}>
          <div style={{width: 24, height: 24, borderRadius: 6, background: '#2F80ED', color: '#fff', fontSize: 14, fontWeight: 900, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{'<>'}</div>
          {['File', 'Edit', 'Selection', 'View', 'Go', 'Run', 'Terminal', 'Help'].map((m) => (
            <span key={m} style={{color: m === 'File' && menuOpen ? '#fff' : undefined, background: m === 'File' && menuOpen ? '#2F3747' : undefined, padding: '4px 8px', borderRadius: 6}}>
              {m}
            </span>
          ))}
          <div style={{flex: 1}} />
          <span style={{opacity: 0.7}}>Visual Studio Code</span>
          <div style={{flex: 1}} />
          <span style={{display: 'flex', gap: 26, opacity: 0.7}}>
            <span>—</span>
            <span>☐</span>
            <span>✕</span>
          </span>
        </div>
        {/* левая полоска */}
        <div style={{position: 'absolute', left: 0, top: 44, bottom: 0, width: 56, background: '#181A20'}} />
        {/* боковая панель */}
        <div style={{position: 'absolute', left: 56, top: 44, bottom: 0, width: SIDE_W, background: '#20232B', borderRight: '1px solid #2B2F3A', fontFamily: fonts.body}}>
          <div style={{padding: '14px 20px', fontSize: 17, fontWeight: 700, letterSpacing: 1.5, color: '#9AA4B5'}}>{sidebarTitle}</div>
          {sidebar}
        </div>
        {/* вкладки */}
        <div style={{position: 'absolute', left: 56 + SIDE_W, right: 0, top: 44, height: 42, background: '#1A1C23', display: 'flex'}}>
          {tabs.map((tb) => (
            <div key={tb.name} style={{padding: '0 22px', display: 'flex', alignItems: 'center', gap: 12, background: '#1E1E24', borderTop: '2px solid #4C8DFF', fontFamily: fonts.body, fontWeight: 600, fontSize: 19, color: '#E1E6EF'}}>
              <span style={{color: '#F2C94C', fontFamily: fonts.mono, fontSize: 16}}>py</span>
              {tb.name}
              <span style={{width: 12, textAlign: 'center', color: '#E1E6EF'}}>{tb.dirty ? '●' : '✕'}</span>
            </div>
          ))}
          <div style={{flex: 1}} />
          {tabs.length ? (
            <div style={{width: 46, display: 'flex', alignItems: 'center', justifyContent: 'center', background: runHl ? 'rgba(76,141,255,0.25)' : 'transparent', borderRadius: 8}}>
              <svg width="22" height="22" viewBox="0 0 24 24">
                <path d="M7 5l12 7-12 7z" fill="#E1E6EF" />
              </svg>
            </div>
          ) : null}
        </div>
        {/* редактор */}
        <div style={{position: 'absolute', left: 56 + SIDE_W, right: 0, top: 86, bottom: panelH, overflow: 'hidden'}}>{editor}</div>
        {/* нижняя панель */}
        {panelK > 0 ? (
          <div style={{position: 'absolute', left: 56 + SIDE_W, right: 0, bottom: 0, height: panelH, background: '#181A20', borderTop: '1px solid #2F3442', overflow: 'hidden'}}>
            <div style={{display: 'flex', gap: 30, padding: '12px 24px', fontFamily: fonts.body, fontWeight: 700, fontSize: 16, color: '#8E98AA', letterSpacing: 1}}>
              <span>PROBLEMS</span>
              <span>OUTPUT</span>
              <span style={{color: '#E1E6EF', borderBottom: '2px solid #4C8DFF', paddingBottom: 4}}>TERMINAL</span>
            </div>
            <div style={{padding: '4px 24px', fontFamily: fonts.mono, fontSize: 22, color: '#D6DEEB', lineHeight: 1.6}}>{panel}</div>
          </div>
        ) : null}
      </div>
      {[0, 1, 2, 3, 4].map((i) => (
        <ActIcon key={i} i={i} active={i === active} />
      ))}
      <Menu open={menuOpen} hl={menuHl} />
    </div>
  );
};

/** Строка кода с простой подсветкой Python. */
export const CodeLine: React.FC<{text: string; n: number; noNum?: boolean}> = ({text, n, noNum}) => {
  const parts: React.ReactNode[] = [];
  const re = /(#.*$)|("[^"]*"?|'[^']*'?)|(\b(?:print|input|exit)\b)|(\b(?:sep|end)(?==))|(\b\d+(?:\.\d+)?\b)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(<span key={i++}>{text.slice(last, m.index)}</span>);
    const col = m[1] ? '#6A9955' : m[2] ? '#CE9178' : m[3] ? '#DCDCAA' : m[4] ? '#9CDCFE' : '#B5CEA8';
    parts.push(
      <span key={i++} style={{color: col}}>
        {m[0]}
      </span>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(<span key={i++}>{text.slice(last)}</span>);
  return (
    <div style={{display: 'flex', fontFamily: fonts.mono, fontSize: 30, lineHeight: 1.7}}>
      {noNum ? null : <span style={{width: 70, color: '#5A6478', textAlign: 'right', paddingRight: 24}}>{n}</span>}
      <span style={{color: '#D4D4D4', whiteSpace: 'pre'}}>{parts}</span>
    </div>
  );
};

export {theme};
