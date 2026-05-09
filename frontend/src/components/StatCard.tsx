import { Card, CardContent, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  color?: string;
  icon?: ReactNode;
}

/** 仪表盘上的统计卡片 */
export default function StatCard({ label, value, hint, color = "primary.main", icon }: StatCardProps) {
  return (
    <Card sx={{ height: "100%" }}>
      <CardContent>
        <Stack direction="row" spacing={1.5} alignItems="center">
          {icon && (
            <Stack
              alignItems="center"
              justifyContent="center"
              sx={{
                width: 40,
                height: 40,
                borderRadius: 2,
                color,
                bgcolor: "rgba(79,70,229,0.08)",
              }}
            >
              {icon}
            </Stack>
          )}
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
        </Stack>
        <Typography variant="h4" sx={{ mt: 1.5, color }}>
          {value}
        </Typography>
        {hint && (
          <Typography variant="caption" color="text.secondary">
            {hint}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
