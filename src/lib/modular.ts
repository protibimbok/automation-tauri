import type { LucideIcon } from "lucide-react";
import type { RouteObject } from "react-router-dom";

export interface MenuItem {
  label: string;
  icon: LucideIcon;
  path: string;
}

export interface MenuGroup {
  label: string;
  /** Hints for modules that filter or extend menu groups. */
  type?: string[];
  /** Platform slug for sessionable groups (e.g. linkedin, facebook). */
  platform?: string;
  items: MenuItem[];
}

export type MenuFilter = (menu: MenuGroup[]) => MenuGroup[];

export interface ModuleRegistration {
  id: string;
  /** Non-negative: from the start (0 = first). Negative: from the end (-1 = last). */
  order?: number;
  menuFilter?: MenuFilter;
  routes?: RouteObject[];
}

const modules: ModuleRegistration[] = [];

export function registerModule(registration: ModuleRegistration): void {
  if (modules.some((module) => module.id === registration.id)) {
    console.warn(
      `[modular] module "${registration.id}" is already registered`,
    );
    return;
  }
  modules.push(registration);
}

export function getModules(): readonly ModuleRegistration[] {
  return getOrderedModules();
}

function getOrderedModules(): ModuleRegistration[] {
  const indexed = modules.map((module, registrationIndex) => ({
    module,
    order: module.order ?? 0,
    registrationIndex,
  }));

  const fromStart = indexed
    .filter((entry) => entry.order >= 0)
    .sort(
      (a, b) =>
        a.order - b.order || a.registrationIndex - b.registrationIndex,
    );

  const fromEnd = indexed
    .filter((entry) => entry.order < 0)
    .sort(
      (a, b) =>
        b.order - a.order || a.registrationIndex - b.registrationIndex,
    );

  return [...fromStart, ...fromEnd].map((entry) => entry.module);
}

export function getMenuGroups(): MenuGroup[] {
  let menu: MenuGroup[] = [];

  for (const mod of getOrderedModules()) {
    if (mod.menuFilter) {
      menu = mod.menuFilter(menu);
    }
  }

  return menu;
}

export function getRoutes(): RouteObject[] {
  return getOrderedModules().flatMap((mod) => mod.routes ?? []);
}
