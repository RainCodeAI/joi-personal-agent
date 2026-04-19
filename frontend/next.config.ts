import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Produces a self-contained server.js for Docker — only what's needed at runtime
  output: "standalone",
  // three.js ships ES modules that Next.js needs to transpile
  transpilePackages: ["three"],
  experimental: {
    optimizePackageImports: [
      "@react-three/fiber",
      "@react-three/drei",
      "@react-three/postprocessing",
    ],
  },
};

export default nextConfig;
