# Figure 3: YOLO Performance Comparison for CAMINA Paper
# Performance comparison showing mAP vs. inference time for YOLO models
# Author: CAMINA Research Team
# Date: September 2025

# Load required libraries
library(ggplot2)
library(dplyr)
library(scales)
library(gridExtra)
library(grid)

# ============================================================================
# DATA CONFIGURATION - EDIT THESE VALUES WHEN REAL DATA IS AVAILABLE
# ============================================================================

# Model performance data (dummy data for now - replace with actual results)
# mAP@0.5 values (0.0 to 1.0 scale)
yolov5n_map <- 0.72    # Baseline model
yolov8n_map <- 0.78    # Improved accuracy
yolov10n_map <- 0.81   # Better accuracy
yolo11n_map <- 0.85    # Best accuracy (selected model)

# Inference time in milliseconds
yolov5n_time <- 12.5   # Fastest
yolov8n_time <- 14.2   # Slightly slower
yolov10n_time <- 16.8  # Moderate increase
yolo11n_time <- 15.1   # Optimal balance (selected model)

# Model names and letter codes
model_names <- c("YOLOv5n", "YOLOv8n", "YOLOv10n", "YOLO11n")
letter_codes <- c("A", "B", "C", "D")

# ============================================================================
# DATA PREPARATION
# ============================================================================

# Create data frame
performance_data <- data.frame(
  model = factor(model_names, levels = model_names),
  letter = letter_codes,
  map_50 = c(yolov5n_map, yolov8n_map, yolov10n_map, yolo11n_map),
  inference_time = c(yolov5n_time, yolov8n_time, yolov10n_time, yolo11n_time),
  selected = c(FALSE, FALSE, FALSE, TRUE)  # YOLO11n is selected
)

# ============================================================================
# VISUALIZATION CONFIGURATION
# ============================================================================

# Simplified design: all crosses, same color
cross_color <- "gray20"  # Dark gray for all points
cross_shape <- 3  # Cross shape (+)
cross_size <- 4  # Consistent size for all points

# Plot dimensions and styling
plot_width <- 8
plot_height <- 6
dpi <- 300

# ============================================================================
# CREATE FIGURE 3
# ============================================================================

# Main scatter plot
p <- ggplot(performance_data, aes(x = inference_time, y = map_50)) +

  # Add simplified cross points for all models
  geom_point(color = cross_color, shape = cross_shape, size = cross_size,
             stroke = 1.2) +

  # Add letter labels next to each point
  geom_text(aes(label = letter),
            nudge_x = 0.3, nudge_y = 0.005,
            size = 4, fontface = "bold", color = "black") +

  # Axis configuration
  scale_x_continuous(
    name = "Inference Time (ms)",
    limits = c(10, 20),
    breaks = seq(10, 20, by = 2),
    expand = expansion(mult = c(0.05, 0.05))
  ) +

  scale_y_continuous(
    name = "mAP@0.5",
    limits = c(0.65, 0.90),
    breaks = seq(0.65, 0.90, by = 0.05),
    labels = number_format(accuracy = 0.01),
    expand = expansion(mult = c(0.02, 0.02))
  ) +

  # Add "Better" direction indicators - positioned in top-left corner
  # Horizontal arrow (pointing left - better inference time)
  annotate("segment", x = 12.0, xend = 11.0, y = 0.88, yend = 0.88,
           arrow = arrow(length = unit(0.3, "cm"), type = "closed"),
           color = "black", linewidth = 0.8) +
  annotate("text", x = 11.5, y = 0.885, label = "Better",
           color = "black", size = 3.5, hjust = 0.5) +

  # Vertical arrow (pointing up - better mAP)
  annotate("segment", x = 10.5, xend = 10.5, y = 0.85, yend = 0.88,
           arrow = arrow(length = unit(0.3, "cm"), type = "closed"),
           color = "black", linewidth = 0.8) +
  annotate("text", x = 10.4, y = 0.865, label = "Better",
           color = "black", size = 3.5, hjust = 0.5, angle = 90) +

  # Highlight optimal region (upper-left quadrant)
  annotate("rect", xmin = 10, xmax = 15.5, ymin = 0.82, ymax = 0.90,
           alpha = 0.1, fill = "green") +



  # Theme and styling
  theme_minimal() +
  theme(
    # Text styling
    axis.title = element_text(size = 11, face = "bold"),
    axis.text = element_text(size = 10),

    # Grid styling
    panel.grid.major = element_line(color = "gray90", linewidth = 0.5),
    panel.grid.minor = element_line(color = "gray95", linewidth = 0.3),

    # Remove legend - we'll create custom table
    legend.position = "none",

    # Plot margins - space at bottom for legend
    plot.margin = margin(20, 20, 100, 20)
  )

