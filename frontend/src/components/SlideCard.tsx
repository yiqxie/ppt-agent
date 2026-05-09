import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Checkbox,
  Chip,
  Stack,
  Typography,
} from "@mui/material";
import type { Slide } from "../api/types";

interface SlideCardProps {
  slide: Slide;
  selected: boolean;
  onToggleSelect: (slide: Slide, selected: boolean) => void;
  onOpen: (slide: Slide) => void;
}

/** 单个 slide 卡片：缩略图 + 标题 + tag + 选择框 */
export default function SlideCard({ slide, selected, onToggleSelect, onOpen }: SlideCardProps) {
  return (
    <Card
      sx={{
        position: "relative",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        outline: selected ? "2px solid" : "none",
        outlineColor: "primary.main",
        "&:hover": { transform: "translateY(-2px)" },
      }}
    >
      <Checkbox
        checked={selected}
        onChange={(e) => onToggleSelect(slide, e.target.checked)}
        sx={{
          position: "absolute",
          top: 6,
          left: 6,
          zIndex: 2,
          bgcolor: "rgba(255,255,255,0.85)",
          borderRadius: 1,
          p: 0.5,
          "&:hover": { bgcolor: "rgba(255,255,255,1)" },
        }}
      />
      <CardActionArea onClick={() => onOpen(slide)} sx={{ flexGrow: 1 }}>
        <Box
          sx={{
            position: "relative",
            paddingTop: "56.25%",
            backgroundColor: "#F1F5F9",
            backgroundImage: `url(${slide.screenshot_url})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        <CardContent sx={{ pb: "16px !important" }}>
          <Typography variant="caption" color="text.secondary">
            第 {slide.slide_index} 页
          </Typography>
          <Typography
            variant="subtitle2"
            sx={{
              mt: 0.5,
              fontWeight: 600,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              minHeight: 40,
            }}
          >
            {slide.title || "未命名"}
          </Typography>
          <Stack direction="row" spacing={0.5} sx={{ mt: 1, flexWrap: "wrap", gap: 0.5 }}>
            {(slide.tags || []).slice(0, 4).map((t) => (
              <Chip key={t} label={t} size="small" variant="outlined" />
            ))}
            {(slide.tags?.length ?? 0) > 4 && (
              <Chip label={`+${slide.tags.length - 4}`} size="small" />
            )}
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
