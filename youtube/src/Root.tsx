import React from 'react';
import {Composition} from 'remotion';
import data from './data/ep01.json';
import {Episode01} from './ep01/Episode01';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Ep01Install"
      component={Episode01}
      durationInFrames={Math.ceil(data.total * 30)}
      fps={30}
      width={1920}
      height={1080}
    />
  </>
);
