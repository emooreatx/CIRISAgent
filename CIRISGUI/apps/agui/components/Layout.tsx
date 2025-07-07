"use client";
import LogoIcon from "../components/ui/floating/LogoIcon";
import Link from "next/link";
import { useAuth } from "../contexts/AuthContext";
import { useRouter } from "next/navigation";
import React, { useState } from "react";
import {
  HoveredLink,
  Menu,
  MenuItem,
  ProductItem,
} from "../components/ui/navbar-menu";
import { cn } from "../lib/utils";
interface LayoutProps {
  children: React.ReactNode;
}

function Navbar({ className }: { className?: string }) {
  const [active, setActive] = useState<string | null>(null);
  return (
    <div className={cn("fixed   inset-x-0 max-w-2xl mx-auto z-50", className)}>
      <Menu setActive={setActive}>
        <LogoIcon className="h-12 w-12 text-brand-primary fill-brand-primary" />
        <MenuItem setActive={setActive} active={active} item="Services1">
          <div className="flex flex-col space-y-4 justify-around text-sm">
            <HoveredLink href="/web-dev">Web Development</HoveredLink>
            <HoveredLink href="/interface-design">Interface Design</HoveredLink>
            <HoveredLink href="/seo">Search Engine Optimization</HoveredLink>
            <HoveredLink href="/branding">Branding</HoveredLink>
          </div>
        </MenuItem>{" "}
        <MenuItem setActive={setActive} active={active} item="Services">
          <div className="flex flex-col space-y-4 text-sm">
            <HoveredLink href="/web-dev">Web Development</HoveredLink>
            <HoveredLink href="/interface-design">Interface Design</HoveredLink>
            <HoveredLink href="/seo">Search Engine Optimization</HoveredLink>
            <HoveredLink href="/branding">Branding</HoveredLink>
          </div>
        </MenuItem>
        <MenuItem setActive={setActive} active={active} item="Products">
          <div className="  text-sm grid grid-cols-2 gap-10 p-4">
            <ProductItem
              title="Algochurn"
              href="https://algochurn.com"
              src="https://assets.aceternity.com/demos/algochurn.webp"
              description="Prepare for tech interviews like never before."
            />
            <ProductItem
              title="Tailwind Master Kit"
              href="https://tailwindmasterkit.com"
              src="https://assets.aceternity.com/demos/tailwindmasterkit.webp"
              description="Production ready Tailwind css components for your next project"
            />
            <ProductItem
              title="Moonbeam"
              href="https://gomoonbeam.com"
              src="https://assets.aceternity.com/demos/Screenshot+2024-02-21+at+11.51.31%E2%80%AFPM.png"
              description="Never write from scratch again. Go from idea to blog in minutes."
            />
            <ProductItem
              title="Rogue"
              href="https://userogue.com"
              src="https://assets.aceternity.com/demos/Screenshot+2024-02-21+at+11.47.07%E2%80%AFPM.png"
              description="Respond to government RFPs, RFIs and RFQs 10x faster using AI"
            />
          </div>
        </MenuItem>
        <MenuItem setActive={setActive} active={active} item="Pricing">
          <div className="flex flex-col space-y-4 text-sm">
            <HoveredLink href="/hobby">Hobby</HoveredLink>
            <HoveredLink href="/individual">Individual</HoveredLink>
            <HoveredLink href="/team">Team</HoveredLink>
            <HoveredLink href="/enterprise">Enterprise</HoveredLink>
          </div>
        </MenuItem>
      </Menu>
    </div>
  );
}
export function Layout({ children }: LayoutProps) {
  const { user, logout, hasRole } = useAuth();
  const router = useRouter();

  const navigation = [
    { name: "Dashboard", href: "/dashboard", minRole: "OBSERVER" },
    { name: "API Explorer", href: "/api-demo", minRole: "OBSERVER" },
    { name: "API Docs", href: "/docs", minRole: "OBSERVER" },
    { name: "Home", href: "/", minRole: "OBSERVER" },
    { name: "Communications", href: "/comms", minRole: "OBSERVER" },
    { name: "Memory", href: "/memory", minRole: "OBSERVER" },
    { name: "Audit", href: "/audit", minRole: "OBSERVER" },
    { name: "Logs", href: "/logs", minRole: "OBSERVER" },
    { name: "Tools", href: "/tools", minRole: "OBSERVER" },
    { name: "System", href: "/system", minRole: "OBSERVER" },
    { name: "Config", href: "/config", minRole: "ADMIN" },
    { name: "Users", href: "/users", minRole: "ADMIN" },
    { name: "WA", href: "/wa", minRole: "OBSERVER" }, // Will be filtered by the page itself based on ADMIN or AUTHORITY role
  ];

  const visibleNavigation = navigation.filter((item) => hasRole(item.minRole));

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar className="top-20" />
      <nav className="bg-white shadow ">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify- h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold">CIRIS GUI</h1>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                {visibleNavigation.map((item) => (
                  <Link
                    key={item.name}
                    href={item.href}
                    className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>
            <div className="flex items-center">
              {user && (
                <div className="flex items-center space-x-4">
                  <span className="text-sm text-gray-700">
                    {user.username || user.user_id} ({user.role})
                  </span>
                  <button
                    onClick={() => logout()}
                    className="text-sm text-gray-500 hover:text-gray-700">
                    Logout
                  </button>
                  {hasRole("SYSTEM_ADMIN") && (
                    <button
                      onClick={() => router.push("/emergency")}
                      className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700">
                      Emergency
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  );
}
