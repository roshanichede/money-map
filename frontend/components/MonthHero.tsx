"use client";

import type { Earnings, MonthRow, Recurring, Summary } from "@/lib/api";
import { monthLabel, moneyRound, shortDate } from "@/lib/format";

type Props = {
  summary: Summary;
  month: MonthRow;
  partial: boolean;
  earnings: Earnings | null;
  recurring: { items: Recurring[]; active_monthly_total_pence: number } | null;
  onSeeBills: () => void;
};

/** The month at a glance: what came in against what went out, on one shared scale. */
export function MonthHero({ summary, month, partial, earnings, recurring, onSeeBills }: Props) {
  const earned = summary.income_pence;
  const spent = summary.spend_pence;
  const scale = Math.max(earned, spent, 1);
  const net = earned - spent;
  const prev = summary.comparison?.prev;
  const name = monthLabel(month.month).split(" ")[0];
  const payday = earnings?.usual_salary_day;
  const waitingForPay = partial && summary.salary_pence === 0 && Boolean(payday);
  const [y, m] = month.month.split("-").map(Number);
  const daysInMonth = new Date(y, m, 0).getDate();
  const day = Number(month.last_date.slice(8, 10));
  const ord = (n: number) => `${n}${[11, 12, 13].includes(n % 100) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;

  const year = earnings?.this_year;
  const yearMonths = (earnings?.months ?? []).filter((m) => earnings?.year && m.month.startsWith(String(earnings.year)));
  const peak = Math.max(...yearMonths.map((m) => m.salary_pence + m.other_income_pence), 1);

  const next = (recurring?.items ?? []).filter((r) => r.active)
    .sort((a, b) => a.next_expected.localeCompare(b.next_expected)).slice(0, 3);

  return (
    <section className="hero" aria-labelledby="hero-h">
      <div className="hero-main">
        <h2 id="hero-h">
          {name} {partial ? <span className="hero-sub">so far, to {shortDate(month.last_date)}</span> : null}
        </h2>
        <div className="flow">
          <div className="flow-row">
            <span className="flow-label">In</span>
            <span className="flow-track"><span className="flow-bar in" style={{ width: `${(earned / scale) * 100}%` }} /></span>
            <span className="flow-val num">{moneyRound(earned)}</span>
          </div>
          <div className="flow-row">
            <span className="flow-label">Out</span>
            <span className="flow-track"><span className="flow-bar out" style={{ width: `${(spent / scale) * 100}%` }} /></span>
            <span className="flow-val num">{moneyRound(spent)}</span>
          </div>
        </div>
        {waitingForPay ? (
          <p className="hero-net wait">
            <span className="hero-net-dot" aria-hidden="true">£</span>
            Your pay usually lands around the {ord(payday!)}
          </p>
        ) : (
          <p className={`hero-net ${net >= 0 ? "good" : "bad"}`}>
            <span className="hero-net-dot" aria-hidden="true">{net >= 0 ? "+" : "−"}</span>
            {net >= 0 ? <>{moneyRound(net)} left over</> : <>{moneyRound(-net)} more went out than came in</>}
          </p>
        )}
        {prev && <p className="hero-prev muted small">Last month: {moneyRound(prev.income_pence)} in, {moneyRound(prev.spend_pence)} out</p>}
        {partial && (
          <div className="month-rail" role="img" aria-label={`Day ${day} of ${daysInMonth}`}>
            <span className="month-rail-fill" style={{ width: `${(day / daysInMonth) * 100}%` }} />
            {payday && <span className="month-rail-pay" style={{ left: `${(payday / daysInMonth) * 100}%` }} title={`Payday around the ${ord(payday)}`} />}
            <span className="month-rail-text small muted">Day {day} of {daysInMonth}</span>
          </div>
        )}
      </div>

      <div className="hero-side">
        <div className="mini">
          <span className="mini-label">Earned in {earnings?.year ?? "total"}</span>
          <span className="mini-val num">{year ? moneyRound(year.income_pence) : "–"}</span>
          {yearMonths.length > 1 && (
            <div className="spark" role="img" aria-label={`Earnings by month in ${earnings?.year}`}>
              {yearMonths.map((m) => {
                const v = m.salary_pence + m.other_income_pence;
                return (
                  <span key={m.month} className="spark-col" title={`${monthLabel(m.month)}: ${moneyRound(v)}`}>
                    <span className="spark-bar" style={{ height: `${Math.max(4, (v / peak) * 100)}%` }} />
                    <span className="spark-x">{monthLabel(m.month, "short")[0]}</span>
                  </span>
                );
              })}
            </div>
          )}
        </div>
        <button className="mini mini-link" onClick={onSeeBills}>
          <span className="mini-label">Bills & subscriptions</span>
          <span className="mini-val num">{moneyRound(recurring?.active_monthly_total_pence ?? 0)}<small> a month</small></span>
          <span className="due-row">
            {next.map((r) => {
              const d = new Date(r.next_expected + "T00:00:00");
              return (
                <span key={r.merchant_key} className="due" title={`${r.merchant}, ${moneyRound(r.typical_amount_pence)}`}>
                  <span className="due-date">
                    <b>{d.getDate()}</b>{d.toLocaleDateString("en-GB", { month: "short" })}
                  </span>
                  <span className="due-name">{r.merchant}</span>
                </span>
              );
            })}
          </span>
        </button>
      </div>
    </section>
  );
}
