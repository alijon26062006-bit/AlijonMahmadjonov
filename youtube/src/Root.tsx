import React from 'react';
import {Composition} from 'remotion';
import data from './data/ep01.json';
import {Episode01} from './ep01/Episode01';
import {Intro} from './intro/Intro';
import {EP02_FRAMES, Episode02} from './ep02/Episode02';
import {EP03_FRAMES, Episode03} from './ep03/Episode03';
import {EP04_FRAMES, Episode04} from './ep04/Episode04';

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
    <Composition id="Ep02Print" component={Episode02} durationInFrames={EP02_FRAMES} fps={30} width={1920} height={1080} />
    <Composition id="Ep03Variables" component={Episode03} durationInFrames={EP03_FRAMES} fps={30} width={1920} height={1080} />
    <Composition id="Ep04Types" component={Episode04} durationInFrames={EP04_FRAMES} fps={30} width={1920} height={1080} />
    <Composition id="Intro" component={Intro} durationInFrames={150} fps={30} width={1920} height={1080} />
  </>
);
