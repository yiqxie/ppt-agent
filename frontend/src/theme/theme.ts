import { createTheme, alpha } from "@mui/material/styles";

/**
 * 全局浅色主题：现代化、柔和、信息密度适中
 * - 主色采用 Indigo，辅色采用 Cyan
 * - 卡片背景纯白 + 微弱阴影 + 圆角 14
 * - 字体使用系统字体栈，支持中英文混排
 */
export const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#4F46E5",
      light: "#818CF8",
      dark: "#3730A3",
      contrastText: "#fff",
    },
    secondary: {
      main: "#06B6D4",
      light: "#67E8F9",
      dark: "#0E7490",
      contrastText: "#fff",
    },
    success: { main: "#10B981" },
    warning: { main: "#F59E0B" },
    error: { main: "#EF4444" },
    background: {
      default: "#F6F8FB",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#0F172A",
      secondary: "#475569",
    },
    divider: "rgba(15, 23, 42, 0.08)",
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: [
      "-apple-system",
      "BlinkMacSystemFont",
      '"Segoe UI"',
      "Roboto",
      '"Helvetica Neue"',
      '"PingFang SC"',
      '"Hiragino Sans GB"',
      '"Microsoft YaHei"',
      "sans-serif",
    ].join(","),
    h4: { fontWeight: 700, letterSpacing: "-0.01em" },
    h5: { fontWeight: 700, letterSpacing: "-0.01em" },
    h6: { fontWeight: 700 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: "#F6F8FB",
        },
        "*::-webkit-scrollbar": { width: 10, height: 10 },
        "*::-webkit-scrollbar-thumb": {
          backgroundColor: "rgba(0,0,0,0.18)",
          borderRadius: 8,
        },
      },
    },
    MuiAppBar: {
      defaultProps: { color: "transparent", elevation: 0 },
      styleOverrides: {
        root: {
          backdropFilter: "saturate(180%) blur(8px)",
          backgroundColor: alpha("#FFFFFF", 0.85),
          borderBottom: "1px solid rgba(15, 23, 42, 0.06)",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          border: "1px solid rgba(15, 23, 42, 0.06)",
          boxShadow: "0 1px 2px rgba(15,23,42,0.04), 0 8px 24px rgba(15,23,42,0.04)",
          transition: "transform 0.2s ease, box-shadow 0.2s ease",
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 10, paddingInline: 14 },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 8, fontWeight: 500 },
      },
    },
  },
});
