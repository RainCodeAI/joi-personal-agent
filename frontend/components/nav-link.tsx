"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavLinkProps = {
  href: string;
  label: string;
  copy: string;
  collapsed?: boolean;
};

export function NavLink({ href, label, copy, collapsed }: NavLinkProps) {
  const pathname = usePathname();
  const active = pathname === href;

  if (collapsed) {
    return (
      <Link
        className={`nav-link nav-link--icon${active ? " active" : ""}`}
        href={href}
        title={label}
        aria-label={label}
      >
        <span className="nav-link-initial">{label[0]}</span>
      </Link>
    );
  }

  return (
    <Link className={`nav-link${active ? " active" : ""}`} href={href}>
      <span className="nav-link-label">
        <span className="nav-link-dot" aria-hidden="true" />
        {label}
      </span>
      <span className="nav-link-copy">{copy}</span>
    </Link>
  );
}
