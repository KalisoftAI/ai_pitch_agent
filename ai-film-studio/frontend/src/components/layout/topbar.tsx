import { Menu, Plus, Radio, Server, WifiOff } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/hooks/queries";
import { useUIStore } from "@/stores/ui";

export function Topbar() {
  const { setSidebarOpen } = useUIStore();
  const { data: health, isError } = useHealth();

  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/70 backdrop-blur-xl">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="hidden items-center gap-2 sm:flex">
          {isError ? (
            <Badge variant="danger">
              <WifiOff className="h-3 w-3" /> API offline
            </Badge>
          ) : (
            <Badge variant={health?.mock_ai ? "warning" : "success"}>
              <Radio className="h-3 w-3" />
              {health?.mock_ai ? "Development mode · Mock AI" : "Live AI mode"}
            </Badge>
          )}
          <Badge variant="default" className="hidden md:inline-flex">
            <Server className="h-3 w-3" /> {health?.storage ?? "local storage"}
          </Badge>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button asChild variant="primary" size="sm">
            <Link to="/create">
              <Plus className="h-4 w-4" />
              New video
            </Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
