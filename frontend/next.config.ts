import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Emits a self-contained server bundle, so the Docker runtime stage needs
  // neither node_modules nor the source tree.
  output: "standalone",
  // Surfaces double-invoked effects in development, which is exactly where a
  // WebSocket client with sloppy cleanup would leak connections.
  eslint: { ignoreDuringBuilds: false },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
