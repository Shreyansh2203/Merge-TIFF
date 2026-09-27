import assert from 'node:assert/strict';
import { afterEach, describe, it } from 'node:test';

import nextConfig from '../../next.config.mjs';

const FUNCTION_ORIGIN = 'http://127.0.0.1:5328';
const ORIGINAL_NODE_ENV = process.env.NODE_ENV;

function setNodeEnv(value) {
  if (value === undefined) {
    delete process.env.NODE_ENV;
  } else {
    process.env.NODE_ENV = value;
  }
}

describe('next.config.mjs rewrites', () => {
  afterEach(() => setNodeEnv(ORIGINAL_NODE_ENV));

  // The README used to tell the reader to hand-write this rewrite into an
  // uncommitted next.config.mjs as step 3 of 3 in Quick Start, so a fresh clone
  // had a dev frontend that 404ed on the only request it makes.
  it('proxies /api/* to the local Flask function in development', async () => {
    setNodeEnv('development');

    assert.deepEqual(await nextConfig.rewrites(), [
      { source: '/api/:path*', destination: `${FUNCTION_ORIGIN}/api/:path*` },
    ]);
  });

  // vercel.json is what routes the deployed copy. A rewrite that survived into
  // a production build would be a second routing table shadowing the one the
  // deployment tests assert against.
  it('registers nothing in production, so vercel.json stays the only router', async () => {
    setNodeEnv('production');

    assert.deepEqual(await nextConfig.rewrites(), []);
  });

  it('registers the rewrite for every value except production', async () => {
    for (const value of [undefined, 'development', 'test']) {
      setNodeEnv(value);

      assert.deepEqual(
        await nextConfig.rewrites(),
        [{ source: '/api/:path*', destination: `${FUNCTION_ORIGIN}/api/:path*` }],
        `NODE_ENV=${value}`
      );
    }
  });
});
