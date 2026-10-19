"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setAccessTokenGetter, type AuthConfig, type User } from "./api";

const TOKEN_KEY = "dp_access_token";

type AuthState = {
  user: User | null;
  authMode: AuthConfig["mode"] | "unknown";
  loading: boolean;
  error: string | null;
  signedIn: boolean;
  signInDev: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
};

const AuthContext = createContext<AuthState | null>(null);

function readStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function writeStoredToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

/**
 * Session-based auth provider.
 * - Without NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: local Bearer JWT via /sign-in (dev).
 * - With Clerk key: wrap the tree in ClerkAuthRoot (see providers.tsx) which supplies tokens.
 */
export function DevAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<AuthState["authMode"]>("unknown");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const getAccessToken = useCallback(async () => token ?? readStoredToken(), [token]);

  useEffect(() => {
    setAccessTokenGetter(getAccessToken);
    return () => setAccessTokenGetter(null);
  }, [getAccessToken]);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      await api.seed();
      const cfg = await api.authConfig();
      setAuthMode(cfg.mode);
      const stored = readStoredToken();
      if (!stored) {
        setToken(null);
        setUser(null);
        return;
      }
      setToken(stored);
      const me = await api.me();
      setUser(me);
    } catch (e) {
      writeStoredToken(null);
      setToken(null);
      setUser(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signInDev = useCallback(async (email: string) => {
    setError(null);
    const res = await api.devLogin(email);
    writeStoredToken(res.access_token);
    setToken(res.access_token);
    setUser(res.user);
    setAuthMode("dev");
  }, []);

  const signOut = useCallback(async () => {
    writeStoredToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      authMode,
      loading,
      error,
      signedIn: !!user,
      signInDev,
      signOut,
      refresh,
      getAccessToken,
    }),
    [user, authMode, loading, error, signInDev, signOut, refresh, getAccessToken]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Used when Clerk supplies the session JWT; still loads /api/me for local roles. */
export function SessionAuthBridge({
  children,
  getToken,
  signedIn,
  clerkLoaded,
}: {
  children: ReactNode;
  getToken: () => Promise<string | null>;
  signedIn: boolean;
  clerkLoaded: boolean;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const getAccessToken = useCallback(async () => {
    try {
      return await getToken();
    } catch {
      return null;
    }
  }, [getToken]);

  useEffect(() => {
    setAccessTokenGetter(getAccessToken);
    return () => setAccessTokenGetter(null);
  }, [getAccessToken]);

  const refresh = useCallback(async () => {
    if (!clerkLoaded) return;
    setError(null);
    setLoading(true);
    try {
      await api.seed();
      if (!signedIn) {
        setUser(null);
        return;
      }
      const me = await api.me();
      setUser(me);
    } catch (e) {
      setUser(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [clerkLoaded, signedIn]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signOut = useCallback(async () => {
    // Clerk UserButton / signOut handled by Clerk; clear local mirror
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      authMode: "clerk" as const,
      loading: !clerkLoaded || loading,
      error,
      signedIn: signedIn && !!user,
      signInDev: async () => {
        throw new Error("Dev login disabled while Clerk is configured");
      },
      signOut,
      refresh,
      getAccessToken,
    }),
    [user, loading, error, signedIn, clerkLoaded, signOut, refresh, getAccessToken]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}

export { AuthContext };
