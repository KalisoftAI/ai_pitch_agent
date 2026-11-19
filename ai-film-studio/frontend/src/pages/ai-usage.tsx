import {
  Activity,
  CheckCircle2,
  CircleDollarSign,
  Cloud,
  Cpu,
  FlaskConical,
  Plug,
  Sparkles,
  Wand2,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Progress, Skeleton } from "@/components/ui/progress";
import { StatCard } from "@/components/ui/stat-card";
import {
  useGenerateAI,
  useHealth,
  useModels,
  useSelectModel,
  useTestModel,
  useUsage,
} from "@/hooks/queries";
import { cn, formatCurrency, formatNumber, titleCase } from "@/lib/utils";
import { toast } from "@/stores/ui";
import type { ProviderStatus } from "@/types";

const TASKS = [
  { value: "script", label: "Script draft" },
  { value: "storyboard", label: "Storyboard" },
  { value: "paragraph", label: "Paragraph rewrite" },
  { value: "short-draft", label: "Short draft" },
];

export function AIUsagePage() {
  const { data: models, isLoading } = useModels();
  const { data: usage } = useUsage();
  const { data: health } = useHealth();
  const selectModel = useSelectModel();
  const testModel = useTestModel();
  const generate = useGenerateAI();

  const [results, setResults] = useState<Record<string, ProviderStatus>>({});
  const [testing, setTesting] = useState<string | null>(null);
  const [task, setTask] = useState("script");
  const [prompt, setPrompt] = useState(
    "Write a 30-second hook about why cash flow matters for a small business.",
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI control room"
        title="Models & usage"
        description="Development mode runs entirely on mock AI. Switch to a local Gemma server or a cloud key when you are ready."
        actions={
          <Badge variant={health?.mock_ai ? "warning" : "success"}>
            {health?.mock_ai ? "Mock AI active" : "Live AI active"}
          </Badge>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Requests"
          value={formatNumber(usage?.total_requests ?? 0)}
          hint="This month"
          icon={Activity}
        />
        <StatCard
          label="Tokens"
          value={formatNumber(usage?.total_tokens ?? 0)}
          hint="Prompt + completion"
          icon={Cpu}
          tone="accent"
        />
        <StatCard
          label="Estimated cost"
          value={formatCurrency(usage?.estimated_cost ?? 0)}
          hint={`Budget ${formatCurrency(usage?.budget_usd ?? 0)}`}
          icon={CircleDollarSign}
          tone="success"
        />
        <StatCard
          label="Selected model"
          value={<span className="text-base">{usage?.selected_model ?? "—"}</span>}
          hint={health?.mock_ai ? "Mock mode" : "Live mode"}
          icon={Wand2}
          tone="warning"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold">Model catalog</h2>
            <span className="text-xs text-muted-foreground">Pick the default for new tasks</span>
          </div>
          {isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-40" />
              ))}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {(models ?? []).map((model) => {
                const result = results[model.id];
                return (
                  <Card
                    key={model.id}
                    className={cn(
                      "panel-hover p-4",
                      model.selected && "border-primary/50 shadow-glow",
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div
                          className={cn(
                            "flex h-9 w-9 items-center justify-center rounded-xl",
                            model.local ? "bg-accent/12 text-accent" : "bg-primary/12 text-primary",
                          )}
                        >
                          {model.local ? <Cpu className="h-4 w-4" /> : <Cloud className="h-4 w-4" />}
                        </div>
                        <div>
                          <p className="text-sm font-medium">{model.label}</p>
                          <p className="text-[11px] text-muted-foreground">
                            {model.provider} · {model.task}
                          </p>
                        </div>
                      </div>
                      {model.selected ? <Badge variant="primary">Default</Badge> : null}
                    </div>
                    <p className="mt-3 min-h-[32px] text-xs leading-relaxed text-muted-foreground">
                      {model.description}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-1.5">
                      <Badge variant={model.local ? "accent" : "default"}>
                        {model.local ? "Local" : "Cloud"}
                      </Badge>
                      <Badge variant={model.configured ? "success" : "warning"}>
                        {model.configured ? "Configured" : "Needs setup"}
                      </Badge>
                      {result ? (
                        <Badge variant={result.reachable ? "success" : "danger"}>
                          {result.reachable ? `${result.latency_ms ?? 0}ms` : "Unreachable"}
                        </Badge>
                      ) : null}
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Button
                        size="sm"
                        variant={model.selected ? "secondary" : "primary"}
                        className="flex-1"
                        disabled={model.selected}
                        loading={selectModel.isPending}
                        onClick={() =>
                          selectModel.mutate(model.id, {
                            onSuccess: () => toast.success(`${model.label} selected`),
                            onError: (error) => toast.error("Could not select model", error.message),
                          })
                        }
                      >
                        {model.selected ? "Selected" : "Use model"}
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={testing === model.id}
                        onClick={() => {
                          setTesting(model.id);
                          testModel.mutate(model.id, {
                            onSuccess: (status) => {
                              setResults((current) => ({ ...current, [model.id]: status }));
                              toast[status.reachable ? "success" : "error"](
                                status.reachable ? "Connection OK" : "Connection failed",
                                status.message,
                              );
                            },
                            onError: (error) =>
                              toast.error("Test failed", error.message),
                            onSettled: () => setTesting(null),
                          });
                        }}
                      >
                        <Plug className="h-3.5 w-3.5" /> Test
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Budget</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  Local models are free. Cloud calls add cost.
                </p>
              </div>
              <CircleDollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <span className="font-display text-2xl font-semibold">
                  {formatCurrency(usage?.estimated_cost ?? 0)}
                </span>
                <span className="text-xs text-muted-foreground">
                  of {formatCurrency(usage?.budget_usd ?? 0)}
                </span>
              </div>
              <Progress
                className="mt-3"
                value={usage?.budget_used_pct ?? 0}
                tone={(usage?.budget_used_pct ?? 0) > 80 ? "warning" : "primary"}
              />
              <div className="mt-4 space-y-2">
                {(usage?.by_model ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">No AI calls recorded yet.</p>
                ) : (
                  usage?.by_model.map((bucket) => (
                    <div
                      key={`${bucket.provider}-${bucket.model}`}
                      className="flex items-center justify-between rounded-lg border border-border/60 bg-card/40 px-3 py-2 text-xs"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium">{bucket.model}</p>
                        <p className="text-muted-foreground">
                          {bucket.requests} calls · {formatNumber(bucket.total_tokens)} tokens
                        </p>
                      </div>
                      <span className="font-mono">{formatCurrency(bucket.estimated_cost)}</span>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Playground</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  Send one prompt to the selected model.
                </p>
              </div>
              <FlaskConical className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <Label htmlFor="task">Task</Label>
                <Select id="task" value={task} onChange={(event) => setTask(event.target.value)}>
                  {TASKS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="prompt">Prompt</Label>
                <Textarea
                  id="prompt"
                  className="min-h-[110px]"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                />
              </div>
              <Button
                className="w-full"
                loading={generate.isPending}
                onClick={() =>
                  generate.mutate(
                    { prompt, task, max_tokens: 400 },
                    {
                      onSuccess: () => toast.success("Response received"),
                      onError: (error) => toast.error("Generation failed", error.message),
                    },
                  )
                }
              >
                <Sparkles className="h-4 w-4" /> Run prompt
              </Button>
              {generate.data ? (
                <div className="rounded-xl border border-border/70 bg-background/50 p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-1.5">
                    <Badge variant="primary">{generate.data.provider}</Badge>
                    <Badge variant="default">{generate.data.model}</Badge>
                    <Badge variant="accent">{generate.data.total_tokens} tokens</Badge>
                    <Badge variant="default">{formatCurrency(generate.data.estimated_cost)}</Badge>
                    {generate.data.cached ? <Badge variant="warning">Cached</Badge> : null}
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{generate.data.text}</p>
                </div>
              ) : null}
              {generate.error ? (
                <div className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger/[0.07] p-3 text-xs text-danger">
                  <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {generate.error.message}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <div className="rounded-2xl border border-primary/20 bg-primary/[0.07] p-5">
            <div className="flex items-center gap-2 text-xs font-medium text-primary">
              <CheckCircle2 className="h-3.5 w-3.5" /> Local model note
            </div>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              {titleCase(health?.mode ?? "development")} mode. The 12B Gemma model needs roughly
              6.5 GB of RAM and runs on CPU. On an 8 GB machine, prefer short prompts and 1024
              context, or use the mock model while designing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
