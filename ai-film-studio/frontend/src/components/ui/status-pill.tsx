import { Badge, type BadgeProps } from "@/components/ui/badge";
import { titleCase } from "@/lib/utils";

const STATUS_VARIANTS: Record<string, BadgeProps["variant"]> = {
  draft: "default",
  scripting: "primary",
  storyboard: "primary",
  storyboarding: "primary",
  ready: "accent",
  rendering: "warning",
  queued: "warning",
  running: "warning",
  rendered: "success",
  completed: "success",
  approved: "success",
  failed: "danger",
  cancelled: "danger",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <Badge variant={STATUS_VARIANTS[status] ?? "default"}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {titleCase(status)}
    </Badge>
  );
}
