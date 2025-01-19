import os
import pickle
import random
import time

import feedparser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from feedgen.feed import FeedGenerator
from datetime import datetime

# If you're actually using openllm's chat, keep it.
# For a stand-alone script, you might just omit this or mock it out.
try:
    from openllm import chat
except ImportError:
    def chat(prompt):
        """Fallback for openllm.chat if not installed."""
        # Return a trivial string so we don't break
        return "Sample Title"


# ------------------
# Global Config
# ------------------

USE_SAFARI = True  # Toggle True to use Safari (non-headless), or False to use headless Chrome

USERNAME = "..."
PASSWORD = "..."

# List of profiles to scrape
profiles = ["..."]  # Replace with actual profile handles

# Path to save cookies
COOKIES_FILE = "x_cookies.pkl"

# Path to save RSS feeds
RSS_OUTPUT_DIR = "/Users/stellar/Documents/Projects/MRoiban.github.io/rss"

# How many tweets to fetch from each profile
TWEETS_PER_PROFILE = 100

# Maximum scrolling attempts if fewer tweets are loaded
MAX_SCROLL_ATTEMPTS = 30

# After scraping each profile, wait a random amount of time (seconds)
AFTER_PROFILE_MIN_WAIT = 30  # lower bound of wait
AFTER_PROFILE_MAX_WAIT = 60  # upper bound of wait

# Fallback or additional tweet selectors
TWEET_SELECTORS = [
    "article[role='article']",
    "div[data-testid='tweet']",
]


# ------------------
# Helper Functions
# ------------------

def random_sleep(min_sec=2, max_sec=5):
    """Sleep for a random time between min_sec and max_sec."""
    import math
    sleep_time = random.uniform(min_sec, max_sec)
    print(f"Sleeping for ~{math.ceil(sleep_time)} seconds...")
    time.sleep(sleep_time)

def initialize_browser():
    """
    Initialize a browser. If USE_SAFARI is True, use Safari.
    Otherwise, use headless Chrome with a decent viewport.
    """
    if USE_SAFARI:
        driver = webdriver.Safari()
        driver.maximize_window()
    else:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        # Spoof user agent for a standard desktop Chrome
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        )
        driver = webdriver.Chrome(options=chrome_options)
        driver.maximize_window()
    return driver

def save_cookies(driver):
    with open(COOKIES_FILE, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    print("Cookies saved to file.")

def load_cookies(driver):
    """Load cookies from file, if they exist, to avoid re-login."""
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, "rb") as f:
            cookies = pickle.load(f)
        driver.get("https://x.com")
        for cookie in cookies:
            # Handle possible domain issues
            if "domain" in cookie and cookie["domain"].startswith("."):
                cookie["domain"] = "x.com"
            driver.add_cookie(cookie)
        print("Cookies loaded.")
        return True
    return False

def login_to_x(driver):
    """Perform login if cookies are missing or invalid."""
    driver.get("https://x.com/login")
    try:
        # Wait for the username field
        username_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "text"))
        )
        username_field.send_keys(USERNAME)
        username_field.send_keys(Keys.RETURN)
        random_sleep(2, 4)

        # Wait for the password field
        password_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        password_field.send_keys(PASSWORD)
        password_field.send_keys(Keys.RETURN)

        # Wait for login to complete (presence of user Profile icon, for instance)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label='Profile']"))
        )
        print("Logged in successfully!")
        save_cookies(driver)
    except Exception as e:
        print(f"Login failed: {e}")
        driver.quit()
        exit()

def navigate_to_profile(driver, profile):
    """Go to the X/Twitter profile page."""
    profile_url = f"https://x.com/{profile}"
    driver.get(profile_url)
    random_sleep(4, 7)
    print(f"Navigated to profile: {profile_url}")

def find_element_with_multiple_selectors(parent, selector_list):
    """
    Attempt to find an element using each CSS selector in `selector_list`.
    Return the first element that matches, or None if none match.
    """
    from selenium.common.exceptions import NoSuchElementException
    for selector in selector_list:
        try:
            return parent.find_element(By.CSS_SELECTOR, selector)
        except NoSuchElementException:
            pass
    return None

