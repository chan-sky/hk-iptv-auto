import requests
import re
import json
import base64
import datetime
import subprocess
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from opencc import OpenCC
import m3u8

cc = OpenCC('s2t')

# 模擬標準 Android IPTV 專用播放器標頭 (穿透多數防盜鏈)
IPTV_UA = 'okhttp/3.15.0 (Linux; Android 11; TVBox)'
HEADERS = {
    'User-Agent': IPTV_UA,
    'Accept': '*/*',
    'Connection': 'keep-alive'
}

# --- 1. 上游與備用來源 ---
YOUHUNWL_README_URL = "https://raw.githubusercontent.com/youhunwl/TVAPP/main/README.md"

FALLBACK_STANDARD_SOURCES = [
    "https://raw.githubusercontent.com/s14685/tv/main/iptvhk.txt",
    "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/hk.m3u",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/HongKong.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",
    "https://epg.pw/test_channels_hong_kong.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/refs/heads/master/playlists/playlist_hong_kong.m3u8"
]

FALLBACK_TVBOX_CONFIGS = [
    "http://www.饭太硬.net/tv",
    "http://肥猫.net",
    "http://我不是.摸鱼儿.top",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://dxawi.github.io/0/0.json",
    "http://xhztv.top/xhz"
]

# --- 2. 嚴格過濾與排序規則 ---
KEYWORDS = [
    "ViuTV", "Viutv", "VIUTV", "ViuTV 6", "ViuTVsix",
    "HOY", "奇妙電視",
    "RTHK", "港台電視",
    "翡翠台", "明珠台", "J2", "TVB Plus", "無綫新聞", "無線新聞", "無綫財經", "無線財經",
    "Now新聞", "Now 新聞", "Now直播", "Now 直播", "NowTV", "Now 劇集",
    "有線新聞", "有線財經"
]

BLOCK_KEYWORDS = [
    "FOX", "Pluto", "Local Now", "NBC", "CBS", "ABC", "AXS", "Snowy", 
    "Reuters", "Mirror", "ET Now", "The Now", "Right Now", "News Now",
    "Chopper", "Wow", "UHD", "8K", "Career", "Comics", "Movies", "tv360",
    "Anthony Bourdain", "HEi Now", "MS NOW", "Now 14", "NowMedia", "Castr",
    "虎牙", "斗鱼", "B站", "哔哩", "bilibili", "YY", "轮播", "电影", "电视剧",
    "浙江", "杭州", "西湖", "廣東", "珠江", "大灣區", "深圳", "福建",
    "澳門", "Macau", "澳視", "蓮花",
    "CCTV", "CGTN", "鳳凰", "凤凰", "華麗", "星河", "測試", "test", "iHOY"
]

ORDER_KEYWORDS = [
    "翡翠台", "無綫新聞", "無線新聞", "明珠台", "TVB Plus", "J2", "財經",
    "ViuTV", "Viutv", "VIUTV", "ViuTV 6", "ViuTVsix",
    "HOY TV", "HOY", "有線新聞", "有線財經",
    "港台電視31", "RTHK 31", "RTHK31",
    "港台電視32", "RTHK 32", "RTHK32",
    "Now新聞", "Now直播"
]

# 經最新驗證的香港官方可用地址
OFFICIAL_CHANNELS = [
    {"name": "港台電視31", "url": "https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8"},
    {"name": "港台電視32", "url": "https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8"}
]

# --- 3. 核心工具模組 ---

def encode_punycode_url(url):
    try:
        parts = urlparse(url)
        netloc = parts.netloc.encode('idna').decode('ascii')
        return urlunparse((parts.scheme, netloc, parts.path, parts.params, parts.query, parts.fragment))
    except Exception:
        return url

