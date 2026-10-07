"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, getToken, setToken, type User } from "@/lib/api";

type AuthState = {
  user: User | null;
  loading: boolean; // true until we know whether a saved token is still valid
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On first load, check the saved token by asking the API who it belongs to
  useEffect(() => {
    const check = getToken()
      ? api<User>("/auth/me").catch(() => {
          setToken(null); // expired or invalid: forget it
          return null;
        })
      : Promise.resolve(null);
    check.then((me) => {
      setUser(me);
      setLoading(false);
    });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api<{ access_token: string }>("/auth/login", {
      method: "POST",
      form: { username: email, password },
    });
    setToken(access_token);
    setUser(await api<User>("/auth/me"));
  }, []);

  const register = useCallback(
    async (email: string, password: string) => {
      await api("/auth/register", { method: "POST", json: { email, password } });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be used inside <AuthProvider>");
  return auth;
}
