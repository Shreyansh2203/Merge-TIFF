/** @type {import('next').NextConfig} */
const LOCAL_FUNCTION_ORIGIN = 'http://127.0.0.1:5328';

const nextConfig = {
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
