import Link from "next/link";

import { ResetForm } from "@/components/AccountForms";
import { AuthShell } from "@/components/AuthShell";

export const dynamic = "force-dynamic";
export const metadata = { title: "Choose a new password · MoneyMap" };

export default async function Reset({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  if (!token) {
    return (
      <AuthShell title="That link isn't complete" sub="Open the link from the email again, or ask for a new one.">
        <Link href="/forgot" className="btn btn-primary auth-submit">Get a new link</Link>
      </AuthShell>
    );
  }
  return (
    <AuthShell title="Choose a new password" sub="The link works once and for one hour.">
      <ResetForm token={token} />
    </AuthShell>
  );
}
