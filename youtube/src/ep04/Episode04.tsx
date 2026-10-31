import React from 'react';
import data from '../data/ep04.json';
import {LessonData, LessonEpisode} from '../lesson/Episode';

export const Episode04: React.FC = () => <LessonEpisode data={data as unknown as LessonData} audio="ep04/soundtrack.wav" />;
export const EP04_FRAMES = Math.ceil(data.total * 30);
