import { AppBar, Avatar, Box, Button, Container, Stack, Toolbar, Typography } from "@mui/material";
import { Outlet, NavLink as RouterLink, useLocation } from "react-router-dom";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import LogoutRoundedIcon from "@mui/icons-material/LogoutRounded";
import LoginRoundedIcon from "@mui/icons-material/LoginRounded";
import { useAppAuth } from "../auth/AuthProvider";

const NAV_ITEMS: { to: string; label: string }[] = [
  { to: "/", label: "概览" },
  { to: "/upload", label: "上传 PPT" },
  { to: "/slides", label: "Slide 库" },
];

/**
 * 全站布局：顶部 AppBar + 主内容容器
 */
export default function MainLayout() {
  const { config, account, signIn, signOut } = useAppAuth();
  const location = useLocation();

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppBar position="sticky">
        <Toolbar disableGutters sx={{ px: { xs: 2, sm: 4 } }}>
          <Stack direction="row" alignItems="center" spacing={1.2} sx={{ flexShrink: 0 }}>
            <Box
              sx={{
                width: 36,
                height: 36,
                borderRadius: 2,
                background: "linear-gradient(135deg,#6366F1,#22D3EE)",
                color: "#fff",
                display: "grid",
                placeItems: "center",
              }}
            >
              <AutoAwesomeRoundedIcon fontSize="small" />
            </Box>
            <Box>
              <Typography variant="h6" sx={{ lineHeight: 1.1 }}>
                {config?.app_name || "PPT Slide Agent"}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                智能切片 · 风格提取 · 一键复用
              </Typography>
            </Box>
          </Stack>

          <Stack direction="row" spacing={0.5} sx={{ ml: 4, flexGrow: 1 }}>
            {NAV_ITEMS.map((item) => {
              const active =
                item.to === "/"
                  ? location.pathname === "/"
                  : location.pathname.startsWith(item.to);
              return (
                <Button
                  key={item.to}
                  component={RouterLink}
                  to={item.to}
                  size="medium"
                  sx={{
                    color: active ? "primary.main" : "text.primary",
                    backgroundColor: active ? "primary.50" : "transparent",
                    "&:hover": { backgroundColor: "rgba(79,70,229,0.08)" },
                    fontWeight: active ? 700 : 500,
                  }}
                >
                  {item.label}
                </Button>
              );
            })}
          </Stack>

          {config?.auth_enabled ? (
            account ? (
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Avatar sx={{ width: 32, height: 32, bgcolor: "primary.light" }}>
                  {(account.name || account.username || "U")[0]}
                </Avatar>
                <Box sx={{ display: { xs: "none", md: "block" } }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {account.name || account.username}
                  </Typography>
                </Box>
                <Button
                  size="small"
                  color="inherit"
                  startIcon={<LogoutRoundedIcon />}
                  onClick={signOut}
                >
                  注销
                </Button>
              </Stack>
            ) : (
              <Button variant="contained" startIcon={<LoginRoundedIcon />} onClick={signIn}>
                登录
              </Button>
            )
          ) : (
            <Typography variant="caption" color="text.secondary">
              本地开发模式
            </Typography>
          )}
        </Toolbar>
      </AppBar>

      <Box component="main" sx={{ flexGrow: 1, py: { xs: 3, md: 4 } }}>
        <Container maxWidth="xl">
          <Outlet />
        </Container>
      </Box>

      <Box
        component="footer"
        sx={{
          py: 2,
          textAlign: "center",
          color: "text.secondary",
          fontSize: 12,
          borderTop: "1px solid rgba(15,23,42,0.06)",
        }}
      >
        © {new Date().getFullYear()} PPT Slide Agent · 由 GPT-4o 视觉模型驱动
      </Box>
    </Box>
  );
}
