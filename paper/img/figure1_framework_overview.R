# CAMINA Framework Overview - Figure 1
# Summary of the implemented framework
# Publication-ready scientific diagram using base R graphics

# Define color palette for different components
colors <- list(
  input = "#2E5984",          # Deep blue for input
  yolo11n = "#8B4B9C",        # Purple for YOLO11n
  yoloworld = "#D4742C",      # Orange for YOLO-World
  cyclist = "#47A76A",        # Green for cyclist logic
  fusion = "#C85450",         # Red for fusion
  edge = "#6B6B6B",          # Gray for edge deployment
  output = "#2E5984",         # Blue for output
  arrow = "#4A4A4A"          # Dark gray for arrows
)

# Create the main framework diagram
create_framework_diagram <- function() {

  # Set up the plotting area
  plot.new()
  plot.window(xlim = c(0, 10), ylim = c(0, 12))

  # Function to draw rounded rectangles
  draw_rounded_rect <- function(x, y, w, h, color, text, text_size = 0.8, text_color = "white") {
    rect(x - w/2, y - h/2, x + w/2, y + h/2,
         col = color, border = "white", lwd = 2)
    text(x, y, text, cex = text_size, col = text_color, font = 2)
  }

  # Function to draw arrows
  draw_arrow <- function(x1, y1, x2, y2, color = colors$arrow, lwd = 2) {
    arrows(x1, y1, x2, y2, col = color, lwd = lwd, length = 0.1, angle = 20)
  }

  # Function to draw text labels
  draw_label <- function(x, y, text, size = 0.7, color = "black", font = 1) {
    text(x, y, text, cex = size, col = color, font = font)
  }

  # Title
  text(5, 11.5, "Summary of the Implemented Framework", cex = 1.2, font = 2, col = "black")

  # 1. INPUT LAYER
  draw_rounded_rect(2, 10.5, 3, 0.8, colors$input, "INPUT LAYER")
  draw_label(2, 9.8, "Urban Images Dataset", 0.7, "black", 2)
  draw_label(2, 9.5, "1,895 images", 0.6, "grey30")
  draw_label(2, 9.2, "(1,295 ImageNet + 600 additional)", 0.6, "grey30")

  # 2. HYBRID DETECTION ARCHITECTURE
  draw_rounded_rect(5, 8.5, 6, 0.6, colors$fusion, "HYBRID DETECTION ARCHITECTURE")

  # YOLO11n Branch
  draw_rounded_rect(2.5, 7.2, 2.8, 0.8, colors$yolo11n, "YOLO11n Branch")
  draw_label(2.5, 6.6, "Primary Model", 0.7, "black", 2)
  draw_label(2.5, 6.3, "6 COCO Classes:", 0.6, "grey30")
  draw_label(2.5, 6.0, "Person + Bicycle (for cyclist logic)", 0.6, "grey30")
  draw_label(2.5, 5.7, "Car, Motorcycle, Bus, Truck", 0.6, "grey30")

  # YOLO-World Branch
  draw_rounded_rect(7.5, 7.2, 2.8, 0.8, colors$yoloworld, "YOLO-World Branch")
  draw_label(7.5, 6.6, "Secondary Model", 0.7, "black", 2)
  draw_label(7.5, 6.3, "3 Emerging Classes:", 0.6, "grey30")
  draw_label(7.5, 6.0, "E-scooter", 0.6, "grey30")
  draw_label(7.5, 5.7, "SUV", 0.6, "grey30")
  draw_label(7.5, 5.4, "Delivery van", 0.6, "grey30")

  # 3. RULE-BASED CYCLIST DETECTION
  draw_rounded_rect(5, 4.5, 4, 0.8, colors$cyclist, "RULE-BASED CYCLIST DETECTION")
  draw_label(5, 3.9, "Algorithm Innovation", 0.7, "black", 2)
  draw_label(5, 3.6, "Person + Bicycle spatial overlap analysis", 0.6, "grey30")
  draw_label(5, 3.3, "IoU threshold >= 0.20", 0.6, "grey30")
  draw_label(5, 3.0, "Geometric constraints -> Unified Cyclist class", 0.6, "grey30")

  # 4. DETECTION FUSION
  draw_rounded_rect(5, 2.0, 3.5, 0.6, colors$fusion, "DETECTION FUSION")
  draw_label(5, 1.5, "Parallel processing + NMS (IoU 0.5)", 0.6, "grey30")
  draw_label(5, 1.2, "9-class taxonomy mapping", 0.6, "grey30")

  # 5. EDGE DEPLOYMENT
  draw_rounded_rect(2.5, 0.5, 2.5, 0.6, colors$edge, "EDGE DEPLOYMENT", text_color = "white")
  draw_label(2.5, 0.0, "Raspberry Pi 5 (8GB)", 0.6, "grey30")
  draw_label(2.5, -0.3, "Real-time processing", 0.6, "grey30")

  # 6. OUTPUT
  draw_rounded_rect(7.5, 0.5, 2.5, 0.6, colors$output, "OUTPUT LAYER")
  draw_label(7.5, 0.0, "9-class urban mobility", 0.6, "grey30")
  draw_label(7.5, -0.3, "Privacy-preserving", 0.6, "grey30")

  # ARROWS showing data flow
  # Input to hybrid architecture
  draw_arrow(2, 10, 2.5, 8.0)
  draw_arrow(2, 10, 7.5, 8.0)

  # Hybrid branches to cyclist detection
  draw_arrow(2.5, 6.4, 4, 5.0)
  draw_arrow(7.5, 6.4, 6, 5.0)

  # Cyclist detection to fusion
  draw_arrow(5, 4.0, 5, 2.6)

  # Fusion to outputs
  draw_arrow(4, 1.7, 2.5, 1.1)
  draw_arrow(6, 1.7, 7.5, 1.1)

  # Add side annotations for key innovations
  draw_label(0.5, 4.5, "KEY\nINNOVATIONS", 0.8, colors$cyclist, 2)
  draw_label(0.5, 3.8, "- Hybrid architecture", 0.6, "black")
  draw_label(0.5, 3.5, "- Cyclist detection algorithm", 0.6, "black")
  draw_label(0.5, 3.2, "- Edge deployment focus", 0.6, "black")
  draw_label(0.5, 2.9, "- Comprehensive 9-class", 0.6, "black")
  draw_label(0.5, 2.6, "  urban mobility coverage", 0.6, "black")

  # Add technical specifications box
  rect(8.5, 8.8, 9.8, 10.2, col = "grey95", border = "grey70")
  draw_label(9.15, 9.8, "TECHNICAL SPECS", 0.7, "black", 2)
  draw_label(9.15, 9.5, "Models: YOLO11n + YOLO-World", 0.5, "grey30")
  draw_label(9.15, 9.3, "NMS IoU: 0.5", 0.5, "grey30")
  draw_label(9.15, 9.1, "Cyclist IoU: >=0.20", 0.5, "grey30")
  draw_label(9.15, 8.9, "Target: Real-time edge", 0.5, "grey30")
}

# Generate the figure
png("/home/tiago/repos/camina/paper/img/figure1_framework_overview.png",
    width = 12, height = 10, units = "in", res = 300, bg = "white")

create_framework_diagram()

dev.off()

# Also create a PDF version for publication
pdf("/home/tiago/repos/camina/paper/img/figure1_framework_overview.pdf",
    width = 12, height = 10, bg = "white")

create_framework_diagram()

dev.off()

cat("Figure 1 - CAMINA Framework Overview generated successfully!\n")
cat("Files saved:\n")
cat("- /home/tiago/repos/camina/paper/img/figure1_framework_overview.png\n")
cat("- /home/tiago/repos/camina/paper/img/figure1_framework_overview.pdf\n")
cat("- /home/tiago/repos/camina/paper/img/figure1_framework_overview.R\n")