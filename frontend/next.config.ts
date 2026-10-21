import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // The browser only ever talks to Next.js; /api/* is proxied to the FastAPI backend.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
