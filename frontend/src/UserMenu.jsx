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
    <div ref={ref} style={{ position: "relative", fontFamily: "'Manrope', sans-serif" }}>
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
          fontSize: 13,
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
            fontSize: 12,
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
          <div style={{ padding: "6px 10px", fontSize: 12, color: "#6B7E92", wordBreak: "break-all" }}>
            {user.email}
          </div>

          <MenuItem
            label="Ayarlar"
            onClick={() => { setOpen(false); navigate("/settings"); }}
            icon={
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.4" />
                <path d="M8 1.5v1.6M8 12.9v1.6M14.5 8h-1.6M3.1 8H1.5M12.5 3.5l-1.1 1.1M4.6 11.4l-1.1 1.1M12.5 12.5l-1.1-1.1M4.6 4.6L3.5 3.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
            }
          />
          <MenuItem
            label="Yardım"
            onClick={() => { setOpen(false); navigate("/help"); }}
            icon={
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <circle cx="8" cy="8" r="6.3" stroke="currentColor" strokeWidth="1.4" />
                <path d="M6.2 6.1a1.8 1.8 0 113 1.3c-.5.4-1.2.7-1.2 1.6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                <circle cx="8" cy="11.4" r=".75" fill="currentColor" />
              </svg>
            }
          />

          <div style={{ height: 1, background: "rgba(255,255,255,0.08)", margin: "6px 2px" }} />

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

function MenuItem({ label, icon, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 9,
        textAlign: "left",
        padding: "8px 10px",
        borderRadius: 6,
        fontSize: 13,
        color: "#E8EDF2",
        cursor: "pointer",
        background: "transparent",
        transition: "background .12s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.06)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <span style={{ display: "flex", color: "#6B7E92" }}>{icon}</span>
      {label}
    </button>
  );
}
