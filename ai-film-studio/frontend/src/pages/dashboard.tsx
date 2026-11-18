import {
  Activity as ActivityIcon,
  ArrowRight,
  Clapperboard,
  Coins,
  FolderKanban,
  Image,
  PlayCircle,
  Plus,
  Sparkles,
  Wand2,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Progress, Skeleton } from "@/components/ui/progress";
import { StatCard } from "@/components/ui/stat-card";
import { StatusPill } from "@/components/ui/status-pill";
import { useDashboard } from "@/hooks/queries";
import {
  CATEGORY_META,
  cn,
  formatCurrency,
  formatNumber,
  formatRelative,
  titleCase,
} from "@/lib/utils";

export function DashboardPage() {
  const { data, isLoading, isError } = useDashboard();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-40 w-full" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="panel p-10 text-center">
        <p className="font-display text-lg font-semibold">Studio is offline</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Start the backend with <code className="text-foreground">uvicorn app.main:app --reload</code>{" "}
          and refresh.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Studio overview"
        title="Make the next video feel inevitable."
        description="Pick a category, shape the story, approve the board, and render locally. Everything stays on this machine."
        actions={
          <Button asChild size="lg">
            <Link to="/create">
              <Plus className="h-4 w-4" /> Create video
            </Link>
          </Button>
        }
      />

      <section className="panel relative overflow-hidden p-6 sm:p-8">
        <div className="grid-bg pointer-events-none absolute inset-0 opacity-40" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-xl">
            <Badge variant="primary" className="mb-3">
              <Sparkles className="h-3 w-3" /> Phase 1 · Local production
            </Badge>
            <h2 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">
              From one idea to a finished business video.
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              The studio writes the script, breaks it into scenes, and renders a preview with
              FFmpeg. Switch to a live model whenever you are ready.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button asChild>
                <Link to="/create">
                  Start a new story <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="secondary">
                <Link to="/projects">Browse projects</Link>
              </Button>
            </div>
          </div>
          <div className="grid w-full max-w-sm gap-3">
            <div className="glass flex items-center justify-between rounded-xl p-4">
              <div>
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Selected model
                </p>
                <p className="mt-1 font-display text-sm font-semibold">
                  {data.usage.selected_model}
                </p>
              </div>
              <Wand2 className="h-5 w-5 text-primary" />
            </div>
            <div className="glass rounded-xl p-4">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Monthly AI budget</span>
                <span className="text-foreground">{formatCurrency(data.usage.estimated_cost)}</span>
              </div>
              <Progress
                className="mt-2"
                value={data.usage.budget_used_pct}
                tone={data.usage.budget_used_pct > 80 ? "warning" : "primary"}
              />
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                {data.usage.budget_used_pct.toFixed(1)}% of {formatCurrency(data.usage.budget_usd)}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Projects"
          value={formatNumber(data.projects_total)}
          hint={`${data.projects_in_progress} in progress`}
          icon={FolderKanban}
        />
        <StatCard
          label="Renders"
          value={formatNumber(data.renders_completed)}
          hint={`${data.renders_active} active now`}
          icon={PlayCircle}
          tone="success"
        />
        <StatCard
          label="Assets"
          value={formatNumber(data.assets_total)}
          hint="Images and clips"
          icon={Image}
          tone="accent"
        />
        <StatCard
          label="AI tokens"
          value={formatNumber(data.usage.total_tokens)}
          hint={`${formatNumber(data.usage.total_requests)} requests`}
          icon={Coins}
          tone="warning"
        />
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold">Categories</h2>
          <span className="text-xs text-muted-foreground">Three focused formats</span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {data.categories.map((category) => {
            const meta = CATEGORY_META[category.id];
            return (
              <Link
                key={category.id}
                to={`/create?category=${category.id}`}
                className="panel panel-hover group relative overflow-hidden p-5"
              >
                <div
                  className={cn(
                    "absolute inset-0 bg-gradient-to-br opacity-60 transition group-hover:opacity-100",
                    meta?.accent,
                  )}
                />
                <div className="relative">
                  <div className="flex items-center justify-between">
                    <Badge variant="default">{meta?.short ?? titleCase(category.id)}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {category.project_count ?? 0} projects
                    </span>
                  </div>
                  <h3 className="mt-4 font-display text-base font-semibold leading-snug">
                    {category.label}
                  </h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">
                    {meta?.description ?? "A focused short-form format."}
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-primary">
                    Create in this format <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Recent projects</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Pick up where the story left off.
              </p>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to="/projects">
                View all <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.recent_projects.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                No projects yet. Create your first video to get started.
              </div>
            ) : (
              data.recent_projects.map((project) => (
                <Link
                  key={project.id}
                  to={`/projects/${project.id}`}
                  className="flex items-center gap-3 rounded-xl border border-transparent px-3 py-3 transition hover:border-border/80 hover:bg-white/[0.04]"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Clapperboard className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{project.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {CATEGORY_META[project.category]?.short ?? project.category} ·{" "}
                      {project.duration_seconds}s · {formatRelative(project.updated_at)}
                    </p>
                  </div>
                  <StatusPill status={project.status} />
                </Link>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Activity</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">Latest studio events.</p>
            </div>
            <ActivityIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {data.recent_activity.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">No activity yet.</p>
            ) : (
              <ol className="relative space-y-4 border-l border-border/70 pl-4">
                {data.recent_activity.map((item) => (
                  <li key={item.id} className="relative">
                    <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-primary/70 ring-4 ring-background" />
                    <p className="text-sm leading-snug">{item.message}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {formatRelative(item.created_at)}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
