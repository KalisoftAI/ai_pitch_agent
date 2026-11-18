import { motion } from "framer-motion";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Check,
  Clapperboard,
  Clock,
  Film,
  LayoutList,
  Pencil,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/progress";
import { StatusPill } from "@/components/ui/status-pill";
import type { ProjectContext } from "@/components/layout/project-layout";
import {
  useApproveStoryboard,
  useGenerateStoryboard,
  useRegenerateScene,
  useReorderScenes,
  useStoryboard,
  useUpdateScene,
} from "@/hooks/queries";
import { cn } from "@/lib/utils";
import { toast } from "@/stores/ui";
import type { Scene } from "@/types";

export function StoryboardPage() {
  const { project } = useOutletContext<ProjectContext>();
  const { data: storyboard, isLoading, isError } = useStoryboard(project.id);
  const generateStoryboard = useGenerateStoryboard(project.id);
  const updateScene = useUpdateScene(project.id);
  const regenerateScene = useRegenerateScene(project.id);
  const reorderScenes = useReorderScenes(project.id);
  const approveStoryboard = useApproveStoryboard(project.id);

  const [sceneCount, setSceneCount] = useState(6);
  const style = project.visual_style;
  const [editing, setEditing] = useState<Scene | null>(null);
  const [activeScene, setActiveScene] = useState<string | null>(null);
  const autoStarted = useRef(false);

  const hasScript = Boolean(project.script?.content.trim());

  useEffect(() => {
    if (!storyboard && !autoStarted.current && !isLoading && hasScript) {
      autoStarted.current = true;
      generateStoryboard.mutate(
        { scene_count: sceneCount, style },
        {
          onSuccess: () => toast.success("Storyboard drafted", "Tune each scene before rendering."),
          onError: (error) => toast.error("Could not generate storyboard", error.message),
        },
      );
    }
  }, [storyboard, isLoading, generateStoryboard, sceneCount, style, hasScript]);

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-48" />
        ))}
      </div>
    );
  }

  if (isError || !storyboard) {
    return (
      <EmptyState
        icon={LayoutList}
        title={hasScript ? "No storyboard yet" : "Write the script first"}
        description={
          hasScript
            ? "The studio will turn the script into timed scenes with narration and visual prompts."
            : "The storyboard is built from the narration. Generate or write the script, then come back."
        }
        action={
          hasScript ? (
            <Button
              onClick={() =>
                generateStoryboard.mutate(
                  { scene_count: sceneCount, style },
                  {
                    onSuccess: () => toast.success("Storyboard drafted"),
                    onError: (error) => toast.error("Could not generate storyboard", error.message),
                  },
                )
              }
              loading={generateStoryboard.isPending}
            >
              <Sparkles className="h-4 w-4" /> Generate storyboard
            </Button>
          ) : (
            <Button asChild>
              <Link to={`/projects/${project.id}/script`}>
                Open script <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          )
        }
      />
    );
  }

  const scenes = [...storyboard.scenes].sort((a, b) => a.order_index - b.order_index);
  const totalDuration = scenes.reduce((sum, scene) => sum + scene.duration_seconds, 0);
  const overTarget = totalDuration > project.duration_seconds + 3;

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= scenes.length) return;
    const reordered = [...scenes];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    reorderScenes.mutate(
      reordered.map((scene, order) => ({ id: scene.id, order_index: order })),
      { onError: (error) => toast.error("Could not reorder scenes", error.message) },
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="primary">{scenes.length} scenes</Badge>
          <Badge variant={overTarget ? "warning" : "default"}>
            <Clock className="h-3 w-3" /> {Math.round(totalDuration)}s / {project.duration_seconds}s
          </Badge>
          <StatusPill status={storyboard.approved ? "approved" : "draft"} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            className="h-9 w-auto"
            value={sceneCount}
            onChange={(event) => setSceneCount(Number(event.target.value))}
          >
            {[3, 4, 5, 6, 8, 10, 12].map((count) => (
              <option key={count} value={count}>
                {count} scenes
              </option>
            ))}
          </Select>
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              generateStoryboard.mutate(
                { scene_count: sceneCount, style },
                {
                  onSuccess: () => toast.success("Storyboard regenerated"),
                  onError: (error) => toast.error("Could not regenerate", error.message),
                },
              )
            }
            loading={generateStoryboard.isPending}
          >
            <RefreshCw className="h-3.5 w-3.5" /> Regenerate
          </Button>
          <Button
            size="sm"
            variant={storyboard.approved ? "success" : "primary"}
            onClick={() =>
              approveStoryboard.mutate(!storyboard.approved, {
                onSuccess: (updated) =>
                  toast.success(updated.approved ? "Storyboard approved" : "Approval removed"),
                onError: (error) => toast.error("Could not update approval", error.message),
              })
            }
            loading={approveStoryboard.isPending}
          >
            <Check className="h-3.5 w-3.5" />
            {storyboard.approved ? "Approved" : "Approve storyboard"}
          </Button>
        </div>
      </div>

      {overTarget ? (
        <div className="rounded-xl border border-warning/30 bg-warning/[0.07] p-3 text-sm text-warning">
          The board runs {Math.round(totalDuration - project.duration_seconds)}s longer than the
          target. Trim narration or shorten scenes before rendering.
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {scenes.map((scene, index) => (
          <motion.div key={scene.id} layout>
            <Card className="h-full">
              <div className="h-1 w-full rounded-t-2xl bg-gradient-to-r from-primary/70 via-fuchsia-500/50 to-accent/60" />
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 font-mono text-xs font-semibold text-primary">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <div className="min-w-0">
                    <CardTitle className="truncate">{scene.title || "Untitled scene"}</CardTitle>
                    <p className="text-[11px] text-muted-foreground">
                      {scene.duration_seconds}s · {scene.transition}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => move(index, -1)}
                    disabled={index === 0 || reorderScenes.isPending}
                    aria-label="Move scene up"
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => move(index, 1)}
                    disabled={index === scenes.length - 1 || reorderScenes.isPending}
                    aria-label="Move scene down"
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    Narration
                  </p>
                  <p className="mt-1 line-clamp-3 text-sm leading-relaxed text-foreground/90">
                    {scene.narration || "—"}
                  </p>
                </div>
                <div className="rounded-xl border border-border/60 bg-background/40 p-3">
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    Visual
                  </p>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                    {scene.visual_prompt || "—"}
                  </p>
                </div>
                <div className="flex items-center justify-between">
                  <Badge variant={scene.status === "approved" ? "success" : "default"}>
                    {scene.status}
                  </Badge>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={activeScene === scene.id}
                      onClick={() => {
                        setActiveScene(scene.id);
                        regenerateScene.mutate(
                          { sceneId: scene.id },
                          {
                            onSuccess: () => toast.success("Scene refreshed"),
                            onError: (error) => toast.error("Could not refresh scene", error.message),
                            onSettled: () => setActiveScene(null),
                          },
                        );
                      }}
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> Scene
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setEditing(scene)}>
                      <Pencil className="h-3.5 w-3.5" /> Edit
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {storyboard.approved ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-success/25 bg-success/[0.07] p-4">
          <div>
            <p className="text-sm font-medium text-success">Storyboard approved</p>
            <p className="text-xs text-muted-foreground">
              Ready to render a preview and final export.
            </p>
          </div>
          <Button asChild>
            <Link to={`/projects/${project.id}/render`}>
              <Film className="h-4 w-4" /> Open rendering <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      ) : null}

      <SceneModal
        scene={editing}
        onClose={() => setEditing(null)}
        onSave={(payload) => {
          if (!editing) return;
          updateScene.mutate(
            { sceneId: editing.id, payload },
            {
              onSuccess: () => {
                toast.success("Scene updated");
                setEditing(null);
              },
              onError: (error) => toast.error("Could not update scene", error.message),
            },
          );
        }}
        saving={updateScene.isPending}
      />
    </div>
  );
}

