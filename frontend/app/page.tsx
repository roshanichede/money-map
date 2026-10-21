// Login can be switched on by environment variables at runtime, so never pre-render.
export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";

import { currentUser, loginEnabled } from "@/auth";
import { Dashboard } from "@/components/Dashboard";

export default async function Home() {
  const user = await currentUser();
  if (loginEnabled && !user) redirect("/signin");
  // DEMO_SITE=1 on the public portfolio deployment: steer people to the sample data, not their own statements.
  return <Dashboard user={user} loginEnabled={loginEnabled} demo={process.env.DEMO_SITE === "1"} />;
}
