import { RunsApi, type RunInfo } from "@/lib/runs";

import type { PostScraperParams } from "./types";

export const LINKEDIN_PLATFORM = "linkedin";
export const POSTS_SCRAPER_TASK = "linkedin.posts_scraper";

export class LinkedinApi {
  static startPostScrape(
    params: PostScraperParams,
    profileUrls: string[],
  ): Promise<RunInfo> {
    const inputs = profileUrls
      .map((url) => url.trim())
      .filter((url) => url.length > 0)
      .map((profile_url) => ({ profile_url }));

    return RunsApi.start(
      LINKEDIN_PLATFORM,
      POSTS_SCRAPER_TASK,
      params as unknown as Record<string, unknown>,
      inputs,
    );
  }

  static listRuns() {
    return RunsApi.list(LINKEDIN_PLATFORM);
  }
}