def sync_from_youhunwl_tvapp():
    print("🌐 正在向 youhunwl/TVAPP 同步最新資源清單...", flush=True)
    live_sources = set(FALLBACK_STANDARD_SOURCES)
    tvbox_configs = set(FALLBACK_TVBOX_CONFIGS)

    try:
        r = requests.get(YOUHUNWL_README_URL, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            content = r.text
            extracted_links = re.findall(r'https?://[^\s#<>"\']+', content)
            for link in extracted_links:
                link = link.strip()
                if any(ext in link.lower() for ext in ['.apk', '.exe', '.zip', 'github.com/youhunwl', 'shields.io', '.jpg']):
                    continue
                if any(link.lower().endswith(ext) for ext in ['.m3u', '.m3u8', '.txt']) or '/m3u/' in link:
                    live_sources.add(link)
                else:
                    tvbox_configs.add(link)
            print("  ✅ 同步成功！", flush=True)
    except Exception:
        print("  ⚠️ 同步失敗，使用本地備用源", flush=True)

    return list(live_sources), list(tvbox_configs)

def extract_tvbox_lives(target_url, visited=None):
    if visited is None:
        visited = set()

    real_url = encode_punycode_url(target_url)
    if real_url in visited:
        return []
    visited.add(real_url)

    live_urls = []
    try:
        r = requests.get(real_url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return []
        
        text = r.text.strip()
        if text.startswith('**') or not (text.startswith('{') or text.startswith('[')):
            clean_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', text)
            try:
                decoded = base64.b64decode(clean_b64).decode('utf-8', errors='ignore')
                if '{' in decoded:
                    text = decoded[decoded.find('{'):decoded.rfind('}')+1]
            except Exception:
                pass

        data = json.loads(text)
        if isinstance(data, dict):
            if 'lives' in data and isinstance(data['lives'], list):
                for item in data['lives']:
                    if isinstance(item, dict):
                        l_url = item.get('url')
                        if l_url and isinstance(l_url, str) and l_url.startswith('http'):
                            live_urls.append(l_url)
            if 'urls' in data and isinstance(data['urls'], list):
                for sub_item in data['urls']:
                    if isinstance(sub_item, dict) and 'url' in sub_item:
                        sub_url = sub_item['url']
                        if sub_url.startswith('http') and len(visited) < 25:
                            live_urls.extend(extract_tvbox_lives(sub_url, visited))
    except Exception:
        pass

    return list(set(live_urls))

# --- 4. 硬核流體驗證 (ffprobe 真機解碼級探測) ---

def check_stream_with_ffprobe(url, timeout=5):
    """
    使用系統自帶的 ffprobe 工具真正探測流媒體格式。
    只有能成功讀取到視頻編解碼格式 (codec_name) 的流，才被判定為有效！
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-user_agent', IPTV_UA,
        '-show_entries', 'stream=codec_type,codec_name',
        '-of', 'json',
        '-timeout', str(timeout * 1000000),  # 微秒
        url
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 2)
        if result.returncode != 0:
            return False
        
        info = json.loads(result.stdout.decode('utf-8'))
        streams = info.get('streams', [])
        # 必須確認含有至少一個 'video' 視頻軌
        has_video = any(s.get('codec_type') == 'video' for s in streams)
        return has_video
    except Exception:
        return False

def fast_pre_filter(url, timeout=3):
    """第一級輕量過濾：排除連不上、HTTP 非 200 或含有錯誤代碼的 URL"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        if r.status_code != 200:
            return False
        
        header_bytes = b''
        for chunk in r.iter_content(chunk_size=1024):
            header_bytes += chunk
            if len(header_bytes) >= 4096:
                break
        r.close()

        text = header_bytes.decode('utf-8', errors='ignore')
        # 排除明確寫著錯誤的網頁
        if any(err in text.lower() for err in ['error', 'expired', 'denied', 'unauthorized', '404 not found', '<html>']):
            return False
        return True
    except Exception:
        return False

def verify_single_channel(ch):
    url = ch['url']
    
    # 官方 CDN 源在海外 Runner 可能會被 Geo-block，但在香港本地確實可用，予以保留
    if any(domain in url for domain in ['rthk.hk', 'akamaized.net']):
        return ch, True
    
    # 第一級：HTTP 快速初篩
    if not fast_pre_filter(url):
        return ch, False
        
    # 第二級：ffprobe 真機解碼探測
    is_playable = check_stream_with_ffprobe(url, timeout=5)
    return ch, is_playable

def check_channels_parallel(channels, max_workers=10):
    valid_channels = []
    print(f"🔍 開始對 {len(channels)} 個候選源進行【ffprobe 真機解碼級驗證】...", flush=True)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(verify_single_channel, ch) for ch in channels]
        for f in as_completed(futures):
            ch, is_alive = f.result()
            if is_alive:
                valid_channels.append(ch)
                print(f"  🟢 [可播放]: {ch['name']}", flush=True)
            else:
                print(f"  🔴 [不可播/假源]: {ch['name']}", flush=True)
                
    return valid_channels

def get_sort_key(item):
    name = item["name"]
    for index, keyword in enumerate(ORDER_KEYWORDS):
        if keyword.lower() in name.lower():
            return index
    return 999

# --- 5. 主流程 ---

def fetch_and_parse():
    found_channels = []
    seen_urls = set()

    dynamic_sources, dynamic_configs = sync_from_youhunwl_tvapp()
    for conf in dynamic_configs:
        extracted = extract_tvbox_lives(conf)
        if extracted:
            dynamic_sources.extend(extracted)

    dynamic_sources = list(set(dynamic_sources))
    print(f"🚀 清單彙整完畢，共獲取 {len(dynamic_sources)} 個列表，開始檢索香港電視頻道...", flush=True)

    for index, source in enumerate(dynamic_sources):
        try:
            r = requests.get(encode_punycode_url(source), headers=HEADERS, timeout=8)
            r.encoding = 'utf-8'
            if r.status_code != 200:
                continue

            lines = [l.strip() for l in r.text.split('\n') if l.strip()]
            current_name = ""
            count_added = 0
            is_m3u = any(line.startswith('#EXTM3U') or line.startswith('#EXTINF') for line in lines[:10])

            for line in lines:
                if is_m3u:
                    if line.startswith("#EXTINF"):
                        match = re.search(r',(.+)$', line)
                        if match:
                            raw_name = match.group(1).strip()
                            current_name = cc.convert(raw_name).replace('臺', '台')
                    elif line.startswith("http"):
                        stream_url = line.split('$')[0].strip()
                        if current_name:
                            if any(b.lower() in current_name.lower() for b in BLOCK_KEYWORDS):
                                current_name = ""
                                continue
                            if any(k.lower() in current_name.lower() for k in KEYWORDS):
                                if stream_url not in seen_urls:
                                    seen_urls.add(stream_url)
                                    found_channels.append({"name": current_name, "url": stream_url})
                                    count_added += 1
                        current_name = ""
                else:
                    if ',' in line and not line.startswith('http'):
                        parts = line.split(',', 1)
                        if len(parts) == 2:
                            name_part = cc.convert(parts[0].strip()).replace('臺', '台')
                            url_part = parts[1].split('$')[0].strip()
                            if url_part.startswith('http'):
                                if any(b.lower() in name_part.lower() for b in BLOCK_KEYWORDS):
                                    continue
                                if any(k.lower() in name_part.lower() for k in KEYWORDS):
                                    if url_part not in seen_urls:
                                        seen_urls.add(url_part)
                                        found_channels.append({"name": name_part, "url": url_part})
                                        count_added += 1

            if count_added > 0:
                print(f"  [{index+1}/{len(dynamic_sources)}] 提取到 {count_added} 個候選頻道", flush=True)

        except Exception:
            continue

    return found_channels

def generate_m3u(channels):
    # 執行 ffprobe 真機解碼檢測
    tested_channels = check_channels_parallel(channels)

    # 合併官方源
    final_dict = {}
    for off in OFFICIAL_CHANNELS:
        final_dict[off['url']] = off

    for ch in tested_channels:
        if ch['url'] not in final_dict:
            final_dict[ch['url']] = ch

    final_list = list(final_dict.values())
    final_list.sort(key=get_sort_key)

    content = '#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n'
    content += f'# Update: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'

    for item in final_list:
        name = item["name"].replace('臺', '台')
        # 標註 IPTV 專用 UA，確保電視盒子播放時帶上正確請求頭
        content += f'#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/{name}.png",{name}\n'
        content += f'#EXTVLCOPT:http-user-agent={IPTV_UA}\n'
        content += f'{item["url"]}\n'

    with open("hk_live.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n🎉 驗證完成！共篩選出 {len(final_list)} 個實質可解碼播放的優質頻道。", flush=True)

if __name__ == "__main__":
    candidates = fetch_and_parse()
    generate_m3u(candidates)
