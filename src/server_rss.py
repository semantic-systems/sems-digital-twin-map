import feedparser
import json
import time
from dateutil import parser
from datetime import datetime, timedelta, timezone
import unicodedata
import requests

from data.connect import autoconnect_db
from data.model import Report

# how long to wait between requests (in seconds)
REQUEST_DELAY = 3600  # 1 hour

# how long to wait before timing out a request (in seconds)
TIMEOUT_DELAY = 60  # 1 minute

# set to True to print more information
VERBOSE = True

# user agent for the requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def get_rss_config(config_path='rss_config.json'):
    """
    Get the RSS configuration from the config file.
    """

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config

def get_entry_timestamp(entry) -> datetime:
    """
    Extracts the timestamp from the entry.
    """

    # dates can be specified in different fields
    # if available, use 'published_parsed' or 'updated_parsed'

    try:
        # Extracting timezone offset if available
        if 'published_parsed' in entry:
            year, month, day, hour, minute, second, wday, day_of_year, daylight_savings = entry['published_parsed']
            tz_offset = timedelta(hours=2)  # hardcoded offset by 2 hours
            return datetime(year, month, day, hour, minute, second) + tz_offset
        
        elif 'updated_parsed' in entry:
            year, month, day, hour, minute, second, wday, day_of_year, daylight_savings = entry['published_parsed']
            tz_offset = timedelta(hours=2)  # hardcoded offset by 2 hours
            return datetime(year, month, day, hour, minute, second) + tz_offset
        
        if 'published' in entry:
            date_str = entry['published']
        elif 'updated' in entry:
            date_str = entry['updated']
        elif 'created' in entry:
            date_str = entry['created']
        else:
            date_str = "Thu, 01 Jan 1970 00:00:00 +0000"
            if VERBOSE: print(f"No date field found in entry with fields {entry.keys()}")
    except Exception as e:
        if VERBOSE: print(f"Error extracting date: {str(e)}")
        date_str = "Thu, 01 Jan 1970 00:00:00 +0000"

    try:
        date_obj = parser.parse(date_str)
    except Exception as e:
        if VERBOSE: print(f"Error parsing date {date_str}: {str(e)}")
        return parser.parse("Thu, 01 Jan 1970 00:00:00 +0000")

    return date_obj

def get_report_identifiers() -> list[str]:
    """
    Get all identifiers from existing reports in the database.
    """

    engine, session = autoconnect_db()

    reports = session.query(Report).all()
    identifiers = [report.identifier for report in reports]

    session.close()
    engine.dispose()

    return identifiers

def check_duplicate(entry, existing_identifiers) -> bool:
    """
    Check if the entry is already in the database.
    Returns True if the entry is already in the database, False otherwise.
    """
    # check if the entry is already in the database
    if entry['id'] in existing_identifiers:
        return True

    return False

def fetch_feed(feed_url, timeout=TIMEOUT_DELAY) -> feedparser.FeedParserDict:
    """
    Fetch the feed data from the given URL with a specified timeout.

    Parameters:
    - feed_url (str): The URL of the feed.
    - timeout (int): The timeout in seconds for the request.

    Returns:
    feedparser.FeedParserDict: The parsed feed data.
    """

    headers = {
        'User-Agent': USER_AGENT
    }

    try:
        response = requests.get(feed_url, timeout=timeout, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        parsed_data = feedparser.parse(response.content)
        return normalize_unicode(parsed_data)
    # timeout exception
    except requests.exceptions.Timeout as e:
        if VERBOSE: print(f"Timeout fetching feed {feed_url}: {e}")
        return None
    # request exception
    except requests.exceptions.RequestException as e:
        if VERBOSE: print(f"Error fetching feed {feed_url}: {e}")
        return None
    # other exceptions
    except Exception as e:
        if VERBOSE: print(f"Error fetching feed {feed_url}: {e}")
        return None 

def normalize_unicode(data):
    """
    Recursively normalize unicode strings in the data.
    """
    try:
        if isinstance(data, dict) or isinstance(data, feedparser.FeedParserDict):
            return {k: normalize_unicode(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [normalize_unicode(i) for i in data]
        elif isinstance(data, str):
            normalized = unicodedata.normalize('NFKD', data)
            return normalized.encode('utf-8', 'ignore').decode('utf-8')
        else:
            return data
    except Exception as e:
        if VERBOSE: print(f"Error normalizing unicode {data} : {e}")
        return data

def filter_entries(feed_entries, keywords) -> list:
    """
    Filter the feed entries by the keywords.
    """

    filtered_entries = []

    for entry in feed_entries:
        for keyword in keywords:
            if keyword.lower() in entry['title'].lower() or keyword.lower() in entry['summary'].lower():
                filtered_entries.append(entry)
                break

    return filtered_entries

def entry_to_report(entry, source: str) -> Report:
    """
    Convert the entry to a db Report object.
    """

    report = Report(
        identifier = entry['id'],
        title = entry['title'],
        description = entry['summary'],
        link = entry['link'],
        source = source,
        timestamp = get_entry_timestamp(entry)
    )

    return report

if __name__ == '__main__':

    # get the RSS configuration
    rss_config = get_rss_config()

    endpoint = rss_config['endpoint']
    keywords = rss_config['keywords']

    while True:
        # get all existing identifiers
        # used to check for duplicates later
        existing_identifiers = get_report_identifiers()

        # request all feeds
        fetched_entries = fetch_feed(endpoint)['entries']
        filtered_entries = filter_entries(fetched_entries, keywords)

        # connect to the database
        engine, session = autoconnect_db()

        # count how many entries were saved
        saved_entries = 0

        for entry in filtered_entries:

            # check if the entry is already in the database
            if check_duplicate(entry, existing_identifiers):
                continue

            # convert the entry to a report object
            report = entry_to_report(entry, source=endpoint)
            session.add(report)
            saved_entries += 1
        
        session.commit()
        session.close()
        engine.dispose()

        if VERBOSE:
            # get the current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{timestamp}: Saved {saved_entries} new entr{'ies' if saved_entries != 1 else 'y'}")

        # wait before the next request
        time.sleep(REQUEST_DELAY)