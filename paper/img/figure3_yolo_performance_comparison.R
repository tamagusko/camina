# =========================
# Accuracy–Speed Scatter (publication-ready, no arrows)
# =========================

# Packages -----------------------------------------------------------
library(ggplot2)
library(grid)
library(gridExtra)

# ---- Input data (edit here) ---------------------------------------
df <- data.frame(
  Method  = c("[A] YOLOv5n", "[B] YOLOv8n", "[C] YOLOv10n", "[D] YOLO11n"),
  Time_ms = c(12.5, 14.2, 16.8, 15.1),
  mAP     = c(0.500, 0.510, 0.530, 0.570)   # Use 0–1 or 0–100. Script adapts.
)

# ---- Dynamic zoom paddings ----------------------------------------
map_is_fraction <- max(df$mAP, na.rm = TRUE) <= 1.5
pad_map  <- if (map_is_fraction) 0.10 else 5   # ±0.10 or ±5 points
pad_time <- 2                                  # ±2 ms

x_min <- min(df$Time_ms) - pad_time
x_max <- max(df$Time_ms) + pad_time
y_min <- min(df$mAP)    - pad_map
y_max <- max(df$mAP)    + pad_map

if (map_is_fraction) {  # keep sensible bounds on [0,1]
  y_min <- max(0, y_min)
  y_max <- min(1, y_max)
}

# ---- Legend table (over-plot) -------------------------------------
legend_df <- data.frame(
  Method     = df$Method,
  `mAP@0.5`  = if (map_is_fraction) sprintf("%.3f", df$mAP) else sprintf("%.1f", df$mAP),
  `Time (ms)`= sprintf("%.1f", df$Time_ms),
  check.names = FALSE
)

tbl <- tableGrob(
  legend_df,
  rows = NULL,
  theme = ttheme_minimal(
    base_size = 12,
    core   = list(
      fg_params = list(fontface = 1, just = "center"),
      bg_params = list(fill = "white", col = "grey70")
    ),
    colhead = list(
      fg_params = list(fontface = 2),
      bg_params = list(fill = "white", col = "grey50")
    )
  )
)

# Position for the table (top-right, with insets)
table_xmin <- x_max - 0.40 * (x_max - x_min)
table_xmax <- x_max - 0.02 * (x_max - x_min)
table_ymin <- y_min + 0.02 * (y_max - y_min)
table_ymax <- y_min + 0.42 * (y_max - y_min)

# ---- Plot ----------------------------------------------------------
p <- ggplot(df, aes(Time_ms, mAP)) +
  # Points only
  geom_point(shape = 21, size = 3.2, stroke = 0.5,
             color = "black", fill = "grey40") +
  
  # Direct labels next to points
  geom_text(
    aes(label = Method),
    nudge_x = 0.20,
    nudge_y = if (map_is_fraction) 0.008 else 0.8,
    hjust = 0, vjust = 0, size = 3.6, family = "sans"
  ) +
  
  # Axes and labels (NO title)
  scale_x_continuous(limits = c(x_min, x_max)) +
  scale_y_continuous(limits = c(y_min, y_max)) +
  labs(
    x = "inference time (ms)",
    y = if (map_is_fraction) "mAP@0.5" else "mAP@0.5 (points)"
  ) +
  
  # Theme
  theme_minimal(base_size = 12) +
  theme(
    plot.title       = element_blank(),
    panel.grid.major = element_line(linetype = "dashed", linewidth = 0.3, colour = "grey80"),
    panel.grid.minor = element_line(linetype = "dotted", linewidth = 0.2, colour = "grey85"),
    axis.title.x     = element_text(margin = margin(t = 6)),
    axis.title.y     = element_text(margin = margin(r = 6)),
    legend.position  = "none"
  ) +
  
  # Legend table placed over the plot
  annotation_custom(
    grob = tbl,
    xmin = table_xmin, xmax = table_xmax,
    ymin = table_ymin, ymax = table_ymax
  )

# ---- Save ----------------------------------------------------------
# Vector PDF (preferred by journals) and a 300-dpi PNG for sharing
ggsave("figure1_yolo_tradeoff_clean.pdf", p, width = 7.2, height = 4.8, device = cairo_pdf)
ggsave("figure1_yolo_tradeoff_clean.png", p, width = 7.2, height = 4.8, dpi = 300)
