// Sign-in can be switched on by environment variables at runtime, so never pre-render.
export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";

import { currentUser, googleEnabled, loginEnabled } from "@/auth";
import { AuthForms } from "@/components/AuthForms";
import { Mark } from "@/components/icons";

export const metadata = { title: "Sign in · MoneyMap" };

export default async function SignIn({ searchParams }: { searchParams: Promise<{ mode?: string }> }) {
  if (!loginEnabled || (await currentUser())) redirect("/");
  const { mode } = await searchParams;
  return (
    <main className="signin">
      <div className="signin-card">
        <div className="brand"><Mark />MoneyMap</div>
        <h1>See where your money went</h1>
        <p className="quiet">Upload your bank statements. MoneyMap sorts your spending and finds your bills.</p>
        <AuthForms googleEnabled={googleEnabled} startWith={mode === "signup" ? "signup" : "signin"} />
        <p className="fine">Your statements stay private to your account. Passwords are stored only as a secure hash.</p>
      </div>
    </main>
  );
}
