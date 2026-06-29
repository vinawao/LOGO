import requests
import sys
import json
import datetime

JSON_URL = "https://vavoo.to/channels"
BASE_PLAY_URL = "https://vavoo.to/play/"
OUTPUT_FILE = "vavoo_kanallar.m3u8"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
VAVOO_DOMAIN = "https://vavoo.to/"


def is_channel_online(channel: dict) -> bool:
    """
    Filter aktif/online.
    Sesuaikan field sesuai isi JSON yang kamu dapat dari JSON_URL.
    """
    # contoh kemungkinan field:
    active = channel.get("active", None)   # bool atau "1"/"true"
    status = channel.get("status", "")    # "online"/"active"/"offline"
    online = channel.get("online", None)  # bool atau "1"

    # jika active/online berupa boolean
    if isinstance(active, bool):
        return active
    if isinstance(online, bool):
        return online

    # jika active/online berupa angka/string
    def truthy(v):
        return str(v).strip().lower() in {"1", "true", "yes", "y", "online", "active"}

    if active is not None and truthy(active):
        return True
    if online is not None and truthy(online):
        return True

    # fallback pakai status string
    st = str(status).strip().lower()
    if st in {"online", "active", "on", "enabled", "ready"}:
        return True
    if st in {"offline", "inactive", "off", "disabled", "down"}:
        return False

    # jika field status tidak jelas, anggap offline (biar aman)
    return False


def fetch_channel_data(url):
    print(f"📡 Channel data is being retrieved from {url}...")
    headers = {
        'User-Agent': USER_AGENT,
        'Referer': VAVOO_DOMAIN
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Successfully retrieved {len(data)} channel data.")
        return data
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
    except requests.exceptions.Timeout:
        print("❌ Request timed out.")
    except json.JSONDecodeError:
        print("❌ The received data is not in JSON format.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    return None


def generate_m3u_file_content(channels):
    print("📺 Creating M3U8 content...")

    m3u_lines = [
        "#EXTM3U",
        f"#EXT-X-USER-AGENT:{USER_AGENT}",
        f"#EXT-X-REFERER:{VAVOO_DOMAIN}",
        f"#EXT-X-ORIGIN:{VAVOO_DOMAIN.rstrip('/')}",
        ""
    ]

    created_count = 0
    skipped_offline = 0

    for channel in channels:
        try:
            # FILTER: hanya online/aktif
            if not is_channel_online(channel):
                skipped_offline += 1
                continue

            channel_id = channel.get('id')
            channel_name = channel.get('name', 'Unnamed Channel').strip()
            channel_group = channel.get('country', 'Other Channels').strip()

            if not channel_id or not channel_name:
                print(f"⚠️ Missing information (ID or Name): {channel} - Skipped.")
                continue

            m3u8_link = f"{BASE_PLAY_URL}{channel_id}/index.m3u8"

            line1 = f'#EXTINF:-1 tvg-logo="000" tvg-name="{channel_name}" group-title="{channel_group}",{channel_name}'
            line2 = '#EXTVLCOPT:http-referrer=https://vavoo.to/'
            extinf_line = line1 + '\n' + line2

            m3u_lines.append(extinf_line)
            m3u_lines.append(m3u8_link)
            created_count += 1

        except Exception as e:
            print(f"❌ Error processing channel: {channel} - Error: {e}")

    print(f"✅ {created_count} channels added (offline skipped: {skipped_offline}).")
    return m3u_lines, created_count


def save_m3u_file(lines, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\n📂 Success! All channels have been saved to the '{filename}' file.")
    except IOError as e:
        print(f"❌ File write error: {e}")
        print("Please ensure you have write permissions for the file.")


def main():
    last_update = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("🚀 VAVOO.TO M3U8 Generator Started...")

    channel_data = fetch_channel_data(JSON_URL)
    if not channel_data:
        print("❌ Channel data could not be received. Script is terminating.")
        sys.exit(1)

    channel_data_sorted = sorted(
        channel_data,
        key=lambda x: (str(x.get('name', '')).strip().lower())
    )

    m3u_content, count = generate_m3u_file_content(channel_data_sorted)
    if count == 0:
        print("❌ No valid channel found to create. Script is terminating.")
        sys.exit(1)

    m3u_content.append(f"# Last-Update: {last_update}")
    save_m3u_file(m3u_content, OUTPUT_FILE)

    total_channels = count
    print(f"\n🎉 Operation completed!")
    print(f"🔢 Total channels: {total_channels}")
    print(f"🕒 Last update: {last_update}")


if __name__ == "__main__":
    main()
