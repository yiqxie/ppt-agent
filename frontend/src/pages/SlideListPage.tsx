import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  IconButton,
  InputAdornment,
  MenuItem,
  Pagination,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import DeleteSweepRoundedIcon from "@mui/icons-material/DeleteSweepRounded";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { batchDeleteSlides, listAllTags, listSlideIds, listSlides } from "../api/client";
import type { ProgressMessage, Slide } from "../api/types";
import SlideCard from "../components/SlideCard";
import { useProgressSocket } from "../hooks/useProgressSocket";

const PAGE_SIZE = 24;

/** Slide 库：列表 / 检索 / 多选 / 批量删除 */
export default function SlideListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const jobId = searchParams.get("job_id") || undefined;
  const [keywordInput, setKeywordInput] = useState(searchParams.get("keyword") || "");
  const keyword = searchParams.get("keyword") || undefined;
  const tag = searchParams.get("tag") || undefined;
  const page = Number(searchParams.get("page") || 1);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [snack, setSnack] = useState<{ msg: string; severity: "success" | "error" } | null>(null);

  const slidesQ = useQuery({
    queryKey: ["slides", { jobId, keyword, tag, page }],
    queryFn: () =>
      listSlides({
        job_id: jobId,
        keyword,
        tag,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  const tagsQ = useQuery({ queryKey: ["all-tags"], queryFn: listAllTags });

  // 实时刷新：收到完成事件就 invalidate
  useProgressSocket((msg: ProgressMessage) => {
    if (msg.type === "slide_completed" || msg.type === "done") {
      queryClient.invalidateQueries({ queryKey: ["slides"] });
      queryClient.invalidateQueries({ queryKey: ["all-tags"] });
    }
  });

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil((slidesQ.data?.total ?? 0) / PAGE_SIZE)),
    [slidesQ.data],
  );

  const updateParams = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams);
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "") next.delete(k);
      else next.set(k, v);
    }
    setSearchParams(next, { replace: true });
  };

  const handleToggle = (slide: Slide, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(slide.id);
      else next.delete(slide.id);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (!slidesQ.data) return;
    if (selected.size === slidesQ.data.items.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(slidesQ.data.items.map((s) => s.id)));
    }
  };

  const deleteMutation = useMutation({
    mutationFn: () => batchDeleteSlides(Array.from(selected)),
    onSuccess: (data) => {
      setSnack({ msg: `已删除 ${data.deleted} 个 slide`, severity: "success" });
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ["slides"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (e: Error) => setSnack({ msg: e.message, severity: "error" }),
  });

  const selectByFilterMutation = useMutation({
    mutationFn: () => listSlideIds({ job_id: jobId, keyword, tag, limit: 10000 }),
    onSuccess: (ids) => {
      setSelected(new Set(ids));
      setSnack({ msg: `已勾选当前筛选结果 ${ids.length} 条`, severity: "success" });
    },
    onError: (e: Error) => setSnack({ msg: e.message, severity: "error" }),
  });

  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="h5">Slide 库</Typography>
        <Typography color="text.secondary" variant="body2">
          {jobId ? "当前按任务过滤；" : ""}
          点击卡片可查看详情 / 编辑 prompt 与 tag。
        </Typography>
      </Box>

      <Card>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
            <TextField
              placeholder="搜索标题 / 摘要 / prompt 内容"
              fullWidth
              size="small"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") updateParams({ keyword: keywordInput || undefined, page: "1" });
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchRoundedIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              select
              size="small"
              label="标签"
              value={tag || ""}
              onChange={(e) => updateParams({ tag: e.target.value || undefined, page: "1" })}
              sx={{ minWidth: 180 }}
            >
              <MenuItem value="">不限</MenuItem>
              {(tagsQ.data || []).map((t) => (
                <MenuItem value={t} key={t}>
                  {t}
                </MenuItem>
              ))}
            </TextField>
            <Button
              variant="outlined"
              onClick={() => {
                setKeywordInput("");
                updateParams({ keyword: undefined, tag: undefined, page: "1" });
              }}
            >
              重置
            </Button>
            <IconButton onClick={() => slidesQ.refetch()}>
              <RefreshRoundedIcon />
            </IconButton>
          </Stack>

          <Stack direction="row" spacing={1} sx={{ mt: 1.5, alignItems: "center" }}>
            {jobId && (
              <Chip
                label={`任务过滤: ${jobId.slice(0, 8)}…`}
                size="small"
                onDelete={() => updateParams({ job_id: undefined })}
              />
            )}
            <Box sx={{ flexGrow: 1 }} />
            <Typography variant="body2" color="text.secondary">
              共 {slidesQ.data?.total ?? 0} 条
            </Typography>
            <Button
              size="small"
              variant="outlined"
              disabled={selectByFilterMutation.isPending}
              onClick={() => selectByFilterMutation.mutate()}
            >
              {selectByFilterMutation.isPending ? "勾选中..." : "一键勾选(当前筛选)"}
            </Button>
            <Button size="small" variant="text" onClick={handleSelectAll}>
              {selected.size === (slidesQ.data?.items.length ?? 0) && selected.size > 0
                ? "取消全选"
                : "全选本页"}
            </Button>
            <Button size="small" variant="text" onClick={() => setSelected(new Set())}>
              清空勾选
            </Button>
            <Button
              size="small"
              color="error"
              variant="contained"
              startIcon={<DeleteSweepRoundedIcon />}
              disabled={selected.size === 0 || deleteMutation.isPending}
              onClick={() => {
                if (window.confirm(`确认删除选中的 ${selected.size} 个 slide？此操作不可恢复。`)) {
                  deleteMutation.mutate();
                }
              }}
            >
              删除选中 ({selected.size})
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {slidesQ.isLoading && (
        <Box sx={{ textAlign: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      )}
      {slidesQ.isError && <Alert severity="error">{(slidesQ.error as Error).message}</Alert>}

      {slidesQ.data && slidesQ.data.items.length === 0 && (
        <Card sx={{ p: 4, textAlign: "center" }}>
          <Typography color="text.secondary">没有找到 slide，调整下检索条件试试。</Typography>
        </Card>
      )}

      <Grid container spacing={2}>
        {slidesQ.data?.items.map((slide) => (
          <Grid item xs={6} sm={4} md={3} lg={2.4} key={slide.id}>
            <SlideCard
              slide={slide}
              selected={selected.has(slide.id)}
              onToggleSelect={handleToggle}
              onOpen={(s) => navigate(`/slides/${s.id}`)}
            />
          </Grid>
        ))}
      </Grid>

      {totalPages > 1 && (
        <Stack alignItems="center" sx={{ mt: 2 }}>
          <Pagination
            page={page}
            count={totalPages}
            onChange={(_, p) => updateParams({ page: String(p) })}
            color="primary"
          />
        </Stack>
      )}

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
