import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Clapperboard,
  Lightbulb,
  MonitorPlay,
  Palette,
  Sparkles,
  Timer,
  Wand2,
} from "lucide-react";
import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Progress, Skeleton } from "@/components/ui/progress";
import { Segmented } from "@/components/ui/segmented";
import { useCategories, useCreateProject, useTopicSuggestions } from "@/hooks/queries";
import {
  ASPECT_RATIOS,
  CATEGORY_META,
  TEMPLATES,
  VISUAL_STYLES,
  cn,
  titleCase,
} from "@/lib/utils";
import { toast } from "@/stores/ui";
import { useWizardStore } from "@/stores/wizard";
import type { Category } from "@/types";

const STEPS = [
  { label: "Category", icon: Clapperboard },
  { label: "Topic", icon: Lightbulb },
  { label: "Look", icon: Palette },
  { label: "Format", icon: Timer },
  { label: "Review", icon: Sparkles },
];

export function WizardPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const wizard = useWizardStore();
  const { data: categories, isLoading } = useCategories();
  const { data: suggestions } = useTopicSuggestions(wizard.category ?? undefined);
  const createProject = useCreateProject();

  useEffect(() => {
    const preset = params.get("category") as Category | null;
    if (preset && !wizard.category) wizard.start(preset);
  }, [params, wizard]);

  const canContinue =
    (wizard.step === 0 && Boolean(wizard.category)) ||
    (wizard.step === 1 && wizard.topic.trim().length > 2) ||
    wizard.step === 2 ||
    wizard.step === 3 ||
    (wizard.step === 4 && Boolean(wizard.category) && wizard.topic.trim().length > 2);

  const finish = () => {
    if (!wizard.category) return;
    const title = wizard.title.trim() || wizard.topic.trim();
    createProject.mutate(
      {
        title,
        category: wizard.category,
        topic: wizard.topic.trim(),
        description: wizard.description.trim(),
        visual_style: wizard.visualStyle,
        template: wizard.template,
        duration_seconds: wizard.duration,
        aspect_ratio: wizard.aspect,
      },
      {
        onSuccess: (project) => {
          toast.success("Project created", "Now shape the script.");
          wizard.reset();
          navigate(`/projects/${project.id}/script?generate=1`);
        },
        onError: (error) => toast.error("Could not create project", error.message),
      },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Create"
        title="Plan a focused video"
        description="Choose the format, pick a sharp topic, and set the visual language. You can refine everything later."
        actions={
          <Button variant="ghost" onClick={() => navigate("/projects")}>
            Cancel
          </Button>
        }
      />

      <div className="panel p-4">
        <div className="flex items-center justify-between gap-2">
          {STEPS.map((step, index) => {
            const active = index === wizard.step;
            const done = index < wizard.step;
            return (
              <div key={step.label} className="flex flex-1 items-center gap-2">
                <div
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border text-sm transition",
                    active
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : done
                        ? "border-success/40 bg-success/10 text-success"
                        : "border-border bg-card text-muted-foreground",
                  )}
                >
                  {done ? <Check className="h-4 w-4" /> : <step.icon className="h-4 w-4" />}
                </div>
                <span
                  className={cn(
                    "hidden text-xs font-medium sm:block",
                    active ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {step.label}
                </span>
                {index < STEPS.length - 1 ? (
                  <div className="hidden h-px flex-1 bg-border sm:block" />
                ) : null}
              </div>
            );
          })}
        </div>
        <Progress className="mt-4" value={((wizard.step + 1) / STEPS.length) * 100} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        <div className="panel min-h-[420px] p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={wizard.step}
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -16 }}
              transition={{ duration: 0.2 }}
            >
              {wizard.step === 0 ? (
                <div>
                  <h2 className="font-display text-xl font-semibold">What kind of video?</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Each format has its own pacing, examples, and visual defaults.
                  </p>
                  {isLoading ? (
                    <div className="mt-6 grid gap-3 md:grid-cols-3">
                      {Array.from({ length: 3 }).map((_, index) => (
                        <Skeleton key={index} className="h-40" />
                      ))}
                    </div>
                  ) : (
                    <div className="mt-6 grid gap-3 md:grid-cols-3">
                      {(categories ?? []).map((category) => {
                        const meta = CATEGORY_META[category.id];
                        const active = wizard.category === category.id;
                        return (
                          <button
                            key={category.id}
                            onClick={() => wizard.start(category.id)}
                            className={cn(
                              "relative overflow-hidden rounded-2xl border p-5 text-left transition",
                              active
                                ? "border-primary/60 bg-primary/10 shadow-glow"
                                : "border-border bg-card/60 hover:border-primary/30 hover:bg-card",
                            )}
                          >
                            <div
                              className={cn(
                                "absolute inset-0 bg-gradient-to-br opacity-50",
                                meta?.accent,
                              )}
                            />
                            <div className="relative">
                              <Badge variant={active ? "primary" : "default"}>
                                {meta?.short ?? titleCase(category.id)}
                              </Badge>
                              <h3 className="mt-3 font-display text-sm font-semibold leading-snug">
                                {category.label}
                              </h3>
                              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                                {meta?.description ?? category.description}
                              </p>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : null}

              {wizard.step === 1 ? (
                <div>
                  <h2 className="font-display text-xl font-semibold">Pick a sharp topic</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    One idea, one outcome. Choose a suggestion or write your own.
                  </p>
                  <div className="mt-5 grid gap-2">
                    {(suggestions ?? []).map((suggestion) => {
                      const active = wizard.topic === suggestion.title;
                      return (
                        <button
                          key={suggestion.title}
                          onClick={() =>
                            wizard.set({
                              topic: suggestion.title,
                              description: suggestion.description,
                            })
                          }
                          className={cn(
                            "rounded-xl border p-3.5 text-left transition",
                            active
                              ? "border-primary/50 bg-primary/10"
                              : "border-border bg-card/50 hover:border-primary/30 hover:bg-card",
                          )}
                        >
                          <p className="text-sm font-medium">{suggestion.title}</p>
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {suggestion.description}
                          </p>
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-5 space-y-3">
                    <div>
                      <Label htmlFor="topic">Or write your own topic</Label>
                      <Input
                        id="topic"
                        value={wizard.topic}
                        onChange={(event) =>
                          wizard.set({ topic: event.target.value, title: "" })
                        }
                        placeholder="e.g. How to cut invoice delays in half"
                      />
                    </div>
                    <div>
                      <Label htmlFor="description">Angle (optional)</Label>
                      <Textarea
                        id="description"
                        className="min-h-[80px]"
                        value={wizard.description}
                        onChange={(event) => wizard.set({ description: event.target.value })}
                        placeholder="What should the viewer understand or do after watching?"
                      />
                    </div>
                  </div>
                </div>
              ) : null}

              {wizard.step === 2 ? (
                <div>
                  <h2 className="font-display text-xl font-semibold">Set the visual language</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    These choices shape prompts, pacing, and the render preview.
                  </p>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    {VISUAL_STYLES.map((style) => {
                      const active = wizard.visualStyle === style.id;
                      return (
                        <button
                          key={style.id}
                          onClick={() => wizard.set({ visualStyle: style.id })}
                          className={cn(
                            "rounded-xl border p-4 text-left transition",
                            active
                              ? "border-primary/50 bg-primary/10"
                              : "border-border bg-card/50 hover:border-primary/30 hover:bg-card",
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-medium">{style.label}</p>
                            {active ? <Check className="h-4 w-4 text-primary" /> : null}
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {style.description}
                          </p>
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-6">
                    <Label>Story template</Label>
                    <div className="mt-2 grid gap-2 sm:grid-cols-3">
                      {TEMPLATES.map((template) => {
                        const active = wizard.template === template.id;
                        return (
                          <button
                            key={template.id}
                            onClick={() => wizard.set({ template: template.id })}
                            className={cn(
                              "rounded-xl border p-3 text-left transition",
                              active
                                ? "border-primary/50 bg-primary/10"
                                : "border-border bg-card/50 hover:border-primary/30",
                            )}
                          >
                            <p className="text-sm font-medium">{template.label}</p>
                            <p className="mt-1 text-[11px] text-muted-foreground">
                              {template.description}
                            </p>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : null}

              {wizard.step === 3 ? (
                <div>
                  <h2 className="font-display text-xl font-semibold">Shape the format</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Short enough to hold attention, long enough to land the idea.
                  </p>
                  <div className="mt-5">
                    <div className="flex items-center justify-between">
                      <Label>Duration</Label>
                      <span className="text-sm font-medium">{wizard.duration}s</span>
                    </div>
                    <input
                      type="range"
                      min={15}
                      max={180}
                      step={5}
                      value={wizard.duration}
                      onChange={(event) =>
                        wizard.set({ duration: Number(event.target.value) })
                      }
                      className="mt-2 w-full accent-[hsl(var(--primary))]"
                    />
                    <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
                      <span>15s</span>
                      <span>90s</span>
                      <span>180s</span>
                    </div>
                  </div>
                  <div className="mt-6">
                    <Label>Aspect ratio</Label>
                    <div className="mt-2">
                      <Segmented
                        value={wizard.aspect}
                        onChange={(aspect) => wizard.set({ aspect })}
                        items={ASPECT_RATIOS.map((ratio) => ({ value: ratio, label: ratio }))}
                      />
                    </div>
                  </div>
                  <div className="mt-6 grid gap-3 sm:grid-cols-3">
                    {[
                      { icon: MonitorPlay, label: "Preview", value: "640 × 360" },
                      { icon: Wand2, label: "Export", value: "1280 × 720" },
                      { icon: Clapperboard, label: "Scenes", value: `${Math.max(3, Math.round(wizard.duration / 8))}` },
                    ].map((item) => (
                      <div key={item.label} className="glass rounded-xl p-3">
                        <item.icon className="h-4 w-4 text-primary" />
                        <p className="mt-2 text-[11px] uppercase tracking-wider text-muted-foreground">
                          {item.label}
                        </p>
                        <p className="text-sm font-medium">{item.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {wizard.step === 4 ? (
                <div>
                  <h2 className="font-display text-xl font-semibold">Review the brief</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Name the project, then the studio will draft the script.
                  </p>
                  <div className="mt-5">
                    <Label htmlFor="title">Project title</Label>
                    <Input
                      id="title"
                      value={wizard.title}
                      onChange={(event) => wizard.set({ title: event.target.value })}
                      placeholder={wizard.topic || "Give this video a name"}
                    />
                  </div>
                  <dl className="mt-6 grid gap-3 sm:grid-cols-2">
                    {[
                      ["Category", CATEGORY_META[wizard.category ?? ""]?.label ?? "—"],
                      ["Topic", wizard.topic || "—"],
                      ["Visual style", titleCase(wizard.visualStyle)],
                      ["Template", titleCase(wizard.template)],
                      ["Duration", `${wizard.duration} seconds`],
                      ["Aspect", wizard.aspect],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-xl border border-border/70 bg-card/50 p-3">
                        <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                          {label}
                        </dt>
                        <dd className="mt-0.5 text-sm font-medium">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ) : null}
            </motion.div>
          </AnimatePresence>

          <div className="mt-8 flex items-center justify-between border-t border-border/70 pt-5">
            <Button
              variant="ghost"
              onClick={wizard.back}
              disabled={wizard.step === 0}
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
            {wizard.step < STEPS.length - 1 ? (
              <Button onClick={wizard.next} disabled={!canContinue}>
                Continue <ArrowRight className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={finish}
                disabled={!canContinue}
                loading={createProject.isPending}
              >
                Create & draft script <Sparkles className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        <aside className="space-y-4">
          <div className="panel p-5">
            <h3 className="font-display text-sm font-semibold">Live brief</h3>
            <div className="mt-4 space-y-3 text-sm">
              <div>
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Category
                </p>
                <p className="mt-0.5">
                  {wizard.category
                    ? CATEGORY_META[wizard.category]?.label
                    : "Choose a format"}
                </p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Topic
                </p>
                <p className="mt-0.5 text-muted-foreground">
                  {wizard.topic || "Pick or write a topic"}
                </p>
              </div>
              <div className="flex gap-2">
                <Badge variant="default">{wizard.duration}s</Badge>
                <Badge variant="default">{wizard.aspect}</Badge>
                <Badge variant="primary">{titleCase(wizard.visualStyle)}</Badge>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-primary/20 bg-primary/[0.07] p-5">
            <div className="flex items-center gap-2 text-xs font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" /> Studio tip
            </div>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Specific beats clever. A topic with a number, a mistake, or a concrete outcome
              usually produces a stronger script and storyboard.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
