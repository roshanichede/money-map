"use client";

import { useEffect, useState } from "react";

import { api, type Account, type CaptureLink } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { Check } from "./icons";

type Source = "applepay" | "sms";

const SOURCES: Record<Source, { title: string; lede: string; steps: React.ReactNode[]; note: string }> = {
  applepay: {
    title: "Apple Pay taps",
    lede: "Every time you tap your phone or watch to pay, the merchant and amount arrive here within seconds.",
    steps: [
      <>On your iPhone, open <b>Shortcuts</b>, go to <b>Automation</b> and tap <b>+</b>.</>,
      <>Choose <b>Transaction</b>. Pick the card for this account, select <b>Run Immediately</b>, then tap <b>Next</b>.</>,
      <>Tap <b>New Blank Automation</b>, then add the action <b>Get Contents of URL</b>.</>,
      <>Paste your link as the URL. Tap the arrow to expand it: set <b>Method</b> to <b>POST</b> and <b>Request Body</b> to <b>JSON</b>.</>,
      <>Add two fields. <code>merchant</code>: choose <b>Shortcut Input</b>, then <b>Merchant</b>. <code>amount</code>: <b>Shortcut Input</b>, then <b>Amount</b>.</>,
      <>Tap <b>Done</b>. Your next tap shows up on MoneyMap tagged <i>just now</i>.</>,
    ],
    note: "Catches Wallet taps only. Online card payments, direct debits and transfers still come from your statement.",
  },
  sms: {
    title: "Bank texts",
    lede: "Indian banks text you for every debit, UPI included. Each text is forwarded here and read automatically.",
    steps: [
      <>On your iPhone, open <b>Shortcuts</b>, go to <b>Automation</b> and tap <b>+</b>.</>,
      <>Choose <b>Message</b>. Under <b>Message Contains</b>, type <code>debited</code>. Select <b>Run Immediately</b>, then <b>Next</b>.</>,
      <>Tap <b>New Blank Automation</b>, then add <b>Get Contents of URL</b>.</>,
      <>Paste your link as the URL. Expand it: <b>Method</b> POST, <b>Request Body</b> JSON.</>,
      <>Add one field: <code>sms</code>, choose <b>Shortcut Input</b>, then <b>Content</b>.</>,
      <>Tap <b>Done</b>. Repeat steps 1 to 5 with <code>credited</code> and <code>spent</code> to catch money in and card payments too.</>,
    ],
    note: "Texts have to reach this iPhone, so keep your Indian SIM or eSIM active on it. OTPs, offers and bill reminders are ignored.",
  },
};

function Steps({ source }: { source: Source }) {
  return (
    <ol className="live-steps">
      {SOURCES[source].steps.map((s, i) => <li key={i}>{s}</li>)}
    </ol>
  );
}

function NewLink({ source, accounts, onCreated }: { source: Source; accounts: Account[]; onCreated: () => void }) {
  const preferred = accounts.find((a) => (source === "sms" ? a.currency === "INR" : a.currency !== "INR")) ?? accounts[0];
  const [accountId, setAccountId] = useState<number | null>(preferred?.id ?? null);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [checked, setChecked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create() {
    if (accountId === null) return;
    setBusy(true);
    try {
      const r = await api.createCaptureLink(accountId, source);
      setLink(`${window.location.origin}${r.path}`);
      setCopied(false);
      setChecked(null);
      onCreated();
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!link) return;
    try { await navigator.clipboard.writeText(link); setCopied(true); } catch { setCopied(false); }
  }

  async function check() {
    if (!link) return;
    try {
      const r = await api.checkCaptureLink(new URL(link).pathname);
      setChecked(r.linked ? `Working: payments will go to ${r.linked}.` : "Working.");
    } catch (e) {
      setChecked(`Not working: ${(e as Error).message}`);
    }
  }

  return (
    <div className="live-new">
      {!link ? (
        <div className="live-form">
          <label className="visually-hidden" htmlFor={`acct-${source}`}>Account</label>
          <select id={`acct-${source}`} className="select" value={accountId ?? ""} onChange={(e) => setAccountId(Number(e.target.value))}>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <button className="btn btn-primary" onClick={create} disabled={busy || accountId === null}>
            {busy ? "Creating…" : "Create my link"}
          </button>
        </div>
      ) : (
        <div className="live-link">
          <p className="small"><b>Your private link.</b> Copy it now: for your security it won&apos;t be shown again (you can always make a new one).</p>
          <div className="live-link-row">
            <input className="input" readOnly value={link} onFocus={(e) => e.target.select()} aria-label="Your private link" />
            <button className="btn btn-primary" onClick={copy}>{copied ? <><Check /> Copied</> : "Copy"}</button>
          </div>
          <div className="live-link-row">
            <button className="btn-link small" onClick={check}>Check the link works</button>
            {checked && <span className="small muted">{checked}</span>}
          </div>
          <Steps source={source} />
        </div>
      )}
    </div>
  );
}

export function LiveTracking({ accounts }: { accounts: Account[] }) {
  const [links, setLinks] = useState<CaptureLink[]>([]);
  const [version, setVersion] = useState(0);
  useEffect(() => { api.captureLinks().then(setLinks).catch(() => setLinks([])); }, [version]);

  if (!accounts.length) {
    return <section className="card"><p className="quiet">Upload a statement first, so there&apos;s an account for live payments to go into.</p></section>;
  }

  return (
    <div className="stack">
      <section className="live-intro">
        <h2>See spending the moment it happens</h2>
        <p>
          Your iPhone can send each payment to MoneyMap as it happens, using the built-in Shortcuts app. Payments
          show up tagged <span className="tag tag-pending">just now</span>, and when you upload the statement later
          each one is replaced by the statement&apos;s own row, so nothing is counted twice.
        </p>
      </section>
      <div className="grid-2">
        {(Object.keys(SOURCES) as Source[]).map((source) => (
          <section key={source} className="card live-card" aria-labelledby={`live-${source}`}>
            <div className="card-head"><h2 id={`live-${source}`}>{SOURCES[source].title}</h2></div>
            <p className="live-lede">{SOURCES[source].lede}</p>
            <NewLink source={source} accounts={accounts} onCreated={() => setVersion((v) => v + 1)} />
            <p className="muted small live-note">{SOURCES[source].note}</p>
          </section>
        ))}
      </div>
      {links.length > 0 && (
        <section className="card" aria-labelledby="links-h">
          <div className="card-head"><h2 id="links-h">Your links</h2><p>Turn one off if you lose your phone or stop using it.</p></div>
          <ul className="rule-list">
            {links.map((l) => (
              <li key={l.id}>
                <span>
                  {SOURCES[l.source].title} → {l.account}
                  <span className="muted small" style={{ display: "block" }}>
                    Made {shortDate(l.created_at.slice(0, 10))}.{" "}
                    {l.uses ? `${l.uses} ${l.uses === 1 ? "payment" : "payments"} received, last on ${shortDate(l.last_used!.slice(0, 10))}.` : "Nothing received yet."}
                  </span>
                </span>
                <button className="btn btn-ghost small" onClick={async () => { await api.revokeCaptureLink(l.id); setVersion((v) => v + 1); }}>
                  Turn off
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