def find_tweet_elements(driver):
    """
    Return a combined list of unique tweet elements found
    using multiple tweet selectors.
    """
    all_tweets = []
    for sel in TWEET_SELECTORS:
        found = driver.find_elements(By.CSS_SELECTOR, sel)
        all_tweets.extend(found)
    # Remove duplicates
    return list(set(all_tweets))

def gather_latest_posts(driver, profile, n):
    """
    Gather up to n of the latest tweets from the user's timeline, 
    scrolling as needed. Returns a list of dicts:
    [{"link": <tweet_url>, "date": <ISO-8601 datetime>}...]
    """
    collected_posts = []
    seen_links = set()
    scroll_attempts = 0

    while len(collected_posts) < n and scroll_attempts < MAX_SCROLL_ATTEMPTS:
        # 1) Find all tweets currently in the DOM
        tweets = find_tweet_elements(driver)
        print(f"DEBUG: Found {len(tweets)} tweet elements in the DOM (raw).")

        # 2) Extract data for new tweets we haven't seen
        new_count_this_round = 0
        for tweet in tweets:
            # Attempt to find a tweet link specifically for this profile
            tweet_link_element = find_element_with_multiple_selectors(tweet, [
                f"a[href*='/{profile}/status/']",
                "time ~ a[href*='/status/']",
            ])
            if not tweet_link_element:
                # Possibly a recommended tweet from another user or ads
                continue

            link = tweet_link_element.get_attribute("href")
            if link in seen_links:
                continue  # already processed

            tweet_time_element = find_element_with_multiple_selectors(tweet, [
                "time",
                "a time",
            ])
            if not tweet_time_element:
                continue

            date = tweet_time_element.get_attribute("datetime")

            collected_posts.append({"link": link, "date": date})
            seen_links.add(link)
            new_count_this_round += 1

            if len(collected_posts) >= n:
                break  # we have enough now

        print(f"Collected {new_count_this_round} new tweets in this round. Total so far: {len(collected_posts)}")

        # 3) If not enough, scroll more
        if len(collected_posts) < n:
            old_total = len(collected_posts)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            random_sleep(3, 6)

            # Check if we gained any new tweets; if not, increment scroll_attempts
            if len(collected_posts) == old_total:
                scroll_attempts += 1
                print(f"No new tweets found after scrolling. Scroll attempts: {scroll_attempts}")
        else:
            # We reached desired n tweets
            break

    print(f"Found {len(collected_posts)} total tweets for {profile} after {scroll_attempts} scroll attempts.")
    return collected_posts[:n]  # Trim list if we got more than needed

def fetch_embed_codes(profile, driver, posts):
    """
    Open a second tab to get each tweet's embed code from publish.twitter.com
    without leaving the profile page in the main tab. 
    Modifies `posts` in place by adding an "embed" key.
    """
    if not posts:
        return posts  # Nothing to fetch

    os.makedirs(RSS_OUTPUT_DIR, exist_ok=True)
    rss_file = os.path.join(RSS_OUTPUT_DIR, f"{profile}.xml")

    _, existing_entries = load_existing_feed_entries(rss_file)

    # 1) Open a new blank tab
    driver.execute_script("window.open('about:blank','_blank');")
    time.sleep(1)

    main_tab = driver.window_handles[0]
    embed_tab = driver.window_handles[1]

    # 2) Switch to the new tab, fetch embed code for each tweet
    for idx, post in enumerate(posts, start=1):
        if post['link'] in existing_entries:
            print(f"Skipping existing tweet (already in RSS): {post['link']}")
            continue
        
        tweet_link = post["link"]
        embed_url = f"https://publish.twitter.com/?query={tweet_link}&widget=Tweet"

        driver.switch_to.window(embed_tab)
        driver.get(embed_url)
        random_sleep(3, 5)

        try:
            textarea = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea"))
            )
            embed_code = textarea.get_attribute("value")
            post["embed"] = embed_code
            print(f"Fetched embed #{idx} for {tweet_link}")
        except Exception as e:
            print(f"Failed to get embed code for {tweet_link}: {e}")
            post["embed"] = None

    # Switch back to main tab (optional)
    driver.switch_to.window(main_tab)
    return posts

