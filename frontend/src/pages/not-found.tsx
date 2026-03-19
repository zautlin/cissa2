export default function NotFound() {
  return (
    <div style={{
      minHeight: "100%",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "hsl(var(--background))",
      padding: "2rem",
    }}>
      <div style={{
        background: "hsl(var(--card))",
        border: "1px solid hsl(var(--border))",
        borderRadius: "0.75rem",
        padding: "2.5rem",
        maxWidth: "420px",
        width: "100%",
        boxShadow: "0 2px 12px rgba(0,0,0,0.07)",
        textAlign: "center",
      }}>
        <div style={{
          width: "52px",
          height: "52px",
          borderRadius: "50%",
          background: "hsl(0 72% 51% / 0.1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: "0 auto 1.25rem",
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="hsl(0 72% 51%)" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
        </div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "hsl(var(--foreground))", margin: "0 0 0.5rem 0" }}>
          404 — Page Not Found
        </h1>
        <p style={{ fontSize: "0.875rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.6, margin: 0 }}>
          This route doesn't exist. Use the sidebar to navigate to a valid page.
        </p>
      </div>
    </div>
  );
}
