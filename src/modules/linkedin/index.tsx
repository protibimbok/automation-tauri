import { Briefcase, FileText } from "lucide-react";

import { registerModule } from "@/lib/modular";
import { DEFAULT_TASK_CAPABILITIES, registerTaskType } from "@/lib/tasks";

import { POSTS_SCRAPER_TASK } from "./api";
import { PostScraperPage } from "./components/PostScraperPage";
import { PostsResultsPage } from "./components/PostsResultsPage";
import { PostsResultsView } from "./components/PostsResultsView";

registerModule({
  id: "linkedin",
  order: 1,
  menuFilter: (menu) => [
    ...menu,
    {
      label: "LinkedIn",
      type: ["sessionable"],
      platform: "linkedin",
      items: [
        {
          label: "Post Scraper",
          icon: FileText,
          path: "/platforms/linkedin/posts",
        },
      ],
    },
  ],
  routes: [
    {
      path: "platforms/linkedin/posts",
      element: <PostScraperPage />,
    },
    {
      path: "platforms/linkedin/posts/runs/:runId",
      element: <PostsResultsPage />,
    },
  ],
});

registerTaskType({
  key: POSTS_SCRAPER_TASK,
  platform: "linkedin",
  label: "LinkedIn Post Scraper",
  icon: Briefcase,
  capabilities: DEFAULT_TASK_CAPABILITIES,
  ResultsView: PostsResultsView,
  resultsPath: (runId) => `/platforms/linkedin/posts/runs/${runId}`,
});

export { LinkedinApi } from "./api";
export { PostScraperPage } from "./components/PostScraperPage";
export { PostsResultsView } from "./components/PostsResultsView";
