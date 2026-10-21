import type { Change, MonthRow, Summary } from "@/lib/api";
import { isPartialMonth, monthLabel, moneyRound, plural, shortDate } from "@/lib/format";

/** Describe one merchant-level change in words, e.g. "3 more Deliveroo orders". */
function driverPhrase(c: Change): string | null {
  const d = c.drivers[0];
  if (!d) return null;
  const more = d.delta_pence > 0;
  if (d.prev_count === 0 && d.this_count === 1) return `a ${moneyRound(d.this_pence)} ${d.merchant} payment`;
  if (d.this_count === 0) return `no ${d.merchant} this month`;
  const n = Math.abs(d.this_count - d.prev_count);
  if (n > 0 && (d.this_count > d.prev_count) === more) {
    return `${n} ${more ? "more" : "fewer"} ${d.merchant} ${n === 1 ? "payment" : "payments"}`;
  }
  return `${d.merchant} costing ${moneyRound(Math.abs(d.delta_pence))} ${more ? "more" : "less"}`;
}

export function Headline({ summary, month }: { summary: Summary; month: MonthRow }) {
  const partial = isPartialMonth(month.month, month.last_date);
  const name = monthLabel(month.month, "long").split(" ")[0];
  const c = summary.comparison;
  const spent = moneyRound(summary.spend_pence);

  const opening = partial ? (
    <>
      In {name} so far, you&apos;ve spent <span className="fig">{spent}</span>
    </>
  ) : (
    <>
      In {name} you spent <span className="fig">{spent}</span>
    </>
  );

  let comparison: React.ReactNode = null;
  let because: string | null = null;
  if (c) {
    const prevName = monthLabel(c.previous, "long").split(" ")[0];
    const diff = summary.spend_pence - c.prev.spend_pence;
    const diffText = <span className="fig">{moneyRound(Math.abs(diff))}</span>;
    if (partial && diff > 0) comparison = <>, already {diffText} more than all of {prevName}</>;
    else if (partial) comparison = <>, {diffText} less than {prevName}&apos;s total so far</>;
    else comparison = <>, {diffText} {diff >= 0 ? "more" : "less"} than {prevName}</>;

    const sameWay = c.changes.filter((ch) => (diff >= 0 ? ch.delta_pence > 0 : ch.delta_pence < 0));
    const phrases = sameWay.slice(0, 2).map(driverPhrase).filter(Boolean) as string[];
    if (phrases.length) because = phrases.join(" and ");
  }

  return (
    <header>
      <h1 className="headline">
        {opening}
        {comparison}
        {because ? <>, mostly {because}.</> : "."}
      </h1>
      <p className="headline-sub">
        {partial
          ? `Your statements run to ${shortDate(month.last_date)}, so this month isn't finished yet.`
          : `Based on ${plural(summary.transaction_count, "transaction")} from ${shortDate(month.first_date)} to ${shortDate(month.last_date)}.`}{" "}
        Transfers between your own accounts aren&apos;t counted as spending.
      </p>
    </header>
  );
}
