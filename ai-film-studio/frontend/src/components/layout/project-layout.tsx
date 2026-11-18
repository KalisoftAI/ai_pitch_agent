import { ArrowLeft, Clapperboard, FileText, LayoutList, Play } from "lucide-react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/progress";
import { StatusPill } from "@/components/ui/status-pill";
import { useProject } from "@/hooks/queries";
import { CATEGORY_META, cn, titleCase } from "@/lib/utils";
import type { Project } from "@/types";

export interface ProjectContext {
  project: Project;
}

const TABS = [
  { to: "", label: "Overview", icon: Clapperboard, end: true },
  { to: "script", label: "Script", icon: FileText },
  { to: "storyboard", label: "Storyboard", icon: LayoutList },
  { to: "render", label: "Render", icon: Play },
];

export function ProjectLayout() {
  const { id } = useParams();
  const { data: project, isLoading, isError } = useProject(id);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-10 w-full max-w-md" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !project) {
    return (
      <div className="panel flex flex-col items-center gap-3 p-10 text-center">
        <p className="font-display text-lg font-semibold">Project not found</p>
        <p className="text-sm text-muted-foreground">
          It may have been deleted, or the API is offline.
        </p>
        <Button asChild variant="secondary">
          <Link to="/projects">
            <ArrowLeft className="h-4 w-4" /> Back to projects
          </Link>
        </Button>
      </div>
    );
  }

  const meta = CATEGORY_META[project.category];
  const completed = [
    Boolean(project.script?.approved),
    Boolean(project.storyboard?.approved),
    project.status === "rendered",
  ].filter(Boolean).length;
  const progress = Math.round((completed / 3) * 100);

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/projects"
          className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> All projects
        </Link>
        <div className="panel relative overflow-hidden p-6">
          <div className={cn("absolute inset-0 bg-gradient-to-br opacity-70", meta?.accent)} />
          <div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="primary">{meta?.label ?? titleCase(project.category)}</Badge>
                <StatusPill status={project.status} />
                <Badge variant="default">{project.aspect_ratio}</Badge>
                <Badge variant="default">{project.duration_seconds}s</Badge>
              </div>
              <h1 className="mt-3 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
                {project.title}
              </h1>
              <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">{project.topic}</p>
            </div>
            <div className="w-full max-w-xs">
              <div className="mb-1.5 flex items-center justify-between text-xs text-muted-foreground">
                <span>Production progress</span>
                <span className="font-medium text-foreground">{progress}%</span>
              </div>
              <Progress value={progress} tone={progress === 100 ? "success" : "primary"} />
              <div className="mt-3 flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
                <span className={project.script?.approved ? "text-success" : ""}>Script</span>
                <span>→</span>
                <span className={project.storyboard?.approved ? "text-success" : ""}>Storyboard</span>
                <span>→</span>
                <span className={project.status === "rendered" ? "text-success" : ""}>Render</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <nav className="no-scrollbar flex gap-1 overflow-x-auto rounded-xl border border-border/80 bg-card/60 p-1">
        {TABS.map((tab) => (
          <NavLink
            key={tab.label}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              cn(
                "inline-flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-medium transition",
                isActive
                  ? "bg-primary/15 text-primary shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.3)]"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
              )
            }
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </NavLink>
        ))}
      </nav>

      <Outlet context={{ project }} />
    </div>
  );
}
