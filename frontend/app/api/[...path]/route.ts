/**
 * Every /api/* call from the browser lands here and is forwarded to the FastAPI backend.
 * With sign-in on, this is where identity is attached: the signed-in user's email plus a shared
 * secret the backend checks, so the browser can never claim to be someone else.
 */
import { currentUser, loginEnabled } from "@/auth";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const PASS_REQUEST = ["content-type", "accept"];
const PASS_RESPONSE = ["content-type", "content-disposition"];

async function forward(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (path[0] === "account") {
    // Sign-up and password checks are server-to-server only (see auth.ts), never via this proxy.
    return Response.json({ detail: "Not found." }, { status: 404 });
  }
  const headers = new Headers();
  for (const h of PASS_REQUEST) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }

  if (loginEnabled) {
    const secret = process.env.INTERNAL_API_SECRET;
    if (!secret) {
      return Response.json({ detail: "Login is on but INTERNAL_API_SECRET isn't set. See .env.example." }, { status: 500 });
    }
    const user = await currentUser();
    if (!user) return Response.json({ detail: "Not signed in." }, { status: 401 });
    headers.set("x-internal-secret", secret);
    headers.set("x-user-email", user.email);
    headers.set("x-user-name", encodeURIComponent(user.name));
  }

  const search = new URL(req.url).search;
  const init: RequestInit = { method: req.method, headers, redirect: "manual", cache: "no-store" };
  if (req.method !== "GET" && req.method !== "HEAD") init.body = await req.arrayBuffer();

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/${path.map(encodeURIComponent).join("/")}${search}`, init);
  } catch {
    return Response.json({ detail: "Can't reach the MoneyMap API. Is the backend running on port 8000?" }, { status: 502 });
  }
  const out = new Headers();
  for (const h of PASS_RESPONSE) {
    const v = res.headers.get(h);
    if (v) out.set(h, v);
  }
  return new Response(res.body, { status: res.status, headers: out });
}

export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
