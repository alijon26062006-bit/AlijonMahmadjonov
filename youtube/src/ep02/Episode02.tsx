import React from 'react';
import data from '../data/ep02.json';
import {LessonData, LessonEpisode} from '../lesson/Episode';

export const Episode02: React.FC = () => <LessonEpisode data={data as unknown as LessonData} audio="ep02/soundtrack.wav" />;
export const EP02_FRAMES = Math.ceil(data.total * 30);
