'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

export type ThemeChoice = 'light' | 'dark' | 'system';

type ThemeState = {
  choice: ThemeChoice;
  setChoice: (choice: ThemeChoice) => void;
};

const ThemeContext = createContext<ThemeState | null>(null);
const STORAGE_KEY = 'averix-theme';

/**
 * Light, dark and system, in that order of respect for the person's own
 * settings: "system" stamps nothing and lets prefers-color-scheme decide.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>('system');

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as ThemeChoice | null;
      if (stored === 'light' || stored === 'dark' || stored === 'system') {
        setChoiceState(stored);
        apply(stored);
      }
    } catch {
      // A private window with storage blocked still gets a working product.
    }
  }, []);

  const setChoice = useCallback((next: ThemeChoice) => {
    setChoiceState(next);
    apply(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignored */
    }
  }, []);

  const value = useMemo(() => ({ choice, setChoice }), [choice, setChoice]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

function apply(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === 'system') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', choice);
  }
}

export function useTheme(): ThemeState {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used inside <ThemeProvider>');
  return context;
}

/**
 * Applied before first paint, so a person who chose dark never sees a white
 * flash on the way in.
 */
export const themeBootstrap = `(function(){try{var c=localStorage.getItem('${STORAGE_KEY}');if(c==='dark'||c==='light'){document.documentElement.setAttribute('data-theme',c);}}catch(e){}})();`;
