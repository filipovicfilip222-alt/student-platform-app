/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "9000",
        pathname: "/professor-avatars/**",
      },
      {
        protocol: "https",
        hostname: "*.fon.bg.ac.rs",
      },
    ],
  },
  // Strict mode to catch potential issues early
  reactStrictMode: true,
}

export default nextConfig
