import type { Metadata, Viewport } from 'next';
import './globals.css';
import { SessionProvider } from '@/lib/session';
import { ThemeProvider, themeBootstrap } from '@/lib/theme';

export const metadata: Metadata = {
  // Resolves the relative asset URLs below against the deployment's own
  // origin, so a staging build does not point social previews at production.
  metadataBase: new URL(process.env.AVERIX_APP_URL ?? 'https://averix.dev'),
  title: {
    default: 'AVERIX — hire developers who can show the work',
    template: '%s · AVERIX',
  },
  description:
    'AVERIX connects clients with software developers. Verified project history, targeted matching, and a workspace where the work actually happens.',
  applicationName: 'AVERIX',
  formatDetection: { telephone: false, email: false, address: false },
  // The assets live in public/ rather than as app/icon.* files so that the
  // same files are served to the manifest, to iOS, and to a browser that asks
  // for /favicon.ico directly without Next generating three copies.
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico', sizes: '48x48' },
      { url: '/icon-192.png', type: 'image/png', sizes: '192x192' },
      { url: '/icon-512.png', type: 'image/png', sizes: '512x512' },
    ],
    apple: [{ url: '/apple-touch-icon.png', sizes: '180x180' }],
  },
  manifest: '/site.webmanifest',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Zoom is left enabled: locking it is an accessibility failure, and the
  // layout is designed to be legible without it.
  maximumScale: 5,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#F7F7F9' },
    { media: '(prefers-color-scheme: dark)', color: '#08080B' },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Applied before first paint so a dark-mode visitor never gets a white flash. */}
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body>
        <a href="#main" className="av-skip">
          Skip to content
        </a>
        <ThemeProvider>
          <SessionProvider>{children}</SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
