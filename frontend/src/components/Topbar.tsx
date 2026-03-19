import { useLocation } from "wouter";

const pageTitles: Record<string, string> = {
  "/": "Platform Overview",
  "/principles/1": "Principle 1 — A Recognition that Economic Measures are Better",
  "/outputs": "Outputs Menu — Wealth Creation Analysis",
  "/underlying-data": "Underlying Data Menu",
};

export default function Topbar({ onToggleSidebar, sidebarOpen }: {
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
}) {
  const [location] = useLocation();
  const title = pageTitles[location] || "CISSA™ Platform";

  return (
    <div className="dashboard-topbar" style={{
      display: "flex",
      alignItems: "center",
      gap: "1rem",
      padding: "0 1.5rem",
      height: "56px",
    }}>
      {/* Hamburger */}
      <button
        onClick={onToggleSidebar}
        data-testid="button-toggle-sidebar"
        style={{
          padding: "0.375rem",
          borderRadius: "0.375rem",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "hsl(var(--muted-foreground))",
          display: "flex",
          alignItems: "center",
        }}
        aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 6h18M3 12h18M3 18h18"/>
        </svg>
      </button>

      {/* Page title */}
      <div style={{
        fontSize: "0.875rem",
        fontWeight: 600,
        color: "hsl(var(--foreground))",
        flex: 1,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}>
        {title}
      </div>

      {/* Right controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        {/* Index selector */}
        <select
          data-testid="select-index"
          style={{
            fontSize: "0.75rem",
            padding: "0.3rem 0.625rem",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.375rem",
            background: "hsl(var(--card))",
            color: "hsl(var(--foreground))",
            cursor: "pointer",
          }}
        >
          <option>ASX 300</option>
          <option>ASX 200</option>
          <option>S&amp;P 500</option>
          <option>FTSE 100</option>
        </select>

        {/* Period selector */}
        <select
          data-testid="select-period"
          style={{
            fontSize: "0.75rem",
            padding: "0.3rem 0.625rem",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.375rem",
            background: "hsl(var(--card))",
            color: "hsl(var(--foreground))",
            cursor: "pointer",
          }}
        >
          <option>2001–2024</option>
          <option>2010–2024</option>
          <option>2015–2024</option>
          <option>2020–2024</option>
        </select>

        {/* Help button */}
        <button
          data-testid="button-help"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.25rem",
            padding: "0.3rem 0.75rem",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.375rem",
            background: "hsl(var(--card))",
            color: "hsl(var(--primary))",
            cursor: "pointer",
            fontSize: "0.75rem",
            fontWeight: 500,
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <path d="M12 17h.01"/>
          </svg>
          Help
        </button>

        {/* User avatar */}
        <div style={{
          width: "30px",
          height: "30px",
          borderRadius: "50%",
          background: "hsl(var(--primary))",
          color: "white",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "0.6875rem",
          fontWeight: 700,
          cursor: "pointer",
        }} data-testid="button-user-avatar">
          GA
        </div>
      </div>
    </div>
  );
}
