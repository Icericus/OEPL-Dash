import os
import sys
import requests
import json
import configparser
from PIL import Image, ImageDraw, ImageFont

tagdict = {} # machash: (mac, hwtype)
hwtypedict = {} # hwtype: (width, height)

config = configparser.ConfigParser()
config.read("config.ini")

def getConfig(key, section='DEFAULT'):
    # Check if the environment variable is set
    env_value = os.getenv(key)
    if env_value is not None:
        return env_value
    # If not set, return the value from the config file
    return config.get(section, key)

def getTagdata():
    # Get the tagdb.json from the AP and extract the macs and hwTypes, then calculate the machash
    tagdb = requests.get("http://" + getConfig("ACCESSPOINTIP") + "/current/tagDB.json")
    hwtypeset = set()
    for tag in tagdb.json():
        match tag:
            case [{"mac": str() as mac, "hwType": int() as hwtype}]:
                if hwtype >= 224:
                    continue
                tagdict[mac] = hwtype
                hwtypeset.add(hwtype)
    # with the set of hwtypes we get the hardware json files from the AP for the resolution data
    for hwtype in hwtypeset:
        hwfilename = str("%0.2X" % hwtype) + ".json"
        typejson = requests.get("http://" + getConfig("ACCESSPOINTIP") + "/tagtypes/" + hwfilename)
        match typejson.json():
            case {"width": int() as width, "height": int() as height, "colortable": dict() as colortable}:
                accent = {k: v for k, v in colortable.items() if k in ['red', 'yellow']}
                hwtypedict[hwtype] = (width, height, accent)

def textShortener(draw, displaywidth, text, font):
    textbounds = draw.textbbox((0, 0), text, font=font)
    textlength = len(text)
    trailingdot = ""
    while textbounds[2] >= displaywidth - 35:
        textlength -= 1
        textbounds = draw.textbbox((0, 0), text[:textlength], font=font)
        trailingdot = "."
    return text[:textlength] + trailingdot

def displayUpload():
    mac = getConfig("MAC")
    hwtype = tagdict[mac]
    tagwidth = hwtypedict[hwtype][0]
    tagheight = hwtypedict[hwtype][1]
    tagaccent = hwtypedict[hwtype][2]
    imagepath = "./current/" + mac + ".jpg"
    payload = {"dither": 0, "mac": mac}
    url = "http://" + getConfig("ACCESSPOINTIP") + "/imgupload"
    print("Generating image for tag " + mac)
    image = Image.new('P', (tagwidth, tagheight))
    palette = [
        255, 255, 255,
        0, 0, 0,
        next(iter(tagaccent.values()))[0], next(iter(tagaccent.values()))[1], next(iter(tagaccent.values()))[2]
    ]
    image.putpalette(palette)
    draw = ImageDraw.Draw(image)

    # drawing stuff here

    rgb_image = image.convert('RGB')
    print("Exporting image to " + imagepath)
    rgb_image.save(imagepath, 'JPEG', quality="maximum")
    if getConfig("SKIPUPLOAD") == "False" or getConfig("SKIPUPLOAD") == "false":
        print("Uploading to " + url)
        files = {"file": open(imagepath, "rb")}
        response = requests.post(url, data=payload, files=files)
        if response.status_code == 200:
            print("Image uploaded successfully to " + mac)
        else:
            print("Failed to upload the image.")

getTagdata()
displayUpload()