def load_existing_feed_entries(rss_file):
    """
    Parse the existing RSS file for all old entries. Returns:
      - old_feed: feedparser's result
      - existing_entries: dict keyed by the entry guid
    """
    old_feed = None
    existing_entries = {}
    if os.path.exists(rss_file):
        old_feed = feedparser.parse(rss_file)
        for entry in old_feed.entries:
            # Typically, entry.id or entry.guid or entry.link can serve as a unique ID
            guid_val = getattr(entry, 'id', None) or getattr(entry, 'guid', None) or entry.link
            existing_entries[guid_val] = entry
    return old_feed, existing_entries

def generate_rss_feed(profile, posts):
    """
    1) Load any existing RSS file and re-add old entries (so we keep them).
    2) Append new tweets if not already present by GUID (the tweet link).
    3) Save updated feed to the same file.
    """
    os.makedirs(RSS_OUTPUT_DIR, exist_ok=True)
    rss_file = os.path.join(RSS_OUTPUT_DIR, f"{profile}.xml")

    old_feed, existing_entries = load_existing_feed_entries(rss_file)

    fg = FeedGenerator()
    fg.title(f"{profile}".capitalize())
    fg.link(href=f"https://x.com/{profile}", rel="alternate")
    fg.description(f"RSS feed of the latest tweets from {profile}.")
    fg.language("en")

    # Add old entries first
    if old_feed is not None:
        for entry in old_feed.entries:
            guid_val = getattr(entry, 'id', None) or getattr(entry, 'guid', None) or entry.link
            fe = fg.add_entry()
            fe.title(entry.title)
            fe.link(href=entry.link, rel="alternate")
            fe.guid(guid_val, permalink=True)
            fe.description(entry.description)
            if hasattr(entry, 'published'):
                fe.pubDate(entry.published)
            elif hasattr(entry, 'updated'):
                fe.pubDate(entry.updated)
            else:
                # Fallback if no date is found
                fe.pubDate(datetime.now().astimezone())

    # Add new items
    new_count = 0
    for post in posts:
        guid_val = post["link"]
        if guid_val in existing_entries:
            print(f"Skipping existing tweet: {guid_val}")
            continue

        fe = fg.add_entry()

        embed_code = post.get("embed", "")
        # Try using openllm or fallback if not installed
        try:
            # Prompt the LLM for a short title
            title_text = chat(
                f"come up with a short title for an rss entry for the following twitter post, "
                f"10 words or less, answer in plain text with only the title:{embed_code}"
            )
        except Exception:
            # Use date as fallback
            title_text = f"Tweeted on {post['date']}"

        fe.title(title_text.strip())
        fe.link(href=post["link"], rel="alternate")
        fe.guid(guid_val, permalink=True)
        fe.description(embed_code if embed_code else "No embed code available")
        fe.pubDate(post["date"])

        new_count += 1

    if new_count > 0:
        fg.rss_file(rss_file, pretty=True)
        print(f"Appended {new_count} new tweet(s). RSS feed updated at {rss_file}")
    else:
        print("No new tweets to add. RSS feed remains unchanged.")

# ------------------
# Main
# ------------------

def main():
    driver = initialize_browser()
    try:
        # Try loading cookies; if unsuccessful, log in
        if not load_cookies(driver):
            login_to_x(driver)

        for profile in profiles:
            # 1) Navigate to the profile
            navigate_to_profile(driver, profile)

            # 2) Gather tweets (links & timestamps)
            posts = gather_latest_posts(driver, profile, TWEETS_PER_PROFILE)

            # 3) Open a second tab and get the embed codes
            posts = fetch_embed_codes(profile, driver, posts)

            # 4) Generate or update the RSS feed
            generate_rss_feed(profile, posts)

            # Rate limit yourself: pause after each profile
            cool_down = random.uniform(AFTER_PROFILE_MIN_WAIT, AFTER_PROFILE_MAX_WAIT)
            print(f"Cooling down for {int(cool_down)} seconds before next profile.")
            time.sleep(cool_down)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
