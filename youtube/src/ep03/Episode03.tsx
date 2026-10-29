import React from 'react';
import data from '../data/ep03.json';
import {LessonData, LessonEpisode} from '../lesson/Episode';

export const Episode03: React.FC = () => <LessonEpisode data={data as unknown as LessonData} audio="ep03/soundtrack.wav" />;
export const EP03_FRAMES = Math.ceil(data.total * 30);
