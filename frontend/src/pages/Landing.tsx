import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { LogoMark } from "@/shell/Sidebar";
import { cn } from "@/lib/utils";

/** Front door: one photograph, the wordmark, one way in. */
export default function Landing() {
  const navigate = useNavigate();
  const [loaded, setLoaded] = useState(false);
  const enter = () => navigate("/worlds");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter") enter();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <main className="relative h-dvh w-full overflow-hidden bg-[#0b0f0a] text-white">
      <img
        src="/ant-frontpage.jpg"
        alt=""
        onLoad={() => setLoaded(true)}
        className={cn(
          "absolute inset-0 size-full object-cover object-[40%_60%] transition-opacity duration-700 ease-out",
          loaded ? "opacity-100" : "opacity-0",
        )}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/25 to-black/20" />
      <div className="absolute inset-0 bg-gradient-to-r from-black/45 via-transparent to-transparent" />

      <header className="absolute inset-x-0 top-0 flex items-center justify-between px-8 py-7 md:px-14">
        <LogoMark className="size-5 text-white/90" />
        <span className="hidden text-2xs uppercase tracking-[0.28em] text-white/60 sm:inline">Swarm research platform</span>
      </header>

      <div className="absolute inset-x-0 bottom-0 px-8 pb-14 md:px-14 md:pb-16">
        <div className="max-w-3xl space-y-6">
          <h1 className="text-[clamp(1.75rem,8.4vw,6rem)] font-extralight leading-none tracking-[0.12em] text-white md:text-[clamp(2.5rem,7.5vw,6rem)] md:tracking-[0.18em]">
            ANTELLIGENCE
          </h1>
          <p className="max-w-2xl text-[15px] leading-relaxed text-white/75">
            Many small agents, one shared trail. Coordination you can replay, verify and trust.
          </p>
          <button
            type="button"
            onClick={enter}
            className="group inline-flex h-11 items-center gap-3 rounded-full bg-white pl-6 pr-5 text-sm font-medium text-black transition-[background-color,transform] duration-base hover:bg-white/90 active:scale-[0.98]"
          >
            Enter
            <ArrowRight className="size-4 transition-transform duration-base group-hover:translate-x-0.5" />
          </button>
        </div>
      </div>

      <p className="absolute bottom-6 right-8 hidden text-2xs tracking-wide text-white/40 md:block md:right-14">
        Research model · not clinical guidance
      </p>
    </main>
  );
}
