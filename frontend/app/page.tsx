// Login can be switched on by environment variables at runtime, so never pre-render.
export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";

import { currentUser, loginEnabled } from "@/auth";
import { Dashboard } from "@/components/Dashboard";

export default async function Home() {
  const user = await currentUser();
  if (loginEnabled && !user) redirect("/signin");
  return <Dashboard user={user} loginEnabled={loginEnabled} />;
}
