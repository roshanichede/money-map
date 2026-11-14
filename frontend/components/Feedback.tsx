"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { IconClose } from "./icons";

/** A short note to the person running MoneyMap. Their email goes with it only if they tick the box. */
export function FeedbackDialog({ open, onClose, page, onSent, canReplyDefault }: {
  open: boolean; onClose: () => void; page: string; onSent: () => void; canReplyDefault: boolean;
}) {
  const [text, setText] = useState("");
  const [canReply, setCanReply] = useState(canReplyDefault);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  async function send() {
    if (!text.trim()) { setError("Write something first."); return; }
    setBusy(true);
    setError(null);
    try {
      await api.feedback(text.trim(), page, canReply);
      setText("");
      onSent();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="fb-h">
        <div className="dialog-head">
          <h2 id="fb-h">Send feedback</h2>
          <button className="btn btn-ghost" onClick={onClose} aria-label="Close"><IconClose /></button>
        </div>
        <p className="muted small" style={{ marginTop: 0 }}>
          Something confusing, wrong or missing? A payment sorted badly? Every note is read.
        </p>
        <label className="visually-hidden" htmlFor="fb-text">Your feedback</label>
        <textarea id="fb-text" className="feedback-text" value={text} maxLength={4000} autoFocus
                  onChange={(e) => setText(e.target.value)} placeholder="What would make MoneyMap better for you?" />
        <label className="check-row">
          <input type="checkbox" checked={canReply} onChange={(e) => setCanReply(e.target.checked)} />
          <span>You can reply to me by email</span>
        </label>
        {error && <div className="error-box" style={{ marginTop: 12 }}>{error}</div>}
        <div className="dialog-foot">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={send} disabled={busy}>{busy ? "Sending…" : "Send"}</button>
        </div>
      </div>
    </>
  );
}
