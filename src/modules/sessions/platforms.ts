import type { LucideIcon } from "lucide-react";
import { Briefcase, MessageCircle, Users } from "lucide-react";

export type PlatformSlug = "linkedin" | "facebook" | "twitter";

export type PlatformDefinition = {
  slug: PlatformSlug;
  name: string;
  icon: LucideIcon;
  checkUrl: string;
};

export const platforms: PlatformDefinition[] = [
  {
    slug: "linkedin",
    name: "LinkedIn",
    icon: Briefcase,
    checkUrl: "https://www.linkedin.com/feed/",
  },
  {
    slug: "facebook",
    name: "Facebook",
    icon: Users,
    checkUrl: "https://www.facebook.com/",
  },
  {
    slug: "twitter",
    name: "X (Twitter)",
    icon: MessageCircle,
    checkUrl: "https://x.com/home",
  },
];

export const sessionPlatforms = platforms;

export function findPlatform(slug: string): PlatformDefinition | undefined {
  return platforms.find((platform) => platform.slug === slug);
}

export function sessionsPath(platform: PlatformSlug): string {
  return `/platforms/${platform}/sessions`;
}
