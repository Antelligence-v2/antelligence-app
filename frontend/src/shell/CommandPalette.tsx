import { Command } from "cmdk";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowRight, Moon, Search, Sun } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { Kbd } from "@/design/Kbd";
import { useThemeToggle } from "@/design/theme";
import { LEGACY_NAV, PRIMARY_NAV, type NavItem } from "./nav";

function Item({ onSelect, icon, label, hint, value }: {
  onSelect: () => void;
  icon: ReactNode;
  label: string;
  hint?: ReactNode;
  value: string;
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="group flex h-10 cursor-pointer select-none items-center gap-3 rounded-md px-2.5 text-sm text-muted-foreground outline-none transition-colors data-[selected=true]:bg-accent data-[selected=true]:text-foreground"
    >
      <span className="flex size-4 items-center justify-center [&_svg]:size-4">{icon}</span>
      <span className="flex-1 truncate">{label}</span>
      {hint}
      <ArrowRight className="size-3.5 opacity-0 transition-opacity group-data-[selected=true]:opacity-60" />
    </Command.Item>
  );
}

function Group({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className="px-1.5 pb-1.5 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1.5 [&_[cmdk-group-heading]]:pt-2.5 [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.08em] [&_[cmdk-group-heading]]:text-muted-foreground"
    >
      {children}
    </Command.Group>
  );
}

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate();
  const { theme, toggle } = useThemeToggle();
  const run = (action: () => void) => {
    onOpenChange(false);
    action();
  };
  const navItem = (item: NavItem) => (
    <Item
      key={item.to}
      value={`${item.label} ${item.description}`}
      icon={<item.icon />}
      label={item.label}
      hint={item.chord ? <span className="flex gap-1">{item.chord.split(" ").map((k) => <Kbd key={k}>{k}</Kbd>)}</span> : undefined}
      onSelect={() => run(() => navigate(item.to))}
    />
  );

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-background/60 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-[18vh] z-50 w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-e3 duration-150 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-[0.98] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-[0.98]"
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Command loop>
            <div className="flex items-center gap-2.5 border-b px-4">
              <Search className="size-4 shrink-0 text-muted-foreground" />
              <Command.Input
                autoFocus
                placeholder="Go to, or run a command…"
                className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <Kbd>esc</Kbd>
            </div>
            <Command.List className="max-h-[min(420px,60vh)] overflow-y-auto overscroll-contain py-1">
              <Command.Empty className="px-4 py-8 text-center text-sm text-muted-foreground">No matches.</Command.Empty>
              <Group heading="Navigate">{PRIMARY_NAV.map(navItem)}</Group>
              <Group heading="Legacy">{LEGACY_NAV.map(navItem)}</Group>
              <Group heading="Preferences">
                <Item
                  value="toggle theme dark light"
                  icon={theme === "dark" ? <Sun /> : <Moon />}
                  label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
                  onSelect={() => run(toggle)}
                />
              </Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
