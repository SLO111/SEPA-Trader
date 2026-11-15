import type { NextConfig } from "next";

// Export static: frontend-ul e servit direct de backend (un singur serviciu, un singur URL).
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
