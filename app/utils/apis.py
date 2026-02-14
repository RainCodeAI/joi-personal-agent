import requests
import os

def get_news_summary(api_key=None, query="technology"):
    if not api_key:
        api_key = os.getenv("NEWSAPI_KEY", "demo")
    if api_key == "demo":
        return "Demo: Top news - AI advances, tech stocks up."
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_key}&pageSize=3"
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        summary = " | ".join([a["title"] for a in articles[:3]])
        return f"News: {summary}"
    return "News unavailable."

def get_weather(location="New York", api_key=None):
    if not api_key:
        api_key = os.getenv("OPENWEATHER_KEY", "demo")
    if api_key == "demo":
        return "Demo: Sunny, 75°F."
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=imperial"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]
        return f"Weather in {location}: {desc}, {temp}°F."
    return "Weather unavailable."
