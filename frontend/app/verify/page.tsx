import Link from "next/link";

import { accountCall } from "@/auth";
import { AuthShell } from "@/components/AuthShell";

export const dynamic = "force-dynamic";
export const metadata = { title: "Confirm your email · MoneyMap" };

export default async function Verify({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  const r = token ? await accountCall("verify", { token }) : null;
  if (r?.ok) {
    return (
      <AuthShell title="Email confirmed" sub="Thanks. Your account is ready.">
        <Link href="/signin" className="btn btn-primary auth-submit">Sign in</Link>
      </AuthShell>
    );
  }
  return (
    <AuthShell title="That link didn't work" sub={r?.data.detail ?? "The link is incomplete. Open it from the email again."}>
      <p className="auth-links">Try signing in: if your email still needs confirming, you can ask for a new link there.</p>
      <Link href="/signin" className="btn btn-primary auth-submit">Go to sign in</Link>
    </AuthShell>
  );
}
