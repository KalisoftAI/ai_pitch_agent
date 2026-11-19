import { useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Cloud,
  CloudUpload,
  Download,
  Film,
  Loader2,
  Play,
  RefreshCw,
  Sparkles,
  Square,
  Terminal,
  Video,
  Volume2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Progress, Skeleton } from "@/components/ui/progress";
import { Segmented } from "@/components/ui/segmented";
import { StatusPill } from "@/components/ui/status-pill";
import type { ProjectContext } from "@/components/layout/project-layout";
import {
  keys,
  useCancelRender,
  useCreateRender,
  usePublishRender,
  useRenderLogs,
  useRenders,
  useStorageGallery,
  useStorageStatus,
} from "@/hooks/queries";
import { api } from "@/services/api";
import { cn, formatRelative, titleCase } from "@/lib/utils";
import { toast } from "@/stores/ui";
import type { RenderJob, StoragePublish } from "@/types";

type Quality = "preview" | "export" | "both";
type Engine = "motion" | "cards";

const STYLES = [
  "auto",
  "cinematic",
  "editorial",
  "neon",
  "minimal",
  "swiss",
  "data",
  "isometric",
  "typographic",
  "infographic",
  "walkthrough",
  "documentary",
  "story",
];

const EFFECTS = [
  "grain",
  "vignette",
  "particles",
  "letterbox",
  "scanlines",
  "lightleak",
  "bokeh",
  "grid",
  "glitch",
  "chromatic",
];

const PATTERNS = [
  "auto",
  "split",
  "full",
  "minimal",
  "data",
  "collage",
  "quote",
  "isometric",
  "typographic",
  "infographic",
  "walkthrough",
  "documentary",
  "story",
];

function cloudUrl(bucket: string, name: string) {
  return `https://storage.cloud.google.com/${bucket}/${name
    .split("/")
    .map(encodeURIComponent)
    .join("/")}`;
}

