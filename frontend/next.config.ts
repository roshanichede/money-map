import type { NextConfig } from "next";

// /api/* is forwarded to the FastAPI backend by app/api/[...path]/route.ts (which also attaches the signed-in user).
const nextConfig: NextConfig = {};

export default nextConfig;
