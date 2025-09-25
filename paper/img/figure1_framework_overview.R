# CAMINA Framework Overview - Figure 1
# Clean, minimal framework diagram for academic publication
# Publication-ready scientific diagram using base R graphics

# Define minimal grayscale palette for professional appearance
colors <- list(
  primary = "#2C2C2C",        # Dark gray for primary components
  secondary = "#5A5A5A",      # Medium gray for secondary elements
  tertiary = "#8A8A8A",       # Light gray for supporting elements
  background = "#F5F5F5",     # Very light gray for backgrounds
  text = "#1A1A1A",          # Near black for text
  arrow = "#404040"          # Dark gray for arrows
)

# Create the main framework diagram
create_framework_diagram <- function() {

  # Set up the plotting area with better proportions
  plot.new()
  plot.window(xlim = c(0, 12), ylim = c(0, 10))

  # Function to draw clean rectangles
  draw_rect <- function(x, y, w, h, color, text, text_size = 0.9, text_color = colors$text) {
    rect(x - w/2, y - h/2, x + w/2, y + h/2,
         col = color, border = colors$primary, lwd = 1.5)
    text(x, y, text, cex = text_size, col = text_color, font = 2)
  }

  # Function to draw clean arrows
  draw_arrow <- function(x1, y1, x2, y2, color = colors$arrow, lwd = 2) {
    arrows(x1, y1, x2, y2, col = color, lwd = lwd, length = 0.12, angle = 25)
  }

  # Function to draw text labels
  draw_label <- function(x, y, text, size = 0.75, color = colors$text, font = 1) {
    text(x, y, text, cex = size, col = color, font = font)
  }

  # NO TITLE - Removed as requested

  # 1. DATASET CREATION
  draw_rect(2, 8.5, 3.5, 0.8, colors$background, "DATASET CREATION")
  draw_label(2, 7.8, "Urban Images Dataset", 0.8, colors$text, 2)
  draw_label(2, 7.5, "1,895 images", 0.7, colors$secondary)
  draw_label(2, 7.2, "New classes: cyclist, e-scooter,", 0.65, colors$secondary)
  draw_label(2, 6.9, "SUV, delivery van", 0.65, colors$secondary)

  # 2. SEMI-AUTOMATED LABELING
  draw_rect(6, 8.5, 3.5, 0.8, colors$background, "SEMI-AUTOMATED LABELING")
  draw_label(6, 7.8, "Hybrid Autolabel Approach", 0.8, colors$text, 2)
  draw_label(6, 7.5, "YOLO-World for new classes", 0.7, colors$secondary)
  draw_label(6, 7.2, "Manual validation & refinement", 0.7, colors$secondary)
  draw_label(6, 6.9, "Quality assurance pipeline", 0.65, colors$secondary)

  # 3. YOLO TRAINING
  draw_rect(10, 8.5, 3.5, 0.8, colors$background, "YOLO TRAINING")
  draw_label(10, 7.8, "Model Training", 0.8, colors$text, 2)
  draw_label(10, 7.5, "YOLOv8n architecture", 0.7, colors$secondary)
  draw_label(10, 7.2, "9-class urban mobility", 0.7, colors$secondary)
  draw_label(10, 6.9, "Optimized for edge deployment", 0.65, colors$secondary)

  # 4. CYCLIST DETECTION LOGIC
  draw_rect(4, 6, 4.5, 0.8, colors$tertiary, "CYCLIST DETECTION LOGIC")
  draw_label(4, 5.3, "Spatial Relationship Analysis", 0.8, colors$text, 2)
  draw_label(4, 5.0, "Person + Bicycle IoU >= 0.20", 0.7, colors$secondary)
  draw_label(4, 4.7, "Geometric constraints validation", 0.7, colors$secondary)
  draw_label(4, 4.4, "Unified cyclist class creation", 0.65, colors$secondary)

  # 5. NCNN OPTIMIZATION
  draw_rect(8, 6, 3.5, 0.8, colors$background, "NCNN OPTIMIZATION")
  draw_label(8, 5.3, "Edge Optimization", 0.8, colors$text, 2)
  draw_label(8, 5.0, "ONNX to NCNN conversion", 0.7, colors$secondary)
  draw_label(8, 4.7, "ARM CPU optimization", 0.7, colors$secondary)
  draw_label(8, 4.4, "Memory efficiency tuning", 0.65, colors$secondary)

  # 6. RASPBERRY PI DEPLOYMENT
  draw_rect(3, 3.5, 3.5, 0.8, colors$primary, "RASPBERRY PI DEPLOYMENT", text_color = "white")
  draw_label(3, 2.8, "Edge Computing Platform", 0.8, "white", 2)
  draw_label(3, 2.5, "Raspberry Pi 5 (8GB RAM)", 0.7, colors$background)
  draw_label(3, 2.2, "Real-time processing", 0.7, colors$background)
  draw_label(3, 1.9, "Privacy-preserving", 0.65, colors$background)

  # 7. OUTPUT
  draw_rect(9, 3.5, 3.5, 0.8, colors$secondary, "OUTPUT DETECTION")
  draw_label(9, 2.8, "Urban Mobility Detection", 0.8, "white", 2)
  draw_label(9, 2.5, "9-class taxonomy", 0.7, colors$background)
  draw_label(9, 2.2, "Real-time inference", 0.7, colors$background)
  draw_label(9, 1.9, "Edge-optimized performance", 0.65, colors$background)

  # ARROWS showing workflow
  # Dataset → Labeling
  draw_arrow(3.75, 8.5, 4.25, 8.5)
  # Labeling → Training
  draw_arrow(7.75, 8.5, 8.25, 8.5)
  # Training → Cyclist Logic
  draw_arrow(10, 7.7, 6, 6.5)
  # Training → NCNN
  draw_arrow(10, 7.7, 8, 6.8)
  # Cyclist Logic → NCNN
  draw_arrow(6.25, 6, 6.75, 6)
  # NCNN → Deployment
  draw_arrow(8, 5.2, 5, 4.0)
  # Deployment → Output
  draw_arrow(4.75, 3.5, 7.25, 3.5)

  # KEY INNOVATIONS box
  rect(0.2, 0.5, 5.8, 1.8, col = colors$background, border = colors$tertiary, lwd = 1.5)
  draw_label(3, 1.6, "KEY INNOVATIONS", 0.9, colors$primary, 2)
  draw_label(1, 1.25, "- New urban mobility classes: cyclist, e-scooter, SUV, delivery van", 0.7, colors$text)
  draw_label(1, 1.0, "- Edge deployment focus: Raspberry Pi 5 optimization with NCNN", 0.7, colors$text)
  draw_label(1, 0.75, "- Hybrid autolabel approach: Semi-automated labeling methodology", 0.7, colors$text)
}

# Generate high-quality figure
png("/home/tiago/repos/camina/paper/img/figure1_framework_overview.png",
    width = 14, height = 10, units = "in", res = 300, bg = "white",
    type = "cairo", antialias = "default")

create_framework_diagram()

dev.off()

# Also create a PDF version for publication
pdf("/home/tiago/repos/camina/paper/img/figure1_framework_overview.pdf",
    width = 14, height = 10, bg = "white", colormodel = "gray")

create_framework_diagram()

dev.off()

cat("CAMINA Framework Overview - Clean Professional Version Generated!\n")
cat("Key improvements made:\n")
cat("✓ Removed title from figure\n")
cat("✓ Converted to minimal grayscale design\n")
cat("✓ Fixed framework flow: Dataset → Labeling → Training → Optimization → Deployment\n")
cat("✓ Updated key innovations to reflect actual contributions\n")
cat("✓ Removed confusing 'hybrid detection architecture' concept\n")
cat("✓ Created clean, professional academic publication design\n")
cat("\nFiles saved:\n")
cat("- /home/tiago/repos/camina/paper/img/figure1_framework_overview.png\n")
cat("- /home/tiago/repos/camina/paper/img/figure1_framework_overview.pdf\n")