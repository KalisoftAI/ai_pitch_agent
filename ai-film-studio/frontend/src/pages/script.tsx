import { ArrowRight, Check, Circle, FileText, RefreshCw, Save, Sparkles, Wand2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label, Select, Textarea } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/progress";
import { StatusPill } from "@/components/ui/status-pill";
import type { ProjectContext } from "@/components/layout/project-layout";
import {
  useApproveScript,
  useGenerateScript,
  useRegenerateParagraph,
  useScript,
  useUpdateScript,
} from "@/hooks/queries";
import {
  estimateReadSeconds,
  estimateWordCount,
  parseParagraphs,
} from "@/lib/utils";
import { toast } from "@/stores/ui";

const TONES = ["confident", "friendly", "authoritative", "conversational", "energetic"];
const AUDIENCES = [
  "small business owners",
  "finance teams",
  "operations managers",
  "founders and CEOs",
  "new ERP users",
];

export function ScriptPage() {
  const { project } = useOutletContext<ProjectContext>();
  const [params, setParams] = useSearchParams();
  const { data: script, isLoading, isError } = useScript(project.id);
  const generateScript = useGenerateScript(project.id);
  const updateScript = useUpdateScript(project.id);
  const regenerateParagraph = useRegenerateParagraph(project.id);
  const approveScript = useApproveScript(project.id);

  const [content, setContent] = useState("");
  const [tone, setTone] = useState("confident");
  const [audience, setAudience] = useState("small business owners");
  const [instructions, setInstructions] = useState("");
  const [view, setView] = useState<"write" | "paragraphs">("write");
  const [activeParagraph, setActiveParagraph] = useState<number | null>(null);
  const autoStarted = useRef(false);

  useEffect(() => {
    if (script) setContent(script.content);
  }, [script]);

  useEffect(() => {
    if (!script && params.get("generate") === "1" && !autoStarted.current) {
      autoStarted.current = true;
      generateScript.mutate(
        { tone, audience, instructions },
        {
          onSuccess: () => {
            toast.success("First draft ready", "Edit it until it sounds like you.");
            params.delete("generate");
            setParams(params, { replace: true });
          },
          onError: (error) => toast.error("Generation failed", error.message),
        },
      );
    }
  }, [script, params, setParams, generateScript, tone, audience, instructions]);

  const paragraphs = useMemo(() => parseParagraphs(content), [content]);
  const dirty = Boolean(script && content !== script.content);
  const words = estimateWordCount(content);
  const readSeconds = estimateReadSeconds(content);

  if (isLoading) {
    return (
      <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        <Skeleton className="h-[420px]" />
        <Skeleton className="h-[300px]" />
      </div>
    );
  }

  const missingScript = isError || !script;

  if (missingScript) {
    return (
      <EmptyState
        icon={FileText}
        title="No script yet"
        description="Generate a first draft from the brief, then edit the narration. You can also write it yourself."
        action={
          <Button
            onClick={() =>
              generateScript.mutate(
                { tone, audience, instructions },
                {
                  onSuccess: () => toast.success("First draft ready"),
                  onError: (error) => toast.error("Generation failed", error.message),
                },
              )
            }
            loading={generateScript.isPending}
          >
            <Sparkles className="h-4 w-4" /> Generate script
          </Button>
        }
      />
    );
  }

  const save = () => {
    updateScript.mutate(content, {
      onSuccess: () => toast.success("Script saved"),
      onError: (error) => toast.error("Save failed", error.message),
    });
  };

  const regenerate = () => {
    generateScript.mutate(
      { tone, audience, instructions },
      {
        onSuccess: (updated) => {
          setContent(updated.content);
          toast.success("Script regenerated");
        },
        onError: (error) => toast.error("Regeneration failed", error.message),
      },
    );
  };

  const regenerateOne = (index: number) => {
    setActiveParagraph(index);
    regenerateParagraph.mutate(
      { index, instruction: instructions },
      {
        onSuccess: (updated) => {
          setContent(updated.content);
          toast.success(`Paragraph ${index + 1} refreshed`);
        },
        onError: (error) => toast.error("Could not refresh paragraph", error.message),
        onSettled: () => setActiveParagraph(null),
      },
    );
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
      <div className="space-y-6">
        <Card>
          <CardHeader className="flex-wrap">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle>Script</CardTitle>
                <Badge variant="default">v{script.version}</Badge>
                <StatusPill status={script.approved ? "approved" : "draft"} />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {words} words · about {readSeconds}s read · target {project.duration_seconds}s
              </p>
            </div>
            <Segmented
              className="w-full sm:w-auto"
              value={view}
              onChange={setView}
              items={[
                { value: "write", label: "Write", icon: FileText },
                { value: "paragraphs", label: "Paragraphs", icon: Wand2 },
              ]}
            />
          </CardHeader>
          <CardContent>
            {view === "write" ? (
              <Textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                className="min-h-[420px] font-mono text-[13px] leading-relaxed"
                spellCheck
              />
            ) : (
              <div className="space-y-3">
                {paragraphs.map((paragraph, index) => (
                  <div
                    key={`${index}-${paragraph.slice(0, 24)}`}
                    className="rounded-xl border border-border/70 bg-card/40 p-4"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                        Paragraph {index + 1}
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        loading={activeParagraph === index}
                        onClick={() => regenerateOne(index)}
                      >
                        <RefreshCw className="h-3.5 w-3.5" /> Regenerate
                      </Button>
                    </div>
                    <p className="text-sm leading-relaxed text-foreground/90">{paragraph}</p>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                {dirty ? "Unsaved changes" : "All changes saved"}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={save} disabled={!dirty} loading={updateScript.isPending}>
                  <Save className="h-4 w-4" /> Save
                </Button>
                <Button
                  variant="outline"
                  onClick={regenerate}
                  loading={generateScript.isPending}
                >
                  <RefreshCw className="h-4 w-4" /> Rewrite all
                </Button>
                <Button
                  variant={script.approved ? "success" : "primary"}
                  onClick={() =>
                    approveScript.mutate(!script.approved, {
                      onSuccess: (updated) =>
                        toast.success(updated.approved ? "Script approved" : "Approval removed"),
                      onError: (error) => toast.error("Could not update approval", error.message),
                    })
                  }
                  loading={approveScript.isPending}
                >
                  <Check className="h-4 w-4" />
                  {script.approved ? "Approved" : "Approve script"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {script.approved ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-success/25 bg-success/[0.07] p-4">
            <div>
              <p className="text-sm font-medium text-success">Script approved</p>
              <p className="text-xs text-muted-foreground">
                The storyboard can now inherit the narration.
              </p>
            </div>
            <Button asChild>
              <Link to={`/projects/${project.id}/storyboard`}>
                Build storyboard <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        ) : null}
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Generation settings</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Used for drafts and rewrites.
              </p>
            </div>
            <Sparkles className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="tone">Tone</Label>
              <Select id="tone" value={tone} onChange={(event) => setTone(event.target.value)}>
                {TONES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="audience">Audience</Label>
              <Select
                id="audience"
                value={audience}
                onChange={(event) => setAudience(event.target.value)}
              >
                {AUDIENCES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="instructions">Extra direction</Label>
              <Textarea
                id="instructions"
                className="min-h-[90px]"
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
                placeholder="Keep it under 120 words, use one concrete example..."
              />
            </div>
            <Button className="w-full" onClick={regenerate} loading={generateScript.isPending}>
              <Wand2 className="h-4 w-4" /> Generate new draft
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quality checks</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <CheckRow
              label="Opens with a clear hook"
              pass={/^(most|how|why|what|stop|imagine|here)/i.test(content.trim())}
            />
            <CheckRow label="Has a concrete example" pass={/\d|example|for instance/i.test(content)} />
            <CheckRow label="Ends with one action" pass={/start|try|use|write|review|ask|track/i.test(content.slice(-220))} />
            <CheckRow
              label={`Fits the ${project.duration_seconds}s target`}
              pass={readSeconds <= project.duration_seconds + 10}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CheckRow({ label, pass }: { label: string; pass: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {pass ? (
        <Check className="h-4 w-4 text-success" />
      ) : (
        <Circle className="h-4 w-4 text-muted-foreground/50" />
      )}
      <span className={pass ? "text-foreground" : "text-muted-foreground"}>{label}</span>
    </div>
  );
}
