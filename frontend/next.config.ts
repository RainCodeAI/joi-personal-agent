import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
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