# Create beautiful custom legend table with proper alignment
legend_data <- data.frame(
  Method = paste0("[", performance_data$letter, "] ", performance_data$model),
  mAP = sprintf("%.3f", performance_data$map_50),
  Time = sprintf("%.1f", performance_data$inference_time),
  stringsAsFactors = FALSE
)

# Convert to grob table for positioning
library(gridExtra)
library(grid)

# Create professionally styled table grob
table_grob <- tableGrob(
  legend_data,
  rows = NULL,  # No row names
  theme = ttheme_minimal(
    core = list(
      fg_params = list(fontsize = 9, hjust = c(0, 1, 1), x = c(0.05, 0.95, 0.95)),  # Left-align Method, right-align numbers
      bg_params = list(fill = c("white", "gray98"), col = "gray85", lwd = 0.5)  # Subtle alternating rows with borders
    ),
    colhead = list(
      fg_params = list(fontsize = 10, fontface = "bold", hjust = c(0, 1, 1), x = c(0.05, 0.95, 0.95)),
      bg_params = list(fill = "gray90", col = "gray70", lwd = 1)  # Header with subtle border
    )
  )
)

# Add subtle styling to table borders
table_grob$widths <- unit(c(1.8, 0.8, 0.8), "in")  # Adjust column widths for better proportions

# Position the table on the plot - bottom-right corner
p_with_legend <- p +
  annotation_custom(
    table_grob,
    xmin = 15.8, xmax = 19.3,
    ymin = 0.66, ymax = 0.72
  )

# ============================================================================
# SAVE FIGURE
# ============================================================================

# Print to screen for preview
print(p_with_legend)

# Save as high-resolution PNG
ggsave(
  filename = "/home/tiago/repos/camina/paper/img/figure3_yolo_performance_comparison.png",
  plot = p_with_legend,
  width = plot_width,
  height = plot_height,
  dpi = dpi,
  bg = "white"
)

# Save as PDF for publication
ggsave(
  filename = "/home/tiago/repos/camina/paper/img/figure3_yolo_performance_comparison.pdf",
  plot = p_with_legend,
  width = plot_width,
  height = plot_height,
  device = "pdf"
)

# ============================================================================
# SUMMARY STATISTICS
# ============================================================================

cat("\n=== YOLO Model Performance Summary ===\n")
cat("Model\t\tmAP@0.5\t\tInference Time (ms)\n")
cat("-----\t\t-------\t\t-------------------\n")
for(i in 1:nrow(performance_data)) {
  cat(sprintf("%-10s\t%.3f\t\t%.1f\n",
              performance_data$model[i],
              performance_data$map_50[i],
              performance_data$inference_time[i]))
}

cat("\nSelected Model: YOLO11n")
cat("\nReason: Optimal balance between accuracy (mAP@0.5 = ", yolo11n_map,
    ") and efficiency (", yolo11n_time, " ms)\n")
cat("Improvement over YOLOv5n baseline: +",
    round((yolo11n_map - yolov5n_map) * 100, 1),
    "% mAP@0.5, +",
    round(yolo11n_time - yolov5n_time, 1),
    " ms inference time\n")

cat("\nFigure saved to:")
cat("\n- PNG: /home/tiago/repos/camina/paper/img/figure3_yolo_performance_comparison.png")
cat("\n- PDF: /home/tiago/repos/camina/paper/img/figure3_yolo_performance_comparison.pdf")
cat("\n- R Code: /home/tiago/repos/camina/paper/img/figure3_yolo_performance_comparison.R\n")