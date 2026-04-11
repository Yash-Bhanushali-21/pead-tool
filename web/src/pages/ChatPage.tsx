import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { MarkdownContent } from "../components/MarkdownContent";
import {
  ChatSidebar,
  ChatSidebarMenuButton,
  turnsToChatMessages,
  type SessionListItem,
  type TurnRow,
} from "../components/ChatSidebar";
import { CHAT_SEED_STORAGE_KEY } from "../lib/technicalChatSeed";
import {
  buildConfirmUserMessage,
  parseToolConfirmMarkers,
  type ToolConfirmPayload,
} from "../lib/toolConfirm";
import type { ChatTurn, StreamEvent } from "../types";

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const SESSION_STORAGE_KEY = "pead_chat_session_id";
const SIDEBAR_EXPANDED_KEY = "pead_chat_sidebar_expanded";
/** Pixels from bottom to still count as "following" the stream (ChatGPT-style). */
const SCROLL_NEAR_BOTTOM_PX = 120;

const DEFAULT_ASSISTANT: ChatTurn = {
  id: "welcome",
  role: "assistant",
  content:
    "Ask about an NSE symbol (e.g. **RELIANCE**, **SMLMAH**). I can run the **news & sentiment** scan alone, the full **PEAD** stack, or combine tool output with a **desk-style verdict** (research-only; not investment advice). Try: *Use the news and sentiment tool on SMLMAH and give me a desk verdict on the headlines.*",
};

type PeadChatLocationState = {
  peadTechnicalChat?: { v: number; userMessage: string };
};

function getSeedPending(location: ReturnType<typeof useLocation>): boolean {
  const st = location.state as PeadChatLocationState | null;
  if (st?.peadTechnicalChat?.v === 1 && st.peadTechnicalChat.userMessage) return true;
  try {
    const raw = sessionStorage.getItem(CHAT_SEED_STORAGE_KEY);
    if (raw) {
      const p = JSON.parse(raw) as { v?: number; userMessage?: string };
      if (p.v === 1 && typeof p.userMessage === "string") return true;
    }
  } catch {
    /* ignore */
  }
  return false;
}

