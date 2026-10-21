import type { Change, MonthRow, Summary as SummaryData } from "@/lib/api";
import { monthLabel, moneyRound, plural, shortDate, signedRound } from "@/lib/format";

/** Describe one merchant-level change in words, e.g. "3 more Deliveroo payments". */
function driverPhrase(c: Change): string | null {
  const d = c.drivers[0];
  if (!d) return null;
  const more = d.delta_pence > 0;
  if (d.prev_count === 0 && d.this_count === 1) return `a ${moneyRound(d.this_pence)} ${d.merchant} payment`;
  if (d.this_count === 0) return `nothing at ${d.merchant}`;
  const n = Math.abs(d.this_count - d.prev_count);
  if (n > 0 && (d.this_count > d.prev_count) === more) {
    return `${n} ${more ? "more" : "fewer"} ${d.merchant} ${n === 1 ? "payment" : "payments"}`;
  }
  return `${d.merchant} costing ${moneyRound(Math.abs(d.delta_pence))} ${more ? "more" : "less"}`;
}

/** One plain-English sentence about the month, built only from calculated figures. */
export function SummarySentence({ summary, month, partial }: { summary: SummaryData; month: MonthRow; partial: boolean }) {
  const name = monthLabel(month.month, "long").split(" ")[0];
  const c = summary.comparison;
  const spent = <b>{moneyRound(summary.spend_pence)}</b>;

  let comparison: React.ReactNode = null;
  let because: string | null = null;
  if (c) {
    const prevName = monthLabel(c.previous, "long").split(" ")[0];
    const diff = summary.spend_pence - c.prev.spend_pence;
    const d = <b>{moneyRound(Math.abs(diff))}</b>;
    // An unfinished month can only fairly be called "more" (it's already over); "less" might not last.
    const explain = !partial || diff > 0;
    if (partial && diff > 0) comparison = <>, already {d} more than all of {prevName}</>;
    else if (partial) comparison = <>. {prevName}&apos;s total was <b>{moneyRound(c.prev.spend_pence)}</b></>;
    else comparison = <>, {d} {diff >= 0 ? "more" : "less"} than {prevName}</>;
    if (explain) {
      const sameWay = c.changes.filter((ch) => (diff >= 0 ? ch.delta_pence > 0 : ch.delta_pence < 0));
      const phrases = sameWay.slice(0, 2).map(driverPhrase).filter(Boolean) as string[];
      if (phrases.length) because = phrases.join(" and ");
    }
  }

  return (
    <div>
      <p className="summary">
        {partial ? <>In {name} so far you&apos;ve spent {spent}</> : <>In {name} you spent {spent}</>}
        {comparison}
        {because ? <>, mostly {because}.</> : "."}
      </p>
      <p className="summary-note">
        {partial
          ? `Statements run to ${shortDate(month.last_date)}, so ${name} isn't finished yet.`
          : `${plural(summary.transaction_count, "transaction")}, ${shortDate(month.first_date)} to ${shortDate(month.last_date)}.`}{" "}
        {summary.transfers_out_pence > 0
          ? `${moneyRound(summary.transfers_out_pence)} moved between your own accounts isn't counted as spending.`
          : "Transfers between your own accounts aren't counted as spending."}
      </p>
    </div>
  );
}

export function Stats({ summary, recurringMonthly, partial }: { summary: SummaryData; recurringMonthly: number; partial: boolean }) {
  const prev = summary.comparison?.prev;
  const noIncomeYet = partial && summary.income_pence === 0;
  return (
    <dl className="stats">
      <div className="stat">
        <dt>Spent</dt>
        <dd className="num">{moneyRound(summary.spend_pence)}</dd>
        <span className="delta">{prev ? `${moneyRound(prev.spend_pence)} last month` : " "}</span>
      </div>
      <div className="stat">
        <dt>Came in</dt>
        <dd className="num">{moneyRound(summary.income_pence)}</dd>
        <span className="delta">
          {noIncomeYet ? "nothing yet this month" : prev ? `${moneyRound(prev.income_pence)} last month` : " "}
        </span>
      </div>
      <div className="stat">
        <dt>Left over</dt>
        <dd className="num">{signedRound(summary.net_pence)}</dd>
        <span className="delta">{partial ? "so far this month" : "income minus spending"}</span>
      </div>
      <div className="stat">
        <dt>Regular payments</dt>
        <dd className="num">{moneyRound(recurringMonthly)}</dd>
        <span className="delta">a month, bills included</span>
      </div>
    </dl>
  );
}
