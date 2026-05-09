import {
  Box,
  Card,
  CardContent,
  Chip,
  IconButton,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import type { UploadJob } from "../api/types";
import { useNavigate } from "react-router-dom";

interface JobCardProps {
  job: UploadJob;
  onDelete?: (job: UploadJob) => void;
  onRestart?: (job: UploadJob) => void;
}

const STATUS_COLOR: Record<string, "default" | "primary" | "success" | "warning" | "error"> = {
  pending: "default",
  running: "primary",
  completed: "success",
  failed: "error",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "等待中",
  running: "处理中",
  completed: "已完成",
  failed: "失败",
};

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

/** 单个 PPT 任务卡片：显示进度 / 状态 / 操作 */
export default function JobCard({ job, onDelete, onRestart }: JobCardProps) {
  const navigate = useNavigate();
  const pct = job.total_slides > 0 ? Math.round((job.processed_slides / job.total_slides) * 100) : 0;

  return (
    <Card>
      <CardContent>
        <Stack direction="row" spacing={2} alignItems="flex-start">
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }} noWrap title={job.original_filename}>
                {job.original_filename}
              </Typography>
              <Chip
                size="small"
                label={STATUS_LABEL[job.status] ?? job.status}
                color={STATUS_COLOR[job.status] ?? "default"}
                variant={job.status === "completed" ? "filled" : "outlined"}
              />
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {formatSize(job.file_size)} · 创建于 {new Date(job.created_at).toLocaleString()}
            </Typography>
          </Box>
          <Stack direction="row" spacing={0.5}>
            {(job.status === "failed" || job.status === "pending") && (
              <Tooltip title="重新开始处理">
                <IconButton size="small" color="primary" onClick={() => onRestart?.(job)}>
                  <PlayArrowRoundedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="查看其下 slide">
              <IconButton size="small" onClick={() => navigate(`/slides?job_id=${job.id}`)}>
                <OpenInNewRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="删除任务及其所有 slide">
              <IconButton size="small" color="error" onClick={() => onDelete?.(job)}>
                <DeleteOutlineRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
        </Stack>

        <Box sx={{ mt: 1.5 }}>
          <Stack direction="row" justifyContent="space-between">
            <Typography variant="caption" color="text.secondary">
              {job.processed_slides} / {job.total_slides || "?"} 页
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {pct}%
            </Typography>
          </Stack>
          <LinearProgress
            variant={job.status === "running" && job.total_slides === 0 ? "indeterminate" : "determinate"}
            value={pct}
            sx={{ mt: 0.5, borderRadius: 1, height: 6 }}
          />
        </Box>

        {job.error_message && (
          <Typography variant="caption" color="error" sx={{ mt: 1, display: "block" }}>
            {job.error_message}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
