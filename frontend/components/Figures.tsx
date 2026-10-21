import type { Summary } from "@/lib/api";
import { moneyRound, signedRound } from "@/lib/format";

export function Figures({ summary, recurringMonthly, partial }: { summary: Summary; recurringMonthly: number; partial: boolean }) {
  const prev = summary.comparison?.prev;
  const noIncomeYet = partial && summary.income_pence === 0;
  return (
    <dl className="figures">
      <div className="figure">
        <dt>Spent</dt>
        <dd>{moneyRound(summary.spend_pence)}</dd>
        {prev && <span className="delta">{moneyRound(prev.spend_pence)} last month</span>}
      </div>
      <div className="figure">
        <dt>Came in</dt>
        <dd>{moneyRound(summary.income_pence)}</dd>
        {noIncomeYet ? (
          <span className="delta">nothing yet this month</span>
        ) : (
          prev && <span className="delta">{moneyRound(prev.income_pence)} last month</span>
        )}
      </div>
      <div className="figure">
        <dt>Left over</dt>
        <dd>{signedRound(summary.net_pence)}</dd>
        <span className="delta">{partial ? "so far this month" : "income minus spending"}</span>
      </div>
      <div className="figure">
        <dt>Regular payments</dt>
        <dd>{moneyRound(recurringMonthly)}</dd>
        <span className="delta">a month, rent and bills included</span>
      </div>
    </dl>
  );
}
