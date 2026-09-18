import { useEffect, useState, useCallback } from "react";
import {
  fetchCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "../services/service";
import { AuthContext } from "./authContextValue";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;
    fetchCurrentUser()
      .then((u) => { if (!ignore) setUser(u); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, []);

  const login = useCallback(async (credentials) => {
    const u = await loginUser(credentials);
    setUser(u);
    return u;
  }, []);

  const register = useCallback(async (data) => {
    const u = await registerUser(data);
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(async () => {
    await logoutUser();
    setUser(null);
  }, []);

  // Profil güncellendiğinde (Ayarlar sayfası) context'teki user'ı yeniden
  // giriş yapmaya gerek kalmadan tazeler — çağıran taraf zaten backend'den
  // dönen güncel user nesnesini elinde tutuyor, burada sadece paylaşılan
  // state'e yazıyoruz.
  const setCurrentUser = useCallback((u) => setUser(u), []);

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    setCurrentUser,
    isAdmin: user?.role === "admin",
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
