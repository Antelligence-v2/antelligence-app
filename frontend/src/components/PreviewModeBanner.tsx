import { Badge } from "@/components/ui/badge";
import { BUILD_INFO, IS_PREVIEW_MODE } from "@/lib/runtime";

export function PreviewModeBanner() {
  if (!IS_PREVIEW_MODE) {
    return null;
  }

  return (
    <div className="border-b border-amber-300 bg-amber-100/95 px-4 py-3 text-amber-950 shadow-sm dark:border-amber-700 dark:bg-amber-950/90 dark:text-amber-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="font-semibold">Antelligence preview mode</div>
          <div className="text-sm opacity-90">
            Frontend is exposed for monitoring only. Backend, transactions, proofs, and local infrastructure remain private.
          </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-500">Proof: Staged</Badge>
          <Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-500">Chain: Local</Badge>
        </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="secondary">host: {BUILD_INFO.previewHostname}</Badge>
          <Badge variant="secondary">build: {BUILD_INFO.buildLabel}</Badge>
          <Badge variant="secondary">git: {BUILD_INFO.gitSha}</Badge>
        </div>
      </div>
    </div>
  );
}
