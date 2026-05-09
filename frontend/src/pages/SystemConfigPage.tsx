import { useMemo, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  MenuItem,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import SaveRoundedIcon from "@mui/icons-material/SaveRounded";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchSystemConfig, updateSystemConfig } from "../api/client";
import type { StagePromptConfig, SystemConfig } from "../api/types";

function parseCandidates(raw: string): string[] {
  return Array.from(
    new Set(
      raw
        .split(/[\n,]/g)
        .map((v) => v.trim())
        .filter(Boolean),
    ),
  );
}

export default function SystemConfigPage() {
  const [snack, setSnack] = useState<{ msg: string; severity: "success" | "error" } | null>(null);
  const [draft, setDraft] = useState<SystemConfig | null>(null);
  const [newStageName, setNewStageName] = useState("");

  const configQ = useQuery({
    queryKey: ["system-config"],
    queryFn: fetchSystemConfig,
    refetchOnWindowFocus: false,
  });

  const effectiveConfig = draft ?? configQ.data ?? null;

  const candidatesText = useMemo(() => {
    return effectiveConfig?.model_candidates.join("\n") ?? "";
  }, [effectiveConfig?.model_candidates]);

  const saveMutation = useMutation({
    mutationFn: async (payload: SystemConfig) =>
      updateSystemConfig({
        azure_foundry_url: payload.azure_foundry_url,
        default_model_deployment: payload.default_model_deployment,
        model_candidates: payload.model_candidates,
        model_settings: payload.model_settings,
        stage_prompts: payload.stage_prompts,
      }),
    onSuccess: (data) => {
      setDraft(data);
      configQ.refetch();
      setSnack({ msg: "系统配置已保存", severity: "success" });
    },
    onError: (e: Error) => setSnack({ msg: e.message, severity: "error" }),
  });

  if (configQ.isLoading && !effectiveConfig) {
    return <Typography>加载系统配置中...</Typography>;
  }

  if (configQ.isError && !effectiveConfig) {
    return <Alert severity="error">{(configQ.error as Error).message}</Alert>;
  }

  if (!effectiveConfig) {
    return <Alert severity="warning">系统配置不可用</Alert>;
  }

  const updateDraft = (updater: (prev: SystemConfig) => SystemConfig) => {
    setDraft((prev) => updater(prev ?? effectiveConfig));
  };

  const addStage = () => {
    const key = newStageName.trim();
    if (!key) return;
    if (effectiveConfig.stage_prompts[key]) {
      setSnack({ msg: `阶段 ${key} 已存在`, severity: "error" });
      return;
    }
    updateDraft((prev) => ({
      ...prev,
      stage_prompts: {
        ...prev.stage_prompts,
        [key]: { system_prompt: "", user_prompt: "" },
      },
    }));
    setNewStageName("");
  };

  const removeStage = (stage: string) => {
    updateDraft((prev) => {
      const next = { ...prev.stage_prompts };
      delete next[stage];
      return { ...prev, stage_prompts: next };
    });
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5">系统配置</Typography>
        <Typography color="text.secondary" variant="body2">
          维护 Azure Foundry 链接、模型选择与参数，以及不同阶段调用模型的提示词模板。
        </Typography>
      </Box>

      <Card>
        <CardContent>
          <Stack spacing={2}>
            <TextField
              label="Azure Foundry 链接"
              fullWidth
              value={effectiveConfig.azure_foundry_url}
              onChange={(e) =>
                updateDraft((prev) => ({ ...prev, azure_foundry_url: e.target.value.trim() }))
              }
              placeholder="https://ai.azure.com/..."
            />
            <Typography variant="caption" color="text.secondary">
              更新时间：{new Date(effectiveConfig.updated_at).toLocaleString()}
            </Typography>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            模型选择与设置
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <TextField
                select
                fullWidth
                label="默认模型部署"
                value={effectiveConfig.default_model_deployment}
                onChange={(e) =>
                  updateDraft((prev) => ({ ...prev, default_model_deployment: e.target.value }))
                }
              >
                {effectiveConfig.model_candidates.map((m) => (
                  <MenuItem value={m} key={m}>
                    {m}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="temperature"
                type="number"
                inputProps={{ step: 0.1, min: 0, max: 2 }}
                value={Number(effectiveConfig.model_settings.temperature ?? 0.3)}
                onChange={(e) =>
                  updateDraft((prev) => ({
                    ...prev,
                    model_settings: {
                      ...prev.model_settings,
                      temperature: Number(e.target.value || 0),
                    },
                  }))
                }
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="max_tokens"
                type="number"
                inputProps={{ min: 128, max: 8192 }}
                value={Number(effectiveConfig.model_settings.max_tokens ?? 1200)}
                onChange={(e) =>
                  updateDraft((prev) => ({
                    ...prev,
                    model_settings: {
                      ...prev.model_settings,
                      max_tokens: Number(e.target.value || 1200),
                    },
                  }))
                }
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="top_p"
                type="number"
                inputProps={{ step: 0.1, min: 0, max: 1 }}
                value={Number(effectiveConfig.model_settings.top_p ?? 1)}
                onChange={(e) =>
                  updateDraft((prev) => ({
                    ...prev,
                    model_settings: {
                      ...prev.model_settings,
                      top_p: Number(e.target.value || 1),
                    },
                  }))
                }
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="候选模型（每行一个，或逗号分隔）"
                multiline
                minRows={3}
                fullWidth
                value={candidatesText}
                onChange={(e) => {
                  const list = parseCandidates(e.target.value);
                  updateDraft((prev) => {
                    const nextDefault =
                      list.includes(prev.default_model_deployment) && prev.default_model_deployment
                        ? prev.default_model_deployment
                        : list[0] || "";
                    return {
                      ...prev,
                      model_candidates: list,
                      default_model_deployment: nextDefault,
                    };
                  });
                }}
              />
              <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: "wrap" }}>
                {effectiveConfig.model_candidates.map((c) => (
                  <Chip key={c} label={c} size="small" sx={{ mb: 1 }} />
                ))}
              </Stack>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
            <Typography variant="h6">分阶段提示词维护</Typography>
            <Stack direction="row" spacing={1}>
              <TextField
                size="small"
                label="新增阶段名"
                value={newStageName}
                onChange={(e) => setNewStageName(e.target.value)}
                placeholder="例如: style_rewrite"
              />
              <Button variant="outlined" startIcon={<AddRoundedIcon />} onClick={addStage}>
                添加阶段
              </Button>
            </Stack>
          </Stack>

          <Divider sx={{ mb: 1 }} />

          {Object.entries(effectiveConfig.stage_prompts).map(([stage, cfg]) => (
            <Accordion key={stage} disableGutters>
              <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ width: "100%" }}>
                  <Typography sx={{ fontWeight: 600 }}>{stage}</Typography>
                  <Box sx={{ flexGrow: 1 }} />
                  <Button
                    size="small"
                    color="error"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      removeStage(stage);
                    }}
                  >
                    删除
                  </Button>
                </Stack>
              </AccordionSummary>
              <AccordionDetails>
                <Stack spacing={2}>
                  <TextField
                    label="System Prompt"
                    multiline
                    minRows={6}
                    fullWidth
                    value={cfg.system_prompt}
                    onChange={(e) =>
                      updateDraft((prev) => ({
                        ...prev,
                        stage_prompts: {
                          ...prev.stage_prompts,
                          [stage]: {
                            ...(prev.stage_prompts[stage] as StagePromptConfig),
                            system_prompt: e.target.value,
                          },
                        },
                      }))
                    }
                  />
                  <TextField
                    label="User Prompt"
                    multiline
                    minRows={3}
                    fullWidth
                    value={cfg.user_prompt}
                    onChange={(e) =>
                      updateDraft((prev) => ({
                        ...prev,
                        stage_prompts: {
                          ...prev.stage_prompts,
                          [stage]: {
                            ...(prev.stage_prompts[stage] as StagePromptConfig),
                            user_prompt: e.target.value,
                          },
                        },
                      }))
                    }
                  />
                </Stack>
              </AccordionDetails>
            </Accordion>
          ))}
        </CardContent>
      </Card>

      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Button
          variant="contained"
          startIcon={<SaveRoundedIcon />}
          disabled={saveMutation.isPending}
          onClick={() => saveMutation.mutate(effectiveConfig)}
        >
          保存配置
        </Button>
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
