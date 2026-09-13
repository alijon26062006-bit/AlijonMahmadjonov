'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { ReactNode } from 'react';
import { ApiFailure, get, post, setCsrfToken } from './api';

export type Role = 'client' | 'developer' | 'admin' | 'moderator';

export type Session = {
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  active_role: Role;
  roles: Role[];
  status: string;
  email_verified: boolean;
  identity_verified: boolean;
  photo_url?: string;
  csrf_token?: string;
  permissions?: string[];
  onboarding_step?: number;
  onboarding_complete?: boolean;
};

type SessionState = {
  session: Session | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<Session>;
  signOut: () => Promise<void>;
  switchRole: (role: Role) => Promise<void>;
  can: (permission: string) => boolean;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({
  initial,
  children,
}: {
  initial?: Session | null;
  children: ReactNode;
}) {
  const [session, setSession] = useState<Session | null>(initial ?? null);
  const [loading, setLoading] = useState(initial === undefined);

  const refresh = useCallback(async () => {
    try {
      const next = await get<Session>('/auth/session');
      // A session without a user is not a session. Trusting the status code
      // alone is how a signed-out visitor ends up inside the signed-in shell,
      // watching every request fail with 401.
      if (next?.user_id) {
        setSession(next);
        if (next.csrf_token) setCsrfToken(next.csrf_token);
      } else {
        setSession(null);
        setCsrfToken(null);
      }
    } catch (error) {
      // Not being signed in is a state, not a failure.
      if (error instanceof ApiFailure && error.isUnauthenticated) {
        setSession(null);
        setCsrfToken(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const next = await post<Session>('/auth/login', { email, password });
    setSession(next);
    if (next.csrf_token) setCsrfToken(next.csrf_token);
    return next;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await post('/auth/logout');
    } finally {
      setSession(null);
      setCsrfToken(null);
    }
  }, []);

  const switchRole = useCallback(async (role: Role) => {
    // The API rotates the CSRF token on a role switch, and api() picks the new
    // one out of the response, so nothing here has to remember it.
    const next = await post<Session>('/auth/role/switch', { role });
    setSession(next);
  }, []);

  const can = useCallback(
    (permission: string) => Boolean(session?.permissions?.includes(permission)),
    [session],
  );

  const value = useMemo<SessionState>(
    () => ({ session, loading, refresh, signIn, signOut, switchRole, can }),
    [session, loading, refresh, signIn, signOut, switchRole, can],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/**
 * Sends a person to their own home when they open a screen that belongs to
 * the other side of the marketplace.
 *
 * Without this a developer who opens the client dashboard sees an empty page
 * and a 403 in the console: every request on it is refused by the API, which
 * is correct but useless to look at.
 */
export function useRoleGuard(role: Role) {
  const { session, loading } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (loading || !session || session.active_role === role) return;
    router.replace(session.active_role === 'client' ? '/dashboard' : session.active_role === 'developer' ? '/feed' : '/admin');
  }, [session, loading, role, router]);
  return session?.active_role === role;
}

export function useSession(): SessionState {
  const context = useContext(SessionContext);
  if (!context) throw new Error('useSession must be used inside <SessionProvider>');
  return context;
}
