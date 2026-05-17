import { useState, useRef, useEffect } from "react";
import { postRunChat } from "../api/api";

export default function RunChatPanel({ open, onClose, runId, runName, selectedFailure }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const endRef = useRef(null);

  const formatChatError = (detail, fallback) => {
    const text = typeof detail === "string" ? detail : fallback || "Chat failed";
    const lower = text.toLowerCase();
    if (
      lower.includes("request too large") ||
      lower.includes("tokens per minute") ||
      lower.includes("rate_limit_exceeded") ||
      lower.includes("413")
    ) {
      return "The LLM request was too large for the current provider limit. Try asking about one specific failure, or redeploy with smaller chat limits.";
    }
    return text.length > 260 ? `${text.slice(0, 260)}...` : text;
  };

  useEffect(() => {
    if (!open) return;
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setInput("");
    setMessages([]);
  }, [runId, open]);

  const send = async () => {
    const text = input.trim();
    if (!text || !runId || loading) return;

    let userPayload = text;
    if (selectedFailure?.id) {
      userPayload = `[User focus: failure id=${selectedFailure.id}, module=${selectedFailure.module || "?"}, severity=${selectedFailure.severity || "?"}]\n${text}`;
    }

    const nextUser = { role: "user", content: text };
    setMessages((m) => [...m, nextUser]);
    setInput("");
    setLoading(true);
    setError(null);

    const historyForApi = messages
      .filter((t) => t.role === "user" || t.role === "assistant")
      .map(({ role, content }) => ({ role, content }));

    try {
      const res = await postRunChat(runId, {
        message: userPayload,
        history: historyForApi,
      });
      const reply = res.data?.reply || "";
      const contextRun = res.data?.context_run_id;
      let out = (reply || "").trim() || "—";
      if (contextRun != null && String(contextRun) !== String(runId)) {
        out =
          `*(Answering from **run #${contextRun}** because your message referenced that run.)*\n\n${out}`;
      }
      setMessages((m) => [...m, { role: "assistant", content: out }]);
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(formatChatError(d, err?.message));
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-[100] flex h-[100dvh] max-h-[100dvh] w-full max-w-md flex-col border-l border-slate-700 bg-slate-950/98 shadow-2xl">
      <div className="flex shrink-0 items-center justify-between px-4 py-3 border-b border-slate-800">
        <div>
          <div className="text-xs text-emerald-400 uppercase tracking-wider">Run assistant</div>
          <div className="text-sm font-medium text-slate-200 truncate max-w-[18rem]" title={runName || ""}>
            {runId ? runName || "Selected upload" : "No upload selected"}
          </div>
          {runId && <div className="mono text-[10px] text-slate-500">Database ID {runId}</div>}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-white text-sm px-2 py-1 rounded border border-slate-700"
          aria-label="Close chat"
        >
          Close
        </button>
      </div>

      {selectedFailure?.id && (
        <div className="shrink-0 px-4 py-2 text-[11px] text-slate-400 border-b border-slate-800/80">
          Focus: failure <span className="font-mono text-emerald-300">#{selectedFailure.id}</span>
        </div>
      )}

      {!runId ? (
        <div className="min-h-0 flex-1 px-4 py-6 text-sm text-slate-400">
          Please open a run first.
        </div>
      ) : (
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-3 space-y-3">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm rounded-lg px-3 py-2 max-w-[95%] min-w-0 ${
              m.role === "user"
                ? "ml-auto bg-emerald-500/15 text-slate-100 border border-emerald-500/25"
                : "mr-auto bg-slate-900/80 text-slate-300 border border-slate-700/60"
            }`}
          >
            <div className="whitespace-pre-wrap break-words font-sans leading-relaxed text-[13px] [overflow-wrap:anywhere]">
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="text-xs text-slate-500 flex items-center gap-2">
            <span className="inline-block h-3 w-3 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
            Thinking…
          </div>
        )}
        {error && (
          <div className="max-w-full rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs leading-relaxed text-amber-300 break-words [overflow-wrap:anywhere]">
            {error}
          </div>
        )}
        <div ref={endRef} />
      </div>
      )}

      {runId && (
      <div className="shrink-0 border-t border-slate-800 bg-slate-950/95 p-3 pt-3 space-y-2 shadow-[0_-8px_24px_rgba(0,0,0,0.35)]">
        <textarea
          rows={3}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={!runId || loading}
          placeholder={runId ? "Message… (Enter to send)" : "Select a run first"}
          className="box-border min-h-[4.5rem] w-full max-w-full resize-none rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 disabled:opacity-50"
        />
        <button
          type="button"
          onClick={send}
          disabled={!runId || loading || !input.trim()}
          className="w-full shrink-0 rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-40"
        >
          Send
        </button>
      </div>
      )}
    </div>
  );
}
