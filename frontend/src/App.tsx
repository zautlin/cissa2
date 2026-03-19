import { Router, Route, Switch, useLocation } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import DashboardHome from "./pages/DashboardHome";
import PrincipleOnePage from "./pages/PrincipleOnePage";
import PrincipleTwoPage from "./pages/PrincipleTwoPage";
import OutputsPage from "./pages/OutputsPage";
import UnderlyingDataPage from "./pages/UnderlyingDataPage";
import ReportsPage from "./pages/ReportsPage";
import MetricsDownloadPage from "./pages/MetricsDownloadPage";
import PipelinePage from "./pages/PipelinePage";
import NotFound from "./pages/not-found";

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <Router hook={useHashLocation}>
      <div className="dashboard-layout" style={{ gridTemplateColumns: sidebarOpen ? "260px 1fr" : "0px 1fr" }}>
        <div className="dashboard-sidebar" style={{ display: sidebarOpen ? undefined : "none" }}>
          <Sidebar />
        </div>
        <div className="dashboard-topbar">
          <Topbar onToggleSidebar={() => setSidebarOpen(v => !v)} sidebarOpen={sidebarOpen} />
        </div>
        <main className="dashboard-main">
          <Switch>
            <Route path="/" component={DashboardHome} />
            <Route path="/principles/1" component={PrincipleOnePage} />
            <Route path="/principles/2" component={PrincipleTwoPage} />
            <Route path="/outputs" component={OutputsPage} />
            <Route path="/underlying-data" component={UnderlyingDataPage} />
            <Route path="/reports" component={ReportsPage} />
            <Route path="/download" component={MetricsDownloadPage} />
            <Route path="/pipeline" component={PipelinePage} />
            <Route component={NotFound} />
          </Switch>
        </main>
      </div>
    </Router>
  );
}
