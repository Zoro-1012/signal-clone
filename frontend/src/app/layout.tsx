import type { Metadata, Viewport } from "next";

import { Providers } from "./providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Signal",
  description: "A secure messaging platform.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#121212" },
  ],
  width: "device-width",
  initialScale: 1,
  // The composer is fixed to the bottom; without this, focusing it on iOS zooms
  // the viewport and the layout jumps.
  maximumScale: 1,
};

/**
 * Applied before first paint, so a dark-theme user never sees a white flash
 * while React hydrates. This has to be inline and blocking to work at all.
 */
const NO_FLASH = `
(function () {
  try {
    var stored = localStorage.getItem('signal-clone:theme') || 'dark';
    var dark = stored === 'dark' ||
      (stored === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', dark);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH }} />
      </head>
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
