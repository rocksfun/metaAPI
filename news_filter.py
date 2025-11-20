import requests
from datetime import datetime, timedelta

def is_high_impact_news_soon(minutes=15):
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        data = requests.get(url, timeout=10).json()
        now = datetime.utcnow()
        for event in data:
            event_time = datetime.strptime(event['date'], "%Y-%m-%d %H:%M:%S")
            if (abs((event_time - now).total_seconds()) < minutes*60 and 
                event['impact'] == "High" and 
                "USD" in event['currency']):
                return True
        return False
    except:
        return False