import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Beklenmeyen bir hata oluştu:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            padding: 24,
            textAlign: "center",
            background: "#0a0e14",
            color: "#e5e7eb",
            fontFamily: "inherit",
          }}
        >
          <h1 style={{ fontSize: 20, margin: 0 }}>Beklenmeyen bir hata oluştu</h1>
          <p style={{ color: "#9ca3af", margin: 0, maxWidth: 480 }}>
            Sayfa beklenmedik bir şekilde çöktü. Sayfayı yenileyerek tekrar deneyebilirsiniz.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              cursor: "pointer",
              border: "1px solid #00D4FF",
              background: "transparent",
              color: "#00D4FF",
              padding: "8px 18px",
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            Sayfayı Yenile
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
