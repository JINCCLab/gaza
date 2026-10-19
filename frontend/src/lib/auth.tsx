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
import { api, type User } from "./api";

type AuthState = {
  users: User[];
  user: User | null;
  setUserId: (id: number) => void;
  refresh: () => Promise<void>;
  loading: boolean;
  error: string | null;
};

const AuthContext = createContext<AuthState | null>(null);

const STORAGE_KEY = "dp_user_id";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [users, setUsers] = useState<User[]>([]);
  const [userId, setUserIdState] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      await api.seed();
      const list = await api.users();
      setUsers(list);
      const stored = Number(localStorage.getItem(STORAGE_KEY) || "");
      const next =
        list.find((u) => u.id === stored)?.id ??
        list.find((u) => u.role === "admin")?.id ??
        list[0]?.id ??
        null;
      setUserIdState(next);
      if (next != null) localStorage.setItem(STORAGE_KEY, String(next));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setUserId = (id: number) => {
    setUserIdState(id);
    localStorage.setItem(STORAGE_KEY, String(id));
  };

  const user = useMemo(
    () => users.find((u) => u.id === userId) ?? null,
    [users, userId]
  );

  const value = useMemo(
    () => ({ users, user, setUserId, refresh, loading, error }),
    [users, user, refresh, loading, error]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}
