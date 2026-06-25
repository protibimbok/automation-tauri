export type LinkedInMedia = {
  kind: string;
  url: string;
  poster?: string;
  label?: string;
};

export type LinkedInPost = {
  post_id: string;
  text: string;
  posted_at: string;
  author_name: string;
  author_url: string;
  post_url: string;
  like_count: number | null;
  comment_count: number | null;
  repost_count: number | null;
  impression_count: number | null;
  media_urls: LinkedInMedia[];
  matched?: boolean;
};

export type PostScraperParams = {
  session_id: string;
  headless: boolean;
  post_count?: number | null;
  start_from?: number | null;
  post_matcher?: string | null;
};

export type ProfileInput = {
  profile_url: string;
};
