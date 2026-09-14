import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./useAuth";

/**
 * Her sayfanın kendi navbar'ına eklenen, kullanıcı adı + çıkış menüsü.
 * Sayfaya özel CSS'lerle çakışmaması için inline stil kullanır.
 */
export default function UserMenu() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div ref={ref} style={{ position: "relative", fontFamily: "sans-serif" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 12px",
          borderRadius: 20,
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "inherit",
          fontSize: 12,
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        <span
          style={{
            width: 22,
            height: 22,
            borderRadius: "50%",
            background: isAdmin ? "#F59E0B" : "#00D4FF",
            color: "#080C10",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 11,
            fontWeight: 800,
            flexShrink: 0,
          }}
        >
          {user.first_name?.[0]?.toUpperCase() || "?"}
        </span>
        <span>
          {user.first_name}
          {isAdmin && <span style={{ opacity: 0.6 }}> · admin</span>}
        </span>
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            background: "#131B24",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 10,
            padding: 8,
            minWidth: 170,
            zIndex: 500,
            boxShadow: "0 10px 30px rgba(0,0,0,0.45)",
          }}
        >
          <div style={{ padding: "6px 10px", fontSize: 11, color: "#6B7E92", wordBreak: "break-all" }}>
            {user.email}
          </div>
          <button
            onClick={handleLogout}
            style={{
              width: "100%",
              textAlign: "left",
              padding: "8px 10px",
              borderRadius: 6,
              fontSize: 13,
              color: "#F87171",
              cursor: "pointer",
              background: "transparent",
              transition: "background .12s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(248,113,113,0.1)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            Çıkış Yap
          </button>
        </div>
      )}
    </div>
  );
}
