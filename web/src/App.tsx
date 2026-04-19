import {
  BrowserRouter,
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import PeadSingleToolPage from "./pages/tools/PeadSingleToolPage";

/** Old tool URLs → unified equity pipeline at `/tools`. */
const LEGACY_TOOL_PATHS = [
  "pead/single",
  "pead/recent",
  "fundamentals",
  "technical",
  "news",
  "scoring",
  "trade-readiness",
  "document-pdf",
  "execution-snapshot",
  "yahoo-calendar",
] as const;

function Layout() {
  const loc = useLocation();
  const toolsActive = loc.pathname === "/tools" || loc.pathname.startsWith("/tools/");

  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <header className="sticky top-0 z-10 shrink-0 border-b border-surface-border bg-surface/95 backdrop-blur">
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
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <Outlet />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/tools" element={<PeadSingleToolPage />} />
          {LEGACY_TOOL_PATHS.map((suffix) => (
            <Route
              key={suffix}
              path={`/tools/${suffix}`}
              element={<Navigate to="/tools" replace />}
            />
          ))}
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
