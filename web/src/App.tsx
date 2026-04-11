import {
  BrowserRouter,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import DocumentPdfToolPage from "./pages/tools/DocumentPdfToolPage";
import ExecutionSnapshotToolPage from "./pages/tools/ExecutionSnapshotToolPage";
import FundamentalsToolPage from "./pages/tools/FundamentalsToolPage";
import NewsToolPage from "./pages/tools/NewsToolPage";
import PeadRecentToolPage from "./pages/tools/PeadRecentToolPage";
import PeadSingleToolPage from "./pages/tools/PeadSingleToolPage";
import ScoringToolPage from "./pages/tools/ScoringToolPage";
import TechnicalToolPage from "./pages/tools/TechnicalToolPage";
import ToolsHub from "./pages/tools/ToolsHub";
import TradeReadinessOnlyToolPage from "./pages/tools/TradeReadinessOnlyToolPage";
import YahooCalendarToolPage from "./pages/tools/YahooCalendarToolPage";

function Layout() {
  const loc = useLocation();
  const toolsActive = loc.pathname === "/tools" || loc.pathname.startsWith("/tools/");

  return (
    <div className="min-h-screen bg-surface">
      <header className="sticky top-0 z-10 border-b border-surface-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-baseline gap-3">
            <span className="text-lg font-semibold tracking-tight text-white">
              PEAD Research
            </span>
            <span className="hidden text-xs text-slate-600 sm:inline">Indian equities</span>
          </div>
          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive
                    ? "bg-surface-raised text-white"
                    : "text-slate-400 hover:bg-surface-raised/60 hover:text-slate-200"
                }`
              }
            >
              Chat
            </NavLink>
            <NavLink
              to="/tools"
              className={() =>
                `rounded-lg px-3 py-2 text-sm font-medium ${
                  toolsActive
                    ? "bg-surface-raised text-white"
                    : "text-slate-400 hover:bg-surface-raised/60 hover:text-slate-200"
                }`
              }
            >
              Tools
            </NavLink>
          </nav>
        </div>
      </header>
      <Outlet />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/tools" element={<ToolsHub />} />
          <Route path="/tools/pead/single" element={<PeadSingleToolPage />} />
          <Route path="/tools/pead/recent" element={<PeadRecentToolPage />} />
          <Route path="/tools/fundamentals" element={<FundamentalsToolPage />} />
          <Route path="/tools/technical" element={<TechnicalToolPage />} />
          <Route path="/tools/news" element={<NewsToolPage />} />
          <Route path="/tools/scoring" element={<ScoringToolPage />} />
          <Route path="/tools/trade-readiness" element={<TradeReadinessOnlyToolPage />} />
          <Route path="/tools/document-pdf" element={<DocumentPdfToolPage />} />
          <Route path="/tools/execution-snapshot" element={<ExecutionSnapshotToolPage />} />
          <Route path="/tools/yahoo-calendar" element={<YahooCalendarToolPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
