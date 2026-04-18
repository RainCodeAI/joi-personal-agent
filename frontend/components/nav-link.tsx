"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavLinkProps = {
  href: string;
  label: string;
  copy: string;
};

export function NavLink({ href, label, copy }: NavLinkProps) {
  const pathname = usePathname();
  const active = pathname === href;

  return (
    <Link className={`nav-link${active ? " active" : ""}`} href={href}>
      <span className="nav-link-label">{label}</span>
      <span className="nav-link-copy">{copy}</span>
    </Link>
  );
}
