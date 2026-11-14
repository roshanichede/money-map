import { ForgotForm } from "@/components/AccountForms";
import { AuthShell } from "@/components/AuthShell";

export const metadata = { title: "Reset your password · MoneyMap" };

export default function Forgot() {
  return (
    <AuthShell title="Reset your password" sub="Enter the email you signed up with and we'll send you a link.">
      <ForgotForm />
    </AuthShell>
  );
}
