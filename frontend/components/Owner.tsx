"use client";

import { useCallback, useEffect, useState } from "react";

import { api, type FeedbackRow, type Invite, type OwnerStats } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { Check } from "./icons";

const MODES: Record<string, string> = {
  invite: "Invite-only: people need a code to create an account.",
  open: "Open: anyone can create an account.",
  closed: "Closed: no new accounts.",
};

function Stat({ value, label }: { value: number | string; label: string }) {
  return <div className="stat"><b className="num">{value}</b><span>{label}</span></div>;
}

function InviteRow({ inv, onRevoke }: { inv: Invite; onRevoke: () => void }) {
  const [copied, setCopied] = useState(false);
  const link = typeof window === "undefined" ? "" : `${window.location.origin}/signin?invite=${inv.code}`;
  const full = inv.uses >= inv.max_uses;
  return (
    <li>
      <span>
        <span className="invite-code">{inv.code}</span>{inv.note && <span className="quiet"> · {inv.note}</span>}
        <span className="muted small" style={{ display: "block" }}>
          Used {inv.uses} of {inv.max_uses} · made {shortDate(inv.created_at.slice(0, 10))}{full ? " · used up" : ""}
        </span>
      </span>
      <span style={{ display: "flex", gap: 6 }}>
        <button className="btn small" onClick={async () => {
          try { await navigator.clipboard.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* no clipboard */ }
        }}>{copied ? <><Check /> Copied</> : "Copy link"}</button>
        <button className="btn btn-ghost small" onClick={onRevoke}>Revoke</button>
      </span>
    </li>
  );
}

/** Only for the person running MoneyMap: who's using it, invite codes, and feedback. */
export function Owner() {
  const [stats, setStats] = useState<OwnerStats | null>(null);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [feedback, setFeedback] = useState<FeedbackRow[]>([]);
  const [note, setNote] = useState("");
  const [uses, setUses] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.ownerStats().then(setStats).catch((e) => setError((e as Error).message));
    api.invites().then(setInvites).catch(() => setInvites([]));
    api.ownerFeedback().then(setFeedback).catch(() => setFeedback([]));
  }, []);
  useEffect(load, [load]);

  async function create() {
    try {
      await api.createInvite(note.trim(), uses);
      setNote("");
      setUses(1);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (error) return <div className="error-box">{error}</div>;
  if (!stats) return <div className="skeleton" aria-busy="true" />;
  const currencies = Object.entries(stats.accounts_by_currency);

  return (
    <div className="stack">
      <section className="card" aria-labelledby="ow-h">
        <div className="card-head"><h2 id="ow-h">People using MoneyMap</h2><p>{MODES[stats.signup_mode] ?? stats.signup_mode}</p></div>
        <div className="stat-grid">
          <Stat value={stats.users} label="accounts" />
          <Stat value={stats.new_this_week} label="new this week" />
          <Stat value={stats.active_this_week} label="active this week" />
          <Stat value={stats.active_this_month} label="active in 30 days" />
          <Stat value={stats.users_with_statements} label="uploaded a statement" />
          <Stat value={stats.statements_uploaded} label="statements uploaded" />
          <Stat value={stats.phone_links_in_use} label="phone links in use" />
          <Stat value={stats.rules_taught} label="rules taught" />
        </div>
        <p className="muted small" style={{ marginBottom: 0 }}>
          {currencies.length ? `Accounts by currency: ${currencies.map(([c, n]) => `${c} ${n}`).join(", ")}. ` : ""}
          {stats.email_set_up ? "Emails (confirm, reset password) are switched on." : "Emails are off: set SMTP on the server to switch on email confirmation and password reset."}
        </p>
      </section>

      <div className="grid-2">
        <section className="card" aria-labelledby="inv-h">
          <div className="card-head"><h2 id="inv-h">Invite codes</h2><p>Send someone the link; the code fills itself in.</p></div>
          <div className="field field-row">
            <input className="input" placeholder="Who it's for (only you see this)" value={note} maxLength={120}
                   onChange={(e) => setNote(e.target.value)} aria-label="Note" />
            <select className="select" value={uses} onChange={(e) => setUses(Number(e.target.value))} aria-label="How many people can use it">
              {[1, 5, 10, 25, 50, 100].map((n) => <option key={n} value={n}>{n === 1 ? "1 person" : `${n} people`}</option>)}
            </select>
            <button className="btn btn-primary" onClick={create}>Make a code</button>
          </div>
          {invites.length === 0 ? <p className="quiet">No codes yet.</p> : (
            <ul className="rule-list">
              {invites.map((i) => (
                <InviteRow key={i.id} inv={i} onRevoke={async () => { await api.revokeInvite(i.id); load(); }} />
              ))}
            </ul>
          )}
        </section>

        <section className="card" aria-labelledby="fbk-h">
          <div className="card-head"><h2 id="fbk-h">Feedback</h2><p>{feedback.length} {feedback.length === 1 ? "note" : "notes"}</p></div>
          {feedback.length === 0 ? <p className="quiet">Nothing yet.</p> : (
            <ul className="rule-list">
              {feedback.map((f) => (
                <li key={f.id} style={{ display: "block" }}>
                  <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{f.text}</p>
                  <span className="muted small">
                    {shortDate(f.created_at.slice(0, 10))}{f.page ? ` · on ${f.page}` : ""}
                    {f.reply_to ? <> · reply to <a href={`mailto:${f.reply_to}`}>{f.reply_to}</a></> : " · no reply wanted"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
