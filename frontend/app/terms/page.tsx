import { Contact, LegalPage } from "@/components/LegalPage";

export const dynamic = "force-dynamic";
export const metadata = { title: "Terms · MoneyMap" };

export default function Terms() {
  return (
    <LegalPage title="Terms of use" updated="14 November 2026">
      <p>These are the rules for using MoneyMap. They&apos;re short on purpose.</p>

      <h2>It&apos;s a free beta</h2>
      <p>
        MoneyMap is free while it&apos;s in beta and joined by invitation. Things will change, and sometimes break. We may
        add features, remove them, or end the beta; if we ever close MoneyMap we&apos;ll give you at least 30 days to
        export your data first.
      </p>

      <h2>It isn&apos;t financial advice</h2>
      <p>
        MoneyMap sorts and summarises your transactions automatically, and it can get things wrong. Check anything
        important against your bank&apos;s own statements. Nothing in the app, including the chat, is financial,
        tax or legal advice.
      </p>

      <h2>Your part</h2>
      <ul>
        <li>Only upload statements for accounts that are yours, or that you have permission to use.</li>
        <li>Keep your password and your phone tracking links private. Turn a link off in <b>Live tracking</b> if you lose your phone.</li>
        <li>Don&apos;t try to access other people&apos;s data, overload the service, or break its security.</li>
        <li>You must be 18 or over.</li>
      </ul>

      <h2>Your data stays yours</h2>
      <p>
        You own your data. You let us store and process it only to run MoneyMap for you, as described in the privacy
        notice. You can export or delete it whenever you like.
      </p>

      <h2>Ending your account</h2>
      <p>
        You can delete your account at any time in <b>Your data</b>. We may suspend an account that breaks these terms or
        puts other people&apos;s data at risk.
      </p>

      <h2>Liability</h2>
      <p>
        MoneyMap is provided “as is”. As far as the law allows, we aren&apos;t liable for losses caused by relying on it.
        Nothing here limits rights you have under UK consumer law, or liability that can&apos;t legally be limited.
      </p>

      <h2>Law and contact</h2>
      <p>These terms are governed by the law of England and Wales. Questions: <Contact />.</p>
    </LegalPage>
  );
}
