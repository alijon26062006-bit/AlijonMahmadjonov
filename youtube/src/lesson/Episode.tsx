import React from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Sequence, staticFile, useVideoConfig} from 'remotion';
import {SceneFade} from '../components/common';
import {KINDS, LessonScene} from './kinds';
import '../fonts';

export type LessonData = {episode: {num: number; title: string; brand: string}; total: number; scenes: LessonScene[]};

/** Урок целиком: сцены по таймингам из JSON + общая звуковая дорожка. */
export const LessonEpisode: React.FC<{data: LessonData; audio: string}> = ({data, audio}) => {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{backgroundColor: '#0B0F17'}}>
      {data.scenes.map((sc) => {
        const Kind = KINDS[sc.kind];
        return (
          <Sequence key={sc.id} name={sc.id} from={Math.round(sc.start * fps)} durationInFrames={Math.round(sc.dur * fps)}>
            <SceneFade dur={sc.dur}>
              <Kind d={sc} brand={data.episode.brand} />
            </SceneFade>
          </Sequence>
        );
      })}
      <Audio src={staticFile(audio)} />
    </AbsoluteFill>
  );
};
