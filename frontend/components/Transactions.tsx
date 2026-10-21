"use client";

import { useEffect, useState } from "react";

import { api, type Account, type ScopeOption, type Txn } from "@/lib/api";
import { categoryLabel, KIND_TAG, money, shortDate } from "@/lib/format";
import { CategoryIcon } from "./CategoryIcon";

type Props = {
  month: string;
  accountId: number | null;
  accounts: Account[];
  category: string | null;
  onCategory: (category: string | null) => void;
  categories: string[];
  refreshKey: number;
  onRecategorised: (message: string) => void;
  /** Compact mode for the overview: no filters, a few rows and a "See all" link. */
  limit?: number;
  onSeeAll?: () => void;
  /** Start with this search, e.g. a payer picked from "Money in". */
  initialQuery?: string;
};

const PAGE = 30;

export function Transactions(props: Props) {
  const { month, accountId, accounts, category, onCategory, categories, refreshKey, onRecategorised, limit, onSeeAll } = props;
  const [rows, setRows] = useState<Txn[]>([]);
  const [q, setQ] = useState(props.initialQuery ?? "");
  const [error, setError] = useState<string | null>(null);
  const [teach, setTeach] = useState<{ txn: Txn; category: string; options: ScopeOption[] } | null>(null);
  const [saving, setSaving] = useState(false);
  const filterKey = `${month}|${accountId}|${category}|${q}`;
  const [page, setPage] = useState({ key: filterKey, shown: PAGE });
  const shown = limit ?? (page.key === filterKey ? page.shown : PAGE);
  const names = new Map(accounts.map((a) => [a.id, a.name]));
  const showAccount = accounts.length > 1 && accountId === null && !limit;

  useEffect(() => {
    const t = setTimeout(() => {
      api.transactions({ month, category: category ?? undefined, q: q.trim() || undefined, accountId })
        .then((r) => { setRows(r); setError(null); })
        .catch((e) => setError(e.message));
    }, 120);
    return () => clearTimeout(t);
  }, [month, accountId, category, q, refreshKey]);

  async function recategorise(t: Txn, next: string) {
    try {
      const r = await api.setCategory(t.id, next, false);
      setRows((rs) => rs.map((x) => (x.id === t.id ? { ...x, category: next, category_source: "manual" } : x)));
      if (r.options.length) setTeach({ txn: t, category: next, options: r.options });
      else onRecategorised(`Moved this ${r.merchant} payment to ${categoryLabel(next)}.`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function applyWider(o: ScopeOption | null) {
    if (!teach) return;
    if (!o) {
      onRecategorised(`Moved just this payment to ${categoryLabel(teach.category)}.`);
      setTeach(null);
      return;
    }
    setSaving(true);
    try {
      const r = await api.addRule(o.spec, teach.category, "edit");
      onRecategorised(`Learned: ${r.rule}. Moved ${r.moved} more ${r.moved === 1 ? "payment" : "payments"}, and new statements will follow it.`);
      setTeach(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card" id="transactions" aria-labelledby="txn-h">
      <div className="card-head">
        <h2 id="txn-h" className={limit ? undefined : "visually-hidden"}>{limit ? "Latest transactions" : "Transactions"}</h2>
        {!limit && <p>Change a category and MoneyMap asks how widely to apply it.</p>}
      </div>
      {!limit && (
        <div className="filters">
          <label className="visually-hidden" htmlFor="txn-search">Search transactions</label>
          <input id="txn-search" className="input" placeholder="Search, e.g. Tesco" value={q} onChange={(e) => setQ(e.target.value)} />
          <label className="visually-hidden" htmlFor="txn-cat">Category</label>
          <select id="txn-cat" className="select" value={category ?? ""} onChange={(e) => onCategory(e.target.value || null)}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
          </select>
          <span className="muted small">{rows.length} {rows.length === 1 ? "transaction" : "transactions"}</span>
        </div>
      )}
      {error && <div className="error-box">{error}</div>}
      {teach && (
        <div className="teach-bar" role="status">
          <p>
            <b>Moved to {categoryLabel(teach.category)}.</b> Should MoneyMap do the same for other payments like
            this one ({teach.txn.merchant})?
          </p>
          <div className="teach-options">
            {teach.options.map((o) => (
              <button key={o.label} className="btn" disabled={saving} onClick={() => applyWider(o)}>
                {o.label}
                <span className="muted small">{o.matches} more{o.would_move < o.matches ? `, ${o.would_move} would change` : ""}</span>
              </button>
            ))}
            <button className="btn btn-ghost" disabled={saving} onClick={() => applyWider(null)}>Just this one</button>
          </div>
        </div>
      )}
      <div className="table-scroll">
        <table className={`table${limit ? " compact" : ""}`}>
          <thead>
            <tr>
              <th className="col-date">Date</th>
              <th>Payee</th>
              {showAccount && <th className="col-acct">Account</th>}
              <th className="col-cat">Category</th>
              <th className="right col-amt">Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, shown).map((t) => (
              <tr key={t.id}>
                <td className="num quiet nowrap">{shortDate(t.date)}</td>
                <td className="payee-cell">
                  <CategoryIcon category={t.category} size={16} />
                  <span className="payee-text">
                  {t.merchant} {t.is_transfer && <span className="tag" title="Matched with a payment in another of your accounts">transfer</span>}
                  {!t.is_transfer && KIND_TAG[t.kind] && (
                    <span className={`tag tag-${t.kind}`} title={KIND_TAG[t.kind]!.title}>{KIND_TAG[t.kind]!.label}</span>
                  )}
                  {!limit && <span className="sub" title={t.description}>{t.description}</span>}
                  </span>
                </td>
                {showAccount && <td className="quiet small acct-cell" title={names.get(t.account_id)}>{names.get(t.account_id)}</td>}
                <td>
                  <label className="visually-hidden" htmlFor={`cat-${t.id}`}>Category for {t.merchant}</label>
                  <select id={`cat-${t.id}`} className={`cat-select${t.category === "Other" ? " other" : ""}`}
                          value={t.category} onChange={(e) => recategorise(t, e.target.value)}>
                    {categories.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
                  </select>
                </td>
                <td className={`right num${t.amount_pence > 0 ? " amount-in" : ""}`}>
                  {t.amount_pence > 0 ? "+" : ""}{money(t.amount_pence)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && !error && <p className="quiet">No transactions match.</p>}
      <div className="card-foot">
        <span />
        {limit && onSeeAll && rows.length > limit && <button className="btn-link" onClick={onSeeAll}>See all {rows.length}</button>}
        {!limit && rows.length > shown && (
          <button className="btn" onClick={() => setPage({ key: filterKey, shown: shown + PAGE })}>
            Show {Math.min(PAGE, rows.length - shown)} more
          </button>
        )}
      </div>
    </section>
  );
}