export function RenderPage() {
  const { project } = useOutletContext<ProjectContext>();
  const { data: renders, isLoading } = useRenders(project.id);
  const createRender = useCreateRender(project.id);
  const cancelRender = useCancelRender(project.id);
  const publishRender = usePublishRender(project.id);
  const { data: storageStatus } = useStorageStatus();
  const { data: gallery } = useStorageGallery(24, Boolean(storageStatus?.enabled));
  const queryClient = useQueryClient();

  const [quality, setQuality] = useState<Quality>("both");
  const [engine, setEngine] = useState<Engine>("motion");
  const [captions, setCaptions] = useState(true);
  const [motionStyle, setMotionStyle] = useState("auto");
  const [effects, setEffects] = useState<string[]>(["grain", "vignette", "particles"]);
  const [audio, setAudio] = useState(true);
  const [patterns, setPatterns] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [live, setLive] = useState<Partial<RenderJob> | null>(null);

  const latest = renders?.[0];
  const active = renders?.find((job) => job.status === "queued" || job.status === "running");
  const selected = renders?.find((job) => job.id === selectedId) ?? latest;
  const display = selected && live && live.id === selected.id ? { ...selected, ...live } : selected;
  const isActive = display?.status === "queued" || display?.status === "running";
  const logs = useRenderLogs(display?.id, Boolean(isActive));

  useEffect(() => {
    if (!active) {
      setLive(null);
      return;
    }
    const source = new EventSource(api.renderEventsUrl(active.id));
    source.addEventListener("progress", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as Partial<RenderJob>;
      setLive(payload);
      if (["completed", "failed", "cancelled"].includes(payload.status ?? "")) {
        source.close();
        void queryClient.invalidateQueries({ queryKey: keys.renders(project.id) });
        void queryClient.invalidateQueries({ queryKey: keys.project(project.id) });
        void queryClient.invalidateQueries({ queryKey: keys.dashboard });
      }
    });
    source.onerror = () => source.close();
    return () => source.close();
  }, [active, project.id, queryClient]);

  useEffect(() => {
    if (!latest || !["completed", "failed", "cancelled"].includes(latest.status)) return;
    void queryClient.invalidateQueries({ queryKey: keys.project(project.id) });
    void queryClient.invalidateQueries({ queryKey: keys.dashboard });
  }, [latest?.id, latest?.status, project.id, queryClient]);

  const approved = Boolean(project.storyboard?.approved);
  const scenes = project.storyboard?.scenes ?? [];
  const storageInfo = (display?.options?.storage ?? null) as StoragePublish | null;
  const logLines = useMemo(
    () => logs.data?.logs ?? (display?.logs ? display.logs.split("\n").filter(Boolean) : []),
    [logs.data, display],
  );

  if (isLoading) {
    return (
      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Skeleton className="h-80" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!approved) {
    return (
      <EmptyState
        icon={Video}
        title="Approve the storyboard first"
        description="Rendering uses the approved scenes, narration, and timing. Finish the board, then come back."
        action={
          <Button asChild>
            <Link to={`/projects/${project.id}/storyboard`}>Open storyboard</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Rendering workspace</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Animated canvas scenes are captured in headless Chrome and encoded locally with FFmpeg.
              </p>
            </div>
            {display ? <StatusPill status={display.status} /> : null}
          </CardHeader>
          <CardContent>
            {display ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    {isActive ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    ) : display.status === "completed" ? (
                      <CheckCircle2 className="h-4 w-4 text-success" />
                    ) : (
                      <Film className="h-4 w-4 text-muted-foreground" />
                    )}
                    <span className="font-medium">{titleCase(display.stage)}</span>
                  </div>
                  <span className="font-mono text-xs text-muted-foreground">
                    {display.progress}%
                  </span>
                </div>
                <Progress
                  value={display.progress}
                  tone={
                    display.status === "failed"
                      ? "danger"
                      : display.status === "completed"
                        ? "success"
                        : "primary"
                  }
                />
                {display.error ? (
                  <div className="rounded-xl border border-danger/30 bg-danger/[0.07] p-3 text-sm text-danger">
                    {display.error}
                  </div>
                ) : null}
                {display.status === "completed" && display.preview_path ? (
                  <video
                    key={display.id}
                    controls
                    className="aspect-video w-full rounded-xl border border-border bg-black"
                    src={api.previewUrl(display.id)}
                  />
                ) : (
                  <div className="flex aspect-video w-full items-center justify-center rounded-xl border border-dashed border-border bg-black/40">
                    <div className="text-center">
                      <Film className="mx-auto h-8 w-8 text-muted-foreground/50" />
                      <p className="mt-2 text-xs text-muted-foreground">
                        {isActive ? "Frames are being composed..." : "Preview appears here"}
                      </p>
                    </div>
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  {isActive ? (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() =>
                        cancelRender.mutate(display.id, {
                          onSuccess: () => toast.info("Render cancelled"),
                          onError: (error) => toast.error("Could not cancel", error.message),
                        })
                      }
                      loading={cancelRender.isPending}
                    >
                      <Square className="h-3.5 w-3.5" /> Cancel render
                    </Button>
                  ) : null}
                  {display.preview_path ? (
                    <Button asChild size="sm" variant="secondary">
                      <a href={api.previewUrl(display.id)} download>
                        <Download className="h-3.5 w-3.5" /> Preview MP4
                      </a>
                    </Button>
                  ) : null}
                  {display.export_path ? (
                    <Button asChild size="sm">
                      <a href={api.exportUrl(display.id)} download>
                        <Download className="h-3.5 w-3.5" /> Export 720p
                      </a>
                    </Button>
                  ) : null}
                  {display.status === "completed" && storageStatus?.enabled ? (
                    storageInfo ? (
                      <Button asChild size="sm" variant="secondary">
                        <a
                          href={cloudUrl(storageInfo.bucket, storageInfo.manifest.name)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <Cloud className="h-3.5 w-3.5" /> Open in GCS
                        </a>
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={publishRender.isPending}
                        onClick={() =>
                          publishRender.mutate(display.id, {
                            onSuccess: (result) =>
                              toast.success("Published to cloud", result.folder),
                            onError: (error) =>
                              toast.error("Cloud publish failed", error.message),
                          })
                        }
                      >
                        <CloudUpload className="h-3.5 w-3.5" /> Publish to GCS
                      </Button>
                    )
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="flex aspect-video items-center justify-center rounded-xl border border-dashed border-border bg-black/30">
                <div className="text-center">
                  <Play className="mx-auto h-8 w-8 text-muted-foreground/50" />
                  <p className="mt-2 text-sm text-muted-foreground">
                    No renders yet. Start one from the panel.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-muted-foreground" />
              <CardTitle>Render log</CardTitle>
            </div>
            <Badge variant="default">{logLines.length} lines</Badge>
          </CardHeader>
          <CardContent>
            <div className="max-h-64 overflow-y-auto rounded-xl border border-border/70 bg-black/50 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
              {logLines.length === 0 ? (
                <p>Waiting for a render...</p>
              ) : (
                logLines.map((line, index) => (
                  <p key={index} className={cn(line.includes("ERROR") && "text-danger")}>
                    {line}
                  </p>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>New render</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Motion graphics take longer. Fast cards are the fallback.
              </p>
            </div>
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Render engine
              </p>
              <Segmented
                value={engine}
                onChange={setEngine}
                items={[
                  { value: "motion", label: "Motion" },
                  { value: "cards", label: "Fast cards" },
                ]}
              />
            </div>
            {engine === "motion" ? (
              <>
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Motion style
                  </p>
                  <select
                    value={motionStyle}
                    onChange={(event) => setMotionStyle(event.target.value)}
                    className="w-full rounded-xl border border-border/70 bg-card/60 px-3 py-2 text-sm capitalize outline-none focus:border-primary/50"
                  >
                    {STYLES.map((style) => (
                      <option key={style} value={style}>
                        {style === "auto" ? "Auto from project" : style}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    <Sparkles className="h-3 w-3" /> Effects
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {EFFECTS.map((effect) => {
                      const selected = effects.includes(effect);
                      return (
                        <button
                          key={effect}
                          type="button"
                          onClick={() =>
                            setEffects((current) =>
                              current.includes(effect)
                                ? current.filter((item) => item !== effect)
                                : [...current, effect],
                            )
                          }
                          className={cn(
                            "rounded-full border px-2.5 py-1 text-[11px] font-medium capitalize transition",
                            selected
                              ? "border-primary/40 bg-primary/15 text-primary"
                              : "border-border/60 bg-card/40 text-muted-foreground hover:border-border",
                          )}
                        >
                          {effect}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <label className="flex cursor-pointer items-center justify-between rounded-xl border border-border/70 bg-card/40 p-3">
                  <div className="flex items-center gap-2">
                    <Volume2 className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">Sound bed</p>
                      <p className="text-xs text-muted-foreground">
                        Procedural cues, whooshes, and a normalised mix.
                      </p>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={audio}
                    onChange={(event) => setAudio(event.target.checked)}
                    className="h-4 w-4 accent-[hsl(var(--primary))]"
                  />
                </label>
                {scenes.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Scene patterns
                    </p>
                    <div className="space-y-1.5">
                      {scenes.map((scene, index) => (
                        <div
                          key={scene.id}
                          className="flex items-center gap-2 rounded-xl border border-border/60 bg-card/30 px-2.5 py-1.5"
                        >
                          <span className="min-w-0 flex-1 truncate text-xs">
                            {index + 1}. {scene.title}
                          </span>
                          <select
                            value={patterns[scene.id] ?? "auto"}
                            onChange={(event) =>
                              setPatterns((current) => ({
                                ...current,
                                [scene.id]: event.target.value,
                              }))
                            }
                            className="w-32 rounded-lg border border-border/60 bg-card/60 px-2 py-1 text-[11px] capitalize outline-none focus:border-primary/50"
                          >
                            {PATTERNS.map((pattern) => (
                              <option key={pattern} value={pattern}>
                                {pattern === "auto" ? "Auto" : pattern}
                              </option>
                            ))}
                          </select>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Output
              </p>
              <Segmented
                value={quality}
                onChange={setQuality}
                items={[
                  { value: "preview", label: "Preview" },
                  { value: "export", label: "Export" },
                  { value: "both", label: "Both" },
                ]}
              />
            </div>
            <label className="flex cursor-pointer items-center justify-between rounded-xl border border-border/70 bg-card/40 p-3">
              <div>
                <p className="text-sm font-medium">Include narration</p>
                <p className="text-xs text-muted-foreground">Show scene captions and voiceover text.</p>
              </div>
              <input
                type="checkbox"
                checked={captions}
                onChange={(event) => setCaptions(event.target.checked)}
                className="h-4 w-4 accent-[hsl(var(--primary))]"
              />
            </label>
            <Button
              className="w-full"
              size="lg"
              loading={createRender.isPending}
              disabled={Boolean(active)}
              onClick={() =>
                createRender.mutate(
                  {
                    quality,
                    include_captions: captions,
                    engine,
                    motion_style: motionStyle === "auto" ? null : motionStyle,
                    effects,
                    audio,
                    scene_patterns: Object.fromEntries(
                      scenes.flatMap((scene, index) => {
                        const pattern = patterns[scene.id];
                        return pattern && pattern !== "auto" ? [[String(index), pattern]] : [];
                      }),
                    ),
                  },
                  {
                    onSuccess: (job) => {
                      setSelectedId(job.id);
                      toast.success("Render queued", "Progress streams in real time.");
                    },
                    onError: (error) => toast.error("Could not start render", error.message),
                  },
                )
              }
            >
              <Play className="h-4 w-4" />
              {active ? "Render in progress" : "Start render"}
            </Button>
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              CPU rendering with headless Chrome. Keep the backend running until the job completes.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>History</CardTitle>
            <Badge variant="default">{renders?.length ?? 0}</Badge>
          </CardHeader>
          <CardContent className="space-y-2">
            {(renders ?? []).length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">No renders yet.</p>
            ) : (
              renders?.map((job) => (
                <button
                  key={job.id}
                  onClick={() => {
                    setSelectedId(job.id);
                    setLive(null);
                  }}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-xl border px-3 py-2.5 text-left transition",
                    display?.id === job.id
                      ? "border-primary/40 bg-primary/10"
                      : "border-border/60 bg-card/40 hover:border-border",
                  )}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {titleCase(job.stage)} · {job.progress}%
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {formatRelative(job.created_at)}
                    </p>
                  </div>
                  <StatusPill status={job.status} />
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Cloud className="h-4 w-4 text-muted-foreground" />
              <CardTitle>Cloud library</CardTitle>
            </div>
            <Badge variant="default">{gallery?.length ?? 0}</Badge>
          </CardHeader>
          <CardContent className="space-y-2">
            {storageStatus && !storageStatus.available ? (
              <p className="rounded-xl border border-border/60 bg-card/30 p-3 text-xs text-muted-foreground">
                {storageStatus.message}
              </p>
            ) : (gallery ?? []).length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Published renders will appear here.
              </p>
            ) : (
              gallery?.map((item) => (
                <a
                  key={item.name}
                  href={
                    storageStatus?.bucket ? cloudUrl(storageStatus.bucket, item.name) : undefined
                  }
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between gap-2 rounded-xl border border-border/60 bg-card/40 px-3 py-2.5 transition hover:border-border"
                >
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium">{item.name.split("/").pop()}</p>
                    <p className="truncate text-[11px] text-muted-foreground">{item.name}</p>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {Math.max(1, Math.round(item.size / 1024))} KB
                  </span>
                </a>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
