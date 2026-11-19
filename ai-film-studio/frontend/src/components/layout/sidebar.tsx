import {
  Clapperboard,
  FolderKanban,
  Image,
  LayoutDashboard,
  PlusCircle,
  Settings,
  Sparkles,
  Wand2,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useHealth } from "@/hooks/queries";
import { useUIStore } from "@/stores/ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/create", label: "Create Video", icon: PlusCircle },
  { to: "/assets", label: "Asset Library", icon: Image },
  { to: "/ai", label: "AI Usage", icon: Wand2 },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const { sidebarOpen, setSidebarOpen } = useUIStore();
  const { data: health } = useHealth();

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-30 bg-black/60 backdrop-blur-sm transition lg:hidden",
          sidebarOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={() => setSidebarOpen(false)}
      />
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col border-r border-border/70 bg-background/85 backdrop-blur-xl transition-transform duration-300 lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-fuchsia-500 shadow-glow">
            <Clapperboard className="h-5 w-5 text-white" />
          </div>
          <div>
            <p className="font-display text-sm font-semibold leading-tight">AI Film Studio</p>
            <p className="text-[11px] text-muted-foreground">Local video production</p>
          </div>
        </div>

        <nav className="mt-2 flex-1 space-y-1 px-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                  isActive
                    ? "bg-primary/12 text-primary shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.25)]"
                    : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground",
                )
              }
            >
              <item.icon className="h-[18px] w-[18px]" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="m-3 rounded-2xl border border-white/10 bg-gradient-to-br from-primary/15 via-card to-card p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            Local-first studio
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
            Scripts, storyboards and renders stay on this machine. No cloud required.
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge variant={health?.mock_ai ? "warning" : "success"}>
              {health?.mock_ai ? "Mock AI" : "Live AI"}
            </Badge>
            <Badge variant={health?.ffmpeg_available ? "success" : "danger"}>
              {health?.ffmpeg_available ? "FFmpeg ready" : "FFmpeg missing"}
            </Badge>
          </div>
        </div>
      </aside>
    </>
  );
}
