import cv2
import numpy as np

cap = cv2.VideoCapture(0)  # or your camera device

# ORB detector
orb = cv2.ORB_create(2000)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

ret, prev_frame = cap.read()
prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
prev_kp, prev_des = orb.detectAndCompute(prev_gray, None)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    kp, des = orb.detectAndCompute(gray, None)
    
    matches = bf.match(prev_des, des)
    matches = sorted(matches, key=lambda x: x.distance)
    
    # Draw top matches
    matched = cv2.drawMatches(prev_frame, prev_kp, frame, kp, matches[:50], None, flags=2)
    cv2.imshow("Visual Odometry", matched)
    
    # Prepare for next iteration
    prev_frame, prev_gray, prev_kp, prev_des = frame, gray, kp, des
    
    if cv2.waitKey(1) == 27:  # ESC to quit
        break

cap.release()
cv2.destroyAllWindows()
