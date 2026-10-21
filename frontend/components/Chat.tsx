"use client";

import { useEffect, useRef, useState } from "react";

import { api, type ChatReply } from "@/lib/api";
import { money, plural, shortDate } from "@/lib/format";
import { Check } from "./icons";

type Turn = { q: string; reply?: ChatReply; error?: string };

function provenance(r: ChatReply): string {
  if (r.source === "claude") return "Worded by Claude. Every figure was checked against your transactions.";
  if (r.guardrail.startsWith("blocked"))
    return "Calculated from your transactions. Claude's wording used a figure that isn't in your data, so it was replaced.";
  return "Calculated directly from your transactions.";
}

export function Chat({ suggestions }: { suggestions: string[] }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setText("");
    setBusy(true);
    setTurns((t) => [...t, { q }]);
    try {
      const reply = await api.ask(q);
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, reply } : turn)));
    } catch (e) {
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, error: (e as Error).message } : turn)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="chat" aria-labelledby="chat-h">
      <div className="chat-head">
        <h2 id="chat-h">Ask about your money</h2>
        <p>Answers use only your statements. Nothing is guessed.</p>
      </div>
      <div className="chat-log" ref={logRef} aria-live="polite">
        {turns.length === 0 && (
          <div className="suggestions">
            {suggestions.map((s) => (
              <button key={s} className="suggestion" onClick={() => ask(s)}>{s}</button>
            ))}
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i}>
            <div className="msg-q">{t.q}</div>
            {t.reply && (
              <div style={{ marginTop: 10 }}>
                <div className="msg-a">{t.reply.answer}</div>
                <div className="msg-meta"><Check size={13} /><span>{provenance(t.reply)}</span></div>
                {t.reply.evidence.length > 0 && (
                  <details className="evidence">
                    <summary>Show the {plural(t.reply.evidence.length, "transaction")} behind this</summary>
                    <ul>
                      {t.reply.evidence.map((e) => (
                        <li key={e.id}>
                          <span>{shortDate(e.date)} {e.merchant}</span>
                          <span className="num">{money(e.amount_pence)}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}
            {t.error && <div className="error-box">Couldn&apos;t answer: {t.error}</div>}
            {!t.reply && !t.error && <div className="thinking" style={{ marginTop: 10 }}>Working it out…</div>}
          </div>
        ))}
      </div>
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
        <label className="visually-hidden" htmlFor="chat-input">Your question</label>
        <input id="chat-input" className="input" placeholder="e.g. How much on takeaways this month?"
               value={text} onChange={(e) => setText(e.target.value)} maxLength={500} />
        <button className="btn btn-primary" disabled={busy || !text.trim()}>Ask</button>
      </form>
    </aside>
  );
}
