import urllib.request
import urllib.error
import ssl
import re
import os

# 1. Daftar URL Sources Anda
URLS = [
    'https://mater.com.ua/ip/sport.m3u', 
    'https://dplay-silk.vercel.app/m3u/arena_sp.m3u',
]

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'playlist_clean.m3u')

# Konfigurasi SSL Context agar mengabaikan error sertifikat (seperti CURLOPT_SSL_VERIFYPEER false)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def fetch_playlist(url):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            if response.status == 200:
                return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching source {url}: {e}")
    return None

def is_channel_online(url):
    if not url.startswith(('http://', 'https://')):
        return False
    try:
        # Menggunakan metode HEAD agar hemat bandwidth dan cepat
        req = urllib.request.Request(url, headers=headers, method='HEAD')
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            # Lolos jika status HTTP 200, 301, atau 302
            if response.status in [200, 301, 302]:
                return True
    except urllib.error.HTTPError as e:
        # Menangkap error 403 (Restricted), 404, 500 dll
        print(f"Channel offline/restricted (HTTP {e.code})")
    except Exception:
        pass
    return False

def main():
    all_entries = []
    m3u_header = '#EXTM3U url-tvg="https://url-epg-anda.com" refresh="43200"'
    
    for source_url in URLS:
        print(f"Fetching source: {source_url} ...")
        content = fetch_playlist(source_url)
        if not content:
            continue
            
        lines = content.replace('\r', '').split('\n')
        current_entry = None
        pending_tags = []
        
        # Pola deteksi tag tambahan
        is_entry_tag = re.compile(r'^#(EXTVLCOPT:|KODIPROP:|EXTGRP:|EXTGENRE:)', re.IGNORECASE)
        
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line == '#EXTM3U':
                continue
                
            if line.startswith('#EXTINF:'):
                current_entry = {'extinf': line, 'extra_tags': list(pending_tags), 'url': ''}
                pending_tags.clear()
                continue
                
            if line.startswith('#'):
                if current_entry is not None:
                    current_entry['extra_tags'].append(line)
                else:
                    if is_entry_tag.match(line):
                        pending_tags.append(line)
                continue
                
            if current_entry is not None:
                current_entry['url'] = line
                print(f"Checking channel: {line[:50]}... ", end="", flush=True)
                
                if is_channel_online(current_entry['url']):
                    print("[ONLINE]")
                    all_entries.append(current_entry)
                else:
                    print("[OFFLINE/SKIPPED]")
                    
                current_entry = None
                pending_tags.clear()

    # Tulis hasil ke file fisik playlist_clean.m3u
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_header + '\n')
        for entry in all_entries:
            f.write(entry['extinf'] + '\n')
            if entry['extra_tags']:
                f.write('\n'.join(entry['extra_tags']) + '\n')
            f.write(entry['url'] + '\n\n')
            
    print(f"\nScan selesai! File '{OUTPUT_FILE}' berhasil diperbarui.")

if __name__ == '__main__':
    main()
