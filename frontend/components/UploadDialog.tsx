"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type Account, type AccountType, type UploadResult, type UploadTarget } from "@/lib/api";
import { plural } from "@/lib/format";
import { Check, Dash, IconClose, IconUpload, Warn } from "./icons";

const TYPES: { value: AccountType; label: string }[] = [
  { value: "current", label: "Current account" },
  { value: "savings", label: "Savings" },
  { value: "credit_card", label: "Credit card" },
  { value: "other", label: "Other" },
];

export function UploadResults({ results }: { results: UploadResult[] }) {
  return (
    <ul className="results">
      {results.map((r, i) => (
        <li key={i}>
          {!r.ok ? <Warn /> : r.reconciled === "ok" ? <Check /> : r.reconciled === "mismatch" ? <Warn /> : <Dash />}
          <span>
            <b>{r.filename}</b>
            {r.ok && r.account ? <> → {r.account}</> : null}:{" "}
            {r.ok ? (
              <>
                {plural(r.rows_added ?? 0, "new transaction")}
                {r.duplicates_skipped ? `, ${r.duplicates_skipped} already imported` : ""}
                {r.transfers_matched ? `, ${plural(r.transfers_matched, "transfer")} matched between your accounts` : ""}.{" "}
                <span className="muted">{r.reconciliation_note}</span>
              </>
            ) : (
              r.error
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

function DropZone({ onFiles, busy }: { onFiles: (f: File[]) => void; busy: boolean }) {
  const [over, setOver] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div
      className={`drop${over ? " over" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFiles(Array.from(e.dataTransfer.files)); }}
    >
      <IconUpload size={22} />
      <strong>Drop your bank statements</strong>
      <span className="quiet small">
        As many files as you like: CSV, Excel or PDF, from UK banks (Lloyds, Barclays, HSBC, Monzo…) and Indian
        banks (HDFC, ICICI, SBI, Axis, Kotak…). They&apos;re read one at a time.
      </span>
      <input ref={ref} type="file" accept=".csv,.txt,.pdf,.xls,.xlsx,text/csv,application/pdf" multiple hidden
             onChange={(e) => { onFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
      <button type="button" className="btn" onClick={() => ref.current?.click()}>
        {busy ? "Add more files" : "Choose files"}
      </button>
    </div>
  );
}

// ---------- the upload queue: files go up one at a time, each with its own status ----------

const MAX_BYTES = 10 * 1024 * 1024;
type Status = "waiting" | "reading" | "done" | "failed";
type Item = { id: string; file: File; status: Status; result?: UploadResult; error?: string; retryable?: boolean };

const fileKey = (f: File) => `${f.name}|${f.size}|${f.lastModified}`;
const sizeLabel = (n: number) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

/** Runs uploads one after another. `target()` is read when each file starts, so a new account created by the
 *  first file is reused for the rest. */
function useUploadQueue(target: () => UploadTarget, onFileDone: (r: UploadResult) => void, onAllDone: () => void) {
  const [items, setItems] = useState<Item[]>([]);
  const running = useRef(false);
  const queue = useRef<Item[]>([]);
  const targetRef = useRef(target);
  const doneRef = useRef({ onFileDone, onAllDone });
  useEffect(() => { targetRef.current = target; doneRef.current = { onFileDone, onAllDone }; });

  const update = (id: string, patch: Partial<Item>) => {
    queue.current = queue.current.map((i) => (i.id === id ? { ...i, ...patch } : i));
    setItems(queue.current);
  };

  const run = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    let didAny = false;
    for (;;) {
      const next = queue.current.find((i) => i.status === "waiting");
      if (!next) break;
      update(next.id, { status: "reading" });
      try {
        const res = (await api.upload([next.file], targetRef.current())).results[0];
        if (res.ok) {
          update(next.id, { status: "done", result: res });
          doneRef.current.onFileDone(res);
          didAny = true;
        } else {
          update(next.id, { status: "failed", error: res.error ?? "Couldn't read this file." });
        }
      } catch (e) {
        const msg = (e as Error).message;
        const tooLarge = /413|too large/i.test(msg);
        // a dropped connection or a sleeping server is worth another go; an oversized file isn't
        update(next.id, { status: "failed", error: tooLarge ? "This file is too large to upload here." : msg, retryable: !tooLarge });
      }
    }
    running.current = false;
    if (didAny) doneRef.current.onAllDone();
  }, []);

  const add = useCallback((files: File[]) => {
    const known = new Set(queue.current.filter((i) => i.status !== "failed").map((i) => fileKey(i.file)));
    const fresh: Item[] = [];
    for (const f of files) {
      if (known.has(fileKey(f))) continue; // the same file picked twice
      known.add(fileKey(f));
      const tooBig = f.size > MAX_BYTES;
      fresh.push({ id: `${fileKey(f)}|${Date.now()}|${Math.random()}`, file: f,
                   status: tooBig ? "failed" : "waiting", error: tooBig ? "Larger than 10 MB." : undefined });
    }
    if (!fresh.length) return;
    queue.current = [...queue.current, ...fresh];
    setItems(queue.current);
    void run();
  }, [run]);

  const retry = (id: string) => { update(id, { status: "waiting", error: undefined }); void run(); };
  const remove = (id: string) => { queue.current = queue.current.filter((i) => i.id !== id); setItems(queue.current); };
  const clearFinished = () => { queue.current = queue.current.filter((i) => i.status === "waiting" || i.status === "reading"); setItems(queue.current); };
  const busy = items.some((i) => i.status === "waiting" || i.status === "reading");
  return { items, add, retry, remove, clearFinished, busy };
}

function QueueList({ items, onRetry, onRemove }: { items: Item[]; onRetry: (id: string) => void; onRemove: (id: string) => void }) {
  if (!items.length) return null;
  const done = items.filter((i) => i.status === "done").length;
  const failed = items.filter((i) => i.status === "failed").length;
  const current = items.findIndex((i) => i.status === "reading");
  const added = items.reduce((n, i) => n + (i.result?.rows_added ?? 0), 0);
  return (
    <div className="queue">
      <div className="queue-head">
        <span>
          {current >= 0 ? `Reading file ${current + 1} of ${items.length}` : `${done} of ${items.length} imported`}
          {failed ? `, ${failed} couldn't be read` : ""}
        </span>
        <span className="muted small">{plural(added, "new transaction")}</span>
      </div>
      <div className="queue-bar" aria-hidden="true">
        <span style={{ width: `${((done + failed) / items.length) * 100}%` }} />
      </div>
      <ul className="queue-list">
        {items.map((i) => {
          const r = i.result;
          return (
            <li key={i.id} className={`q-${i.status}`}>
              <span className="q-icon" aria-hidden="true">
                {i.status === "reading" ? <span className="spinner" /> : i.status === "done"
                  ? (r?.reconciled === "mismatch" ? <Warn /> : <Check />)
                  : i.status === "failed" ? <Warn /> : <Dash />}
              </span>
              <span className="q-main">
                <span className="q-name" title={i.file.name}>{i.file.name}</span>
                <span className="q-detail">
                  {i.status === "waiting" && `Waiting · ${sizeLabel(i.file.size)}`}
                  {i.status === "reading" && "Reading…"}
                  {i.status === "failed" && i.error}
                  {i.status === "done" && r && (
                    <>
                      {plural(r.rows_added ?? 0, "new transaction")}{r.account ? ` → ${r.account}` : ""}
                      {r.duplicates_skipped ? `, ${r.duplicates_skipped} already imported` : ""}
                      {r.transfers_matched ? `, ${plural(r.transfers_matched, "transfer")} matched` : ""}
                      {r.reconciled === "mismatch" && <span className="q-warn"> {r.reconciliation_note}</span>}
                    </>
                  )}
                </span>
              </span>
              {i.status === "failed" && i.retryable && (
                <button className="btn-link small" onClick={() => onRetry(i.id)}>Try again</button>
              )}
              {(i.status === "waiting" || i.status === "failed") && (
                <button className="btn btn-ghost q-remove" onClick={() => onRemove(i.id)} aria-label={`Remove ${i.file.name}`}>
                  <IconClose />
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function DemoNotice() {
  return (
    <p className="demo-notice" role="note">
      Demo site: the quickest way in is the sample data.
    </p>
  );
}

export function UploadDialog({ open, onClose, accounts, onImported, demo = false }: {
  open: boolean; onClose: () => void; accounts: Account[]; onImported: () => void; demo?: boolean;
}) {
  const [choice, setChoice] = useState("detect");
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<AccountType>("current");
  const [error, setError] = useState<string | null>(null);
  const createdAccount = useRef<number | null>(null); // a new account made by the first file of a batch

  const queue = useUploadQueue(
    () => {
      if (choice === "new") {
        return createdAccount.current !== null
          ? { kind: "existing", accountId: createdAccount.current }
          : { kind: "new", name: newName.trim(), type: newType };
      }
      return choice === "detect" ? { kind: "detect" } : { kind: "existing", accountId: Number(choice) };
    },
    (r) => { if (choice === "new" && createdAccount.current === null && r.account_id) createdAccount.current = r.account_id; },
    () => onImported(),
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  function add(files: File[]) {
    if (!files.length) return;
    if (choice === "new" && !newName.trim()) { setError("Give the new account a name first."); return; }
    setError(null);
    if (!queue.busy) createdAccount.current = null;
    queue.add(files);
  }

  function close() {
    if (!queue.busy) queue.clearFinished();
    onClose();
  }

  return (
    <>
      <div className="scrim" onClick={close} />
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="up-h">
        <div className="dialog-head">
          <h2 id="up-h">Add statements</h2>
          <button className="btn btn-ghost" onClick={close} aria-label="Close"><IconClose /></button>
        </div>
        {demo && <DemoNotice />}
        <DropZone onFiles={add} busy={queue.busy} />
        <div className="field">
          <label htmlFor="up-account">Which account are these from?</label>
          <select id="up-account" className="select" value={choice} disabled={queue.busy}
                  onChange={(e) => setChoice(e.target.value)}>
            <option value="detect">Work it out from the file</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            <option value="new">A new account…</option>
          </select>
          {choice === "detect" && (
            <span className="muted small">
              Uses the account number in the file, or matches it to payments you&apos;ve already imported. Otherwise it becomes a new account you can rename.
            </span>
          )}
        </div>
        {choice === "new" && (
          <div className="field field-row">
            <input className="input" placeholder="Name, e.g. Monzo" value={newName} onChange={(e) => setNewName(e.target.value)} aria-label="New account name" />
            <select className="select" value={newType} onChange={(e) => setNewType(e.target.value as AccountType)} aria-label="Account type">
              {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
        )}
        {error && <div className="error-box" style={{ marginTop: 14 }}>{error}</div>}
        <QueueList items={queue.items} onRetry={queue.retry} onRemove={queue.remove} />
        <div className="dialog-foot">
          {queue.busy && <span className="muted small">You can close this; files keep uploading.</span>}
          <button className="btn" onClick={close}>{queue.items.some((i) => i.status === "done") ? "Done" : "Close"}</button>
        </div>
      </div>
    </>
  );
}

export function Welcome({ onImported, demo = false }: { onImported: () => void; demo?: boolean }) {
  const queue = useUploadQueue(() => ({ kind: "detect" }), () => {}, () => onImported());
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function run(job: () => Promise<{ results: UploadResult[] }>) {
    setBusy(true);
    setError(null);
    try { setResults((await job()).results); onImported(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return (
    <div className="welcome">
      <h2>See where your money went, without linking your bank.</h2>
      <p className="lede">
        Upload the statements you already have. MoneyMap sorts every payment, finds your regular bills, keeps
        money moved between your own accounts out of your spending, and answers questions in plain English.
      </p>
      <div className="card">
        {demo && <DemoNotice />}
        {demo ? (
          <div style={{ display: "flex", justifyContent: "center", padding: "12px 0" }}>
            <button className="btn btn-primary" onClick={() => run(() => api.demo())} disabled={busy}>
              {busy ? "Loading sample data…" : "Try it with sample data"}
            </button>
          </div>
        ) : (
          <>
            <DropZone onFiles={(f) => f.length && queue.add(f)} busy={queue.busy} />
            <QueueList items={queue.items} onRetry={queue.retry} onRemove={queue.remove} />
            <div style={{ display: "flex", justifyContent: "center", marginTop: 12 }}>
              <button className="btn-link" onClick={() => run(() => api.demo())} disabled={busy}>
                Or try it with sample data (current account, savings and a credit card)
              </button>
            </div>
          </>
        )}
        {results && <UploadResults results={results} />}
        {error && <div className="error-box" style={{ marginTop: 12 }}>{error}</div>}
      </div>
      <div className="how">
        <div><b>Getting your statement</b>In online banking, open the account and look for Download, Export or Statements. Choose CSV or Excel if offered; PDF works too.</div>
        <div><b>Several accounts, two currencies</b>Upload each one. Transfers between them are matched so nothing counts twice, and pounds and rupees are kept apart.</div>
        <div><b>Your files aren&apos;t kept</b>Statements are read, then thrown away. Only the transactions are saved, and you can delete them any time.</div>
      </div>
    </div>
  );
}
