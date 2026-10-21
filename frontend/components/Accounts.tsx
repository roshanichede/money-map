"use client";

import { useState } from "react";

import { api, type Account, type AccountType } from "@/lib/api";
import { money, plural, setCurrency, shortDate, SYMBOLS } from "@/lib/format";
import { AccountIcon, Info } from "./icons";

const TYPES: { value: AccountType; label: string }[] = [
  { value: "current", label: "Current account" },
  { value: "savings", label: "Savings" },
  { value: "credit_card", label: "Credit card" },
  { value: "other", label: "Other" },
];

function AccountCard({ a, onChanged, onOpen }: { a: Account; onChanged: (msg?: string) => void; onOpen: () => void }) {
  const [name, setName] = useState(a.name);
  const [confirming, setConfirming] = useState(false);

  setCurrency(a.currency); // this card's balance in its own currency
  async function save(patch: { name?: string; account_type?: AccountType; currency?: string }) {
    await api.updateAccount(a.id, patch);
    onChanged();
  }
  async function remove() {
    const r = await api.deleteAccount(a.id);
    onChanged(`Deleted ${a.name} and its ${plural(r.deleted_transactions, "transaction")}.`);
  }

  return (
    <article className="card account-card">
      <div className="account-top">
        <span className="account-icon"><AccountIcon type={a.account_type} /></span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <label className="visually-hidden" htmlFor={`acct-${a.id}`}>Account name</label>
          <input id={`acct-${a.id}`} className="account-name" value={name} onChange={(e) => setName(e.target.value)}
                 onBlur={() => name.trim() && name !== a.name && save({ name })}
                 onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
          <div className="muted small">{[a.bank, a.last4 && `••${a.last4}`].filter(Boolean).join(" ") || "No account number in the file"}</div>
        </div>
      </div>
      <div>
        <div className="account-bal num">{a.balance_pence === null ? "—" : money(a.balance_pence)}</div>
        <div className="muted small">
          {a.balance_pence === null ? "This export has no running balance" : `Balance on ${shortDate(a.balance_date!)}`}
        </div>
      </div>
      <dl className="kv">
        <dt>Type</dt>
        <dd>
          <label className="visually-hidden" htmlFor={`type-${a.id}`}>Account type</label>
          <select id={`type-${a.id}`} className="cat-select" value={a.account_type} onChange={(e) => save({ account_type: e.target.value as AccountType })}>
            {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </dd>
        <dt>Currency</dt>
        <dd>
          <label className="visually-hidden" htmlFor={`cur-${a.id}`}>Currency</label>
          <select id={`cur-${a.id}`} className="cat-select" value={a.currency} onChange={(e) => save({ currency: e.target.value })}>
            {Object.entries(SYMBOLS).map(([code, sym]) => <option key={code} value={code}>{sym} {code}</option>)}
          </select>
        </dd>
        <dt>Statements cover</dt>
        <dd>{a.first_date ? `${shortDate(a.first_date)} to ${shortDate(a.last_date!)}` : "—"}</dd>
        <dt>Transactions</dt>
        <dd className="num">{a.transaction_count}</dd>
        <dt>Transfers matched</dt>
        <dd className="num">{a.transfers_matched}</dd>
      </dl>
      <div className="account-actions">
        <button className="btn-link" onClick={onOpen}>View transactions</button>
        {confirming ? (
          <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button className="btn btn-danger" onClick={remove}>Delete it</button>
            <button className="btn-link" onClick={() => setConfirming(false)}>Cancel</button>
          </span>
        ) : (
          <button className="btn btn-ghost btn-danger" onClick={() => setConfirming(true)}>Delete account</button>
        )}
      </div>
    </article>
  );
}

export function Accounts({ accounts, onChanged, onOpenAccount, onAdd }: {
  accounts: Account[]; onChanged: (msg?: string) => void; onOpenAccount: (id: number) => void; onAdd: () => void;
}) {
  const total = accounts.reduce((sum, a) => sum + (a.balance_pence ?? 0), 0);
  const withBalance = accounts.filter((a) => a.balance_pence !== null).length;
  return (
    <div className="stack">
      <div className="banner">
        <Info />
        <span>
          Money moving between your own accounts, such as savings transfers and credit card repayments, is matched
          automatically and left out of spending. Card purchases count as spending instead of the repayment that clears them.
          {withBalance > 1 && <> Combined balance of accounts that show one: <b className="num">{money(total)}</b>.</>}
        </span>
      </div>
      <div className="accounts">
        {accounts.map((a) => <AccountCard key={`${a.id}-${a.name}`} a={a} onChanged={onChanged} onOpen={() => onOpenAccount(a.id)} />)}
      </div>
      <div><button className="btn" onClick={onAdd}>Add another account&apos;s statements</button></div>
    </div>
  );
}
