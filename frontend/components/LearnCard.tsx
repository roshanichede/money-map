"use client";

import { useCallback, useEffect, useState } from "react";

import { api, type Question, type RuleSpec } from "@/lib/api";
import { categoryLabel, money, moneyRound, plural, shortDate } from "@/lib/format";

type Props = { categories: string[]; refreshKey: number; onTaught: (message: string) => void };

/** One question at a time about the payments MoneyMap is least sure of, biggest amounts first.
 *  Each answer becomes a rule, so it also sorts future statements. */
export function LearnCard({ categories, refreshKey, onTaught }: Props) {
  const [data, setData] = useState<{ total: number; items: Question[] } | null>(null);
  const [category, setCategory] = useState("");
  const [scope, setScope] = useState(0);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  // "they're for different things": sort this person's payments by hand (only while it's still the same question)
  const [splitKey, setSplitKey] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());

  const load = useCallback(() => {
    api.questions().then((d) => { setData(d); setCategory(""); setScope(0); setPicked(new Set()); }).catch(() => setData(null));
  }, []);
  useEffect(load, [load, refreshKey]);

  const q = data?.items[0];
  if (!data || !q) return null;
  const split = splitKey === q.key;
  if (!open) {
    return (
      <button className="learn-banner" onClick={() => setOpen(true)}>
        <span className="learn-badge num">{data.total}</span>
        <span><b>Help MoneyMap sort the rest</b><span className="muted">One answer sorts every payment like it.</span></span>
        <span className="btn btn-primary">Start</span>
      </button>
    );
  }

  const scopes: { label: string; spec: RuleSpec }[] = [
    { label: q.word ? `Only ${q.name}, when the note says “${q.word}”` : q.spec.payee ? `Only ${q.name}, when there's no note` : `Every ${q.name} payment`, spec: q.spec },
    ...q.alternatives,
  ];
  const choices = categories.filter((c) => (q.direction === "out" ? !["Salary", "Other income"].includes(c) : true));

  async function save() {
    if (!q || !category) return;
    setBusy(true);
    try {
      const r = await api.addRule(scopes[scope].spec, category, "question");
      onTaught(`Learned: ${r.rule}. Moved ${plural(r.moved, "payment")}.`);
      load();
    } finally {
      setBusy(false);
    }
  }

  async function sortPicked() {
    if (!category || picked.size === 0) return;
    setBusy(true);
    try {
      const r = await api.categorise([...picked], category);
      onTaught(`Sorted ${plural(r.updated, "payment")} as ${categoryLabel(category)}. Nothing else changes.`);
      load();
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: number) {
    setPicked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }

  async function skip() {
    if (!q) return;
    setBusy(true);
    try {
      await api.dismissQuestion(q.key);
      load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card learn-card" aria-labelledby="learn-h">
      <div className="card-head">
        <h2 id="learn-h">Help MoneyMap learn</h2>
        <button className="btn-link small" onClick={() => setOpen(false)}>
          {data.total === 1 ? "1 question" : `${data.total} questions`}, biggest first. Close
        </button>
      </div>
      <p className="learn-q">{q.question}</p>
      <p className="muted small" style={{ margin: "-4px 0 8px" }}>
        {plural(q.count, "payment")}, {moneyRound(q.total_pence)} in total. Right now they&apos;re{" "}
        {q.direction === "out" ? "“Not sorted yet”" : "counted as money from a person"}.
      </p>
      {split ? (
        <>
          <p className="small" style={{ margin: "0 0 8px" }}>
            Tick the payments that belong together, pick what they were for, and sort them. Repeat for the next set.
            These don&apos;t teach a rule, so future payments to {q.name} will still be asked about.
          </p>
          <div className="learn-split-tools small">
            <button className="btn-link small" onClick={() => setPicked(new Set(q.payments.map((p) => p.id)))}>Tick all</button>
            <button className="btn-link small" onClick={() => setPicked(new Set())}>Clear</button>
            <span className="muted">{picked.size} ticked</span>
          </div>
          <ul className="learn-examples learn-pick">
            {q.payments.map((p) => (
              <li key={p.id}>
                <label>
                  <input type="checkbox" checked={picked.has(p.id)} onChange={() => toggle(p.id)} />
                  <span className="num">{shortDate(p.date)}</span><span title={p.description}>{p.description}</span>
                  <span className="num">{money(p.amount_pence)}</span>
                </label>
              </li>
            ))}
          </ul>
          <div className="learn-form">
            <label className="visually-hidden" htmlFor="learn-cat">Category</label>
            <select id="learn-cat" className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">These were for…</option>
              {choices.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
            </select>
            <button className="btn btn-primary" disabled={!category || picked.size === 0 || busy} onClick={sortPicked}>
              Sort {picked.size || ""} {picked.size === 1 ? "payment" : "payments"}
            </button>
            <button className="btn btn-ghost" disabled={busy} onClick={() => { setSplitKey(null); setPicked(new Set()); }}>Back</button>
          </div>
        </>
      ) : (
        <>
        <ul className="learn-examples">
          {q.examples.map((e, i) => (
            <li key={i}><span className="num">{shortDate(e.date)}</span><span title={e.description}>{e.description}</span>
              <span className="num">{money(e.amount_pence)}</span></li>
          ))}
        </ul>
        {scopes.length > 1 && (
          <fieldset className="learn-scope" style={{ border: 0, padding: 0 }}>
            <legend className="visually-hidden">Apply the answer to</legend>
            {scopes.map((s, i) => (
              <label key={s.label}>
                <input type="radio" name="learn-scope" checked={scope === i} onChange={() => setScope(i)} />
                {s.label}
              </label>
            ))}
          </fieldset>
        )}
        <div className="learn-form">
          <label className="visually-hidden" htmlFor="learn-cat">Category</label>
          <select id="learn-cat" className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Choose a category…</option>
            {choices.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
          </select>
          <button className="btn btn-primary" disabled={!category || busy} onClick={save}>Save</button>
          <button className="btn btn-ghost" disabled={busy} onClick={skip}>Skip</button>
        </div>
          {q.count > 1 && (q.payments?.length ?? 0) > 1 && (
            <button className="btn-link small" style={{ marginTop: 10 }} onClick={() => { setSplitKey(q.key); setCategory(""); }}>
              They&apos;re for different things? Sort them one by one
            </button>
          )}
        </>
      )}
      <p className="muted small" style={{ margin: "10px 0 0" }}>
        Tip: you can also tell the chat, e.g. “garba is entertainment”.
      </p>
    </section>
  );
}
