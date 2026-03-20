import { Router, Route, Switch } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { useState, lazy, Suspense } from "react";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import { DrillDownProvider } from "./context/DrillDown";
import { ErrorBoundary } from "./components/ErrorBoundary";

const DashboardHome      = lazy(() => import("./pages/DashboardHome"));
const PrincipleOnePage   = lazy(() => import("./pages/PrincipleOnePage"));
const PrincipleTwoPage   = lazy(() => import("./pages/PrincipleTwoPage"));
const PrincipleThreePage = lazy(() => import("./pages/PrincipleThreePage"));
const PrincipleFourPage  = lazy(() => import("./pages/PrincipleFourPage"));
const PrincipleFivePage  = lazy(() => import("./pages/PrincipleFivePage"));
const PrincipleSixPage   = lazy(() => import("./pages/PrincipleSixPage"));
const OutputsPage        = lazy(() => import("./pages/OutputsPage"));
const UnderlyingDataPage = lazy(() => import("./pages/UnderlyingDataPage"));
const ReportsPage        = lazy(() => import("./pages/ReportsPage"));
const MetricsDownloadPage = lazy(() => import("./pages/MetricsDownloadPage"));
const PipelinePage       = lazy(() => import("./pages/PipelinePage"));
const ExecutiveDashboard = lazy(() => import("./pages/ExecutiveDashboard"));
const NotFound           = lazy(() => import("./pages/not-found"));

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <DrillDownProvider>
      <Router hook={useHashLocation}>
        <div className="dashboard-layout" style={{ gridTemplateColumns: sidebarOpen ? "260px 1fr" : "0px 1fr" }}>
          <div className="dashboard-sidebar" style={{ display: sidebarOpen ? undefined : "none" }}>
            <ErrorBoundary fallback={<div style={{ padding: "1rem", color: "#ef4444" }}>Sidebar error</div>}>
              <Sidebar />
            </ErrorBoundary>
          </div>
          <div className="dashboard-topbar">
            <ErrorBoundary fallback={<div style={{ padding: "0.5rem", color: "#ef4444" }}>Topbar error</div>}>
              <Topbar onToggleSidebar={() => setSidebarOpen(v => !v)} sidebarOpen={sidebarOpen} />
            </ErrorBoundary>
          </div>
          <main className="dashboard-main">
            <ErrorBoundary>
            <Suspense fallback={<div style={{ padding: "2rem", color: "hsl(var(--muted-foreground))", fontSize: "0.875rem" }}>Loading…</div>}>
            <Switch>
              <Route path="/" component={DashboardHome} />
              <Route path="/principles/1" component={PrincipleOnePage} />
              <Route path="/principles/1/:tab" component={PrincipleOnePage} />
              <Route path="/principles/2" component={PrincipleTwoPage} />
              <Route path="/principles/2/:tab" component={PrincipleTwoPage} />
              <Route path="/principles/3" component={PrincipleThreePage} />
              <Route path="/principles/3/:tab" component={PrincipleThreePage} />
              <Route path="/principles/4" component={PrincipleFourPage} />
              <Route path="/principles/4/:tab" component={PrincipleFourPage} />
              <Route path="/principles/5" component={PrincipleFivePage} />
              <Route path="/principles/5/:tab" component={PrincipleFivePage} />
              <Route path="/principles/6" component={PrincipleSixPage} />
              <Route path="/principles/6/:tab" component={PrincipleSixPage} />
              <Route path="/outputs" component={OutputsPage} />
              <Route path="/underlying-data" component={UnderlyingDataPage} />
              <Route path="/reports" component={ReportsPage} />
              <Route path="/download" component={MetricsDownloadPage} />
              <Route path="/pipeline" component={PipelinePage} />
              <Route path="/executive" component={ExecutiveDashboard} />
              <Route component={NotFound} />
            </Switch>
            </Suspense>
            </ErrorBoundary>
          </main>
        </div>
      </Router>
    </DrillDownProvider>
  );
}
