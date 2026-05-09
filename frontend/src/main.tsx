import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { theme } from "./theme/theme";
import MainLayout from "./components/MainLayout";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import SlideListPage from "./pages/SlideListPage";
import SlideDetailPage from "./pages/SlideDetailPage";
import { AppAuthProvider } from "./auth/AuthProvider";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 10_000,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <AppAuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<MainLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="upload" element={<UploadPage />} />
                <Route path="slides" element={<SlideListPage />} />
                <Route path="slides/:id" element={<SlideDetailPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AppAuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
