Usage on Raspberry Pi 5:
  # Copy package to Pi
  scp -r raspberry_pi_deployment_all/ pi@raspberrypi:~/camina/

  # Run benchmark
 python raspberry_pi_inference_test.py --models-dir . --runs 20

  # Use in applications
  model = YOLO('yolo11n_ncnn', task='detect')
  results = model.predict('image.jpg')