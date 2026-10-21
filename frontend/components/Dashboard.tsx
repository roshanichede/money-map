"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { SessionUser } from "@/auth";
import { api, type Account, type Earnings, type Overview, type Recurring, type Summary } from "@/lib/api";
import { isUnfinished, monthLabel } from "@/lib/format";
import { Accounts } from "./Accounts";
import { CategoryBars } from "./CategoryBars";
import { ChatDrawer } from "./Chat";
import { Highlights } from "./Highlights";
import { LearnCard } from "./LearnCard";
import { IconChat, IconUpload } from "./icons";
import { MoneyIn } from "./MoneyIn";
import { MonthsChart } from "./MonthsChart";
import { RecurringList } from "./RecurringList";
import { Sidebar, VIEWS, type View } from "./Sidebar";
import { Stats, SummarySentence } from "./Summary";
import { Transactions } from "./Transactions";
import { UploadDialog, Welcome } from "./UploadDialog";
import { YourData } from "./YourData";

type RecurringData = { items: Recurring[]; active_monthly_total_pence: number };

function readView(): View {
  if (typeof window === "undefined") return "overview";
  const v = window.location.hash.replace(/^#\/?/, "") as View;
  return VIEWS.some((x) => x.id === v) ? v : "overview";
}

export function Dashboard({ user, loginEnabled }: { user: SessionUser; loginEnabled: boolean }) {
  const [view, setView] = useState<View>("overview");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [month, setMonth] = useState<string | null>(null); // "all" is allowed on the Transactions view
  const [summary, setSummary] = useState<Summary | null>(null);
  const [recurring, setRecurring] = useState<RecurringData | null>(null);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [category, setCategory] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dataVersion, setDataVersion] = useState(0);
  const [chatOpen, setChatOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ----- routing by hash, so back/forward and links work -----
  useEffect(() => {
    const sync = () => setView(readView());
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  const go = useCallback((v: View) => {
    if (v !== "transactions") setSearch("");
    window.location.hash = `/${v}`;
    window.scrollTo({ top: 0 });
  }, []);

  // ----- data -----
  const load = useCallback((acct: number | null, keepMonth: boolean) => {
    api.accounts().then((list) => {
      setAccounts(list);
      if (acct !== null && !list.some((a) => a.id === acct)) setAccountId(null);
    }).catch(() => {});
    api.overview(acct)
      .then((o) => {
        setOverview(o);
        setError(null);
        setMonth((m) => (keepMonth && m && (m === "all" || o.months.some((x) => x.month === m)) ? m : o.months.at(-1)?.month ?? null));
      })
      .catch((e) => setError(e.message));
    api.recurring(acct).then(setRecurring).catch(() => {});
    api.earnings(acct).then(setEarnings).catch(() => {});
  }, []);

  useEffect(() => {
    load(null, false);
    api.categories().then(setCategories).catch(() => {});
  }, [load]);

  const refresh = useCallback((keepMonth = true) => {
    setRefreshKey((k) => k + 1);
    if (!keepMonth) setDataVersion((v) => v + 1);
    load(accountId, keepMonth);
  }, [accountId, load]);

  const months = useMemo(() => overview?.months ?? [], [overview]);
  const latest = months.at(-1)?.month ?? null;
  const overviewMonth = month && month !== "all" ? month : latest;
  const monthRow = months.find((m) => m.month === overviewMonth);

  useEffect(() => {
    if (!overviewMonth) return;
    api.summary(overviewMonth, accountId).then(setSummary).catch((e) => setError(e.message));
  }, [overviewMonth, accountId, refreshKey]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  function chooseAccount(id: number | null) {
    setAccountId(id);
    setCategory(null);
    load(id, true);
    setRefreshKey((k) => k + 1);
  }

  const suggestions = useMemo(() => {
    if (!latest) return [];
    const last = monthLabel(latest).split(" ")[0];
    const prev = months.length > 1 ? monthLabel(months.at(-2)!.month).split(" ")[0] : null;
    return [
      prev ? `Why did ${last} cost more or less than ${prev}?` : `Where did my money go in ${last}?`,
      "How much did I spend on takeaways this month?",
      "How much did I earn?",
      prev ? `Where did my money go in ${prev}?` : "How much did I spend on groceries?",
    ];
  }, [months, latest]);

  const accountName = accountId === null ? "all accounts" : accounts.find((a) => a.id === accountId)?.name ?? "this account";
  const title = VIEWS.find((v) => v.id === view)!.label;
  const hasData = (overview?.transaction_count ?? 0) > 0 || accounts.length > 0;
  const showFilters = hasData && (view === "overview" || view === "transactions" || view === "regular");

  // ----- render -----
  let body: React.ReactNode;
  if (!overview) {
    body = error ? <div className="error-box">{error}</div> : <div className="skeleton" aria-busy="true" />;
  } else if (!hasData) {
    body = <Welcome onImported={() => refresh(false)} />;
  } else if (view === "overview") {
    body = summary && monthRow && summary.month === overviewMonth ? (
      <div className="stack">
        <SummarySentence summary={summary} month={monthRow} partial={isUnfinished(monthRow, months)} />
        <Stats summary={summary} earnings={earnings} recurringMonthly={recurring?.active_monthly_total_pence ?? 0}
               partial={isUnfinished(monthRow, months)} />
        <LearnCard categories={categories} refreshKey={refreshKey} onTaught={(m) => { setToast(m); refresh(); }} />
        <div className="grid-2">
          <Highlights items={summary.highlights} onCategory={(c) => { setCategory(c); go("transactions"); }} />
          {earnings && <MoneyIn earnings={earnings}
                                onSeePayer={(name) => { setCategory(null); setMonth("all"); go("transactions"); setSearch(name); }} />}
        </div>
        <div className="grid-2-wide">
          <CategoryBars summary={summary} onSelect={(c) => { setCategory(c); go("transactions"); }} />
          {recurring && <RecurringList items={recurring.items} monthlyTotal={recurring.active_monthly_total_pence}
                                       limit={6} onSeeAll={() => go("regular")} />}
        </div>
        <MonthsChart months={months} selected={overviewMonth!} onSelect={setMonth} />
        <Transactions month={overviewMonth!} accountId={accountId} accounts={accounts} category={null} onCategory={() => {}}
                      categories={categories} refreshKey={refreshKey} limit={6} onSeeAll={() => go("transactions")}
                      onRecategorised={(m) => { setToast(m); refresh(); }} />
      </div>
    ) : <div className="skeleton" aria-busy="true" />;
  } else if (view === "transactions") {
    body = (
      <Transactions key={search} initialQuery={search}
                    month={month === "all" ? "" : overviewMonth ?? ""} accountId={accountId} accounts={accounts}
                    category={category} onCategory={setCategory} categories={categories} refreshKey={refreshKey}
                    onRecategorised={(m) => { setToast(m); refresh(); }} />
    );
  } else if (view === "regular") {
    body = recurring && <RecurringList items={recurring.items} monthlyTotal={recurring.active_monthly_total_pence} />;
  } else if (view === "accounts") {
    body = <Accounts accounts={accounts} onAdd={() => setUploadOpen(true)}
                     onChanged={(msg) => { if (msg) setToast(msg); refresh(!msg); }}
                     onOpenAccount={(id) => { chooseAccount(id); go("transactions"); }} />;
  } else {
    body = <YourData refreshKey={refreshKey} categorisedRate={overview.categorised_rate} loginEnabled={loginEnabled}
                     onDeleted={() => { setToast("All your data was deleted."); setAccountId(null); refresh(false); }}
                     onRuleDeleted={(m) => { setToast(m); refresh(); }} />;
  }

  return (
    <div className="app">
      <Sidebar view={view} onView={go} user={user} loginEnabled={loginEnabled} accountCount={accounts.length} />
      <main className="main">
        <div className="topbar">
          <h1>{hasData ? title : "Welcome"}</h1>
          <div className="topbar-controls">
            {showFilters && accounts.length > 1 && (
              <>
                <label className="visually-hidden" htmlFor="acct-filter">Account</label>
                <select id="acct-filter" className="select" value={accountId ?? ""}
                        onChange={(e) => chooseAccount(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">All accounts</option>
                  {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </>
            )}
            {showFilters && view !== "regular" && months.length > 0 && (
              <>
                <label className="visually-hidden" htmlFor="month-filter">Month</label>
                <select id="month-filter" className="select" value={view === "transactions" ? month ?? "" : overviewMonth ?? ""}
                        onChange={(e) => setMonth(e.target.value)}>
                  {view === "transactions" && <option value="all">All months</option>}
                  {[...months].reverse().map((m) => (
                    <option key={m.month} value={m.month}>
                      {monthLabel(m.month)}{isUnfinished(m, months) ? " (so far)" : ""}
                    </option>
                  ))}
                </select>
              </>
            )}
            {hasData && (
              <button className="btn" onClick={() => setChatOpen(true)}><IconChat />Ask</button>
            )}
            <button className="btn btn-primary" onClick={() => setUploadOpen(true)}><IconUpload />Add statements</button>
          </div>
        </div>
        {error && overview && <div className="error-box" style={{ marginBottom: 16 }}>{error}</div>}
        {body}
      </main>
      <ChatDrawer key={`${dataVersion}-${accountId}`} open={chatOpen} onClose={() => setChatOpen(false)}
                  suggestions={suggestions} accountId={accountId} scopeLabel={accountName}
                  onTaught={() => refresh()} />
      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} accounts={accounts} onImported={() => refresh(false)} />
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
