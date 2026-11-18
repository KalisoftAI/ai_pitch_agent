import { Clapperboard, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/progress";
import { StatusPill } from "@/components/ui/status-pill";
import { useDeleteProject, useProjects } from "@/hooks/queries";
import { CATEGORY_META, cn, formatRelative, titleCase } from "@/lib/utils";
import { toast } from "@/stores/ui";

type Filter = "all" | "business-tips" | "erp-walkthrough" | "financial-education";

export function ProjectsPage() {
  const { data: projects, isLoading, isError } = useProjects();
  const deleteProject = useDeleteProject();
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const visible = useMemo(() => {
    return (projects ?? []).filter((project) => {
      const matchesFilter = filter === "all" || project.category === filter;
      const query = search.trim().toLowerCase();
      const matchesSearch =
        !query ||
        project.title.toLowerCase().includes(query) ||
        project.topic.toLowerCase().includes(query);
      return matchesFilter && matchesSearch;
    });
  }, [projects, filter, search]);

  const target = projects?.find((project) => project.id === pendingDelete);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Library"
        title="Projects"
        description="Every video idea, script, storyboard, and render in one place."
        actions={
          <Button asChild>
            <Link to="/create">
              <Plus className="h-4 w-4" /> New project
            </Link>
          </Button>
        }
      />

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Segmented
          className="max-w-2xl"
          value={filter}
          onChange={setFilter}
          items={[
            { value: "all", label: "All" },
            { value: "business-tips", label: "Business" },
            { value: "erp-walkthrough", label: "ERP" },
            { value: "financial-education", label: "Finance" },
          ]}
        />
        <div className="relative w-full lg:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search projects..."
            className="pl-9"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-44 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="panel p-10 text-center text-sm text-muted-foreground">
          Could not load projects. Check that the API is running.
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon={Clapperboard}
          title="No projects match"
          description="Adjust the filters or start a fresh story. A project holds the script, storyboard, and render together."
          action={
            <Button asChild>
              <Link to="/create">
                <Plus className="h-4 w-4" /> Create video
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((project) => {
            const meta = CATEGORY_META[project.category];
            return (
              <Card key={project.id} className="panel-hover group overflow-hidden">
                <div className={cn("h-1.5 w-full bg-gradient-to-r", meta?.accent)} />
                <CardContent className="space-y-4 p-5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex flex-wrap gap-1.5">
                      <Badge variant="primary">{meta?.short ?? titleCase(project.category)}</Badge>
                      <StatusPill status={project.status} />
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="opacity-0 transition group-hover:opacity-100"
                      onClick={() => setPendingDelete(project.id)}
                      aria-label="Delete project"
                    >
                      <Trash2 className="h-4 w-4 text-danger" />
                    </Button>
                  </div>
                  <div>
                    <Link
                      to={`/projects/${project.id}`}
                      className="font-display text-base font-semibold leading-snug transition hover:text-primary"
                    >
                      {project.title}
                    </Link>
                    <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                      {project.topic}
                    </p>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>
                      {project.aspect_ratio} · {project.duration_seconds}s
                    </span>
                    <span>{formatRelative(project.updated_at)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button asChild size="sm" variant="secondary" className="flex-1">
                      <Link to={`/projects/${project.id}/script`}>Open workspace</Link>
                    </Button>
                    {project.storyboard?.approved ? (
                      <Button asChild size="sm" variant="outline">
                        <Link to={`/projects/${project.id}/render`}>Render</Link>
                      </Button>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title="Delete this project?"
        description="The script, storyboard, and render records will be removed. This cannot be undone."
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={deleteProject.isPending}
              onClick={() => {
                if (!pendingDelete) return;
                deleteProject.mutate(pendingDelete, {
                  onSuccess: () => {
                    toast.success("Project deleted");
                    setPendingDelete(null);
                  },
                  onError: (error) => toast.error("Delete failed", error.message),
                });
              }}
            >
              Delete project
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{target?.title}</span> will be permanently
          removed from the studio.
        </p>
      </Modal>
    </div>
  );
}
