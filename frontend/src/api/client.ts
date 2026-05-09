import axios, { AxiosError, type AxiosInstance } from "axios";
import type {
  PublicConfig,
  Slide,
  SlideList,
  SystemConfig,
  SystemConfigUpdateIn,
  SlideUpdateInput,
  UploadJob,
  UploadJobList,
} from "./types";

// 全局 token 提供者（由 auth 模块在 MSAL 拿到 token 后注入）
let tokenProvider: (() => Promise<string | null>) | null = null;
export function setApiTokenProvider(fn: (() => Promise<string | null>) | null) {
  tokenProvider = fn;
}

// 在生产部署中，前后端可能同源，或后端通过反向代理映射到 /api
// 因此默认使用相对路径，浏览器自动用当前 origin
const baseURL = "";

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 120_000,
});

apiClient.interceptors.request.use(async (config) => {
  if (tokenProvider) {
    const token = await tokenProvider();
    if (token) {
      config.headers.set("Authorization", `Bearer ${token}`);
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (resp) => resp,
  (err: AxiosError) => {
    // 统一格式化错误，方便上层显示
    const detail =
      (err.response?.data as { detail?: string } | undefined)?.detail ||
      err.message ||
      "请求失败";
    return Promise.reject(new Error(detail));
  },
);

// ============= 公共 =============
export async function fetchPublicConfig(): Promise<PublicConfig> {
  const { data } = await apiClient.get<PublicConfig>("/api/config");
  return data;
}

// ============= Job =============
export async function uploadPptFiles(files: File[], onProgress?: (pct: number) => void) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));
  const { data } = await apiClient.post<{ jobs: UploadJob[] }>(
    "/api/jobs/upload",
    fd,
    {
      onUploadProgress(e) {
        if (e.total && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      },
      headers: { "Content-Type": "multipart/form-data" },
    },
  );
  return data.jobs;
}

export async function listJobs(params: {
  status?: string;
  skip?: number;
  limit?: number;
} = {}): Promise<UploadJobList> {
  const { data } = await apiClient.get<UploadJobList>("/api/jobs", { params });
  return data;
}

export async function getJob(jobId: string): Promise<UploadJob> {
  const { data } = await apiClient.get<UploadJob>(`/api/jobs/${jobId}`);
  return data;
}

export async function startJob(jobId: string): Promise<UploadJob> {
  const { data } = await apiClient.post<UploadJob>(`/api/jobs/${jobId}/start`);
  return data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiClient.delete(`/api/jobs/${jobId}`);
}

// ============= Slide =============
export async function listSlides(params: {
  job_id?: string;
  keyword?: string;
  tag?: string;
  skip?: number;
  limit?: number;
} = {}): Promise<SlideList> {
  const { data } = await apiClient.get<SlideList>("/api/slides", { params });
  return data;
}

export async function listSlideIds(params: {
  job_id?: string;
  keyword?: string;
  tag?: string;
  limit?: number;
} = {}): Promise<string[]> {
  const { data } = await apiClient.get<{ ids: string[] }>("/api/slides/query/ids", { params });
  return data.ids;
}

export async function getSlide(slideId: string): Promise<Slide> {
  const { data } = await apiClient.get<Slide>(`/api/slides/${slideId}`);
  return data;
}

export async function updateSlide(slideId: string, payload: SlideUpdateInput): Promise<Slide> {
  const { data } = await apiClient.put<Slide>(`/api/slides/${slideId}`, payload);
  return data;
}

export async function batchDeleteSlides(slideIds: string[]): Promise<{ deleted: number }> {
  const { data } = await apiClient.post<{ deleted: number }>(
    "/api/slides/batch-delete",
    { slide_ids: slideIds },
  );
  return data;
}

export async function listAllTags(): Promise<string[]> {
  const { data } = await apiClient.get<{ tags: string[] }>("/api/slides/tags/all");
  return data.tags;
}

// ============= System Config =============
export async function fetchSystemConfig(): Promise<SystemConfig> {
  const { data } = await apiClient.get<SystemConfig>("/api/system-config");
  return data;
}

export async function updateSystemConfig(payload: SystemConfigUpdateIn): Promise<SystemConfig> {
  const { data } = await apiClient.put<SystemConfig>("/api/system-config", payload);
  return data;
}

// ============= WebSocket =============
export function buildProgressWsUrl(jobId?: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.host;
  const url = new URL(`${proto}://${host}/ws/progress`);
  if (jobId) url.searchParams.set("job_id", jobId);
  return url.toString();
}
