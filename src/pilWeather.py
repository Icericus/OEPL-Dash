import requests
import os
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import configparser

config = configparser.ConfigParser()
config.read("config.ini")

def getConfig(key, section='DEFAULT'):
    # Check if the environment variable is set
    env_value = os.getenv(key)
    if env_value is not None:
        return env_value
    # If not set, return the value from the config file
    return config.get(section, key)

def draw_text_centered(draw, position, text, font, fill=None):
    # Get text bounding box
    left, top, right, bottom = font.getbbox(text)
    text_width = right - left
    text_height = bottom - top

    # Calculate position for the top-left corner of the text
    x = position[0] - text_width // 2
    y = position[1] - text_height // 2

    # Draw the text
    draw.text((x, y), text, font=font, fill=fill)

def get_weather_data():
    """Fetch weather data from OpenMeteo API"""
    base_url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": getConfig("LATITUDE"),  # Default to Berlin, you should change this
        "longitude": getConfig("LONGITUDE"),
        "current": ["is_day", "temperature_2m", "weather_code", "wind_speed_10m", "wind_direction_10m", "precipitation_probability"],
        "hourly": ["temperature_2m", "weather_code", "wind_speed_10m", "precipitation_probability"],
        "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max", "sunrise", "sunset"],
        "timezone": "auto",
        "forecast_days": 5
    }

    response = requests.get(base_url, params=params)
    return response.json()

def getWeatherIcons(code, isDay=True):
    """Convert OpenMeteo weather code to weathericons.ttf character"""
    # Mapping based on WMO codes: https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM
    # You mentioned you already have this function, so I'm just creating a placeholder
    icon_map = {
        0: "\uf00d",  # Clear sky
        1: "\uf00c",  # Mainly clear
        2: "\uf002",  # Partly cloudy
        3: "\uf041",  # Overcast
        45: "\uf003",  # Fog
        48: "\uf063",  # Depositing rime fog
        51: "\uf01a",  # Light drizzle
        53: "\uf01a",  # Moderate drizzle
        55: "\uf01a",  # Dense drizzle
        56: "\uf0b5",  # Light freezing drizzle
        57: "\uf0b5",  # Dense freezing drizzle
        61: "\uf019",  # Slight rain
        63: "\uf019",  # Moderate rain
        65: "\uf019",  # Heavy rain
        66: "\uf0b5",  # Light freezing rain
        67: "\uf0b5",  # Heavy freezing rain
        71: "\uf01b",  # Slight snow fall
        73: "\uf01b",  # Moderate snow fall
        75: "\uf01b",  # Heavy snow fall
        77: "\uf015",  # Snow grains
        80: "\uf01a",  # Slight rain showers
        81: "\uf01a",  # Moderate rain showers
        82: "\uf01a",  # Violent rain showers
        85: "\uf01b",  # Slight snow showers
        86: "\uf01b",  # Heavy snow showers
        95: "\uf01d",  # Thunderstorm
        96: "\uf01e",  # Thunderstorm with slight hail
        99: "\uf01e",  # Thunderstorm with heavy hail
    }
    if not isDay and code <= 2:
        nightIcons = ["\uf02e", "\uf083", "\uf086"]
        return nightIcons[code]
    return icon_map.get(code, "\uf07b")  # Default: question mark

def format_time(time_str):
    """Format time from ISO to HH:MM"""
    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    return dt.strftime('%H:%M')

def get_wind_direction_icon(degrees):
    """Convert wind direction in degrees to an arrow icon"""
    # Assuming weathericons.ttf has directional arrows
    # This maps the wind direction to one of 8 compass points
    directions = ["\uf060", "\uf05e", "\uf061", "\uf05d", "\uf05c", "\uf05b", "\uf059", "\uf05a"]
    index = round(degrees / 45) % 8
    return directions[index]

