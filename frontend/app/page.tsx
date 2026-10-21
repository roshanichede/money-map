"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { CategoryBars } from "@/components/CategoryBars";
import { Chat } from "@/components/Chat";
import { Figures } from "@/components/Figures";
import { Headline } from "@/components/Headline";
import { Mark } from "@/components/icons";
import { MonthsChart } from "@/components/MonthsChart";
import { RecurringList } from "@/components/RecurringList";
import { Transactions } from "@/components/Transactions";
import { EmptyState, PickFiles, UploadResults, useUpload } from "@/components/Upload";
import { YourData } from "@/components/YourData";
import { api, type Overview, type Recurring, type Summary } from "@/lib/api";
import { isPartialMonth, monthLabel } from "@/lib/format";

export default function Home() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [month, setMonth] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [recurring, setRecurring] = useState<{ items: Recurring[]; active_monthly_total_pence: number } | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [category, setCategory] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dataVersion, setDataVersion] = useState(0); // bumps on upload/delete: resets the chat
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);


  const loadOverview = useCallback((keepMonth: boolean) => {
    api.overview()
      .then((o) => {
        setOverview(o);
        setError(null);
        setMonth((m) => (keepMonth && m && o.months.some((x) => x.month === m) ? m : o.months.at(-1)?.month ?? null));
      })
      .catch(() => setError("Can't reach the MoneyMap API. Is the backend running on port 8000?"));
    api.recurring().then(setRecurring).catch(() => {});
  }, []);

  /** Re-read everything after an upload, a category change or a delete. */
  const refresh = useCallback((keepMonth = true) => {
    setRefreshKey((k) => k + 1);
    if (!keepMonth) setDataVersion((v) => v + 1);
    loadOverview(keepMonth);
  }, [loadOverview]);

  useEffect(() => {
    loadOverview(false);
    api.categories().then(setCategories).catch(() => {});
  }, [loadOverview]);

  useEffect(() => {
    if (!month) return;
    api.summary(month).then(setSummary).catch((e) => setError(e.message));
  }, [month, refreshKey]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  const up = useUpload(() => refresh(false));
  const months = useMemo(() => overview?.months ?? [], [overview]);
  const monthRow = months.find((m) => m.month === month);

  const suggestions = useMemo(() => {
    if (months.length === 0) return [];
    const last = monthLabel(months.at(-1)!.month).split(" ")[0];
    const prev = months.length > 1 ? monthLabel(months.at(-2)!.month).split(" ")[0] : null;
    return [
      prev ? `Why did ${last} cost more or less than ${prev}?` : `Where did my money go in ${last}?`,
      "How much did I spend on takeaways this month?",
      "What subscriptions do I have?",
      prev ? `Where did my money go in ${prev}?` : "How much did I spend on groceries?",
    ];
  }, [months]);

  if (error && !overview) {
    return <main className="shell"><div className="error-box" style={{ marginTop: 40 }}>{error}</div></main>;
  }
  if (!overview) return <main className="shell" aria-busy="true" />;

  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand"><Mark />MoneyMap</div>
        {months.length > 0 && (
          <div className="topbar-actions">
            <PickFiles onFiles={up.upload} disabled={up.busy}>{up.busy ? "Reading…" : "Add statements"}</PickFiles>
          </div>
        )}
      </div>

      {up.results && months.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <UploadResults results={up.results} />
          <button className="btn-link" style={{ fontSize: 13, marginTop: 6 }} onClick={up.clear}>Dismiss</button>
        </div>
      )}
      {up.error && <div className="error-box">{up.error}</div>}

      {months.length === 0 ? (
        <EmptyState onDone={() => refresh(false)} />
      ) : (
        <>
          <nav className="months" role="tablist" aria-label="Month">
            {months.map((m) => (
              <button key={m.month} role="tab" aria-selected={m.month === month} className="month-tab"
                      ref={(el) => { if (el && m.month === month) el.scrollIntoView({ block: "nearest", inline: "nearest" }); }}
                      onClick={() => { setMonth(m.month); setCategory(null); }}>
                {monthLabel(m.month, "short")} {m.month.slice(0, 4)}
                {isPartialMonth(m.month, m.last_date) && <small>so far</small>}
              </button>
            ))}
          </nav>

          <div className="grid">
            <div className="main-col">
              {summary && monthRow && summary.month === month && (
                <>
                  <section>
                    <Headline summary={summary} month={monthRow} />
                    <Figures summary={summary} recurringMonthly={recurring?.active_monthly_total_pence ?? 0}
                             partial={isPartialMonth(monthRow.month, monthRow.last_date)} />
                  </section>
                  <CategoryBars
                    summary={summary}
                    selected={category}
                    onSelect={(c) => {
                      setCategory(c);
                      if (c) document.getElementById("transactions")?.scrollIntoView({ behavior: "smooth", block: "start" });
                    }}
                  />
                  <MonthsChart months={months} selected={month!} onSelect={(m) => { setMonth(m); setCategory(null); }} />
                  {recurring && <RecurringList items={recurring.items} monthlyTotal={recurring.active_monthly_total_pence} />}
                  <Transactions
                    month={month!}
                    category={category}
                    onClearCategory={() => setCategory(null)}
                    categories={categories}
                    refreshKey={refreshKey}
                    onRecategorised={(msg) => { setToast(msg); refresh(); }}
                  />
                  <YourData refreshKey={refreshKey} categorisedRate={overview.categorised_rate}
                            onDeleted={() => { setToast("All your data was deleted."); refresh(false); }} />
                </>
              )}
            </div>
            <div className="side-col">
              <Chat key={dataVersion} suggestions={suggestions} />
            </div>
          </div>
        </>
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </main>
  );
}
