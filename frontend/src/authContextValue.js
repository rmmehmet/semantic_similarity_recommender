import { createContext } from "react";

// Ham context nesnesi ayrı bir dosyada — AuthContext.jsx sadece <AuthProvider>
// bileşenini export etsin diye (react-refresh/only-export-components kuralı
// bir dosyanın SADECE bileşen export etmesini ister).
export const AuthContext = createContext(null);
