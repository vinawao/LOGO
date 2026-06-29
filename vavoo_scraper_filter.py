import requests
import sys
import json
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================
# CONFIG
# ==========================

JSON_URL = "https://vavoo.to/channels"
BASE_PLAY_URL = "https://vavoo.to/play/"
OUTPUT_FILE = "vavoo_kanallar.m3u8"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

VAVOO_DOMAIN = "https://vavoo.to/"

MAX_THREADS = 20
TIMEOUT = 5

session = requests.Session()

session.headers.update({
    "User-Agent": USER_AGENT,
    "Referer": VAVOO_DOMAIN,
    "Origin": VAVOO_DOMAIN.rstrip("/")
})


# ==========================
# DOWNLOAD JSON
# ==========================

def fetch_channel_data():

    print("Downloading channels...")

    try:
        r = session.get(JSON_URL, timeout=20)

        r.raise_for_status()

        data = r.json()

        print(f"Total channels : {len(data)}")

        return data

    except Exception as e:

        print(e)

        return None


# ==========================
# ONLINE CHECK
# ==========================

def is_channel_online(channel):

    channel_id = channel.get("id")

    if not channel_id:

        return None

    url = f"{BASE_PLAY_URL}{channel_id}/index.m3u8"

    try:

        r = session.head(
            url,
            allow_redirects=True,
            timeout=TIMEOUT
        )

        if r.status_code == 405:

            r = session.get(
                url,
                stream=True,
                timeout=TIMEOUT
            )

        if r.status_code != 200:

            return None

        r = session.get(
            url,
            timeout=TIMEOUT
        )

        if "#EXTM3U" not in r.text:

            return None

        return channel

    except:

        return None


# ==========================
# FILTER ONLINE
# ==========================

def filter_online_channels(channels):

    online = []

    total = len(channels)

    print("\nChecking online channels...\n")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures = [
            executor.submit(is_channel_online, ch)
            for ch in channels
        ]

        checked = 0

        for future in as_completed(futures):

            checked += 1

            result = future.result()

            if result:

                online.append(result)

            print(
                f"\rChecked {checked}/{total} | Online : {len(online)}",
                end=""
            )

    print()

    return online


# ==========================
# CREATE M3U
# ==========================

def generate_m3u(channels):

    lines = [

        "#EXTM3U",

        f"#EXT-X-USER-AGENT:{USER_AGENT}",

        f"#EXT-X-REFERER:{VAVOO_DOMAIN}",

        f"#EXT-X-ORIGIN:{VAVOO_DOMAIN.rstrip('/')}",

        ""

    ]

    for ch in channels:

        name = ch.get("name", "Unknown").strip()

        group = ch.get("country", "Other").strip()

        cid = ch["id"]

        url = f"{BASE_PLAY_URL}{cid}/index.m3u8"

        lines.append(

            f'#EXTINF:-1 tvg-logo="000" tvg-name="{name}" group-title="{group}",{name}'

        )

        lines.append("#EXTVLCOPT:http-referrer=https://vavoo.to/")

        lines.append(url)

    return lines


# ==========================
# SAVE
# ==========================

def save_file(lines):

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        f.write("\n".join(lines))


# ==========================
# MAIN
# ==========================

def main():

    print("=" * 50)

    print("VAVOO M3U Generator")

    print("=" * 50)

    channels = fetch_channel_data()

    if not channels:

        sys.exit(1)

    channels = sorted(

        channels,

        key=lambda x: x.get("name", "").lower()

    )

    online = filter_online_channels(channels)

    if len(online) == 0:

        print("No online channels.")

        sys.exit(1)

    m3u = generate_m3u(online)

    last_update = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    m3u.append("")

    m3u.append(f"# Last-Update: {last_update}")

    save_file(m3u)

    print()

    print("=" * 50)

    print(f"Total JSON      : {len(channels)}")

    print(f"Online Channels : {len(online)}")

    print(f"Offline         : {len(channels)-len(online)}")

    print(f"Saved           : {OUTPUT_FILE}")

    print(f"Last Update     : {last_update}")

    print("=" * 50)


if __name__ == "__main__":

    main()