export default function ChatPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatTurn[]>([DEFAULT_ASSISTANT]);
  const [fromTechnicalTool, setFromTechnicalTool] = useState(false);
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false);
  const [sidebarDesktopExpanded, setSidebarDesktopExpanded] = useState(() => {
    if (typeof window === "undefined") return true;
    try {
      const v = localStorage.getItem(SIDEBAR_EXPANDED_KEY);
      if (v === "0" || v === "false") return false;
      return true;
    } catch {
      return true;
    }
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => {
    if (typeof window === "undefined") return "";
    try {
      return localStorage.getItem(SESSION_STORAGE_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [toolLog, setToolLog] = useState<string[]>([]);
  /** When true, new tokens scroll the thread to the bottom; false after user scrolls up. */
  const [followOutput, setFollowOutput] = useState(true);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  /** Prevents duplicate seed handling (e.g. React Strict Mode double effect). */
  const seedConsumedRef = useRef(false);
  /** One-time restore from SQLite when landing with a saved session id (no technical seed). */
  const hydrateRanRef = useRef(false);

  const refreshSessions = useCallback(async () => {
    try {
      setSessionsLoading(true);
      const res = await fetch("/api/chat/sessions?limit=50");
      if (!res.ok) throw new Error((await res.text()) || res.statusText);
      const data = (await res.json()) as { sessions?: SessionListItem[] };
      setSessions(data.sessions ?? []);
      setSessionsError(null);
    } catch (e) {
      setSessionsError(e instanceof Error ? e.message : String(e));
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const toggleDesktopSidebar = useCallback(() => {
    setSidebarDesktopExpanded((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_EXPANDED_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const handleScrollAreaScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distance <= SCROLL_NEAR_BOTTOM_PX;
    stickToBottomRef.current = atBottom;
    setFollowOutput(atBottom);
  }, []);

  /** Scroll after layout; double rAF so scrollHeight reflects new content (streaming tokens). */
  const scrollPinnedToBottom = useCallback(() => {
    if (!stickToBottomRef.current) return;
    const el = scrollContainerRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    });
  }, []);

  const jumpToBottom = useCallback(() => {
    stickToBottomRef.current = true;
    setFollowOutput(true);
    const el = scrollContainerRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    });
  }, []);

  const loadSessionHistory = useCallback(async (sid: string) => {
    setHistoryLoading(true);
    try {
      const res = await fetch(`/api/chat/sessions/${encodeURIComponent(sid)}`);
      if (!res.ok) throw new Error((await res.text()) || res.statusText);
      const data = (await res.json()) as { session_id: string; turns: TurnRow[] };
      const turns = data.turns ?? [];
      setSessionId(sid);
      try {
        localStorage.setItem(SESSION_STORAGE_KEY, sid);
      } catch {
        /* ignore */
      }
      setMessages(turns.length > 0 ? turnsToChatMessages(turns) : [DEFAULT_ASSISTANT]);
      setFromTechnicalTool(false);
      setToolLog([]);
      setSessionsError(null);
    } catch (e) {
      setSessionsError(e instanceof Error ? e.message : String(e));
    } finally {
      setHistoryLoading(false);
      requestAnimationFrame(() => jumpToBottom());
    }
  }, [jumpToBottom]);

  const startNewChat = useCallback(() => {
    try {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setSessionId("");
    setMessages([DEFAULT_ASSISTANT]);
    setFromTechnicalTool(false);
    setToolLog([]);
    stickToBottomRef.current = true;
    setFollowOutput(true);
    requestAnimationFrame(() => jumpToBottom());
    void refreshSessions();
  }, [refreshSessions, jumpToBottom]);

  const runStream = useCallback(
    async (
      apiMessages: { role: string; content: string }[],
      assistantId: string,
    ) => {
      setLoading(true);
      setToolLog([]);
      try {
        const res = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: apiMessages,
            session_id: sessionId || undefined,
            persist: true,
          }),
        });

        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || res.statusText);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";
        let acc = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split("\n\n");
          buffer = chunks.pop() ?? "";

          for (const chunk of chunks) {
            const line = chunk.trim();
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (raw === "[DONE]") continue;

            let ev: StreamEvent;
            try {
              ev = JSON.parse(raw) as StreamEvent;
            } catch {
              continue;
            }

            if (ev.type === "session_ack") {
              const sid = (ev as { session_id?: string }).session_id;
              if (typeof sid === "string" && sid) {
                setSessionId(sid);
                try {
                  localStorage.setItem(SESSION_STORAGE_KEY, sid);
                } catch {
                  /* ignore */
                }
              }
            }
            if (ev.type === "text_delta" && ev.content) {
              acc += ev.content;
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === assistantId ? { ...msg, content: acc } : msg,
                ),
              );
            }
            if (ev.type === "tool_call") {
              const name = (ev as { tool_name?: string }).tool_name ?? "tool";
              const args = (ev as { args?: unknown }).args;
              setToolLog((t) => [
                ...t,
                `→ ${name}(${typeof args === "object" ? JSON.stringify(args) : String(args)})`,
              ]);
            }
            if (ev.type === "tool_result") {
              const prev = (ev as { content_preview?: string }).content_preview ?? "";
              setToolLog((t) => [...t, `← ${prev.slice(0, 280)}${prev.length > 280 ? "…" : ""}`]);
            }
            if (ev.type === "done" && typeof (ev as { output?: string }).output === "string") {
              const out = (ev as { output: string }).output;
              if (out && !acc) {
                setMessages((m) =>
                  m.map((msg) =>
                    msg.id === assistantId ? { ...msg, content: out } : msg,
                  ),
                );
              }
            }
            if (ev.type === "error") {
              const msg = (ev as { message?: string }).message ?? "Unknown error";
              setMessages((m) =>
                m.map((row) =>
                  row.id === assistantId ? { ...row, content: `**Error:** ${msg}` } : row,
                ),
              );
            }
          }
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setMessages((m) =>
          m.map((row) =>
            row.id === assistantId ? { ...row, content: `**Error:** ${msg}` } : row,
          ),
        );
      } finally {
        setLoading(false);
        void refreshSessions();
      }
    },
    [sessionId, refreshSessions],
  );

  /** After React commits new message/tool DOM (and when streaming ends → Markdown swap), pin scroll. */
  useLayoutEffect(() => {
    if (!stickToBottomRef.current) return;
    scrollPinnedToBottom();
  }, [messages, toolLog, loading, scrollPinnedToBottom]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (hydrateRanRef.current) return;
    if (getSeedPending(location)) return;
    let cancelled = false;
    const sid = (() => {
      try {
        return localStorage.getItem(SESSION_STORAGE_KEY) ?? "";
      } catch {
        return "";
      }
    })();
    if (!sid) {
      hydrateRanRef.current = true;
      return;
    }
    hydrateRanRef.current = true;
    void (async () => {
      setHistoryLoading(true);
      try {
        const res = await fetch(`/api/chat/sessions/${encodeURIComponent(sid)}`);
        if (!res.ok) return;
        const data = (await res.json()) as { turns?: TurnRow[] };
        const turns = data.turns ?? [];
        if (cancelled) return;
        if (turns.length > 0) {
          setMessages(turnsToChatMessages(turns));
          requestAnimationFrame(() => jumpToBottom());
        }
      } catch {
        /* ignore */
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [location, jumpToBottom]);

  useEffect(() => {
    if (seedConsumedRef.current) return;

    const st = location.state as PeadChatLocationState | null;
    let userMessage: string | null = null;

    if (st?.peadTechnicalChat?.v === 1 && st.peadTechnicalChat.userMessage) {
      userMessage = st.peadTechnicalChat.userMessage;
    } else {
      try {
        const raw = sessionStorage.getItem(CHAT_SEED_STORAGE_KEY);
        if (raw) {
          const p = JSON.parse(raw) as { v?: number; userMessage?: string };
          if (p.v === 1 && typeof p.userMessage === "string") userMessage = p.userMessage;
        }
      } catch {
        /* ignore */
      }
    }

    if (!userMessage) return;

    seedConsumedRef.current = true;
    sessionStorage.removeItem(CHAT_SEED_STORAGE_KEY);
    navigate(".", { replace: true, state: {} });

    try {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setSessionId("");

    const userMsg: ChatTurn = { id: uid(), role: "user", content: userMessage };
    const assistantId = uid();

    setFromTechnicalTool(true);
    stickToBottomRef.current = true;
    setFollowOutput(true);
    setMessages([userMsg, { id: assistantId, role: "assistant", content: "" }]);
    setTimeout(() => jumpToBottom(), 50);

    void runStream([{ role: "user", content: userMessage }], assistantId);
  }, [location.state, navigate, runStream, jumpToBottom]);

  const sendMessageText = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading || historyLoading) return;
      const userMsg: ChatTurn = { id: uid(), role: "user", content: trimmed };
      const assistantId = uid();
      setInput("");
      setToolLog([]);
      stickToBottomRef.current = true;
      setFollowOutput(true);
      setTimeout(() => jumpToBottom(), 50);
      setMessages((prev) => {
        const apiPayload = [...prev, userMsg].map(({ role, content }) => ({ role, content }));
        void runStream(apiPayload, assistantId);
        return [...prev, userMsg, { id: assistantId, role: "assistant", content: "" }];
      });
    },
    [loading, historyLoading, runStream, jumpToBottom],
  );

  const send = useCallback(() => {
    void sendMessageText(input);
  }, [input, sendMessageText]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-surface lg:flex-row">
      <ChatSidebar
        sessions={sessions}
        loading={sessionsLoading}
        listError={sessionsError}
        selectedSessionId={sessionId}
        mobileOpen={sidebarMobileOpen}
        desktopExpanded={sidebarDesktopExpanded}
        onCloseMobile={() => setSidebarMobileOpen(false)}
        onToggleDesktop={toggleDesktopSidebar}
        onSelectSession={(id) => void loadSessionHistory(id)}
        onNewChat={startNewChat}
        onRefresh={() => void refreshSessions()}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="border-b border-surface-border bg-surface-raised/40 px-3 py-3 lg:px-4">
          <div className="mx-auto max-w-4xl space-y-2">
            <div className="flex flex-wrap items-start gap-2">
              <ChatSidebarMenuButton onClick={() => setSidebarMobileOpen(true)} />
              {!sidebarDesktopExpanded ? (
                <ChatSidebarMenuButton
                  forScreen="desktop"
                  variant="panel"
                  onClick={() => {
                    setSidebarDesktopExpanded(true);
                    try {
                      localStorage.setItem(SIDEBAR_EXPANDED_KEY, "1");
                    } catch {
                      /* ignore */
                    }
                  }}
                />
              ) : null}
              {fromTechnicalTool && (
                <p className="min-w-0 flex-1 rounded-lg border border-emerald-900/50 bg-emerald-950/30 px-3 py-2 text-xs text-emerald-100/90">
                  <strong className="text-emerald-50">Technical analysis</strong> context is loaded
                  in the thread below. Ask follow-ups; the agent should ground answers in the JSON
                  you attached (research only — not investment advice).
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate-400">
                PydanticAI coordinator · responses stream · requires{" "}
                <code className="text-sky-300">OPENAI_API_KEY</code> on the server. Chats persist to
                local SQLite (<code className="text-slate-500">CHAT_SQLITE_PATH</code>). From{" "}
                <strong className="font-medium text-slate-300">Tools → Technical</strong>, use{" "}
                <strong className="font-medium text-slate-300">Continue in chat</strong> to load a
                run here. Use the left drawer for past sessions.
              </p>
              <button
                type="button"
                className="shrink-0 rounded-lg border border-slate-600 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800/80"
                onClick={startNewChat}
              >
                New session
              </button>
            </div>
            {sessionId ? (
              <p className="font-mono text-[10px] text-slate-600">
                Session: {sessionId}
              </p>
            ) : null}
            {historyLoading ? (
              <p className="text-xs text-slate-500">Loading conversation…</p>
            ) : null}
          </div>
        </div>

        <main className="relative mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col px-4 py-6">
        <div
          ref={scrollContainerRef}
          onScroll={handleScrollAreaScroll}
          className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overflow-x-hidden overscroll-contain pb-40 [scrollbar-gutter:stable]"
        >
          <div className="flex flex-col gap-3">
            {messages.map((m, i) => {
              const isStreamingAssistant =
                loading && m.role === "assistant" && i === messages.length - 1;
              return (
                <article
                  key={m.id}
                  className={`rounded-2xl border px-4 py-3 ${
                    m.role === "user"
                      ? "ml-8 border-sky-900/50 bg-sky-950/30"
                      : "mr-4 border-surface-border bg-surface-raised/60"
                  } ${isStreamingAssistant ? "min-w-0 [contain:layout]" : "min-w-0"}`}
                >
                  <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
                    {m.role === "user" ? "You" : "Agent"}
                  </div>
                  <div className="max-w-none text-slate-200">
                    {m.role === "assistant" ? (
                      <AssistantMessageBody
                        content={m.content}
                        onConfirmRun={sendMessageText}
                        streaming={isStreamingAssistant}
                      />
                    ) : (
                      <MarkdownContent source={m.content} />
                    )}
                  </div>
                </article>
              );
            })}
          </div>

          {toolLog.length > 0 && (
            <aside className="rounded-xl border border-surface-border bg-black/30 p-3 font-mono text-xs text-slate-400">
              <div className="mb-2 font-sans text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Tool trace
              </div>
              <ul className="max-h-52 space-y-1 overflow-y-auto">
                {toolLog.map((line, i) => (
                  <li key={i} className="break-all">
                    {line}
                  </li>
                ))}
              </ul>
            </aside>
          )}
          <div ref={bottomRef} className="h-px shrink-0" aria-hidden />
        </div>

        {loading && !followOutput ? (
          <div className="pointer-events-none absolute bottom-36 right-4 z-20 flex justify-end sm:right-6">
            <button
              type="button"
              onClick={jumpToBottom}
              className="pointer-events-auto rounded-full border border-surface-border bg-slate-900/95 px-4 py-2 text-xs font-medium text-sky-200 shadow-lg backdrop-blur transition hover:bg-slate-800"
            >
              Jump to latest
            </button>
          </div>
        ) : null}

        <div
          className={`fixed bottom-0 left-0 right-0 border-t border-surface-border bg-surface/95 p-4 backdrop-blur ${
            sidebarDesktopExpanded ? "lg:left-72" : "lg:left-0"
          }`}
        >
          <div className="mx-auto flex max-w-4xl gap-2">
            <textarea
              className="min-h-[52px] flex-1 resize-none rounded-xl border border-surface-border bg-surface-raised px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              placeholder="e.g. Use news and sentiment on SMLMAH and give a desk verdict…"
              value={input}
              disabled={loading || historyLoading}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              rows={2}
            />
            <button
              type="button"
              onClick={() => void send()}
              disabled={loading || historyLoading || !input.trim()}
              className="self-end rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "…" : "Send"}
            </button>
          </div>
        </div>
      </main>
      </div>
    </div>
  );
}

function AssistantMessageBody({
  content,
  onConfirmRun,
  streaming,
}: {
  content: string;
  onConfirmRun: (text: string) => void;
  /** While tokens arrive, render plain text to avoid re-parsing Markdown every frame (layout thrash / “dancing”). */
  streaming?: boolean;
}) {
  const { cleaned, confirms } = parseToolConfirmMarkers(content);
  if (streaming) {
    const text = cleaned.length > 0 ? cleaned : "\u00a0";
    return (
      <div className="whitespace-pre-wrap break-words text-[15px] leading-relaxed text-slate-200">
        {text}
      </div>
    );
  }
  return (
    <>
      {cleaned.length > 0 ? <MarkdownContent source={cleaned} /> : null}
      {confirms.map((c, i) => (
        <ToolConfirmCard key={i} payload={c} onConfirmRun={onConfirmRun} />
      ))}
    </>
  );
}

function ToolConfirmCard({
  payload,
  onConfirmRun,
}: {
  payload: ToolConfirmPayload;
  onConfirmRun: (text: string) => void;
}) {
  return (
    <div className="mt-3 rounded-lg border border-amber-800/60 bg-amber-950/35 px-3 py-2">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-200/90">
        Confirm tool run
      </div>
      {payload.label ? (
        <p className="mt-1 text-xs text-amber-50/95">{payload.label}</p>
      ) : null}
      <pre className="mt-2 max-h-32 overflow-auto rounded bg-black/40 p-2 text-[10px] leading-snug text-slate-400">
        {payload.tool}
        {"\n"}
        {JSON.stringify(payload.args, null, 2)}
      </pre>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void onConfirmRun(buildConfirmUserMessage(payload))}
          className="rounded-lg bg-amber-600/90 px-3 py-1.5 text-xs font-semibold text-amber-50 hover:bg-amber-500"
        >
          Yes, run this
        </button>
        <button
          type="button"
          onClick={() =>
            void onConfirmRun(
              "No — cancel that suggestion. I will clarify which tool and symbol I want.",
            )
          }
          className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800/80"
        >
          No
        </button>
      </div>
    </div>
  );
}

