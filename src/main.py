import os
import requests
import configparser
from pilWeather import drawWeather
from pilCalendar import drawCalendar
from datetime import datetime
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

def dith_rounded_rectangle(draw, xy, radius, fill=0, outline=None, width=1):
    (x1, y1), (x2, y2) = xy
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    # Create a mask image with rounded corners
    mask = Image.new('L', (x2 - x1, y2 - y1), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, x2 - x1, y2 - y1), radius, fill=255)

    # Determine the fill color and whether it should be dithered
    if fill > 2:
        base_fill = fill - 3
        dither = True
    else:
        base_fill = fill
        dither = False

    # Create a pattern for dithering
    pattern = [
        [base_fill, 0],
        [0, base_fill]
    ]

    # Draw the dithered rectangle
    for y in range(y1, y2):
        for x in range(x1, x2):
            if mask.getpixel((x - x1, y - y1)) == 255:
                if dither:
                    pattern_value = pattern[(y - y1) % 2][(x - x1) % 2]
                    draw.point((x, y), fill=pattern_value)
                else:
                    draw.point((x, y), fill=base_fill)

    # Draw the outline if specified
    if outline is not None:
        draw.rounded_rectangle((x1, y1, x2, y2), radius, outline=outline, width=width)

def drawHeader():
    mac = getConfig("MAC")
    hwtype = tagdict[mac]
    tagwidth, tagheight = hwtypedict[hwtype][0], hwtypedict[hwtype][1]
    width, height = int(tagwidth * (5/8)), int(tagheight * 0.1)
    tagaccent = hwtypedict[hwtype][2]
    image = Image.new("P", (width, height))
    palette = [
        255, 255, 255,
        0, 0, 0,
        next(iter(tagaccent.values()))[0], next(iter(tagaccent.values()))[1], next(iter(tagaccent.values()))[2]
    ]
    image.putpalette(palette)
    font = ImageFont.truetype(getConfig("HEADER_FONT"), 34)
    draw = ImageDraw.Draw(image)

    dith_rounded_rectangle(draw, ((1, 1), (499, 47)), 10, fill=5, outline=1, width=2)
    today = datetime.now().strftime("%d.%m.%Y")
    draw.text((15, 4), today, fill=1, font=font)
    # anything else here?
    return image

def textShortener(draw, displaywidth, text, font):
    textbounds = draw.textbbox((0, 0), text, font=font)
    textlength = len(text)
    trailingdot = ""
    while textbounds[2] >= displaywidth:
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

    print("Drawing Date")
    image.paste(drawHeader())
    print("Drawing calendar")
    image.paste(drawCalendar(tagaccent), (500,0))
    print("Drawing weather")
    image.paste(drawWeather(tagaccent), (0, 48))

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
# drawCalendar().show()
displayUpload()
