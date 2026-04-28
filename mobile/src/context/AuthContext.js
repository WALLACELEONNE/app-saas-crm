import React, { createContext, useContext, useEffect, useState } from "react";
import { currentUser, login as apiLogin, logout as apiLogout } from "../api/client";

const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const u = await currentUser();
      setUser(u);
      setLoading(false);
    })();
  }, []);

  return (
    <Ctx.Provider value={{
      user, loading,
      signIn: async (email, password) => {
        const r = await apiLogin(email, password);
        setUser(r.user);
        return r;
      },
      signOut: async () => { await apiLogout(); setUser(null); },
    }}>{children}</Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
