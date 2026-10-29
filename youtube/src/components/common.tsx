import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {fonts, theme} from '../theme';

export const EASE = Easing.bezier(0.16, 1, 0.3, 1);
const CL = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/** 0..1 между двумя моментами (в секундах от начала сцены). */
export const useRamp = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (startSec: number, durSec = 0.5, easing = EASE) =>
    interpolate(frame, [startSec * fps, (startSec + durSec) * fps], [0, 1], {...CL, easing});
};

export const useSec = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return frame / fps;
};

/** Фон: тёмный градиент, сетка и виньетка. */
export const Background: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: theme.bg}}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(1100px 700px at ${50 + Math.sin(frame / 160) * 8}% ${
            42 + Math.cos(frame / 200) * 6
          }%, rgba(76,141,255,0.16), transparent 70%), radial-gradient(800px 600px at 85% 90%, rgba(155,135,245,0.10), transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
          maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 80%)',
        }}
      />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)'}} />
    </AbsoluteFill>
  );
};

/** Плавное появление и исчезновение сцены. */
export const SceneFade: React.FC<{dur: number; children: React.ReactNode}> = ({dur, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill
      style={{
        opacity: interpolate(frame, [0, 0.35 * fps, dur * fps - 0.3 * fps, dur * fps], [0, 1, 1, 0], CL),
        scale: interpolate(frame, [0, 0.6 * fps], [1.025, 1], {...CL, easing: EASE}),
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

/** Метка главы в левом верхнем углу. */
export const ChapterTag: React.FC<{step?: string; title: string}> = ({step, title}) => {
  const r = useRamp();
  const k = r(0.2, 0.6);
  return (
    <div
      style={{
        position: 'absolute',
        left: 72,
        top: 56,
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        opacity: k,
        translate: `${(1 - k) * -30}px 0`,
        fontFamily: fonts.body,
        fontWeight: 700,
        fontSize: 26,
        color: theme.text,
        zIndex: 20,
      }}
    >
      {step ? (
        <span
          style={{
            padding: '8px 16px',
            borderRadius: 999,
            background: 'rgba(16,28,52,0.9)',
            border: `1.5px solid ${theme.accent}`,
            color: theme.accent,
            letterSpacing: 1,
          }}
        >
          {step}
        </span>
      ) : null}
      <span style={{padding: '8px 18px', borderRadius: 999, background: 'rgba(11,15,23,0.78)'}}>{title}</span>
    </div>
  );
};

/** Подпись курса внизу слева. */
export const Brand: React.FC<{text?: string}> = ({text = 'PYTHON С НУЛЯ · УРОК 1'}) => (
  <div
    style={{
      position: 'absolute',
      left: 72,
      bottom: 44,
      fontFamily: fonts.body,
      fontWeight: 700,
      fontSize: 22,
      color: theme.muted,
      letterSpacing: 2,
      zIndex: 20,
    }}
  >
    {text}
  </div>
);

/** Окно программы с заголовком и кнопками. */
export const WindowFrame: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  light?: boolean;
  appear?: number;
  children: React.ReactNode;
}> = ({x, y, w, h, title, light, appear = 0, children}) => {
  const r = useRamp();
  const k = r(appear, 0.45);
  const bar = light ? '#E9ECF2' : '#1A2131';
  const body = light ? '#F7F8FA' : '#0F1420';
  const fg = light ? '#2A3140' : theme.text;
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        height: h,
        borderRadius: 14,
        overflow: 'hidden',
        background: body,
        boxShadow: '0 40px 120px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08)',
        opacity: k,
        scale: interpolate(k, [0, 1], [0.94, 1]),
        translate: `0 ${(1 - k) * 30}px`,
      }}
    >
      <div
        style={{
          height: 44,
          background: bar,
          display: 'flex',
          alignItems: 'center',
          padding: '0 18px',
          fontFamily: fonts.body,
          fontWeight: 600,
          fontSize: 18,
          color: fg,
          justifyContent: 'space-between',
        }}
      >
        <span>{title}</span>
        <span style={{display: 'flex', gap: 26, opacity: 0.7, fontSize: 18}}>
          <span>—</span>
          <span>☐</span>
          <span>✕</span>
        </span>
      </div>
      <div style={{position: 'absolute', top: 44, left: 0, right: 0, bottom: 0}}>{children}</div>
    </div>
  );
};

