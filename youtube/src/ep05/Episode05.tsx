import React from 'react';
import data from '../data/ep05.json';
import {LessonData, LessonEpisode} from '../lesson/Episode';

export const Episode05: React.FC = () => <LessonEpisode data={data as unknown as LessonData} audio="ep05/soundtrack.wav" />;
export const EP05_FRAMES = Math.ceil(data.total * 30);
