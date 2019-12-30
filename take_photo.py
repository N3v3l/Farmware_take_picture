#!/usr/bin/env python
'''Take a photo.

Take a photo using a USB or Raspberry Pi camera.
'''

import os
from time import time, sleep
import json
import requests
import numpy as np
import cv2
from farmware_tools import get_config_value


def farmware_api_url():
    major_version = int(os.getenv('FARMBOT_OS_VERSION', '0.0.0')[0])
    base_url = os.environ['FARMWARE_URL']
    return base_url + 'api/v1/' if major_version > 5 else base_url

def log(message, message_type):
    'Send a message to the log.'
    try:
        os.environ['FARMWARE_URL']
    except KeyError:
        print(message)
    else:
        log_message = '[take-photo] ' + str(message)
        headers = {
            'Authorization': 'bearer {}'.format(os.environ['FARMWARE_TOKEN']),
            'content-type': "application/json"}
        payload = json.dumps(
            {"kind": "send_message",
             "args": {"message": log_message, "message_type": message_type}})
        requests.post(farmware_api_url() + 'celery_script',
                      data=payload, headers=headers)

def rotate(image):
    'Rotate image if calibration data exists.'
    angle = float(os.environ['CAMERA_CALIBRATION_total_rotation_angle'])
    sign = -1 if angle < 0 else 1
    turns, remainder = -int(angle / 90.), abs(angle) % 90  # 165 --> -1, 75
    if remainder > 45: turns -= 1 * sign  # 75 --> -1 more turn (-2 turns total)
    angle += 90 * turns                   #        -15 degrees
    image = np.rot90(image, k=turns)
    height, width, _ = image.shape
    matrix = cv2.getRotationMatrix2D((int(width / 2), int(height / 2)), angle, 1)
    return cv2.warpAffine(image, matrix, (width, height))

def image_filename():
    'Prepare filename with timestamp.'
    epoch = int(time())
    filename = '{timestamp}.jpg'.format(timestamp=epoch)
    return filename

def upload_path(filename):
    'Filename with path for uploading an image.'
    try:
        images_dir = os.environ['IMAGES_DIR']
    except KeyError:
        images_dir = '/tmp/images'
    path = images_dir + os.sep + filename
    return path

def usb_camera_photo():
    'Take a photo using a USB camera.'
    # Settings
    camera_port = 0      # default USB camera port
    discard_frames = 20  # number of frames to discard for auto-adjust

    # Check for camera
    if not os.path.exists('/dev/video' + str(camera_port)):
        print("No camera detected at video{}.".format(camera_port))
        camera_port += 1
        print("Trying video{}...".format(camera_port))
        if not os.path.exists('/dev/video' + str(camera_port)):
            print("No camera detected at video{}.".format(camera_port))
            log("USB Camera not detected.", "error")

    # Open the camera
    camera = cv2.VideoCapture(camera_port)
    sleep(0.1)


    #setup camera parameters
    brightness = get_config_value(farmware_name='take-photo', config_name='brightness_val', value_type=float)
    contrast = get_config_value(farmware_name='take-photo', config_name='contrast_val', value_type=float)
    saturation = get_config_value(farmware_name='take-photo', config_name='saturation_val', value_type=float)
    hue = get_config_value(farmware_name='take-photo', config_name='hue_val', value_type=float)
    gain = get_config_value(farmware_name='take-photo', config_name='gain_val', value_type=float)
    width = get_config_value(farmware_name='take-photo', config_name='width_val', value_type=int)
    height = get_config_value(farmware_name='take-photo', config_name='height_val', value_type=int)
    
    if width != 640:
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, width);
        log("Resolution width:{}".format(width), "info")
    else:
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    
    if height != 480:
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height);
        log("Resolution height:{}".format(height), "info")
    else:
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if brightness != 10.0:
        camera.set(cv2.CAP_PROP_BRIGHTNESS, brightness)
        log("set brightness", "info")
    if contrast != 10.0:
        camera.set(cv2.CAP_PROP_CONTRAST, contrast)
        log("set contrast", "info")

    if saturation != 10.0:
        camera.set(cv2.CAP_PROP_SATURATION, saturation)
        log("set saturation", "info")

    if hue != 10.0:
        camera.set(cv2.CAP_PROP_HUE, hue)
        log("set hue", "info")

    if gain != 10.0:
        camera.set(cv2.CAP_PROP_GAIN, gain)
        log("set gain", "info")


    # Let camera adjust
    for _ in range(discard_frames):
        camera.grab()

    # Take a photo
    ret, image = camera.read()

    # Close the camera
    camera.release()

    # Output
    if ret:  # an image has been returned by the camera
        filename = image_filename()
        # Try to rotate the image
        try:
            final_image = rotate(image)
        except:
            final_image = image
        else:
            filename = 'rotated_' + filename
        # Save the image to file
        cv2.imwrite(upload_path(filename), final_image)
        print("Image saved: {}".format(upload_path(filename)))
    else:  # no image has been returned by the camera
        log("Problem getting image.", "error")

def rpi_camera_photo():
    'Take a photo using the Raspberry Pi Camera.'
    from subprocess import call
    try:
        filename_path = upload_path(image_filename())
        retcode = call(
            ["raspistill", "-w", "640", "-h", "480", "-o", filename_path])
        if retcode == 0:
            print("Image saved: {}".format(filename_path))
        else:
            log("Problem getting image.", "error")
    except OSError:
        log("Raspberry Pi Camera not detected.", "error")

if __name__ == '__main__':
    try:
        CAMERA = os.environ['camera']
    except (KeyError, ValueError):
        CAMERA = 'USB'  # default camera

    if 'RPI' in CAMERA:
        rpi_camera_photo()
    else:
        usb_camera_photo()
