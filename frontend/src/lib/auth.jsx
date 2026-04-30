import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("agro_user") || "null"); } catch { return null; }
  });
  const [loading, setLoading] = useState(false);
  const [hydrating, setHydrating] = useState(() => Boolean(localStorage.getItem("agro_token")));

  const login = async (email, password) => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      if (data.tenant_selection_required) {
        return {
          ok: false,
          tenantSelectionRequired: true,
          selectionToken: data.selection_token,
          memberships: data.memberships || [],
        };
      }
      persistSession(data);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e?.response?.data?.detail || "Falha no login" };
    } finally { setLoading(false); }
  };

  const persistSession = (data) => {
    localStorage.setItem("agro_token", data.access_token);
    localStorage.setItem("agro_refresh", data.refresh_token);
    localStorage.setItem("agro_user", JSON.stringify(data.user));
    setHydrating(false);
    setUser(data.user);
  };

  const selectTenant = async (selectionToken, membershipId) => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/select-tenant", {
        selection_token: selectionToken,
        membership_id: membershipId,
      });
      persistSession(data);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e?.response?.data?.detail || "Falha no login" };
    } finally { setLoading(false); }
  };

  const switchTenant = async (membershipId) => {
    const { data } = await api.post("/auth/switch-tenant", { membership_id: membershipId });
    persistSession(data);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("agro_token");
    localStorage.removeItem("agro_refresh");
    localStorage.removeItem("agro_user");
    setHydrating(false);
    setUser(null);
  };

  useEffect(() => {
    if (!user) {
      setHydrating(false);
      return;
    }
    api.get("/auth/me")
      .then((r) => {
        localStorage.setItem("agro_user", JSON.stringify(r.data));
        setUser(r.data);
      })
      .catch(() => logout())
      .finally(() => setHydrating(false));
  // eslint-disable-next-line
  }, []);

  const can = (permission) => Boolean(user?.permissions?.includes(permission));
  const canAny = (permissions = []) => permissions.some((p) => can(p));

  return (
    <AuthCtx.Provider value={{ user, login, selectTenant, switchTenant, logout, loading, hydrating, can, canAny }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
