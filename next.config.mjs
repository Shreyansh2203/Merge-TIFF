/** @type {import('next').NextConfig} */
const LOCAL_FUNCTION_ORIGIN = 'http://127.0.0.1:5328';

// Baseline hardening for the page this app serves. The CSP has to allow
// inline scripts and styles because Next injects both at runtime; anything
// stricter needs nonce-based CSP via middleware, which a single-page app does
// not justify. object/base-uri/frame-ancestors are the parts that carry the
// weight here, alongside nosniff and the referrer policy.
const SECURITY_HEADERS = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'no-referrer' },
  { key: 'X-Frame-Options', value: 'DENY' },
  {
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      "connect-src 'self'",
      "font-src 'self'",
      "object-src 'none'",
      "base-uri 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
    ].join('; '),
  },
];

const nextConfig = {
  async headers() {
    return [{ source: '/:path*', headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    // In development the UI runs on :3000 and the Flask function on :5328, and
    // nothing under `api/` is served by `next dev`, so the browser's
    // fetch('/api/merge') would 404. On Vercel it is `vercel.json` that routes
    // the request, so this rewrite stays out of any production build rather
    // than becoming a second thing that has to be kept correct.
    if (process.env.NODE_ENV === 'production') {
      return [];
    }
    return [
      {
        source: '/api/:path*',
        destination: `${LOCAL_FUNCTION_ORIGIN}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
