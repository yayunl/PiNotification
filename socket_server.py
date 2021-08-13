# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-

import time
import subprocess
import digitalio
import board
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789
import socket, json

# Socket 
s = socket.socket()
host = '' #ip of raspberry pi
port = 12333
s.bind((host, port))
s.listen(5)

  

# Configuration for CS and DC pins (these are FeatherWing defaults on M0/M4):
cs_pin = digitalio.DigitalInOut(board.CE0)
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = None

# Config for display baudrate (default max is 24mhz):
BAUDRATE = 64000000

# Setup SPI bus using hardware SPI:
spi = board.SPI()

# Create the ST7789 display:
disp = st7789.ST7789(
    spi,
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=BAUDRATE,
    width=240,
    height=240,
    x_offset=0,
    y_offset=80,
)

# Create blank image for drawing.
# Make sure to create image with mode 'RGB' for full color.
height = disp.width  # we swap height/width to rotate it to landscape!
width = disp.height
image = Image.new("RGB", (width, height))
rotation = 180

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))
disp.image(image, rotation)
# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height - padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0


# Alternatively load a TTF font.  Make sure the .ttf font file is in the
# same directory as the python script!
# Some other nice fonts to try: http://www.dafont.com/bitmap.php
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)

# Turn on the backlight
backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output()
backlight.value = True


# Socket connection
conn, addr = s.accept()
print('Connected by', addr)

recved, data = None, None

with conn:
    while True:
        recved = conn.recv(1024)
        try:
            data = json.loads(recved.decode('utf-8'))
        except:
            data = recved

        if data == b'bye':
            print("Bye!")
            break
        else:
            try:
                # Draw a black filled box to clear the image.
                draw.rectangle((0, 0, width, height), outline=0, fill=0)
                # Write four lines of text.
                y = top

                for project, vals in data.items():

                    # Shell scripts for system monitoring from here:
                    # https://unix.stackexchange.com/questions/119126/command-to-display-memory-usage-disk-usage-and-cpu-load
                    proj = f"Project: {project} ({vals.get('total')})"

                    draft_and_submit = vals.get('draft_and_submit')
                    analyze_and_clarify =  vals.get('analyze_and_clarify')
                    review_and_verify = vals.get('review_and_verify')

                    # cmd = "free -m | awk 'NR==2{printf \"Mem: %s/%s MB  %.2f%%\", $3,$2,$3*100/$2 }'"
                    # MemUsage = subprocess.check_output(cmd, shell=True).decode("utf-8")
                    #
                    # cmd = 'df -h | awk \'$NF=="/"{printf "Disk: %d/%d GB  %s", $3,$2,$5}\''
                    # Disk = subprocess.check_output(cmd, shell=True).decode("utf-8")
                    #
                    # cmd = "cat /sys/class/thermal/thermal_zone0/temp |  awk '{printf \"CPU Temp: %.1f C\", $(NF-0) / 1000}'"  # pylint: disable=line-too-long
                    # Temp = subprocess.check_output(cmd, shell=True).decode("utf-8")

                    draw.text((x, y), proj, font=font, fill="#FFFFFF")
                    y += font.getsize(proj)[1]

                    draw.text((x, y), draft_and_submit, font=font, fill="#FFFF00")
                    y += font.getsize(draft_and_submit)[1]

                    # Green
                    draw.text((x, y), analyze_and_clarify, font=font, fill="#00FF00")
                    y += font.getsize(analyze_and_clarify)[1]

                    draw.text((x, y), review_and_verify, font=font, fill="#0000FF")
                    y += font.getsize(review_and_verify)[1]

                    # draw.text((x, y), Temp, font=font, fill="#FF00FF")
                    # y += font.getsize(Disk)[1]
                    # y += font.getsize(review_and_verify)[1]
                    # top += y

                    # Display image.
                    disp.image(image, rotation)
                    time.sleep(0.1)

            except Exception as e:
                pass