export type CursorPoint = {t: number; x: number; y: number};

/** Курсор мыши: двигается между точками и показывает клики. */
export const Cursor: React.FC<{path: CursorPoint[]; clicks: number[]; appear?: number}> = ({path, clicks, appear = 0}) => {
  const sec = useSec();
  let x = path[0].x;
  let y = path[0].y;
  for (let i = 0; i < path.length - 1; i++) {
    const a = path[i];
    const b = path[i + 1];
    if (sec >= a.t && sec <= b.t) {
      const k = EASE(Math.min(1, Math.max(0, (sec - a.t) / Math.max(0.001, b.t - a.t))));
      x = a.x + (b.x - a.x) * k;
      y = a.y + (b.y - a.y) * k;
      break;
    }
    if (sec > b.t) {
      x = b.x;
      y = b.y;
    }
  }
  const pressed = clicks.some((c) => sec >= c && sec < c + 0.12);
  const opacity = Math.min(1, Math.max(0, (sec - appear) / 0.3));
  return (
    <>
      {clicks.map((c) =>
        sec >= c && sec < c + 0.5 ? (
          <div
            key={c}
            style={{
              position: 'absolute',
              left: x - 30,
              top: y - 30,
              width: 60,
              height: 60,
              borderRadius: '50%',
              border: `3px solid ${theme.accent2}`,
              opacity: 1 - (sec - c) / 0.5,
              scale: 0.4 + (sec - c) * 2.2,
              zIndex: 49,
            }}
          />
        ) : null,
      )}
      <svg
        width={40}
        height={48}
        viewBox="0 0 20 24"
        style={{position: 'absolute', left: x - 4, top: y - 2, zIndex: 50, opacity, scale: pressed ? 0.88 : 1}}
      >
        <path
          d="M2 1 L2 19 L6.5 15 L9.5 22 L12.5 20.7 L9.6 14 L16 14 Z"
          fill="#fff"
          stroke="#111"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
      </svg>
    </>
  );
};

/** Рабочий стол: обои и панель задач. */
export const Desktop: React.FC<{dim?: number; terminalIcon?: boolean}> = ({dim = 0}) => {
  const icons = [
    {x: 840, kind: 'start'},
    {x: 905, kind: 'folder'},
    {x: 970, kind: 'browser'},
    {x: 1035, kind: 'terminal'},
  ];
  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(900px 600px at 25% 30%, #2B4C9B 0%, transparent 60%), radial-gradient(900px 700px at 80% 75%, #5B3FA8 0%, transparent 60%), linear-gradient(135deg, #10172A, #1A1433)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: 64,
          background: 'rgba(14,18,28,0.82)',
          borderTop: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        {icons.map((ic) => (
          <TaskIcon key={ic.kind} x={ic.x} kind={ic.kind} />
        ))}
        <div
          style={{
            position: 'absolute',
            right: 28,
            top: 18,
            fontFamily: fonts.body,
            fontWeight: 600,
            fontSize: 20,
            color: '#C9D2E3',
          }}
        >
          10:24
        </div>
      </div>
      <AbsoluteFill style={{background: `rgba(5,8,14,${dim})`}} />
    </AbsoluteFill>
  );
};

const TaskIcon: React.FC<{x: number; kind: string}> = ({x, kind}) => {
  const base: React.CSSProperties = {
    position: 'absolute',
    left: x - 22,
    top: 10,
    width: 44,
    height: 44,
    borderRadius: 10,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };
  if (kind === 'start')
    return (
      <div style={base}>
        <div style={{display: 'grid', gridTemplateColumns: '12px 12px', gap: 3}}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} style={{width: 12, height: 12, background: '#4CA3FF', borderRadius: 2}} />
          ))}
        </div>
      </div>
    );
  if (kind === 'folder')
    return (
      <div style={base}>
        <div style={{width: 30, height: 22, background: '#F2C14E', borderRadius: 4}} />
      </div>
    );
  if (kind === 'browser')
    return (
      <div style={base}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'conic-gradient(#4C8DFF 0 33%, #34D399 0 66%, #FF6B6B 0)',
            boxShadow: 'inset 0 0 0 7px rgba(255,255,255,0.0)',
          }}
        >
          <div style={{width: 14, height: 14, borderRadius: '50%', background: '#fff', margin: 9}} />
        </div>
      </div>
    );
  return (
    <div style={{...base, background: '#0C0C0C', border: '1px solid #3A3A3A'}}>
      <span style={{fontFamily: fonts.mono, color: '#E8EDF5', fontSize: 16, fontWeight: 700}}>{'>_'}</span>
    </div>
  );
};

