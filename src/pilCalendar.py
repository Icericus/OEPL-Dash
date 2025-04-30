import os
import configparser
import caldav
from datetime import datetime, timedelta
import pytz
from PIL import Image, ImageDraw, ImageFont
import copy
import vobject

config = configparser.ConfigParser()
config.read("config.ini")

def getConfig(key, section='DEFAULT'):
    # Check if the environment variable is set
    env_value = os.getenv(key)
    if env_value is not None:
        return env_value
    # If not set, return the value from the config file
    return config.get(section, key)

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

def tzConvert(dt):
    """Convert a datetime from GMT to CET."""
    if dt.tzinfo is None:
        dt = pytz.timezone("GMT").localize(dt)
    return dt.astimezone(pytz.timezone(getConfig("TIMEZONE")))

def textShortener(draw, displaywidth, text, font):
    textbounds = draw.textbbox((0, 0), text, font=font)
    textlength = len(text)
    trailingdot = ""
    while textbounds[2] >= displaywidth:
        textlength -= 1
        textbounds = draw.textbbox((0, 0), text[:textlength], font=font)
        trailingdot = "."
    return text[:textlength] + trailingdot

def drawCalendar(tagaccent):
    client = caldav.DAVClient(getConfig("CALDAV_URL"), username=getConfig("CAL_USERNAME"), password=getConfig("CAL_PASSWORD"))
    principal = client.principal()
    calendars = principal.calendars()

    datetime_events = []
    date_only_events = []

    calendars = (cal for cal in calendars if cal.name in getConfig("CALENDAR_NAME").split(","))
    if not calendars:
        print(f"Calendar '{getConfig('CALENDAR_NAME')}' not found.")
        return

    # Get the current date and the date for the next day
    # today = datetime.now().date()
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    day_after_tomorrow = today + timedelta(days=2)

    # Define the time range for the events
    start_time = datetime.combine(today, datetime.min.time())
    end_time = datetime.combine(day_after_tomorrow, datetime.max.time())

    # Fetch events within the specified time range
    events = []
    for index, cal in enumerate(calendars):
        calevents = cal.date_search(start=start_time, end=end_time)
        for event in calevents:
            events.append((event, int(getConfig("CALENDAR_COLOR").split(",")[index])))

    # processing multiday events so that things stop exploding
    processed_datetime_events = []
    processed_dateonly_events = []
    for event, color in events:
        # print(f"preprocessing: summary: {event.vobject_instance.vevent.summary.value}, start:{event.vobject_instance.vevent.dtstart.value}, end:{event.vobject_instance.vevent.dtend.value}")
        vevent = event.vobject_instance.vevent
        start_time = vevent.dtstart.value
        end_time = vevent.dtend.value

        # datetime event check
        if isinstance(start_time, datetime) and isinstance(end_time, datetime):
            start_time = tzConvert(start_time)
            end_time = tzConvert(end_time)

            # multiday event check
            if start_time.date() != end_time.date():
                # create a copy for the first day (until midnight)
                day1_end = datetime.combine(start_time.date(), datetime.max.time()).replace(tzinfo=start_time.tzinfo)

                # create copy of original
                event_copy1 = copy.copy(event)
                event_copy1.vobject_instance = vobject.readOne(event.data)
                event_copy1.vobject_instance.vevent.dtend.value = day1_end
                processed_datetime_events.append((event_copy1, color))

                # create copy for second day1
                day2_start = datetime.combine(start_time.date() + timedelta(days=1), datetime.min.time()).replace(tzinfo=end_time.tzinfo)
                if end_time > start_time + timedelta(days=2):
                    day2_end = datetime.combine(start_time.date(), datetime.max.time().replace(tzinfo=end_time.tzinfo))
                else:
                    day2_end = end_time
                event_copy2 = copy.copy(event)
                event_copy2.vobject_instance = vobject.readOne(event.data)
                event_copy2.vobject_instance.vevent.dtstart.value = day2_start
                event_copy2.vobject_instance.vevent.dtend.value = day2_end

                processed_datetime_events.append((event_copy2, color))
                continue
            # not multiday
            processed_datetime_events.append((event, color))
        else:
            # This is a date-only (all-day) event
                event_start_date = start_time
                event_end_date = end_time

                # For all-day events, the end date is exclusive, so we subtract one day
                if event_end_date:
                    event_end_date = event_end_date - timedelta(days=1)

                # Check if event spans multiple days
                if event_end_date and event_start_date != event_end_date:
                    # Process each day of the multi-day all-day event
                    event_copy1 = copy.copy(event)
                    event_copy1.vobject_instance = vobject.readOne(event.data)
                    event_copy1.vobject_instance.vevent.dtstart.value = event_start_date
                    event_copy1.vobject_instance.vevent.dtend.value = event_start_date + timedelta(days=1)
                    processed_dateonly_events.append((event_copy1, color))

                    event_copy2 = copy.copy(event)
                    event_copy2.vobject_instance = vobject.readOne(event.data)
                    event_copy2.vobject_instance.vevent.dtstart.value = event_start_date + timedelta(days=1)
                    event_copy2.vobject_instance.vevent.dtend.value = event_start_date + timedelta(days=2)
                    processed_dateonly_events.append((event_copy2, color))
                else:
                    # Single day all-day event
                    processed_dateonly_events.append((event, color))

    #     print(f"summary: {event.vobject_instance.vevent.summary.value}, start:{event.vobject_instance.vevent.dtstart.value}, end:{event.vobject_instance.vevent.dtend.value}")

    processed_datetime_events = sorted(processed_datetime_events, key=lambda event: event[0].vobject_instance.vevent.dtstart.value)
    # drawing part
    width, height = 300, 480
    image = Image.new("P", (width, height))
    palette = [
        255, 255, 255,
        0, 0, 0,
        next(iter(tagaccent.values()))[0], next(iter(tagaccent.values()))[1], next(iter(tagaccent.values()))[2]
    ]
    image.putpalette(palette)
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype(getConfig("CALENDAR_FONT"), 13)
    column_width = width // 2
    hour_height = height / 27
    for i in range(4, 27):
        y = i * hour_height
        for x in range(0, width, 7):
            draw.line((x, y, x, y), fill=1)
    draw.line((0, 1 * hour_height, width, 1 * hour_height), fill=1)
    draw.line((0, 3 * hour_height, width, 3 * hour_height), fill=1)
    draw.line((column_width, 0, column_width, height), fill=1)
    draw.text((column_width // 2, 10), today.strftime("%A"), fill=1, font=font, anchor='mm')
    draw.text((column_width + column_width // 2, 10), tomorrow.strftime("%A"), fill=1, font=font, anchor='mm')

    # Allday events
    todayindex = 0
    tomorrowindex = 0
    for index, event in enumerate(processed_dateonly_events):
        # print(f"dateonly: summary: {event[0].vobject_instance.vevent.summary.value}, start:{event[0].vobject_instance.vevent.dtstart.value}, end:{event[0].vobject_instance.vevent.dtend.value}")
        event_start = event[0].vobject_instance.vevent.dtstart.value
        event_end = event[0].vobject_instance.vevent.dtend.value
        event_name = event[0].vobject_instance.vevent.summary.value
        event_color = event[1]

        if event_start == today and todayindex <= 2:
            x = 0
            y_start = (todayindex + 1) * hour_height + 1
            y_end = (todayindex + 2) * hour_height - 1
            todayindex = todayindex + 1
        elif event_start == tomorrow and tomorrowindex <= 2:
            x = column_width
            y_start = (tomorrowindex + 1) * hour_height + 1
            y_end = (tomorrowindex + 2) * hour_height - 1
            tomorrowindex = tomorrowindex + 1
        else:
            continue

        dith_rounded_rectangle(draw, [(x + 2, y_start), (x + column_width - 2, y_end)], 6, fill=event_color, outline=1, width=1)
        draw.text((x + 10, y_start), textShortener(draw, column_width - 20, event_name, font), fill=1, font=font)



    # Timed/Normal events
    overlapside = "L"
    for index, event in enumerate(processed_datetime_events):
        # print(f"normal: summary: {event[0].vobject_instance.vevent.summary.value}, start:{event[0].vobject_instance.vevent.dtstart.value}, end:{event[0].vobject_instance.vevent.dtend.value}")
        event_start = tzConvert(event[0].vobject_instance.vevent.dtstart.value)
        event_end = tzConvert(event[0].vobject_instance.vevent.dtend.value)
        event_name = event[0].vobject_instance.vevent.summary.value
        event_color = event[1]

        if event_start.date() == today:
            x = 0
        elif event_start.date() == tomorrow:
            x = column_width
        else:
            continue

        y_start = (event_start.hour + event_start.minute / 60 + 3) * hour_height
        y_end = (event_end.hour + event_end.minute / 60 + 3) * hour_height

        # print(f"event: {event_name}, ystart: {y_start}, ystop: {y_end}")
        # Check for overlaps with the previous event
        previous_overlap = False
        if index > 0:
            previous_event_end = tzConvert(processed_datetime_events[index - 1][0].vobject_instance.vevent.dtend.value)
            if event_start < previous_event_end:
                previous_overlap = True

        # Check for overlaps with the next event
        next_overlap = False
        if index < len(processed_datetime_events) - 1:
            next_event_start = tzConvert(processed_datetime_events[index + 1][0].vobject_instance.vevent.dtstart.value)
            if event_end > next_event_start:
                next_overlap = True

        if previous_overlap or next_overlap:
            if overlapside == "L":
                dith_rounded_rectangle(draw, [(x + 2, y_start), (x + column_width // 2 - 2, y_end)], 6, fill=event_color, outline=1, width=1)
                draw.text((x + 10, y_start + 2), textShortener(draw, column_width // 2 - 20, event_name, font), fill=1, font=font)
                overlapside = "R"
            elif overlapside == "R":
                dith_rounded_rectangle(draw, [(x + column_width // 2 + 2, y_start), (x + column_width - 2, y_end)], 6, fill=event_color, outline=1, width=1)
                draw.text((x + column_width // 2 + 10, y_start + 2), textShortener(draw, column_width // 2 - 20, event_name, font), fill=1, font=font)
                overlapside = "L"
        else:
            dith_rounded_rectangle(draw, [(x + 2, y_start), (x + column_width - 2, y_end)], 6, fill=event_color, outline=1, width=1)
            draw.text((x + 10, y_start + 2), textShortener(draw, column_width - 20, event_name, font), fill=1, font=font)

    return image

if __name__ == "__main__":
    tagaccent = {}
    tagaccent["yellow"] = [255,255,0]
    drawCalendar(tagaccent).save("calendar-dashboard.png")
