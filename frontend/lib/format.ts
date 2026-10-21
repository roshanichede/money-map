const gbp = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
const gbpRound = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });

export const money = (pence: number) => gbp.format(pence / 100);
export const moneyRound = (pence: number) => gbpRound.format(Math.round(pence / 100));
export const signedMoney = (pence: number) => (pence > 0 ? "+" : pence < 0 ? "−" : "") + money(Math.abs(pence));
export const signedRound = (pence: number) =>
  (pence > 0 ? "+" : pence < 0 ? "−" : "") + moneyRound(Math.abs(pence));

export const compactPounds = (pence: number) => {
  const pounds = pence / 100;
  return Math.abs(pounds) >= 1000 ? `£${(pounds / 1000).toFixed(pounds % 1000 === 0 ? 0 : 1)}K` : `£${Math.round(pounds)}`;
};

export function monthLabel(month: string, style: "long" | "short" = "long") {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-GB", { month: style, year: style === "long" ? "numeric" : undefined });
}

export function shortDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** True when the latest month's data stops before the month ends (an export taken mid-month).
 *  Earlier months are never "unfinished": a quiet account simply had no payments late in the month. */
export function isUnfinished(row: { month: string; last_date: string }, months: { month: string }[]) {
  return row.month === months.at(-1)?.month && isPartialMonth(row.month, row.last_date);
}

export function isPartialMonth(month: string, lastDate: string) {
  const [y, m] = month.split("-").map(Number);
  const daysInMonth = new Date(y, m, 0).getDate();
  return Number(lastDate.slice(8, 10)) < daysInMonth - 1;
}

export function plural(n: number, one: string, many = one + "s") {
  return `${n} ${n === 1 ? one : many}`;
}

/** "Other" reads like a real category; it really means we couldn't tell. */
export const categoryLabel = (c: string) => (c === "Other" ? "Not sorted yet" : c);

/** A month-on-month change in words: "£45 more", "£24 less", "new", "same". */
export function changeWords(delta: number, prev: number) {
  if (Math.round(delta / 100) === 0) return "same";
  if (prev === 0) return "new";
  return `${moneyRound(Math.abs(delta))} ${delta > 0 ? "more" : "less"}`;
}

export const KIND_TAG: Record<string, { label: string; title: string } | undefined> = {
  salary: { label: "salary", title: "Counted as earnings: regular pay from an employer" },
  income: { label: "income", title: "Counted as earnings: interest or a one-off payment from a company" },
  paid_back: { label: "paid back", title: "A person paying their share of something (the note says what), so it's taken off that spending, not counted as earnings" },
  from_person: { label: "from a person", title: "Money from a person with no note saying what for: not counted as earnings or spending" },
  refund: { label: "refund", title: "A refund from a shop, taken off your spending" },
};
