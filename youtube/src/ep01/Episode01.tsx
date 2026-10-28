import React from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Sequence, staticFile, useVideoConfig} from 'remotion';
import data from '../data/ep01.json';
import {SceneFade} from '../components/common';
import {SceneData} from './scenes';
import {LESSON_SCENES as SCENES} from './lesson';
import '../fonts';

export const Episode01: React.FC = () => {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{backgroundColor: '#0B0F17'}}>
      {(data.scenes as unknown as SceneData[]).map((sc) => {
        const Scene = SCENES[sc.id];
        return (
          <Sequence key={sc.id} name={sc.id} from={Math.round(sc.start * fps)} durationInFrames={Math.round(sc.dur * fps)}>
            <SceneFade dur={sc.dur}>
              <Scene d={sc} />
            </SceneFade>
          </Sequence>
        );
      })}
      <Audio src={staticFile('ep01/soundtrack.wav')} />
    </AbsoluteFill>
  );
};
