import type { ChatTurn } from "../types";

export type SessionListItem = {
  id: string;
  created_at: string;
  updated_at: string;
  source?: string | null;
  turn_count: number;
  last_turn_at?: string | null;
};

export type TurnRow = {
  id: number;
  session_id: string;
  user_content: string;
  assistant_content: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

/** Rebuild UI messages from persisted turns (one user + one assistant per turn). */
export function turnsToChatMessages(turns: TurnRow[]): ChatTurn[] {
  const out: ChatTurn[] = [];
  for (const t of turns) {
    out.push({
      id: `hist-${t.id}-u`,
      role: "user",
      content: t.user_content,
    });
    let assistantText = t.assistant_content ?? "";
    if (t.error) {
      assistantText = assistantText
        ? `${assistantText}\n\n**Error:** ${t.error}`
        : `**Error:** ${t.error}`;
    }
    if (!assistantText.trim()) {
      assistantText = "_(No assistant reply recorded yet.)_";
    }
    out.push({
      id: `hist-${t.id}-a`,
      role: "assistant",
      content: assistantText,
    });
  }
  return out;
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 16);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16);
  }
}

type Props = {
  sessions: SessionListItem[];
  loading: boolean;
  listError: string | null;
  selectedSessionId: string;
  mobileOpen: boolean;
  /** When false on large screens, panel collapses (ChatGPT-style). */
  desktopExpanded: boolean;
  onCloseMobile: () => void;
  onToggleDesktop: () => void;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onRefresh: () => void;
};

export function ChatSidebar({
  sessions,
  loading,
  listError,
  selectedSessionId,
  mobileOpen,
  desktopExpanded,
  onCloseMobile,
  onToggleDesktop,
  onSelectSession,
  onNewChat,
  onRefresh,
}: Props) {
  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close sidebar"
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={onCloseMobile}
        />
      ) : null}

      <aside
        className={`fixed bottom-0 left-0 top-0 z-50 flex w-[min(100%,18rem)] flex-col border-r border-surface-border bg-slate-950/95 backdrop-blur transition-[transform,width] duration-200 ease-out lg:static lg:z-0 lg:min-h-0 lg:bg-slate-950/80 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        } ${
          desktopExpanded
            ? "lg:w-72 lg:max-w-72 lg:translate-x-0 lg:opacity-100"
            : "lg:pointer-events-none lg:w-0 lg:max-w-0 lg:overflow-hidden lg:border-r-0 lg:opacity-0"
        }`}
      >
        <div className="flex min-w-[18rem] shrink-0 items-center justify-between gap-2 border-b border-surface-border px-3 py-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Chats
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              title="Collapse sidebar"
              onClick={onToggleDesktop}
              className="hidden rounded-lg p-1.5 text-slate-500 hover:bg-slate-800 hover:text-slate-300 lg:inline-flex"
              aria-label="Collapse sidebar"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
                />
              </svg>
            </button>
            <button
              type="button"
              title="Refresh list"
              onClick={onRefresh}
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </button>
            <button
              type="button"
              onClick={onNewChat}
              className="rounded-lg bg-sky-600/90 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-500"
            >
              New chat
            </button>
          </div>
        </div>

        <div className="min-h-0 min-w-[18rem] flex-1 overflow-y-auto px-2 py-2">
          {listError ? (
            <p className="px-2 text-xs text-rose-400">{listError}</p>
          ) : null}
          {loading && sessions.length === 0 ? (
            <p className="px-2 text-xs text-slate-500">Loading sessions…</p>
          ) : null}
          {!loading && sessions.length === 0 && !listError ? (
            <p className="px-2 text-xs text-slate-500">No saved sessions yet. Send a message to start.</p>
          ) : null}
          <ul className="space-y-0.5">
            {sessions.map((s) => {
              const active = s.id === selectedSessionId;
              const when = formatWhen(s.last_turn_at || s.updated_at);
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelectSession(s.id);
                      onCloseMobile();
                    }}
                    className={`w-full rounded-lg px-2.5 py-2 text-left text-sm transition ${
                      active
                        ? "bg-sky-900/50 text-sky-100"
                        : "text-slate-300 hover:bg-slate-800/80"
                    }`}
                  >
                    <div className="line-clamp-2 font-medium leading-snug">
                      {when || "Session"}
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] text-slate-500">
                      {s.turn_count} turn{s.turn_count === 1 ? "" : "s"} · {s.id.slice(0, 8)}…
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>
    </>
  );
}

type MenuButtonProps = {
  onClick: () => void;
  /** `mobile` = small screens only; `desktop` = lg+ only (e.g. reopen rail). */
  forScreen?: "mobile" | "desktop";
  /** "menu" = hamburger; "panel" = chevron (expand history rail). */
  variant?: "menu" | "panel";
};

/** Opens session history drawer / rail. */
export function ChatSidebarMenuButton({
  onClick,
  forScreen = "mobile",
  variant = "menu",
}: MenuButtonProps) {
  const visibility =
    forScreen === "desktop" ? "hidden lg:inline-flex" : "inline-flex lg:hidden";
  return (
    <button
      type="button"
      aria-label={variant === "panel" ? "Expand chat history" : "Open chat history"}
      title={variant === "panel" ? "Show chat history" : undefined}
      onClick={onClick}
      className={`${visibility} rounded-lg border border-surface-border bg-slate-900/90 p-2 text-slate-300 shadow-sm hover:bg-slate-800`}
    >
      {variant === "panel" ? (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      ) : (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      )}
    </button>
  );
}
