import {
  ArrowRight,
  CheckCircle2,
  Circle,
  Clapperboard,
  FileText,
  LayoutList,
  PlayCircle,
} from "lucide-react";
import { Link, useOutletContext } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import type { ProjectContext } from "@/components/layout/project-layout";
import { useRenders } from "@/hooks/queries";
import { CATEGORY_META, formatRelative, titleCase } from "@/lib/utils";

export function ProjectOverviewPage() {
  const { project } = useOutletContext<ProjectContext>();
  const { data: renders } = useRenders(project.id);
  const meta = CATEGORY_META[project.category];

  const steps = [
    {
      label: "Script",
      description: "Draft, edit, and approve the narration.",
      done: Boolean(project.script?.approved),
      exists: Boolean(project.script),
      to: `/projects/${project.id}/script`,
      icon: FileText,
    },
    {
      label: "Storyboard",
      description: "Turn the script into timed scenes.",
      done: Boolean(project.storyboard?.approved),
      exists: Boolean(project.storyboard),
      to: `/projects/${project.id}/storyboard`,
      icon: LayoutList,
    },
    {
      label: "Render",
      description: "Produce a preview and final export.",
      done: project.status === "rendered",
      exists: Boolean(renders?.length),
      to: `/projects/${project.id}/render`,
      icon: PlayCircle,
    },
  ];

  const latest = renders?.[0];

  return (
    <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Production checklist</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Three approvals stand between this idea and a finished video.
              </p>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {steps.map((step) => (
              <div
                key={step.label}
                className="flex items-center gap-3 rounded-xl border border-border/70 bg-card/40 p-4"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <step.icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium">{step.label}</p>
                    {step.done ? (
                      <Badge variant="success">Approved</Badge>
                    ) : step.exists ? (
                      <Badge variant="warning">In review</Badge>
                    ) : (
                      <Badge variant="default">Not started</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{step.description}</p>
                </div>
                {step.done ? (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                ) : (
                  <Circle className="h-5 w-5 text-muted-foreground/50" />
                )}
                <Button asChild size="sm" variant={step.done ? "ghost" : "secondary"}>
                  <Link to={step.to}>
                    Open <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Brief</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">The creative direction for this video.</p>
            </div>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 sm:grid-cols-2">
              {[
                ["Category", meta?.label ?? titleCase(project.category)],
                ["Topic", project.topic],
                ["Visual style", titleCase(project.visual_style)],
                ["Template", titleCase(project.template)],
                ["Duration", `${project.duration_seconds} seconds`],
                ["Aspect ratio", project.aspect_ratio],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-border/70 bg-card/40 p-3">
                  <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    {label}
                  </dt>
                  <dd className="mt-0.5 text-sm font-medium">{value}</dd>
                </div>
              ))}
            </dl>
            {project.description ? (
              <div className="mt-3 rounded-xl border border-border/70 bg-card/40 p-3">
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Angle
                </p>
                <p className="mt-1 text-sm leading-relaxed">{project.description}</p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Latest render</CardTitle>
            <StatusPill status={latest?.status ?? "draft"} />
          </CardHeader>
          <CardContent>
            {latest ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Clapperboard className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{titleCase(latest.stage)}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatRelative(latest.created_at)} · {latest.progress}%
                    </p>
                  </div>
                </div>
                <Button asChild variant="secondary" className="w-full">
                  <Link to={`/projects/${project.id}/render`}>
                    Open render workspace <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            ) : (
              <div className="space-y-3 text-sm text-muted-foreground">
                <p>No renders yet. Approve the script and storyboard first.</p>
                <Button asChild variant="secondary" className="w-full">
                  <Link to={`/projects/${project.id}/render`}>
                    Go to rendering <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="rounded-2xl border border-primary/20 bg-primary/[0.07] p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-primary">Next action</p>
          <p className="mt-2 font-display text-base font-semibold">
            {!project.script
              ? "Draft the script"
              : !project.script.approved
                ? "Review and approve the script"
                : !project.storyboard
                  ? "Generate the storyboard"
                  : !project.storyboard.approved
                    ? "Approve the storyboard"
                    : "Render the video"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {!project.script
              ? "The studio can write a first draft in seconds."
              : !project.script.approved
                ? "Edit the narration until it sounds like you."
                : "Scenes will inherit the approved narration."}
          </p>
          <Button asChild className="mt-4 w-full">
            <Link
              to={
                !project.script || !project.script.approved
                  ? `/projects/${project.id}/script`
                  : !project.storyboard || !project.storyboard.approved
                    ? `/projects/${project.id}/storyboard`
                    : `/projects/${project.id}/render`
              }
            >
              Continue <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