function SceneModal({
  scene,
  onClose,
  onSave,
  saving,
}: {
  scene: Scene | null;
  onClose: () => void;
  onSave: (payload: Partial<Scene>) => void;
  saving: boolean;
}) {
  const [title, setTitle] = useState("");
  const [narration, setNarration] = useState("");
  const [visualPrompt, setVisualPrompt] = useState("");
  const [duration, setDuration] = useState(5);
  const [transition, setTransition] = useState("fade");

  useEffect(() => {
    if (!scene) return;
    setTitle(scene.title);
    setNarration(scene.narration);
    setVisualPrompt(scene.visual_prompt);
    setDuration(scene.duration_seconds);
    setTransition(scene.transition);
  }, [scene]);

  return (
    <Modal
      open={Boolean(scene)}
      onClose={onClose}
      title="Edit scene"
      description="Adjust the narration, visual direction, and timing."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={saving}
            onClick={() =>
              onSave({
                title,
                narration,
                visual_prompt: visualPrompt,
                duration_seconds: duration,
                transition,
              })
            }
          >
            Save scene
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="scene-title">Title</Label>
          <Input id="scene-title" value={title} onChange={(event) => setTitle(event.target.value)} />
        </div>
        <div>
          <Label htmlFor="scene-narration">Narration</Label>
          <Textarea
            id="scene-narration"
            className="min-h-[100px]"
            value={narration}
            onChange={(event) => setNarration(event.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="scene-visual">Visual prompt</Label>
          <Textarea
            id="scene-visual"
            className="min-h-[80px]"
            value={visualPrompt}
            onChange={(event) => setVisualPrompt(event.target.value)}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="scene-duration">Duration (seconds)</Label>
            <Input
              id="scene-duration"
              type="number"
              min={1}
              max={30}
              step={0.5}
              value={duration}
              onChange={(event) => setDuration(Number(event.target.value))}
            />
          </div>
          <div>
            <Label htmlFor="scene-transition">Transition</Label>
            <Select
              id="scene-transition"
              value={transition}
              onChange={(event) => setTransition(event.target.value)}
            >
              {["fade", "cut", "slide", "zoom", "dissolve"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className={cn("rounded-xl border border-border/60 bg-card/40 p-3 text-xs text-muted-foreground")}>
          <Clapperboard className="mb-1 h-3.5 w-3.5 text-primary" />
          Visual prompts are stored for the renderer and future image generation. The Phase 1
          renderer uses typographic scene cards.
        </div>
      </div>
    </Modal>
  );
}
