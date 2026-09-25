"use client";

import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const LINKS = [
  { href: ROUTES.admin.users, label: "Users", kind: "users" as const },
  {
    href: ROUTES.admin.buyers,
    label: "Buyers",
    kind: "biz" as const,
    type: "buyer" as const,
  },
  {
    href: `${ROUTES.admin.businesses}?type=supplier`,
    label: "Suppliers",
    kind: "biz" as const,
    type: "supplier" as const,
  },
  {
    href: ROUTES.admin.suppliers,
    label: "Verifications",
    kind: "verify" as const,
  },
  { href: ROUTES.admin.roles, label: "Roles", kind: "roles" as const },
  {
    href: ROUTES.admin.permissions,
    label: "Permissions",
    kind: "permissions" as const,
  },
];

export function AdminIdentityNav({ className }: { className?: string }) {
  const pathname = usePathname();
  const [bizType, setBizType] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    setBizType(params.get("type"));
  }, [pathname]);

  return (
    <nav className={cn("tb-admin-id-nav", className)} aria-label="Identity">
      <span className="tb-admin-id-nav__label">Identity</span>
      {LINKS.map((link) => {
        let active = false;
        if (link.kind === "users") {
          active = pathname.startsWith("/admin/users");
        } else if (link.kind === "verify") {
          active = pathname.startsWith("/admin/suppliers");
        } else if (link.kind === "roles") {
          active = pathname.startsWith("/admin/roles");
        } else if (link.kind === "permissions") {
          active = pathname.startsWith("/admin/permissions");
        } else if (link.kind === "biz") {
          const onList = pathname === "/admin/businesses";
          const onDetail = pathname.startsWith("/admin/businesses/");
          if (onList) {
            active = bizType === link.type;
          } else if (onDetail) {
            
            
            active = false;
          }
        }
        return (
          <Link
            key={link.href}
            href={link.href}
            data-active={active}
            onClick={() => {
              if (link.kind === "biz") setBizType(link.type);
            }}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
