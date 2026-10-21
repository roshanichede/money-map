"use client";

import { useEffect, useRef, useState } from "react";

import { api, type ChatReply } from "@/lib/api";
import { money, plural, shortDate } from "@/lib/format";
import { Check, IconClose } from "./icons";

type Turn = { q: string; reply?: ChatReply; error?: string };

function provenance(r: ChatReply): string {
  if (r.source === "claude") return "Worded by Claude. Every figure was checked against your transactions.";
  if (r.guardrail.startsWith("blocked"))
    return "Calculated from your transactions. Claude's wording used a figure that isn't in your data, so it was replaced.";
  return "Calculated directly from your transactions.";
}

type Props = { open: boolean; onClose: () => void; suggestions: string[]; accountId: number | null; scopeLabel: string };

/** The conversation survives closing the drawer; it resets when the data or the account filter changes (via key). */
export function ChatDrawer({ open, onClose, suggestions, accountId, scopeLabel }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, open]);
  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setText("");
    setBusy(true);
    setTurns((t) => [...t, { q }]);
    try {
      const reply = await api.ask(q, accountId);
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, reply } : turn)));
    } catch (e) {
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, error: (e as Error).message } : turn)));
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="chat-h">
        <div className="drawer-head">
          <div>
            <h2 id="chat-h">Ask about your money</h2>
            <p>Answers use only your statements ({scopeLabel}).</p>
          </div>
          <button className="btn btn-ghost" onClick={onClose} aria-label="Close"><IconClose /></button>
        </div>
        <div className="chat-log" ref={logRef} aria-live="polite">
          {turns.length === 0 && (
            <div className="suggestions">
              {suggestions.map((s) => <button key={s} className="suggestion" onClick={() => ask(s)}>{s}</button>)}
            </div>
          )}
          {turns.map((t, i) => (
            <div key={i}>
              <div style={{ display: "flex", justifyContent: "flex-end" }}><div className="msg-q">{t.q}</div></div>
              {t.reply && (
                <div style={{ marginTop: 10 }}>
                  <div className="msg-a">{t.reply.answer}</div>
                  <div className="msg-meta"><Check size={13} /><span>{provenance(t.reply)}</span></div>
                  {t.reply.evidence.length > 0 && (
                    <details className="evidence">
                      <summary>Show the {plural(t.reply.evidence.length, "transaction")} behind this</summary>
                      <ul>
                        {t.reply.evidence.map((e) => (
                          <li key={e.id}><span>{shortDate(e.date)} {e.merchant}</span><span className="num">{money(e.amount_pence)}</span></li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )}
              {t.error && <div className="error-box" style={{ marginTop: 10 }}>Couldn&apos;t answer: {t.error}</div>}
              {!t.reply && !t.error && <div className="thinking" style={{ marginTop: 10 }}>Working it out…</div>}
            </div>
          ))}
        </div>
        <form className="chat-form" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
          <label className="visually-hidden" htmlFor="chat-input">Your question</label>
          <input id="chat-input" ref={inputRef} className="input" placeholder="e.g. How much on takeaways this month?"
                 value={text} onChange={(e) => setText(e.target.value)} maxLength={500} />
          <button className="btn btn-primary" disabled={busy || !text.trim()}>Ask</button>
        </form>
      </aside>
    </>
  );
}
