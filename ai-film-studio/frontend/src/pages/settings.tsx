import {
  BookOpen,
  CheckCircle2,
  Cpu,
  ExternalLink,
  HardDrive,
  Monitor,
  Server,
  Terminal,
  Video,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/progress";
import { useHealth, useModels } from "@/hooks/queries";
import { titleCase } from "@/lib/utils";

const COMMANDS = [
  {
    label: "Backend",
    command: "cd ai-film-studio\\backend\n..\\.venv\\Scripts\\python -m uvicorn app.main:app --reload --port 8000",
  },
  {
    label: "Frontend",
    command: "cd ai-film-studio\\frontend\nnpm run dev",
  },
  {
    label: "Local Gemma",
    command: "cd ai-film-studio\npowershell -ExecutionPolicy Bypass -File scripts\\start_gemma.ps1",
  },
];

export function SettingsPage() {
  const { data: health, isLoading, isError } = useHealth();
  const { data: models } = useModels();
  const selected = models?.find((model) => model.selected);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Settings"
        title="Studio configuration"
        description="Local endpoints, storage, and the exact commands to run the studio."
      />

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : isError || !health ? (
        <div className="panel flex items-center gap-3 p-5 text-sm text-danger">
          <XCircle className="h-5 w-5" />
          Backend is unreachable. Start the FastAPI server and refresh.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="panel p-4">
            <Server className="h-4 w-4 text-primary" />
            <p className="mt-2 text-[11px] uppercase tracking-wider text-muted-foreground">
              Mode
            </p>
            <p className="text-sm font-medium">{titleCase(health.mode)}</p>
            <Badge className="mt-2" variant={health.mock_ai ? "warning" : "success"}>
              {health.mock_ai ? "Mock AI" : "Live AI"}
            </Badge>
          </div>
          <div className="panel p-4">
            <Video className="h-4 w-4 text-accent" />
            <p className="mt-2 text-[11px] uppercase tracking-wider text-muted-foreground">
              Renderer
            </p>
            <p className="text-sm font-medium">{titleCase(health.render_mode)}</p>
            <Badge className="mt-2" variant={health.ffmpeg_available ? "success" : "danger"}>
              {health.ffmpeg_available ? "FFmpeg ready" : "FFmpeg missing"}
            </Badge>
          </div>
          <div className="panel p-4">
            <Cpu className="h-4 w-4 text-warning" />
            <p className="mt-2 text-[11px] uppercase tracking-wider text-muted-foreground">
              Default model
            </p>
            <p className="truncate text-sm font-medium">{selected?.label ?? "—"}</p>
            <Badge className="mt-2" variant={selected?.local ? "accent" : "default"}>
              {selected?.local ? "Local" : "Cloud"}
            </Badge>
          </div>
          <div className="panel p-4">
            <HardDrive className="h-4 w-4 text-success" />
            <p className="mt-2 text-[11px] uppercase tracking-wider text-muted-foreground">
              Storage
            </p>
            <p className="truncate text-sm font-medium" title={health.storage}>
              {health.storage}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Run the studio</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Three terminals: API, UI, and optionally the local model.
              </p>
            </div>
            <Terminal className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-3">
            {COMMANDS.map((item) => (
              <div key={item.label}>
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  {item.label}
                </p>
                <pre className="overflow-x-auto rounded-xl border border-border/70 bg-black/50 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
                  {item.command}
                </pre>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Endpoints</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">Local services and docs.</p>
              </div>
              <Monitor className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Row label="Frontend" value="http://localhost:5173" />
              <Row label="API" value="http://127.0.0.1:8000" />
              <Row label="Swagger" value="http://127.0.0.1:8000/docs" link />
              <Row label="Gemma base URL" value={health?.gemma_base_url ?? "—"} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Phase 1 boundaries</CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  What this local studio deliberately does not do yet.
                </p>
              </div>
              <BookOpen className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Check ok label="Local scripts, storyboards, and FFmpeg renders" />
              <Check ok label="Mock AI by default, live providers optional" />
              <Check ok label="Assets stored under local storage/" />
              <Check label="No cloud deployment or GCP resources" />
              <Check label="No Lemo-Opuscar engine rebuild (adapter only)" />
            </CardContent>
          </Card>

          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
                Open API docs <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </Button>
            <Button asChild variant="ghost">
              <a href="https://github.com/ggml-org/llama.cpp" target="_blank" rel="noreferrer">
                llama.cpp <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, link }: { label: string; value: string; link?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-card/40 px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      {link ? (
        <a
          href={value}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline"
        >
          {value} <ExternalLink className="h-3 w-3" />
        </a>
      ) : (
        <span className="truncate font-mono text-xs">{value}</span>
      )}
    </div>
  );
}

function Check({ ok, label }: { ok?: boolean; label: string }) {
  return (
    <div className="flex items-start gap-2">
      {ok ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
      ) : (
        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/50" />
      )}
      <span className={ok ? "text-foreground" : "text-muted-foreground"}>{label}</span>
    </div>
  );
}
