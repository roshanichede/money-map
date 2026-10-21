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

  const load = useCallback(() => {
    api.questions().then((d) => { setData(d); setCategory(""); setScope(0); }).catch(() => setData(null));
  }, []);
  useEffect(load, [load, refreshKey]);

  const q = data?.items[0];
  if (!data || !q) return null;

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
        <p>{data.total === 1 ? "1 question" : `${data.total} questions, biggest amounts first`}</p>
      </div>
      <p className="learn-q">{q.question}</p>
      <p className="muted small" style={{ margin: "-4px 0 8px" }}>
        {plural(q.count, "payment")}, {moneyRound(q.total_pence)} in total. Right now they&apos;re{" "}
        {q.direction === "out" ? "“Not sorted yet”" : "counted as money from a person"}.
      </p>
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
      <p className="muted small" style={{ margin: "10px 0 0" }}>
        Tip: you can also tell the chat, e.g. “garba is entertainment”.
      </p>
    </section>
  );
}
