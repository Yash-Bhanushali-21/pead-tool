import { useCallback, useRef, useState } from "react";
import type { ChatTurn, StreamEvent } from "../types";

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatTurn[]>([
    {
      id: uid(),
      role: "assistant",
      content:
        "Ask about an NSE symbol (e.g. **RELIANCE**, **SMLMAH**). I can run the **news & sentiment** scan alone, the full **PEAD** stack, or combine tool output with a **desk-style verdict** (research-only; not investment advice). Try: *Use the news and sentiment tool on SMLMAH and give me a desk verdict on the headlines.*",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [toolLog, setToolLog] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatTurn = { id: uid(), role: "user", content: text };
    const assistantId = uid();
    setMessages((m) => [...m, userMsg, { id: assistantId, role: "assistant", content: "" }]);
    setInput("");
    setLoading(true);
    setToolLog([]);
    setTimeout(scrollToBottom, 50);

    const payload = {
      messages: [...messages, userMsg].map(({ role, content }) => ({ role, content })),
    };

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
                row.id === assistantId
                  ? { ...row, content: `**Error:** ${msg}` }
                  : row,
              ),
            );
          }
          scrollToBottom();
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
      scrollToBottom();
    }
  }, [input, loading, messages]);

  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <div className="border-b border-surface-border bg-surface-raised/40 px-4 py-3">
        <div className="mx-auto max-w-4xl">
          <p className="text-sm text-slate-400">
            PydanticAI coordinator · responses stream · requires{" "}
            <code className="text-sky-300">OPENAI_API_KEY</code> on the server. For structured
            technical, fundamental, and news panels (not just prose), use{" "}
            <strong className="font-medium text-slate-300">Tools → PEAD — single symbol</strong>.
          </p>
        </div>
      </div>

      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 px-4 py-6">
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto pb-32">
          {messages.map((m) => (
            <article
              key={m.id}
              className={`rounded-2xl border px-4 py-3 ${
                m.role === "user"
                  ? "ml-8 border-sky-900/50 bg-sky-950/30"
                  : "mr-4 border-surface-border bg-surface-raised/60"
              }`}
            >
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
                {m.role === "user" ? "You" : "Agent"}
              </div>
              <div className="max-w-none whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
                {renderMarkdownLite(m.content)}
              </div>
            </article>
          ))}
          <div ref={bottomRef} />
        </div>

        {toolLog.length > 0 && (
          <aside className="rounded-xl border border-surface-border bg-black/30 p-3 font-mono text-xs text-slate-400">
            <div className="mb-2 font-sans text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Tool trace
            </div>
            <ul className="max-h-40 space-y-1 overflow-y-auto">
              {toolLog.map((line, i) => (
                <li key={i} className="break-all">
                  {line}
                </li>
              ))}
            </ul>
          </aside>
        )}

        <div className="fixed bottom-0 left-0 right-0 border-t border-surface-border bg-surface/95 p-4 backdrop-blur">
          <div className="mx-auto flex max-w-4xl gap-2">
            <textarea
              className="min-h-[52px] flex-1 resize-none rounded-xl border border-surface-border bg-surface-raised px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              placeholder="e.g. Use news and sentiment on SMLMAH and give a desk verdict…"
              value={input}
              disabled={loading}
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
              disabled={loading || !input.trim()}
              className="self-end rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "…" : "Send"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

function renderMarkdownLite(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const bolded = line.split(/(\*\*[^*]+\*\*)/g).map((part, j) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={j} className="font-semibold text-white">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
    return (
      <p key={i} className={line.startsWith("- ") ? "ml-4 list-item list-disc" : ""}>
        {bolded}
      </p>
    );
  });
}
