import createNextIntlPlugin from 'next-intl/plugin';
import type { NextConfig } from 'next';

const apiOrigin = process.env.API_ORIGIN;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    if (!apiOrigin) {
      return [];
    }

    return [
      {
        source: '/api/:path*',
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
};

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');

export default withNextIntl(nextConfig);
