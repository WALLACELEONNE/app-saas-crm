import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("agro_user") || "null"); } catch { return null; }
  });
  const [loading, setLoading] = useState(false);

  const login = async (email, password) => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("agro_token", data.access_token);
      localStorage.setItem("agro_refresh", data.refresh_token);
      localStorage.setItem("agro_user", JSON.stringify(data.user));
      setUser(data.user);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e?.response?.data?.detail || "Falha no login" };
    } finally { setLoading(false); }
  };

  const logout = () => {
    localStorage.removeItem("agro_token");
    localStorage.removeItem("agro_refresh");
    localStorage.removeItem("agro_user");
    setUser(null);
  };

  useEffect(() => {
    if (!user) return;
    api.get("/auth/me").catch(() => logout());
  // eslint-disable-next-line
  }, []);

  return (
    <AuthCtx.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
