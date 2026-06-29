import requests
import sys
import json
import datetime

# --- Settings and Constants ---

# JSON address from which channels will be retrieved
JSON_URL = "https://vavoo.to/channels"

# URLs that form the basis of M3U8 links
BASE_PLAY_URL = "https://vavoo.to/play/"

# Name of the output file
OUTPUT_FILE = "vavoo_kanallar.m3u8"

# User-Agent to be used in requests (taken from your example code)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

# Main domain for Referer and Origin
VAVOO_DOMAIN = "https://vavoo.to/"


def fetch_channel_data(url):
    """
    It retrieves JSON channel data from the specified URL.
    """
    print(f"📡 Channel data is being retrieved from {url}...")
    headers = {
        'User-Agent': USER_AGENT,
        'Referer': VAVOO_DOMAIN
    }
    
    try:
        # Let's add a 15-second timeout.
        response = requests.get(url, headers=headers, timeout=15)
        
        # Check the HTTP 200 (Successful) status code.
        response.raise_for_status()
        
        # Process returned data as JSON
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
    """
    Converts the channel list to M3U8 format.
    """
    print("📺 Creating M3U8 content...")



# Header information for M3U8 file 
        m3u_lines = [
        "#EXTM3U",
        f"#EXT-X-USER-AGENT:{USER_AGENT}",
        f"#EXT-X-REFERER:{VAVOO_DOMAIN}",
        f"#EXT-X-ORIGIN:{VAVOO_DOMAIN.rstrip('/')}"
    ]
    
    created_count = 0
    

    # Convert each channel to M3U8 format
    for channel in channels:
        try:
            channel_id = channel.get('id')
            channel_name = channel.get('name', 'Unnamed Channel').strip()
            # We are using 'country' as the group title.
            channel_group = channel.get('country', 'Other Channels').strip()

            # Skip this channel if you are missing necessary information.
            if not channel_id or not channel_name:
                print(f"⚠️ Missing information (ID or Name): {channel} - Skipped.")
                continue

            # Generate the desired URL format
            # Example: https://vavoo.to/play/1735806851/index.m3u8
            m3u8_link = f"{BASE_PLAY_URL}{channel_id}/index.m3u8"
            
            # Create the EXTINF line
            line1 = f'#EXTINF:-1 tvg-logo="000" tvg-name="{channel_name}" group-title="{channel_group}",{channel_name}'
            line2 = '#EXTVLCOPT:http-referrer=https://vavoo.to/'
            extinf_line = line1 + '\n' + line2

           
            m3u_lines.append(extinf_line)
            m3u_lines.append(m3u8_link)
            created_count += 1

        
        except Exception as e:
            print(f"❌ Error processing channel: {channel} - Error: {e}")

    print(f"✅ {created_count} channels have been added to M3U8 format.")
    return m3u_lines, created_count

def save_m3u_file(lines, filename):
    """
    It saves the generated M3U8 content to a file.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\n📂 Success! All channels have been saved to the '{filename}' file.")
    except IOError as e:
        print(f"❌ File write error: {e}")
        print("Please ensure you have write permissions for the file.")

def main():
    """
    Main function.
    """
    print("🚀 VAVOO.TO M3U8 Generator Started...")
    
    # Step 1: Extract the Data
    channel_data = fetch_channel_data(JSON_URL)
    
    if not channel_data:
        print("❌ Channel data could not be received. Script is terminating.")
        sys.exit(1)
        
    # Step 2: Generate the M3U8 Content
    m3u_content, count = generate_m3u_file_content(channel_data)
    
    if count == 0:
        print("❌ No valid channel found to create. Script is terminating.")
        sys.exit(1)
        
    # Step 3: Save to File
    save_m3u_file(m3u_content, OUTPUT_FILE)
    
    print("\n🎉 Operation completed!")

# Call the main() function when the script is executed directly
if __name__ == "__main__":
    main()
