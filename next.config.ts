import type { NextConfig } from 'next';
const config: NextConfig = {
  poweredByHeader: false,
  compress: false, // Local streaming responses must not wait in a gzip buffer.
  experimental: { proxyTimeout: 3600000 },
  async rewrites() { return [{ source: '/api/:path*', destination: 'http://127.0.0.1:8000/api/:path*' }]; },
  async headers() { const policy="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' ws://127.0.0.1:3000; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'"; return [{source: '/:path*', headers: [{key:'X-Content-Type-Options',value:'nosniff'},{key:'Referrer-Policy',value:'same-origin'},{key:'X-Frame-Options',value:'SAMEORIGIN'},{key:'Content-Security-Policy',value:policy}]}]; }
};
export default config;
