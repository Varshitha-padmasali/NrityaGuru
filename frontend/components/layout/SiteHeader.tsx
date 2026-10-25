import Link from "next/link";
import { Suspense } from "react";
import { LogoMark } from "@/components/brand/DancerIllustration";
import { NavLinks } from "./NavLinks";
import { BackendStatus } from "./BackendStatus";

export const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/learn", label: "Learn" },
  { href: "/mudras", label: "Mudras" },
  { href: "/practice", label: "Practice" },
  { href: "/progress", label: "Progress" },
] as const;

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-ivory/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 rounded-md" aria-label="NrityaGuru home">
          <LogoMark className="h-8 w-8" />
          <span className="font-display text-2xl font-semibold tracking-tight text-maroon-dark">NrityaGuru</span>
        </Link>
        {/* NavLinks reads the current path, so it sits inside Suspense (Next.js cache components rule). */}
        <Suspense fallback={<div className="flex-1" />}>
          <NavLinks items={NAV_ITEMS} />
        </Suspense>
        <BackendStatus />
      </div>
    </header>
  );
}
