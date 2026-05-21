"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Brain,
  Settings,
  Zap,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/investigate", icon: Search, label: "Investigate" },
  { href: "/memory", icon: Brain, label: "Memory" },
  { href: "/config", icon: Settings, label: "Config" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r bg-card flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Zap className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="font-bold text-lg">AutoSRE</h1>
            <p className="text-xs text-muted-foreground">AI Investigation</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href));

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Status */}
      <div className="p-4 border-t">
        <div className="flex items-center gap-2 text-sm">
          <Activity className="w-4 h-4 text-green-500" />
          <span className="text-muted-foreground">System Online</span>
        </div>
      </div>
    </aside>
  );
}
