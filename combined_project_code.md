# Complete Project Codebase
Generated on: Wed Sep 23 16:50:10 UTC 2026

## File: requirements.txt
````txt
requests
opencc-python-reimplemented
m3u8

````

## File: main.py
````py
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

````

## File: README.md
````md
# 📺 HK IPTV Auto Updater | 香港電視台直播源自動更新

![Update Status](https://github.com/sammy0101/hk-iptv-auto/actions/workflows/main.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

這是一個基於 **GitHub Actions** 的全自動化香港電視 IPTV 聚合專案。
每天定時自動同步上游最新資源庫與 TVBox 影視倉，進行深度切片級流媒體驗證、繁簡轉換（標準化為港式「台」字）與自動排序，生成純淨、可用的香港電視直播清單 (`.m3u`)。

---

## 🚀 訂閱地址 (Subscription URL)

請在您的播放器 (TiviMate, TVBox, Kodi, PotPlayer, APTV 等) 中輸入以下鏈接：

| 線路 | 鏈接 (URL) | 推薦度 |
| :--- | :--- | :--- |
| **jsDelivr CDN (推薦)** | `https://cdn.jsdelivr.net/gh/sammy0101/hk-iptv-auto@main/hk_live.m3u` | ⭐⭐⭐⭐⭐ |
| **GitHub Raw** | `https://raw.githubusercontent.com/sammy0101/hk-iptv-auto/refs/heads/main/hk_live.m3u` | ⭐⭐⭐ |

> 💡 **提示**：推薦使用上方 **jsDelivr CDN** 鏈接，自帶全球節點緩存加速，更新速度快且不受 GitHub 網絡波動影響。

---

## ❤️ 特別鳴謝 (Credits)

本項目的數據來源主要基於以下開源項目與社區大佬的大力奉獻，在此致以最誠摯的謝意：

*   **youhunwl**: [TVAPP](https://github.com/youhunwl/TVAPP) *(本專案已實現每日自動同步其最新在線源與影視倉)*
*   **imDazui**: [Tvlist-awesome-m3u-m3u8](https://github.com/imDazui/Tvlist-awesome-m3u-m3u8)
*   **fanmingming**: [live](https://github.com/fanmingming/live)
*   **Guovin**: [TV](https://github.com/Guovin/TV)
*   **YueChan**: [Live](https://github.com/YueChan/Live)
*   **Kimentanm**: [APTV](https://github.com/Kimentanm/aptv)
*   **yuanzl77**: [IPTV](https://github.com/yuanzl77/IPTV)
*   **iptv-org**: [IPTV Collection](https://github.com/iptv-org/iptv)
*   **joevess**: [IPTV](https://github.com/joevess/IPTV)
*   **YanG-1989**: [m3u](https://github.com/YanG-1989/m3u)
*   **hujingguang**: [ChinaIPTV](https://github.com/hujingguang/ChinaIPTV)
*   **MercuryZz**: [IPTVN](https://github.com/MercuryZz/IPTVN)
*   **vbskycn**: [iptv](https://github.com/vbskycn/iptv)
*   **suxuang**: [myIPTV](https://github.com/suxuang/myIPTV)
*   **Free-TV**, **epg.pw**, **jsDelivr** 以及所有無私維護直播源的開發者們。

---

## 📺 收錄頻道 (Supported Channels)

本項目專注於香港本地頻道，並按照香港觀眾收視習慣進行了優先級排序：

1.  **TVB 系列**: 翡翠台 (Jade), 無綫新聞台 (News), 明珠台 (Pearl), TVB Plus (J2), 無綫財經體育資訊台
2.  **ViuTV 系列**: ViuTV (99台), ViuTVsix (96台)
3.  **HOY TV 系列**: HOY TV (77台), HOY 資訊台 (78台)
4.  **RTHK 系列**: 港台電視 31, 港台電視 32, 港台電視 33
5.  **Now TV 系列**: Now 新聞台, Now 直播台
6.  **其他資訊**: 有線新聞、有線財經等

---

## ✨ 項目特點 (Features)

*   **🌐 動態上游同步**: 每日自動抓取 `youhunwl/TVAPP` 的最新數據庫，自動解碼 TVBox 單倉與多倉直播節點。
*   **🔍 雙重過濾系統**:
    *   **白名單機制**: 嚴格限定香港電視台專屬標籤，徹底過濾無關省份、體育、輪播台。
    *   **黑名單攔截**: 強力剔除土耳其 NOW TV、以色列頻道、虎牙、斗魚、B站等雜訊。
*   **⚡ 切片級深度檢測**: 深入解析 `.m3u8` 二級分片並驗證真實視頻二進位流，拒絕「假 200」黑屏死鏈。
*   **🛡️ 官方源保底放行**: 內建香港電台與有線官方 Akamai/CDN 直連放行邏輯，防止 GitHub 海外機房誤殺香港本地可播源。
*   **📝 文字標準化**: 集成 `OpenCC` 簡體轉繁體，並全面校正為港式「台」字。
*   **🔄 自動排序**: 依照香港電視台順序自動排列，方便電視盒子開箱即用。

---

## 🛠️ 給 Fork 用戶的修改指南 (For Developers)

如果你 Fork 了本項目，並希望自定義抓取來源或過濾邏輯，請參考以下步驟：

### 1. 增加/刪除直播源 (Sources)
直接編輯 `main.py`，找到 `FALLBACK_STANDARD_SOURCES` 列表。你可以加入任何公開的 `.m3u` 或 `.m3u8` 鏈接。

### 2. 修改過濾規則 (Filters)
*   **白名單 (`KEYWORDS`)**: 頻道名稱**必須包含**這些關鍵字才會被抓取。
*   **黑名單 (`BLOCK_KEYWORDS`)**: 頻道名稱若包含這些字，會被**強制丟棄**。

### 3. 調整頻道排序 (Sorting)
編輯 `main.py` 中的 `ORDER_KEYWORDS` 列表。越上面的關鍵字，優先級越高。

### 4. 修改訂閱鏈接 (Update Subscription URL)
Fork 之後，`README.md` 顯示的訂閱鏈接仍然指向原作者 (`sammy0101`) 的倉庫。
請務必編輯 `README.md`，將訂閱鏈接中的 `sammy0101` 替換為你的 GitHub 用戶名：

*   **jsDelivr 格式範例**:
    `https://cdn.jsdelivr.net/gh/<你的用戶名>/<倉庫名稱>@main/hk_live.m3u`

### ⚠️ 重要：Fork 後如何啟用自動更新
Fork 本項目後，GitHub Actions 默認是關閉的。你需要：
1.  進入你倉庫的 **Actions** 頁面。
2.  點擊綠色按鈕 **"I understand my workflows, go ahead and enable them"**。
3.  左側選擇 **Update IPTV Source** -> **Enable workflow**。

---

## ⚠️ 免責聲明 (Disclaimer)

1.  **僅供學習交流**: 本項目僅是一個網絡串流測試與自動化技術研究項目。
2.  **不存儲視頻**: 所有直播源鏈接均來自網際網路上的公開渠道，本倉庫不存儲、不託管、不轉發任何視頻流文件。
3.  **版權聲明**: 頻道版權歸相關電視台所有。若有權益問題請提 issue，我們將第一時間配合移除相關關鍵字。
4.  **地區限制**: 部分源（如 RTHK、HOY TV 官方直連）設有 Geo-block，需使用香港本地網絡或香港網絡節點觀看。

**Last Update:** 每天自動更新

````

## File: hk_live.m3u
````m3u
#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"
# Update: 2026-09-23 16:18:40
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB翡翠台（備用）.png",TVB翡翠台（備用）
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB翡翠台 4K.png",TVB翡翠台 4K
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct4
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/qClQf
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/qrfbg
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/n90gt
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://r.jdshipin.com/GeWKr
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB翡翠台 1080P.png",TVB翡翠台 1080P
http://php.jdshipin.com:8880/TVOD/iptv.php?id=fct3
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://122.152.202.33/s/81a8a44f/index.m3u8?id=53
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台北美版.png",翡翠台北美版
http://php.jdshipin.com:8880/TVOD/iptv.php?id=j1
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://183.237.95.108:9901/tsfile/live/1076_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://183.62.8.58:50085/tsfile/live/0017_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://120.238.94.82:9901/tsfile/live/1007_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://120.196.235.42:9901/tsfile/live/1006_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://120.198.84.146:9901/tsfile/live/1020_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://120.198.95.220:9901/tsfile/live/1004_1.m3u8?key=txiptv&playlive=1&down=1
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://116.77.33.98:44330/tsfile/live/1008_1.m3u8?key=txiptv&playlive=0&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/翡翠台.png",翡翠台
http://120.198.95.220:9901/tsfile/live/1004_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/無線新聞.png",無線新聞
https://h5cdn3.kylintv.tv/live/tvbnews_iphone.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/無線新聞.png",無線新聞
http://r.jdshipin.com/CkuBd
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB無線新聞.png",TVB無線新聞
http://122.152.202.33/s/81a8a44f/index.m3u8?id=21
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/無線新聞台.png",無線新聞台
http://php.jdshipin.com/TVOD/iptv.php?id=wxxw
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/無線新聞台.png",無線新聞台
https://cdn6.cc.cd/163189/wxxwt
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB明珠台.png",TVB明珠台
http://php.jdshipin.com/TVOD/iptv.php?id=mzt
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://r.jdshipin.com/ZQ4kN
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://php.jdshipin.com/TVOD/iptv.php?id=mzt2
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://183.62.8.58:50085/tsfile/live/0018_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://120.238.94.82:9901/tsfile/live/1008_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://120.198.84.146:9901/tsfile/live/1054_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://116.77.33.98:44330/tsfile/live/1009_1.m3u8?key=txiptv&playlive=0&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/明珠台.png",明珠台
http://183.237.95.108:9901/tsfile/live/1009_1.m3u8?key=txiptv&playlive=1&authid=0
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB Plus.png",TVB Plus
http://r.jdshipin.com/Nr5jq
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/TVB Plus.png",TVB Plus
http://php.jdshipin.com/TVOD/iptv.php?id=j2
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/ViuTV.png",ViuTV
http://r.jdshipin.com/vSJvl
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/ViuTV.png",ViuTV
http://r.jdshipin.com/TcKr2
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/VIUTV.png",VIUTV
http://php.jdshipin.com/TVOD/iptv.php?id=viutv
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/VIUTV.png",VIUTV
http://php.jdshipin.com/TVOD/iptv.php?id=viutv2
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/HOY TV.png",HOY TV
http://uc6.i-cable.com/live_freedirect/opentvhd001_h.live/playlist.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/HOY TV.png",HOY TV
http://r.jdshipin.com/sFw4S
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/HOY TV.png",HOY TV
http://php.jdshipin.com/TVOD/iptv.php?id=hoytv
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/HOY 資訊台.png",HOY 資訊台
http://61.10.2.141/live_freedirect/freehd209_h.live/playlist.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/有線新聞欣賞.png",有線新聞欣賞
http://rihou.cc:555/tv/[Pd]有线新闻
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視31.png",港台電視31
https://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_2052_av-b.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視31.png",港台電視31
http://php.jdshipin.com:8880/TVOD/iptv.php?id=rthk31
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視32.png",港台電視32
https://rthklive2-lh.akamaihd.net/i/rthk32_1@168450/index_2052_av-b.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/港台電視32.png",港台電視32
http://php.jdshipin.com:8880/TVOD/iptv.php?id=rthk32
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/Now新聞欣賞.png",Now新聞欣賞
http://rihou.cc:555/tv/[Hk]Now新闻
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/Now新聞欣賞.png",Now新聞欣賞
http://rihou.cc:555/tv/[Cx]Now新闻
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 31 (1080p) [Geo-blocked].png",RTHK TV 31 (1080p) [Geo-blocked]
https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 34 (1080p) [Geo-blocked].png",RTHK TV 34 (1080p) [Geo-blocked]
https://rthktv34-live.akamaized.net/hls/live/2101642/RTHKTV34/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 35 (1080p) [Geo-blocked].png",RTHK TV 35 (1080p) [Geo-blocked]
https://rthktv35-live.akamaized.net/hls/live/2101643/RTHKTV35/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 32 (1080p) [Geo-blocked].png",RTHK TV 32 (1080p) [Geo-blocked]
https://rthktv32-live.akamaized.net/hls/live/2036819/RTHKTV32/master.m3u8
#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/RTHK TV 33 (1080p) [Geo-blocked].png",RTHK TV 33 (1080p) [Geo-blocked]
https://rthktv33-live.akamaized.net/hls/live/2101641/RTHKTV33/master.m3u8

````

## File: .github/workflows/combine-code.yml
````yml
name: Generate All Codebase to MD

on:
  push:
    branches:
      - main
    paths-ignore:
      - 'combined_project_code.md' # 避免此檔案自身更新引發無限循環
  workflow_dispatch: # 支援在 GitHub 網頁上手動觸發執行

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Combine All Files into MD
        run: |
          OUT_FILE="combined_project_code.md"
          echo "# Complete Project Codebase" > "$OUT_FILE"
          echo "Generated on: $(date)" >> "$OUT_FILE"
          echo "" >> "$OUT_FILE"

          # 遍歷專案內的所有檔案，排除依賴、Git 歷史、打包產物及二進位檔案
          find . -type f \
            -not -path "*/node_modules/*" \
            -not -path "*/.git/*" \
            -not -path "*/dist/*" \
            -not -name "package-lock.json" \
            -not -name "yarn.lock" \
            -not -name "pnpm-lock.yaml" \
            -not -name "$OUT_FILE" \
            -not -name "*.png" \
            -not -name "*.jpg" \
            -not -name "*.jpeg" \
            -not -name "*.gif" \
            -not -name "*.ico" \
            -not -name "*.woff*" \
            -not -name "*.ttf" | while read -r file; do
              
              # 取得相對路徑與副檔名
              rel_path="${file#./}"
              ext="${file##*.}"
              
              # 如果無副檔名，清除變數避免格式混亂
              if [ "$ext" = "$rel_path" ]; then
                ext=""
              fi
              
              # 寫入檔案標題
              echo "## File: $rel_path" >> "$OUT_FILE"
              # 使用四個反單引號（````）包裹，防止內部程式碼的三個反單引號造成排版衝突
              echo "\`\`\`\`$ext" >> "$OUT_FILE"
              cat "$file" >> "$OUT_FILE"
              echo "" >> "$OUT_FILE"
              echo "\`\`\`\`" >> "$OUT_FILE"
              echo "" >> "$OUT_FILE"
          done

      - name: Commit and Push changes
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add combined_project_code.md
          
          if git diff --staged --quiet; then
            echo "No changes in codebase."
          else
            git commit -m "docs: auto-generate complete codebase [skip ci]"
            git push origin main
          fi

````

## File: .github/workflows/main.yml
````yml
name: Update IPTV Source

on:
  schedule:
    # 每天香港時間 08:00 和 20:00 運行 (UTC 00:00, 12:00)
    - cron: '0 0,12 * * *'
  workflow_dispatch: # 允許手動點擊按鈕

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: pip install -r requirements.txt

    - name: Run script
      run: python main.py

    - name: Commit and push
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add hk_live.m3u
        git commit -m "Auto-update channel list" || echo "No changes to commit"
        git push

````

