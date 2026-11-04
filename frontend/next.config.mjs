const radarApiUrl = process.env.RADAR_API_URL || 'http://localhost:8000'

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${radarApiUrl}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
