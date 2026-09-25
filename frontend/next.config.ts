import type { NextConfig } from "next";

const API_PROXY_TARGET =
  process.env.API_PROXY_TARGET?.replace(/\/$/, "") || "http://127.0.0.1:8000";

if (process.env.VERCEL === "1" && !process.env.API_PROXY_TARGET?.trim()) {
  throw new Error(
    "Set API_PROXY_TARGET on Vercel to your Render API URL " +
      "(e.g. https://tradebay-1.onrender.com), then Redeploy.",
  );
}

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_PROXY_TARGET}/api/:path*`,
      },
      {
        source: "/uploads/:path*",
        destination: `${API_PROXY_TARGET}/uploads/:path*`,
      },
    ];
  },
};

export default nextConfig;
