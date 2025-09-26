dev@camina-rpi1:~/camina$ python model/raspberry_pi_deployment_all/safe_timing_test.py
🛡️ CAMINA Safe NCNN Timing Test - Raspberry Pi 5
=======================================================
🖥️ Platform: Linux-6.12.25+rpt-rpi-2712-aarch64-with-glibc2.36
🔧 Python: 3.11.2

📸 Test image: 000000001053_jpg.rf.07079145a5cc3a104425edb556c7591b.jpg

🤖 Testing YOLOV5N...
📊 Size: 9.73 MB
🛡️ Running in isolated subprocess...
✅ Avg time: 66.42 ms
🚀 Avg FPS: 15.1
📈 Range: 66.23 - 66.74 ms
✔️ Success rate: 20/20
-------------------------------------------------------
🤖 Testing YOLOV8N...
📊 Size: 11.65 MB
🛡️ Running in isolated subprocess...
✅ Avg time: 64.83 ms
🚀 Avg FPS: 15.4
📈 Range: 64.57 - 65.60 ms
✔️ Success rate: 20/20
-------------------------------------------------------
🤖 Testing YOLOV10N...
📊 Size: 8.83 MB
🛡️ Running in isolated subprocess...
❌ Test failed - no valid results
🔍 Error details: layer torch.topk not exists or registered
...
💡 YOLOv10n has known NCNN compatibility issues (torch.topk)
   See yolov10n_ncnn/COMPATIBILITY_ISSUE.md for alternatives
-------------------------------------------------------
🤖 Testing YOLO11N...
📊 Size: 10.04 MB
🛡️ Running in isolated subprocess...
✅ Avg time: 64.90 ms
🚀 Avg FPS: 15.4
📈 Range: 64.46 - 66.74 ms
✔️ Success rate: 20/20
-------------------------------------------------------

🏆 SAFE TIMING RESULTS SUMMARY
=======================================================
Model      Size(MB)  Time(ms)   FPS      FPS/MB
-------------------------------------------------------
YOLOV8N    11.65     64.83      15.4     1.3
YOLO11N    10.04     64.90      15.4     1.5
YOLOV5N    9.73      66.42      15.1     1.6

💾 Results saved to: safe_timing_results.json