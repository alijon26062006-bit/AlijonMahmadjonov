import React from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Background, EASE} from '../components/common';
import {fonts, theme} from '../theme';
import '../fonts';

const CL = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/** Заставка канала на 5 секунд: скобки < > съезжаются, удар, появляется «Python с нуля». */
export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const s = (sec: number) => sec * fps;
  // скобки летят к центру и встречаются в момент удара (1.15 с)
  const fly = interpolate(frame, [s(0.1), s(1.15)], [0, 1], {...CL, easing: EASE});
  const hit = spring({frame: frame - s(1.15), fps, config: {damping: 9, stiffness: 160}});
  const ring = interpolate(frame, [s(1.15), s(2.2)], [0, 1], CL);
  const title = spring({frame: frame - s(1.35), fps, config: {damping: 14, stiffness: 110}});
  const sub = interpolate(frame, [s(1.9), s(2.5)], [0, 1], {...CL, easing: EASE});
  const line = interpolate(frame, [s(2.1), s(3.0)], [0, 1], {...CL, easing: EASE});
  const out = interpolate(frame, [durationInFrames - s(0.5), durationInFrames], [1, 0], CL);
  const flash = frame < s(1.15) ? 0 : interpolate(frame, [s(1.15), s(1.45)], [0.32, 0], CL);
  const shake = frame >= s(1.15) && frame < s(1.45) ? Math.sin(frame * 3.1) * (1 - (frame - s(1.15)) / s(0.3)) * 10 : 0;

  return (
    <AbsoluteFill style={{opacity: out, translate: `${shake}px ${shake * 0.6}px`}}>
      <Background />
      {/* волна от удара */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '37%',
          width: 200,
          height: 200,
          marginLeft: -100,
          marginTop: -100,
          borderRadius: '50%',
          border: `4px solid ${theme.accent2}`,
          scale: 1 + ring * 9,
          opacity: frame < s(1.15) ? 0 : (1 - ring) * 0.7,
        }}
      />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
        {/* скобки < > */}
        <div style={{display: 'flex', alignItems: 'center', height: 220, translate: `0 ${-title * 110}px`, scale: 1 - title * 0.35}}>
          <span style={{fontFamily: fonts.mono, fontWeight: 700, fontSize: 200, color: theme.accent, translate: `${(1 - fly) * -900}px 0`, opacity: fly, textShadow: `0 0 60px ${theme.accent}`}}>
            {'<'}
          </span>
          <span style={{width: interpolate(hit, [0, 1], [10, 70]), height: 150, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <span style={{fontFamily: fonts.mono, fontWeight: 700, fontSize: 200, color: theme.accent2, opacity: hit, scale: hit}}>/</span>
          </span>
          <span style={{fontFamily: fonts.mono, fontWeight: 700, fontSize: 200, color: theme.accent, translate: `${(1 - fly) * 900}px 0`, opacity: fly, textShadow: `0 0 60px ${theme.accent}`}}>
            {'>'}
          </span>
        </div>
        {/* название */}
        <div
          style={{
            marginTop: -40,
            fontFamily: fonts.display,
            fontWeight: 800,
            fontSize: 150,
            color: theme.text,
            opacity: Math.min(1, title * 1.4),
            scale: interpolate(title, [0, 1], [0.8, 1]),
            letterSpacing: interpolate(title, [0, 1], [30, 0]),
            textShadow: '0 20px 80px rgba(76,141,255,0.45)',
          }}
        >
          Python <span style={{color: theme.accent}}>с нуля</span>
        </div>
        <div style={{marginTop: 26, height: 6, width: 760 * line, borderRadius: 3, background: `linear-gradient(90deg, ${theme.accent}, ${theme.accent2})`}} />
        <div style={{marginTop: 28, fontFamily: fonts.body, fontWeight: 700, fontSize: 40, letterSpacing: 8, color: theme.muted, opacity: sub, translate: `0 ${(1 - sub) * 20}px`}}>
          КУРС ПРОГРАММИРОВАНИЯ
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{background: theme.accent2, opacity: flash, mixBlendMode: 'screen'}} />
      <Audio src={staticFile('intro/intro.wav')} />
    </AbsoluteFill>
  );
};
