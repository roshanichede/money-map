// Sign-in can be switched on by environment variables at runtime, so never pre-render.
export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";

import { currentUser, googleEnabled, loginEnabled } from "@/auth";
import { AuthForms } from "@/components/AuthForms";
import { CategoryIcon } from "@/components/CategoryIcon";
import { Mark } from "@/components/icons";

export const metadata = { title: "Sign in · MoneyMap" };

/** What the product does, shown rather than told: raw statement lines on the left, sorted payments on the right. */
const EXAMPLES = [
  { raw: "FPO A KHAN RENT 01OCT26 09:12", name: "A Khan", category: "Rent & housing", amount: "−£390.00" },
  { raw: "BGC NORTHGATE STORES LTD", name: "Northgate Stores", category: "Salary", amount: "+£768.40", income: true },
  { raw: "DEB DELIVEROO PLUS LONDON GB CD 4821", name: "Deliveroo", category: "Takeaways", amount: "−£20.88" },
  { raw: "FPI J SMITH CAB SPLIT ••5749", name: "J Smith paid you back", category: "Transport", amount: "+£12.00" },
];

export default async function SignIn({ searchParams }: { searchParams: Promise<{ mode?: string }> }) {
  if (!loginEnabled || (await currentUser())) redirect("/");
  const { mode } = await searchParams;
  const demo = process.env.DEMO_SITE === "1";
  return (
    <main className="auth">
      <section className="auth-story" aria-label="What MoneyMap does">
        <div className="auth-brand"><Mark />MoneyMap</div>
        <div className="auth-story-body">
          <h1>Your bank statement, finally readable.</h1>
          <p>Upload the CSV or PDF you already have. MoneyMap sorts every payment, spots your pay and finds your bills.</p>
          <ol className="sorter" aria-label="Example: statement lines sorted into categories">
            {EXAMPLES.map((e) => (
              <li key={e.raw}>
                <span className="sorter-raw">{e.raw}</span>
                <span className="sorter-arrow" aria-hidden="true">
                  <svg width="18" height="12" viewBox="0 0 18 12"><path d="M0 6h15m-4-4 4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
                </span>
                <span className="sorter-out">
                  <CategoryIcon category={e.category} size={16} />
                  <span className="sorter-text"><b>{e.name}</b><span>{e.category}</span></span>
                  <span className={`sorter-amt num${e.income ? " in" : ""}`}>{e.amount}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
        <p className="auth-story-foot">No bank login. Your statement files aren&apos;t kept.</p>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-inner">
          <div className="auth-brand auth-brand-small"><Mark />MoneyMap</div>
          <AuthForms googleEnabled={googleEnabled} startWith={mode === "signup" ? "signup" : "signin"} demo={demo} />
        </div>
      </section>
    </main>
  );
}
