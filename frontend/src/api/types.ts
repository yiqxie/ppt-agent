// 后端 API 类型定义（手动同步自 backend/app/schemas/schemas.py）

export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface UploadJob {
  id: string;
  original_filename: string;
  file_size: number;
  status: JobStatus;
  total_slides: number;
  processed_slides: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadJobList {
  items: UploadJob[];
  total: number;
}

export interface SlideStyleMeta {
  overall_style?: string;
  color_palette?: {
    primary?: string;
    secondary?: string;
    accent?: string;
    background?: string;
  };
  typography?: string;
  layout?: string;
  imagery?: string;
}

export interface Slide {
  id: string;
  job_id: string;
  slide_index: number;
  screenshot_url: string;
  prompt_url: string;
  prompt_text: string;
  title?: string | null;
  summary?: string | null;
  tags: string[];
  style_meta: SlideStyleMeta;
  created_at: string;
  updated_at: string;
}

export interface SlideList {
  items: Slide[];
  total: number;
}

export interface SlideUpdateInput {
  prompt_text?: string;
  title?: string;
  summary?: string;
  tags?: string[];
}

export interface PublicConfig {
  app_name: string;
  auth_enabled: boolean;
  tenant_id?: string | null;
  api_audience?: string | null;
  api_scope?: string | null;
}

export interface StagePromptConfig {
  system_prompt: string;
  user_prompt: string;
}

export interface SystemConfig {
  azure_foundry_url: string;
  default_model_deployment: string;
  model_candidates: string[];
  model_settings: {
    temperature?: number;
    max_tokens?: number;
    top_p?: number;
    [key: string]: unknown;
  };
  stage_prompts: Record<string, StagePromptConfig>;
  updated_at: string;
}

export interface SystemConfigUpdateIn {
  azure_foundry_url?: string;
  default_model_deployment?: string;
  model_candidates?: string[];
  model_settings?: {
    temperature?: number;
    max_tokens?: number;
    top_p?: number;
    [key: string]: unknown;
  };
  stage_prompts?: Record<string, StagePromptConfig>;
}

// WebSocket 进度消息
export type ProgressMessage =
  | {
      type: "job_update";
      job_id: string;
      status?: JobStatus;
      total_slides?: number;
      processed_slides?: number;
    }
  | {
      type: "slide_completed";
      job_id: string;
      processed_slides: number;
      total_slides: number;
      slide: Slide;
    }
  | {
      type: "done";
      job_id: string;
      status: JobStatus;
      total_slides: number;
      processed_slides: number;
    }
  | {
      type: "error";
      job_id: string;
      status?: JobStatus;
      error_message: string;
    };
