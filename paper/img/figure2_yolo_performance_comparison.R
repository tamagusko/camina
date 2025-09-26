# =========================
# Accuracy–Speed Scatter (publication-ready, no arrows)
# =========================

# Packages -----------------------------------------------------------
library(ggplot2)
library(grid)
library(gridExtra)

# ---- Input data (edit here) ---------------------------------------
df <- data.frame(
  Method  = c("YOLOv5n", "YOLOv8n", "YOLO11n"),
  Time_ms = c(66.42, 64.83, 64.90),
  mAP     = c(0.550, 0.560, 0.563)   # Use 0–1 or 0–100. Script adapts.
)

# ---- Focused axis ranges for better visualization ------------------
map_is_fraction <- max(df$mAP, na.rm = TRUE) <= 1.5

# Set focused axis ranges to highlight differences
x_min <- 64
x_max <- 68
y_min <- 0.50
y_max <- 0.60

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
  
  # Direct labels with custom positioning to avoid overlap
  geom_text(
    aes(label = Method),
    nudge_x = c(0.1, 0.1, 0.1),  # Same horizontal offset
    nudge_y = c(0.000, -0.002, 0.000),  # Different vertical offsets to separate overlapping labels
    hjust = 0, vjust = 0, size = 3.6, family = "sans"
  ) +

  # Add "better" arrow pointing diagonally to upper-left (45 degrees)
  annotate("segment",
           x = x_max - 0.8 * (x_max - x_min),
           y = y_max - 0.15 * (y_max - y_min),
           xend = x_max - 0.92 * (x_max - x_min),
           yend = y_max - 0.05 * (y_max - y_min),
           arrow = arrow(length = unit(0.25, "cm"), type = "closed"),
           size = 1.2, color = "black") +

  # Add "better" label
  annotate("text",
           x = x_max - 0.8 * (x_max - x_min),
           y = y_max - 0.06 * (y_max - y_min),
           label = "better", hjust = 0.5, vjust = 0.5,
           size = 4, fontface = "italic", family = "sans") +
  
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
ggsave("figure2_performance_comparison.pdf", p, width = 7.2, height = 4.8, device = cairo_pdf)
ggsave("figure2_performance_comparison.png", p, width = 7.2, height = 4.8, dpi = 300)