/** Карточка «новое понятие»: появляется во время объяснения термина. */
export const Explainer: React.FC<{
  show: number;
  hide?: number;
  term: string;
  text: string;
  label?: string;
  color?: string;
  x?: number;
  y?: number;
  w?: number;
}> = ({show, hide = 1e9, term, text, label = 'НОВОЕ ПОНЯТИЕ', color = theme.accent2, x = 1260, y = 300, w = 580}) => {
  const r = useRamp();
  const k = r(show, 0.55) * (1 - r(hide, 0.4));
  if (k <= 0) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        padding: '30px 34px',
        borderRadius: 24,
        background: 'rgba(14,20,34,0.94)',
        border: `2px solid ${color}`,
        boxShadow: `0 30px 90px rgba(0,0,0,0.55), 0 0 40px ${color}33`,
        opacity: k,
        translate: `${(1 - k) * 60}px 0`,
        fontFamily: fonts.body,
        zIndex: 40,
      }}
    >
      <div style={{fontWeight: 800, fontSize: 18, letterSpacing: 3, color}}>{label}</div>
      <div style={{marginTop: 12, fontFamily: fonts.display, fontWeight: 800, fontSize: 36, color: theme.text, lineHeight: 1.15}}>
        {term}
      </div>
      <div style={{marginTop: 14, fontWeight: 600, fontSize: 27, color: '#C9D2E3', lineHeight: 1.4}}>{text}</div>
    </div>
  );
};

/** Клавиша клавиатуры; нажимается в момент press. */
export const Keycap: React.FC<{label: string; press?: number; w?: number}> = ({label, press = -1, w = 150}) => {
  const sec = useSec();
  const down = press >= 0 && sec >= press && sec < press + 0.25;
  return (
    <div
      style={{
        width: w,
        height: 130,
        borderRadius: 22,
        background: down ? '#2A3550' : '#1E2638',
        border: `2px solid ${down ? theme.accent2 : '#3A4766'}`,
        boxShadow: down ? '0 2px 0 #0B0F17' : '0 10px 0 #0B0F17',
        translate: `0 ${down ? 8 : 0}px`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: fonts.display,
        fontWeight: 800,
        fontSize: 48,
        color: down ? theme.accent2 : theme.text,
      }}
    >
      {label}
    </div>
  );
};

/** Набранный к моменту sec текст (для эффектов печати). */
export type Typed = {t: number; text: string; times: number[]};
export const typedNow = (tp: Typed, sec: number) => tp.text.slice(0, tp.times.filter((t) => t <= sec).length);

/** Рамка-подсветка с подписью. */
export const Highlight: React.FC<{show: number; hide?: number; x: number; y: number; w: number; h: number; label?: string; color?: string; labelPos?: 'top' | 'bottom' | 'right'}> = ({
  show,
  hide = 1e9,
  x,
  y,
  w,
  h,
  label,
  color = theme.accent2,
  labelPos = 'bottom',
}) => {
  const r = useRamp();
  const k = r(show, 0.4) * (1 - r(hide, 0.3));
  if (k <= 0) return null;
  const lp: React.CSSProperties =
    labelPos === 'top' ? {left: 0, bottom: h + 12} : labelPos === 'right' ? {left: w + 18, top: h / 2 - 22} : {left: 0, top: h + 12};
  return (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, zIndex: 45, opacity: k}}>
      <div style={{position: 'absolute', inset: 0, borderRadius: 12, border: `3px solid ${color}`, boxShadow: `0 0 24px ${color}66`, scale: interpolate(k, [0, 1], [1.08, 1])}} />
      {label ? (
        <div
          style={{
            position: 'absolute',
            ...lp,
            whiteSpace: 'nowrap',
            padding: '8px 16px',
            borderRadius: 10,
            background: color,
            color: '#0B0F17',
            fontFamily: fonts.body,
            fontWeight: 800,
            fontSize: 24,
          }}
        >
          {label}
        </div>
      ) : null}
    </div>
  );
};
