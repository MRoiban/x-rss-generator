# X (Twitter) to RSS Feed Generator

Automatically converts X/Twitter profiles into RSS feeds with embedded tweets. Built with Python and Selenium.

## Features

* Scrapes latest tweets from specified X profiles
* Generates RSS feeds with embedded tweets
* Smart cookie management for authentication
* Rate limiting and cool-down periods to avoid detection
* Supports both Safari and headless Chrome browsers
* Customizable number of tweets per profile
* Maintains existing RSS entries when updating feeds

## Technical Stack

* Python 3.x
* Selenium WebDriver
* OpenAI integration for tweet title generation
* FeedGenerator for RSS creation

## Configuration

Set up your credentials and preferences in .env:

```
USERNAME="your_x_username"

PASSWORD="your_x_password"

PROFILES="profile1,profile2"
```

## Requirements

`pip install -r requirements.txt`

## Usage

`python main.py`

The script will:

1. Log into X using provided credentials
2. Navigate through each profile
3. Collect latest tweets
4. Generate embedded tweet codes
5. Create/update RSS feeds in the output directory

## Note

This tool is intended for personal use and should be used responsibly in accordance with X's terms of service. Includes built-in delays and rate limiting to prevent server strain.
