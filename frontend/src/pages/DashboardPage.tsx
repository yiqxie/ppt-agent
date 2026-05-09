import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  IconButton,
  Snackbar,
  Stack,
  Typography,
} from "@mui/material";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import UploadRoundedIcon from "@mui/icons-material/UploadRounded";
import SummarizeRoundedIcon from "@mui/icons-material/SummarizeRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import HourglassTopRoundedIcon from "@mui/icons-material/HourglassTopRounded";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteJob, listJobs, listSlides, startJob } from "../api/client";
import type { ProgressMessage, UploadJob } from "../api/types";
import StatCard from "../components/StatCard";
import JobCard from "../components/JobCard";
import { useProgressSocket } from "../hooks/useProgressSocket";

/**
 * 仪表盘：统计 + 最近任务列表 + 实时进度。
 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [snack, setSnack] = useState<{ msg: string; severity: "success" | "error" } | null>(null);

  const jobsQ = useQuery({
    queryKey: ["jobs", { skip: 0, limit: 20 }],
    queryFn: () => listJobs({ skip: 0, limit: 20 }),
    refetchInterval: 15_000,
  });
  const slidesCountQ = useQuery({
    queryKey: ["slides-count"],
    queryFn: () => listSlides({ skip: 0, limit: 1 }),
    refetchInterval: 30_000,
  });

  // 订阅全局进度，收到任意 job 变化就刷新列表
  useProgressSocket((msg: ProgressMessage) => {
    if (msg.type === "slide_completed" || msg.type === "job_update" || msg.type === "done") {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
    if (msg.type === "done" || msg.type === "slide_completed") {
      queryClient.invalidateQueries({ queryKey: ["slides-count"] });
    }
    if (msg.type === "error") {
      setSnack({ msg: `任务失败：${msg.error_message}`, severity: "error" });
    }
  });

  const stats = useMemo(() => {
    const items = jobsQ.data?.items ?? [];
    return {
      total: jobsQ.data?.total ?? 0,
      running: items.filter((i) => i.status === "running").length,
      completed: items.filter((i) => i.status === "completed").length,
      failed: items.filter((i) => i.status === "failed").length,
    };
  }, [jobsQ.data]);

  const deleteMutation = useMutation({
    mutationFn: (job: UploadJob) => deleteJob(job.id),
    onSuccess: () => {
      setSnack({ msg: "已删除任务及其 slide", severity: "success" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["slides-count"] });
    },
    onError: (e: Error) => setSnack({ msg: e.message, severity: "error" }),
  });

  const restartMutation = useMutation({
    mutationFn: (job: UploadJob) => startJob(job.id),
    onSuccess: () => {
      setSnack({ msg: "已重新开始处理", severity: "success" });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (e: Error) => setSnack({ msg: e.message, severity: "error" }),
  });

  return (
    <Stack spacing={3}>
      {/* Hero */}
      <Card
        sx={{
          background:
            "linear-gradient(135deg, rgba(99,102,241,0.95) 0%, rgba(34,211,238,0.95) 100%)",
          color: "#fff",
          border: "none",
        }}
      >
        <CardContent sx={{ p: { xs: 3, md: 4 } }}>
          <Stack
            direction={{ xs: "column", md: "row" }}
            spacing={3}
            alignItems={{ md: "center" }}
            justifyContent="space-between"
          >
            <Box>
              <Typography variant="overline" sx={{ opacity: 0.85 }}>
                PPT Slide Agent
              </Typography>
              <Typography variant="h4" sx={{ mt: 0.5 }}>
                把每一页 PPT 变成可复用的 prompt 模板
              </Typography>
              <Typography variant="body1" sx={{ mt: 1, opacity: 0.9 }}>
                上传 PPT，自动截图、AI 提取风格 / 配色 / 配图、保存到云端，并生成检索标签。
              </Typography>
            </Box>
            <Stack direction="row" spacing={1.5}>
              <Button
                size="large"
                variant="contained"
                color="inherit"
                sx={{ color: "primary.main", bgcolor: "#fff", "&:hover": { bgcolor: "#F8FAFC" } }}
                startIcon={<UploadRoundedIcon />}
                onClick={() => navigate("/upload")}
              >
                上传 PPT
              </Button>
              <Button
                size="large"
                variant="outlined"
                sx={{ color: "#fff", borderColor: "rgba(255,255,255,0.7)" }}
                onClick={() => navigate("/slides")}
              >
                浏览 Slide 库
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {/* 统计卡片 */}
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label="总任务数"
            value={stats.total}
            hint="累计上传过的 PPT 文件数"
            icon={<SummarizeRoundedIcon />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label="进行中"
            value={stats.running}
            hint="实时刷新"
            color="warning.main"
            icon={<HourglassTopRoundedIcon />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label="已完成"
            value={stats.completed}
            color="success.main"
            icon={<CheckCircleRoundedIcon />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label="累计 Slide"
            value={slidesCountQ.data?.total ?? 0}
            hint="已生成的 slide 总数"
            color="secondary.main"
            icon={<ErrorOutlineRoundedIcon />}
          />
        </Grid>
      </Grid>

      {/* 最近任务 */}
      <Box>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
          <Typography variant="h6">最近任务</Typography>
          <IconButton onClick={() => jobsQ.refetch()} size="small">
            <RefreshRoundedIcon />
          </IconButton>
        </Stack>
        {jobsQ.isError && <Alert severity="error">{(jobsQ.error as Error).message}</Alert>}
        {jobsQ.data && jobsQ.data.items.length === 0 && (
          <Card sx={{ p: 4, textAlign: "center" }}>
            <Typography color="text.secondary">还没有任何上传记录，去上传第一个 PPT 试试吧 👆</Typography>
          </Card>
        )}
        <Grid container spacing={2}>
          {jobsQ.data?.items.map((job) => (
            <Grid item xs={12} md={6} lg={4} key={job.id}>
              <JobCard
                job={job}
                onDelete={(j) => {
                  if (window.confirm(`确认删除任务「${j.original_filename}」及其所有 slide 吗？此操作不可恢复。`)) {
                    deleteMutation.mutate(j);
                  }
                }}
                onRestart={(j) => restartMutation.mutate(j)}
              />
            </Grid>
          ))}
        </Grid>
      </Box>

      <Snackbar
        open={!!snack}
        autoHideDuration={4500}
        onClose={() => setSnack(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity={snack?.severity} onClose={() => setSnack(null)} variant="filled">
          {snack?.msg}
        </Alert>
      </Snackbar>
    </Stack>
  );
}
