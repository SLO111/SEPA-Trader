import type { NextConfig } from "next";

// Static export: the frontend is served directly by the backend (one service, one URL).
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
