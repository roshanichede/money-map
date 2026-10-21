"use client";

import { useEffect, useState } from "react";

import { api, type ImportRow, type RuleRow } from "@/lib/api";
import { plural } from "@/lib/format";
import { Check, Dash, Warn } from "./icons";

const VIA: Record<string, string> = { edit: "from a category you changed", question: "from your answer", chat: "from the chat" };

export function YourData({ refreshKey, categorisedRate, loginEnabled, onDeleted, onRuleDeleted }: {
  refreshKey: number; categorisedRate: number; loginEnabled: boolean; onDeleted: () => void;
  onRuleDeleted: (message: string) => void;
}) {
  const [imports, setImports] = useState<ImportRow[]>([]);
  const [rules, setRules] = useState<RuleRow[]>([]);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => { api.imports().then(setImports).catch(() => setImports([])); }, [refreshKey]);
  useEffect(() => { api.rules().then(setRules).catch(() => setRules([])); }, [refreshKey]);

  async function removeRule(r: RuleRow) {
    const res = await api.deleteRule(r.id);
    onRuleDeleted(`Forgot “${r.text}”. ${plural(res.moved, "payment")} went back to the built-in sorting.`);
  }

  async function remove() {
    await api.deleteAll();
    setConfirming(false);
    onDeleted();
  }

  return (
    <div className="grid-2-wide">
      <section className="card" aria-labelledby="imports-h">
        <div className="card-head">
          <h2 id="imports-h">Imported files</h2>
          <p>{Math.round(categorisedRate * 100)}% of transactions sorted automatically</p>
        </div>
        {imports.length === 0 ? <p className="quiet">Nothing imported yet.</p> : (
          <ul className="data-list">
            {imports.map((u) => (
              <li key={u.id}>
                {u.reconciled === "ok" ? <Check /> : u.reconciled === "mismatch" ? <Warn /> : <Dash />}
                <span>
                  <b>{u.filename}</b>{u.account && <span className="quiet"> → {u.account}</span>}
                  <span className="quiet">: {plural(u.rows_added, "transaction")} added{u.duplicates_skipped ? `, ${u.duplicates_skipped} duplicates skipped` : ""}.</span>
                  <span className="muted small" style={{ display: "block" }}>{u.reconciliation_note}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <div className="stack" style={{ alignContent: "start" }}>
        <section className="card" aria-labelledby="rules-h">
          <div className="card-head">
            <h2 id="rules-h">What MoneyMap has learned</h2>
            <p>{plural(rules.length, "rule")}</p>
          </div>
          {rules.length === 0 ? (
            <p className="quiet">Nothing yet. Change a category, answer a question on the overview, or tell the chat something like “garba is entertainment”.</p>
          ) : (
            <ul className="rule-list">
              {rules.map((r) => (
                <li key={r.id}>
                  <span>{r.text}<span className="muted small" style={{ display: "block" }}>
                    {plural(r.payments, "payment")} sorted by it · {VIA[r.taught_via] ?? "learned"}</span></span>
                  <button className="btn btn-ghost small" onClick={() => removeRule(r)}>Forget</button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card" aria-labelledby="store-h">
          <div className="card-head"><h2 id="store-h">How your data is kept</h2></div>
          <ul className="facts">
            <li><Check /><span><b>Statement files aren&apos;t kept.</b> A PDF or CSV is read in memory, its transactions are pulled out, then the file is discarded. Only its name and the import result are saved.</span></li>
            <li><Check /><span><b>Account numbers aren&apos;t stored in full.</b> Only the last four digits, plus a one-way fingerprint used to recognise the same account in a later upload.</span></li>
            <li><Check /><span>
              <b>{loginEnabled ? "Each person sees only their own data." : "Everything stays on this computer."}</b>{" "}
              {loginEnabled
                ? "You sign in with Google, and every transaction is tied to your account."
                : "Transactions are saved in a database file next to the app. No login, no cloud."}
            </span></li>
            <li><Check /><span><b>The chat sends Claude only calculated facts</b> (totals, merchant names, dates), and only if an API key is set. Never your statements or account numbers.</span></li>
          </ul>
        </section>
        <section className="card" aria-labelledby="ctrl-h">
          <div className="card-head"><h2 id="ctrl-h">Take it with you, or delete it</h2></div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <a className="btn" href="/api/export" download>Export all as CSV</a>
            {confirming ? (
              <>
                <button className="btn btn-danger" onClick={remove}>Yes, delete everything</button>
                <button className="btn-link" onClick={() => setConfirming(false)}>Cancel</button>
              </>
            ) : (
              <button className="btn btn-danger" onClick={() => setConfirming(true)}>Delete all my data</button>
            )}
          </div>
          {confirming && <p className="muted small" style={{ margin: "10px 0 0" }}>This removes every account, transaction and everything MoneyMap has learned. It can&apos;t be undone.</p>}
        </section>
      </div>
    </div>
  );
}
