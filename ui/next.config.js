/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  distDir: 'dist',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;
