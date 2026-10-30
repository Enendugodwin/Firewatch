import { useEffect } from "react";
import { Outlet } from "react-router-dom";

import { useUiStore } from "@/store/ui";
import { CommandPalette } from "./CommandPalette";
import { OrbitalField } from "./OrbitalField";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";
import { TopBar } from "./TopBar";

/**
 * Application shell: full-bleed orbital grid field, glass sidebar, sticky
 * header, scrolling workspace and a persistent status bar.
 */
export function AppShell() {
  const theme = useUiStore((state) => state.theme);
  const setCommandOpen = useUiStore((state) => state.setCommandOpen);
  const setSidebarOpen = useUiStore((state) => state.setSidebarOpen);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("theme-dark", "theme-contrast");
    root.classList.add(theme === "contrast" ? "theme-contrast" : "theme-dark");
  }, [theme]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable === true;

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
        return;
      }
      if (!typing && event.key === "/") {
        event.preventDefault();
        setCommandOpen(true);
        return;
      }
      if (event.key === "Escape") setSidebarOpen(false);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setCommandOpen, setSidebarOpen]);

  return (
    <div className="relative flex min-h-screen bg-canvas">
      <OrbitalField />

      <a
        href="#workspace"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[100] focus:rounded-full focus:bg-[#FAFAFA] focus:px-4 focus:py-2 focus:text-xs focus:text-[#05070F]"
      >
        Skip to workspace
      </a>

      <Sidebar />

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="workspace" className="min-w-0 flex-1">
          <div className="mx-auto w-full max-w-[1680px] px-3 py-5 sm:px-[22px] sm:py-6">
            <Outlet />
          </div>
        </main>
        <StatusBar />
      </div>

      <CommandPalette />
    </div>
  );
}
