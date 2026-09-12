/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The floating development badge sits on top of the bottom navigation,
  // which is exactly where a thumb goes on a phone.
  devIndicators: false,
  // The API is a separate service. In development it is proxied through the
  // same origin so the session cookie is first-party and CSRF stays simple;
  // in production the reverse proxy does the same thing (see infrastructure/).
  async rewrites() {
    const api = process.env.AVERIX_API_URL || 'http://localhost:8080';
    return [{ source: '/api/v1/:path*', destination: `${api}/api/v1/:path*` }];
  },
};
export default nextConfig;
