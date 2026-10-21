/** Money is shown in the currency of the accounts on screen (set by the dashboard): £ or ₹, never mixed. */
export const SYMBOLS: Record<string, string> = { GBP: "£", INR: "₹", EUR: "€", USD: "$" };
let current = "GBP";
let exact = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
let whole = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });

export function setCurrency(code: string) {
  if (code === current || !SYMBOLS[code]) return;
  current = code;
  const locale = code === "INR" ? "en-IN" : "en-GB"; // en-IN groups as 1,23,456
  exact = new Intl.NumberFormat(locale, { style: "currency", currency: code });
  whole = new Intl.NumberFormat(locale, { style: "currency", currency: code, maximumFractionDigits: 0 });
}
export const currencySymbol = () => SYMBOLS[current];

export const money = (pence: number) => exact.format(pence / 100);
export const moneyRound = (pence: number) => whole.format(Math.round(pence / 100));
export const signedMoney = (pence: number) => (pence > 0 ? "+" : pence < 0 ? "−" : "") + money(Math.abs(pence));
export const signedRound = (pence: number) =>
  (pence > 0 ? "+" : pence < 0 ? "−" : "") + moneyRound(Math.abs(pence));

/** Axis labels: £1.2K, ₹1.5L (lakh), ₹2Cr (crore). */
export const compactPounds = (pence: number) => {
  const units = pence / 100;
  const sym = SYMBOLS[current];
  const fmt = (v: number, suffix: string) => `${sym}${Number.isInteger(v) ? v : v.toFixed(1)}${suffix}`;
  if (current === "INR") {
    if (Math.abs(units) >= 1e7) return fmt(units / 1e7, "Cr");
    if (Math.abs(units) >= 1e5) return fmt(units / 1e5, "L");
  }
  return Math.abs(units) >= 1000 ? fmt(units / 1000, "K") : `${sym}${Math.round(units)}`;
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
