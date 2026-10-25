"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { IconClose, IconMenu } from "@/components/ui/Icons";

interface NavItem {
  href: string;
  label: string;
}

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export function NavLinks({ items }: { items: readonly NavItem[] }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <nav aria-label="Main" className="flex flex-1 items-center justify-end md:justify-start">
      <ul className="hidden items-center gap-1 md:flex">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={isActive(pathname, item.href) ? "page" : undefined}
              className={cn(
                "rounded-full px-3.5 py-2 text-[15px] font-medium transition-colors",
                isActive(pathname, item.href) ? "bg-maroon-soft text-maroon" : "text-ink-muted hover:text-maroon",
              )}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>

      <button
        type="button"
        className="rounded-full p-2 text-maroon md:hidden"
        aria-expanded={open}
        aria-controls="mobile-nav"
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <IconClose /> : <IconMenu />}
      </button>

      {open ? (
        <ul id="mobile-nav" className="absolute inset-x-0 top-16 border-b border-line bg-ivory px-4 py-3 shadow-lg md:hidden">
          {items.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={isActive(pathname, item.href) ? "page" : undefined}
                className={cn("block rounded-lg px-3 py-3 text-base font-medium", isActive(pathname, item.href) ? "bg-maroon-soft text-maroon" : "text-ink")}
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </nav>
  );
}
