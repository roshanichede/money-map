import { Contact, LegalPage } from "@/components/LegalPage";

export const dynamic = "force-dynamic";
export const metadata = { title: "Privacy · MoneyMap" };

export default function Privacy() {
  return (
    <LegalPage title="Privacy notice" updated="17 November 2026">
      <p>
        MoneyMap reads the bank statements you upload and shows you where your money went. This page explains, in plain
        English, what that means for your data. The short version: we keep only what the app needs to work, we never sell
        or share it for advertising, and you can delete all of it yourself, at any time, in two clicks.
      </p>

      <h2>Who runs MoneyMap</h2>
      <p>MoneyMap is run by Roshani Chede in the UK, who is the data controller for the information below. To get in touch, <Contact />.</p>

      <h2>What we keep</h2>
      <ul>
        <li><b>Your account:</b> email, name, and your password as a one-way hash (we can&apos;t read it). If you use Google, we get your name, email and profile picture from Google.</li>
        <li><b>Transactions from your statements:</b> date, description, amount, and the category MoneyMap gave it.</li>
        <li><b>Accounts:</b> a name you choose, the type, the currency and the last four digits of the account number. The full number is never stored.</li>
        <li><b>What MoneyMap learns from you:</b> rules like “garba is entertainment”, and categories you change.</li>
        <li><b>Live tracking, if you set it up:</b> the merchant and amount your phone sends for each payment.</li>
        <li><b>Feedback you send</b>, and your email with it only if you tick “you can reply to me”.</li>
        <li><b>Basic usage:</b> when you last used the app, so we can count active users. No tracking across other websites.</li>
        <li><b>Anonymous usage stats:</b> which screens and features are used (for example “opened Regular payments”, “uploaded a PDF”), sent to PostHog in the EU. Never amounts, payee names or your email: you&apos;re identified only by a scrambled code. No cookies, no screen recordings. Switch it off in <b>Your data</b>.</li>
      </ul>

      <h2>What we don&apos;t keep</h2>
      <ul>
        <li><b>Your statement files.</b> A PDF, CSV or Excel file is read in memory, the transactions are taken out, and the file is thrown away.</li>
        <li><b>Your bank login.</b> MoneyMap never asks for it and never connects to your bank.</li>
        <li>No advertising or analytics cookies. The only cookie is the one that keeps you signed in.</li>
      </ul>

      <h2>Why we use it</h2>
      <p>
        Only to provide the service you signed up for (UK GDPR: performance of a contract), and to keep it secure and
        working. We don&apos;t sell your data, use it for advertising, or use it to train AI models.
      </p>

      <h2>Who else handles it</h2>
      <p>MoneyMap runs on a few services that store or process data on our behalf, under their own data protection terms:</p>
      <ul>
        <li><b>Vercel</b> hosts the website.</li>
        <li><b>Render</b> runs the server that reads your statements (Frankfurt, EU).</li>
        <li><b>Neon</b> hosts the database (Frankfurt, EU).</li>
        <li><b>Anthropic</b> powers the “Ask” chat. It is sent calculated facts (totals, merchant names, dates) to answer your question, never your statement files or account numbers.</li>
        <li><b>PostHog</b> (EU) counts anonymous feature usage, as described above.</li>
        <li><b>Google</b>, only if you choose “Continue with Google”, and our email provider, to send sign-up and password emails.</li>
      </ul>
      <p>Some of these companies are based in the US; transfers are covered by the UK&apos;s adequacy arrangements or standard contractual clauses.</p>

      <h2>How long we keep it</h2>
      <p>
        Until you delete it. <b>Your data → Delete all my data</b> removes your transactions and accounts but keeps your
        login. <b>Delete my account</b> removes everything, including your login, straight away. Copies can remain in the
        database provider&apos;s short-term backups for up to 7 days before they are gone for good.
      </p>

      <h2>Your rights</h2>
      <p>
        You can see and download your data (<b>Your data → Export all as CSV</b>), correct it, or delete it at any time. You
        can also ask us for a copy, or object to how it is used: <Contact />. If you&apos;re unhappy with how we handle
        your data, you can complain to the Information Commissioner&apos;s Office at ico.org.uk.
      </p>

      <h2>Security</h2>
      <p>
        Everything travels over HTTPS. Each person can only ever see their own data. Passwords are hashed, sign-in attempts
        are rate-limited, sessions end after 14 days, and phone tracking links are stored only as a fingerprint so they
        can&apos;t be rebuilt from the database.
      </p>

      <h2>Age</h2>
      <p>MoneyMap is for people aged 18 and over.</p>

      <h2>Changes</h2>
      <p>If this notice changes in a way that matters, we&apos;ll tell you in the app before it takes effect.</p>
    </LegalPage>
  );
}