def drawWeather(tagaccent, width=500, height=430):
    """Create the weather widget with the three sections"""
    # Create a new image with white background
    image = Image.new('P', (width, height))
    palette = [
        255, 255, 255,
        0, 0, 0,
        next(iter(tagaccent.values()))[0], next(iter(tagaccent.values()))[1], next(iter(tagaccent.values()))[2]
    ]
    image.putpalette(palette)
    draw = ImageDraw.Draw(image)

    # Load fonts
    try:
        bigweather_font = ImageFont.truetype("./fonts/weathericons.ttf", 100)
        weather_font = ImageFont.truetype("./fonts/weathericons.ttf", 45)
        large_font = ImageFont.truetype(getConfig("WEATHER_FONT"), 26)
        medium_font = ImageFont.truetype(getConfig("WEATHER_FONT"), 24)
        small_font = ImageFont.truetype(getConfig("WEATHER_FONT"), 18)
    except IOError:
        # Fallback to default fonts if custom fonts are not available
        bigweather_font = ImageFont.load_default()
        weather_font = ImageFont.load_default()
        large_font = ImageFont.load_default()
        medium_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Get weather data
    weather_data = get_weather_data()

    # Section heights
    section_height = height // 3

    # Draw section borders for visual clarity
    draw.line([(0, section_height), (width, section_height)], fill=1, width=2)
    draw.line([(0, section_height*2), (width, section_height*2)], fill=1, width=2)

    # Top Section - Current Weather
    current = weather_data["current"]
    daily = weather_data["daily"]

    # Weather icon
    icon = getWeatherIcons(current["weather_code"], current["is_day"])
    draw.text((10, 0), icon, fill=1, font=bigweather_font)

    # Current temperature
    temp_text = f"{current['temperature_2m']:.1f}°C"
    draw.text((150, 15), temp_text, fill=1, font=large_font)

    # Wind info
    wind_speed = f"{current['wind_speed_10m']:.1f} km/h"
    wind_icon = get_wind_direction_icon(current["wind_direction_10m"])
    draw.text((150, 50), f"Wind: {wind_speed}", fill=1, font=medium_font)
    draw.text((410, -20), wind_icon, fill=1, font=bigweather_font)

    # Precipitation chance
    precip_text = f"Precipitation: {current['precipitation_probability']}%"
    draw.text((150, 75), precip_text, fill=1, font=medium_font)

    # Sunrise/Sunset
    sunrise = format_time(daily["sunrise"][0])
    sunset = format_time(daily["sunset"][0])
    draw.text((150, 100), f"Sunrise: {sunrise} | Sunset: {sunset}", fill=1, font=medium_font)

    # Middle Section - 7-hour Forecast
    hourly = weather_data["hourly"]
    current_hour = datetime.now().hour
    hour_width = width // 7

    for i in range(7):
        # decorative dotted lines
        xdot = (i + 1) * hour_width
        if not i == 6:
            for y in range(section_height, section_height * 2, 7):
                draw.line((xdot, y, xdot, y), fill=1)

        hour_index = current_hour + i + 1
        if hour_index >= 24:
            hour_index = hour_index - 24

        x_pos = i * hour_width + hour_width // 2
        y_pos = section_height - 2

        # Time
        time_text = f"{hour_index:02d}:00"
        draw_text_centered(draw, (x_pos, y_pos + 10), time_text, fill=1, font=small_font)

        # Weather icon
        icon = getWeatherIcons(hourly["weather_code"][hour_index])
        draw.text((x_pos - 24, y_pos + 23), icon, fill=1, font=weather_font)

        # Temperature
        temp_text = f"{hourly['temperature_2m'][hour_index]:.1f}°C"
        draw_text_centered(draw, (x_pos, y_pos + 90), temp_text, fill=1, font=small_font)

        # Wind speed
        wind_text = f"{hourly['wind_speed_10m'][hour_index]:.0f} km/h"
        draw_text_centered(draw, (x_pos, y_pos + 110), wind_text, fill=1, font=small_font)

        # Precipitation
        precip_text = f"{hourly['precipitation_probability'][hour_index]}%"
        draw_text_centered(draw, (x_pos, y_pos + 130), precip_text, fill=1, font=small_font)

    # Bottom Section - 4-day Forecast
    day_width = width // 4

    for i in range(4):
        # decorative dotted lines
        xdot = (i + 1) * day_width
        for y in range(section_height * 2, section_height * 3, 7):
            draw.line((xdot, y, xdot, y), fill=1)

        day_index = i  # Start today
        x_pos = i * day_width + day_width // 2
        y_pos = section_height * 2 + 5

        # Date
        today = datetime.now()
        forecast_date = today + timedelta(days=day_index)
        date_text = forecast_date.strftime("%a %d.%m")
        draw_text_centered(draw, (x_pos, y_pos + 10), date_text, fill=1, font=medium_font)

        # Weather icon
        icon = getWeatherIcons(daily["weather_code"][day_index])
        draw.text((x_pos - 25, y_pos + 30), icon, fill=1, font=weather_font)

        # Temperature range
        temp_min = daily["temperature_2m_min"][day_index]
        temp_max = daily["temperature_2m_max"][day_index]
        temp_text = f"{temp_min:.1f}°C-{temp_max:.1f}°C"
        draw_text_centered(draw, (x_pos, y_pos + 95), temp_text, fill=1, font=small_font)

        # Precipitation
        precip_text = f"Precip: {daily['precipitation_probability_max'][day_index]}%"
        draw_text_centered(draw, (x_pos, y_pos + 120), precip_text, fill=1, font=small_font)

    return image

if __name__ == "__main__":
    tagaccent = {}
    tagaccent["yellow"] = [255,255,0]
    drawWeather(tagaccent).save("weather_dashboard.png")
    # weather_widget.show()  # Display the image
