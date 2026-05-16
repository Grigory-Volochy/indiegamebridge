import type { NextConfig } from "next";

const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Next strips trailing slashes from rewrite destinations; Django's APPEND_SLASH
  // would 301 them back, looping. We force the slash on the destination and
  // suppress Next's own 308 strip on the inbound URL so the browser doesn't flicker.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      // Each Django URL prefix that the browser needs to reach directly (for
      // same-origin cookies in dev) gets its own rewrite. Add a line per new
      // prefix Django mounts.
      { source: "/accounts/:path*", destination: `${apiBase}/accounts/:path*/` },
      { source: "/auth/:path*", destination: `${apiBase}/auth/:path*/` },
    ];
  },
};

export default nextConfig;
