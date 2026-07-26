import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Surfaces double-invoked effects in development, which is exactly where a
  // WebSocket client with sloppy cleanup would leak connections.
  eslint: { ignoreDuringBuilds: false },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
