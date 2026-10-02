import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = { children: ReactNode; resetKey: string };
type State = { error: Error | null };

/** Contains a crashing page so the shell (nav, palette) keeps working; resets on navigation. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Page crashed", error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-8">
        <div className="max-w-md space-y-4 text-center">
          <div className="mx-auto flex size-10 items-center justify-center rounded-full bg-danger/12 text-danger">
            <AlertTriangle className="size-5" />
          </div>
          <div className="space-y-1">
            <h2 className="text-[15px] font-semibold">This page hit an error</h2>
            <p className="text-sm text-muted-foreground">The rest of the app still works. Details are in the browser console.</p>
          </div>
          <pre className="max-h-32 overflow-auto rounded-md border bg-surface-2 p-3 text-left font-mono text-2xs text-muted-foreground">{error.message}</pre>
          <Button variant="outline" size="sm" onClick={() => this.setState({ error: null })}>
            <RotateCcw /> Try again
          </Button>
        </div>
      </div>
    );
  }
}
