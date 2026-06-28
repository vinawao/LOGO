import requests
import sys
import json

# --- Ayarlar ve Sabitler ---

# Kanalların çekileceği JSON adresi
JSON_URL = "https://vavoo.to/channels"

# M3U8 linklerinin temelini oluşturan URL
BASE_PLAY_URL = "https://vavoo.to/play/"

# Çıktı dosyasının adı
OUTPUT_FILE = "vavoo_kanallar.m3u8"

# İsteklerde kullanılacak User-Agent (Örnek kodunuzdan alındı)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

# Referer ve Origin için ana domain
VAVOO_DOMAIN = "https://vavoo.to/"


def fetch_channel_data(url):
    """
    Belirtilen URL'den JSON kanal verisini çeker.
    """
    print(f"📡 Kanal verisi {url} adresinden çekiliyor...")
    headers = {
        'User-Agent': USER_AGENT,
        'Referer': VAVOO_DOMAIN
    }
    
    try:
        # 15 saniye zaman aşımı ekleyelim
        response = requests.get(url, headers=headers, timeout=15)
        
        # HTTP 200 (Başarılı) durum kodunu kontrol et
        response.raise_for_status() 
        
        # Dönen veriyi JSON olarak işle
        data = response.json()
        print(f"✅ Başarıyla {len(data)} adet kanal bilgisi alındı.")
        return data
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Hatası: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Bağlantı Hatası: {e}")
    except requests.exceptions.Timeout:
        print("❌ İstek zaman aşımına uğradı.")
    except json.JSONDecodeError:
        print("❌ Alınan veri JSON formatında değil.")
    except Exception as e:
        print(f"❌ Beklenmedik bir hata oluştu: {e}")
        
    return None

def generate_m3u_file_content(channels):
    """
    Kanal listesini M3U8 formatına dönüştürür.
    """
    print("📺 M3U8 içeriği oluşturuluyor...")
    
    # M3U8 dosyası için başlık (header) bilgileri
    m3u_lines = [
        "#EXTM3U",
        f"#EXT-X-USER-AGENT:{USER_AGENT}",
        f"#EXT-X-REFERER:{VAVOO_DOMAIN}",
        f"#EXT-X-ORIGIN:{VAVOO_DOMAIN.rstrip('/')}"
    ]
    
    created_count = 0
    
    # Her bir kanalı M3U8 formatına çevir
    for channel in channels:
        try:
            channel_id = channel.get('id')
            channel_name = channel.get('name', 'İsimsiz Kanal').strip()
            # Grup başlığı olarak 'country' alanını kullanıyoruz
            channel_group = channel.get('country', 'Diğer Kanallar').strip()

            # Gerekli bilgiler eksikse bu kanalı atla
            if not channel_id or not channel_name:
                print(f"⚠️  Eksik bilgi (ID veya İsim): {channel} - Atlanıyor.")
                continue

            # İstenen URL formatını oluştur
            # Örnek: https://vavoo.to/play/1735806851/index.m3u8
            m3u8_link = f"{BASE_PLAY_URL}{channel_id}/index.m3u8"
            
            # EXTINF satırını oluştur
            extinf_line = f'#EXTINF:-1 tvg-name="{channel_name}" group-title="{channel_group}",{channel_name}'
            
            m3u_lines.append(extinf_line)
            m3u_lines.append(m3u8_link)
            created_count += 1
            
        except Exception as e:
            print(f"❌ Kanal işlenirken hata: {channel} - Hata: {e}")

    print(f"✅ {created_count} adet kanal M3U8 formatına eklendi.")
    return m3u_lines, created_count

def save_m3u_file(lines, filename):
    """
    Oluşturulan M3U8 içeriğini dosyaya kaydeder.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\n📂 Başarılı! Tüm kanallar '{filename}' dosyasına kaydedildi.")
    except IOError as e:
        print(f"❌ Dosya yazma hatası: {e}")
        print("Lütfen dosya yazma izinleriniz olduğundan emin olun.")

def main():
    """
    Ana çalışma fonksiyonu.
    """
    print("🚀 VAVOO.TO M3U8 Oluşturucu Başlatıldı...")
    
    # 1. Adım: Veriyi Çek
    channel_data = fetch_channel_data(JSON_URL)
    
    if not channel_data:
        print("❌ Kanal verisi alınamadı. Betik sonlandırılıyor.")
        sys.exit(1)
        
    # 2. Adım: M3U8 İçeriğini Oluştur
    m3u_content, count = generate_m3u_file_content(channel_data)
    
    if count == 0:
        print("❌ Oluşturulacak geçerli kanal bulunamadı. Betik sonlandırılıyor.")
        sys.exit(1)
        
    # 3. Adım: Dosyaya Kaydet
    save_m3u_file(m3u_content, OUTPUT_FILE)
    
    print("\n🎉 İşlem tamamlandı!")

# Betik doğrudan çalıştırıldığında main() fonksiyonunu çağır
if __name__ == "__main__":
    main()
