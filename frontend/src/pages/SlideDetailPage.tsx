import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  IconButton,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import SaveRoundedIcon from "@mui/icons-material/SaveRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { batchDeleteSlides, getSlide, updateSlide } from "../api/client";
import type { Slide } from "../api/types";

/** 单个 slide 的查看 / 编辑页 */
export default function SlideDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const slideQ = useQuery({
    queryKey: ["slide", id],
    queryFn: () => getSlide(id),
    enabled: !!id,
  });

  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [promptText, setPromptText] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [snack, setSnack] = useState<{ msg: string; severity: "success" | "error" } | null>(null);

  useEffect(() => {
    if (slideQ.data) {
      setTitle(slideQ.data.title || "");
      setSummary(slideQ.data.summary || "");
      setPromptText(slideQ.data.prompt_text || "");
      setTagsInput((slideQ.data.tags || []).join(", "));
    }
  }, [slideQ.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateSlide(id, {
        title,
        summary,
        prompt_text: promptText,
        tags: tagsInput
          .split(/[，,]/g)
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    onSuccess: (data) => {
      setSnack({ msg: "已保存", severity: "success" });
      queryClient.setQueryData(["slide", id], data);
      queryClient.invalidateQueries({ queryKey: ["slides"] });
      queryClient.invalidateQueries({ queryKey: ["all-tags"] });
    },
    onError: (e: Error) => setSnack({ msg: e.message, severity: "error" }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => batchDeleteSlides([id]),
    onSuccess: () => {
      setSnack({ msg: "已删除", severity: "success" });
      navigate(-1);
      queryClient.invalidateQueries({ queryKey: ["slides"] });
    },
    onError: (e: Error) => setSnack({ msg: e.message, severity: "error" }),
  });

  if (slideQ.isLoading) {
    return (
      <Box sx={{ textAlign: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (slideQ.isError || !slideQ.data) {
    return (
      <Alert severity="error">
        {slideQ.error instanceof Error ? slideQ.error.message : "未找到 slide"}
      </Alert>
    );
  }

  const slide: Slide = slideQ.data;
  const palette = slide.style_meta?.color_palette || {};

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <IconButton onClick={() => navigate(-1)}>
          <ArrowBackRoundedIcon />
        </IconButton>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h6">第 {slide.slide_index} 页 · {slide.title || "未命名"}</Typography>
          <Typography variant="caption" color="text.secondary">
            最后更新：{new Date(slide.updated_at).toLocaleString()}
          </Typography>
        </Box>
        <Button
          color="error"
          startIcon={<DeleteOutlineRoundedIcon />}
          onClick={() => {
            if (window.confirm("确认删除此 slide？此操作不可恢复。")) deleteMutation.mutate();
          }}
        >
          删除
        </Button>
        <Button
          variant="contained"
          startIcon={<SaveRoundedIcon />}
          disabled={saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          保存修改
        </Button>
      </Stack>

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={6}>
          <Card>
            <Box
              sx={{
                width: "100%",
                aspectRatio: "16 / 9",
                backgroundColor: "#0F172A",
                backgroundImage: `url(${slide.screenshot_url})`,
                backgroundSize: "contain",
                backgroundRepeat: "no-repeat",
                backgroundPosition: "center",
              }}
            />
            <CardContent>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
                <Button
                  size="small"
                  variant="outlined"
                  href={slide.screenshot_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  打开原图
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  href={slide.prompt_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  下载 Prompt JSON
                </Button>
              </Stack>
            </CardContent>
          </Card>

          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                自动提取的视觉元数据
              </Typography>
              <Divider sx={{ mb: 1.5 }} />
              <Stack spacing={1.2}>
                <Typography variant="body2">
                  <strong>整体风格：</strong>{slide.style_meta?.overall_style || "—"}
                </Typography>
                <Typography variant="body2">
                  <strong>字体观感：</strong>{slide.style_meta?.typography || "—"}
                </Typography>
                <Typography variant="body2">
                  <strong>布局：</strong>{slide.style_meta?.layout || "—"}
                </Typography>
                <Typography variant="body2">
                  <strong>配图：</strong>{slide.style_meta?.imagery || "—"}
                </Typography>
                <Box>
                  <Typography variant="body2" sx={{ mb: 0.5 }}>
                    <strong>配色：</strong>
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    {(["primary", "secondary", "accent", "background"] as const).map((k) => {
                      const v = (palette as Record<string, string | undefined>)[k];
                      return (
                        <Stack key={k} alignItems="center" sx={{ flex: 1 }}>
                          <Box
                            sx={{
                              width: "100%",
                              height: 40,
                              borderRadius: 1.5,
                              backgroundColor: v || "#E2E8F0",
                              border: "1px solid rgba(15,23,42,0.08)",
                            }}
                          />
                          <Typography variant="caption" sx={{ mt: 0.5 }}>
                            {k}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {v || "—"}
                          </Typography>
                        </Stack>
                      );
                    })}
                  </Stack>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Stack spacing={2}>
                <TextField
                  label="标题"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  fullWidth
                  size="small"
                />
                <TextField
                  label="摘要"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  fullWidth
                  size="small"
                  multiline
                  minRows={2}
                />
                <TextField
                  label="标签 (用 , 分隔)"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  fullWidth
                  size="small"
                  helperText="例如：商务, 蓝白配色, 数据图表"
                />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    当前标签预览：
                  </Typography>
                  <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: "wrap", gap: 0.5 }}>
                    {tagsInput
                      .split(/[，,]/g)
                      .map((t) => t.trim())
                      .filter(Boolean)
                      .map((t) => (
                        <Chip key={t} label={t} size="small" />
                      ))}
                  </Stack>
                </Box>
                <TextField
                  label="Prompt 模板"
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  fullWidth
                  multiline
                  minRows={12}
                  helperText="可直接复用到生成式工具中描述此 slide 的视觉风格。"
                />
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Snackbar
        open={!!snack}
        autoHideDuration={3500}
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
