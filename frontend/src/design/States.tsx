import type { ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function EmptyState({ icon, title, children, className }: { icon?: ReactNode; title: string; children?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-12 text-center", className)}>
      {icon && <div className="mb-1 text-muted-foreground [&_svg]:size-5">{icon}</div>}
      <p className="text-sm font-medium">{title}</p>
      {children && <div className="max-w-sm text-sm text-muted-foreground">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: Error | null; onRetry?: () => void; className?: string }) {
  return (
    <div className={cn("flex items-start gap-3 rounded-xl border border-danger/25 bg-danger/[0.06] p-4", className)}>
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-medium">Couldn't load this</p>
        <p className="text-sm text-muted-foreground">{error?.message ?? "Unknown error."}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCcw /> Retry
        </Button>
      )}
    </div>
  );
}
