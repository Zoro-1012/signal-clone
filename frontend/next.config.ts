import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Emits a self-contained server bundle, so the Docker runtime stage needs
  // neither node_modules nor the source tree.
  output: "standalone",

  // This app lives in a monorepo subdirectory. Left to infer, Next walks up
  // looking for a lockfile, finds the repository root, and either warns or
  // fails the build depending on the bundler. Pinning the root to this package
  // makes the build behave identically whether it runs from the repo root, from
  // frontend/, or inside a Docker context.
  turbopack: { root: path.resolve(process.cwd()) },
  outputFileTracingRoot: path.resolve(process.cwd()),

  eslint: { ignoreDuringBuilds: false },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
