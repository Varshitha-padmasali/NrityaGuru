import type { Metadata } from "next";
import type { ReactNode } from "react";
// Fonts are self-hosted from npm packages, so the app also works offline (e.g. during a demo without internet).
import "@fontsource-variable/cormorant-garamond";
import "@fontsource-variable/cormorant-garamond/wght-italic.css";
import "@fontsource-variable/source-sans-3";
import "@fontsource/tiro-devanagari-sanskrit/devanagari-400.css";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { MockModeBanner, SiteFooter } from "@/components/layout/SiteFooter";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "NrityaGuru — Bharatanatyam learning", template: "%s · NrityaGuru" },
  description: "Learn Bharatanatyam mudras, practise in front of your camera, and get reference-based feedback.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <a href="#main" className="sr-only z-50 rounded bg-maroon px-4 py-2 text-ivory focus:not-sr-only focus:fixed focus:left-4 focus:top-4">
          Skip to content
        </a>
        <MockModeBanner />
        <SiteHeader />
        <main id="main" className="flex-1">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
