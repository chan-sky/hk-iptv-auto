import requests
import re
import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from opencc import OpenCC

# 初始化繁簡轉換器
cc = OpenCC('s2t')

# --- 設定區 ---

# 1. 來源列表
SOURCE_URLS = [
    "https://iptv.clbug.com/download.php?type=ipv4&category=%E9%A6%99%E6%B8%AF%E9%A2%91%E9%81%93&format=m3u",
    # 香港專用源 (優先)
    "https://raw.githubusercontent.com/s14685/tv/main/iptvhk.txt",
    "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/hk.m3u",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/HongKong.m3u8",
    "https://raw.githubusercontent.com/iptv-js/iptv/main/txt/ew_hk.txt",
    "https://raw.githubusercontent.com/chingithub1/iptv/main/Original",
    "https://raw.githubusercontent.com/LiuYi0526/IPTVnew/main/IPTVnews.txt",
    # 其他綜合源
    "https://raw.githubusercontent.com/Supprise0901/TVBox_live/refs/heads/main/live.txt",
    "https://raw.githubusercontent.com/Guovin/iptv-api/refs/heads/gd/output/result.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E5%8F%B0%E6%B9%BE%E9%A6%99%E6%B8%AF%E6%BE%B3%E9%97%A8202506.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E5%8F%B0%E6%B9%BE%E9%A6%99%E6%B8%AF%E6%BE%B3%E9%97%A82023.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E5%8F%B0%E6%B9%BE%E9%A6%99%E6%B8%AF%E6%BE%B3%E9%97%A82022-7.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E5%8F%B0%E6%B9%BE%E9%A6%99%E6%B8%AF%E6%BE%B3%E9%97%A82022-11.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E5%8F%B0%E6%B9%BE%E9%A6%99%E6%B8%AF%E6%B5%B7%E5%A4%96202005.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E5%8F%B0%E6%B9%BE%E9%A6%99%E6%B8%AF%E6%B5%B7%E5%A4%96202003.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E5%8F%B0%E6%B9%BE%E9%A6%99%E6%B8%AF%E6%B5%B7%E5%A4%96.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/1300%E4%B8%AA%E7%9B%B4%E6%92%AD%E6%BA%90%E5%85%A8%E9%83%A8%E6%9C%89%E6%95%88%E3%80%90%E5%85%A8%E9%83%A84k%E8%80%81%E7%94%B5%E8%84%91%E5%88%AB%E7%94%A8%E3%80%91.m3u8",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/5000%E4%B8%AA%E7%9B%B4%E6%92%AD%E6%BA%90%E5%85%A8%E9%83%A8%E6%9C%89%E6%95%88.m3u",
    "https://raw.githubusercontent.com/imDazui/Tvlist-awesome-m3u-m3u8/refs/heads/master/m3u/%E6%88%91%E7%9A%84%E6%92%AD%E6%94%BE%E6%BA%90.m3u8",
    "https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/ipv4.m3u",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    "https://raw.githubusercontent.com/yuanzl77/IPTV/main/live.m3u",
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://iptv-org.github.io/iptv/countries/hk.m3u",
    "https://raw.githubusercontent.com/joevess/IPTV/main/home.m3u8",
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/refs/heads/master/playlists/playlist_hong_kong.m3u8",
    "https://raw.githubusercontent.com/vbskycn/iptv/refs/heads/master/tv/iptv4.m3u",
    "https://epg.pw/test_channels_hong_kong.m3u",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/MercuryZz/IPTVN/refs/heads/Files/GAT.m3u"
]

# 2. 包含關鍵字 (必須包含這些字才抓取)
KEYWORDS = [
    "ViuTV", "HOY", "RTHK", "Jade", "Pearl", "J2", "J5", "Now", 
    "无线", "無線", "有线", "有線", "翡翠", "明珠", "港台", 
]

# 3. 黑名單關鍵字 (包含這些字的一律丟棄)
BLOCK_KEYWORDS = [
    # 來自你的日誌分析 (美國/英語台)
    "FOX", "Pluto", "Local", "NBC", "CBS", "ABC", "AXS", "Snowy", 
    "Reuters", "Mirror", "ET Now", "The Now", "Right Now", "News Now",
    "Chopper", "Wow", "UHD", "8K", "Career", "Comics", "Movies",
    "CBTV","Pearl","AccuWeather","Jadeed","Curiosity","Electric",
    "Warfare","Knowledge","MagellanTV","70s","80s","90s","Rock",
    "Winnipeg","Edmonton","RightNow","Times","True","Mindanow",
    "Jade","70's","80's","Romedy","WSOC","NowMedia",
    
    # 來自你的日誌分析 (大陸/澳門台)
    "浙江", "杭州", "西湖", "廣東", "珠江", "大灣區", # 排除 "杭州西湖明珠"
    "澳門", "Macau", "有線 CH", "互動新聞",           # 排除澳門有線
    "CCTV", "CGTN", "鳳凰", "凤凰", "華麗", "星河", "延时", "測試", "iHOY", "福建"
]

# 4. 【已更新】頻道排序優先級 (越上面越靠前)
ORDER_KEYWORDS = [
    "翡翠", "無線新聞", "明珠", "J2", "J5", "財經",  # TVB系列
    "ViuTV", "Viutv", "VIUTV", "ViuTV 6", "ViuTVsix",  # Viu系列 (包含你加入的大小寫變體)
    "HOY", "奇妙", "有線",                         # HOY/Cable系列
    "港台電視31", "RTHK 31",                      # RTHK系列
    "港台電視32", "RTHK 32",
    "Now新聞", "Now直播"                          # Now系列
]

# 5. 必備的官方/穩定源
STATIC_CHANNELS = [
    {"name": "港台電視31 (官方)", "url": "https://rthklive1-lh.akamaihd.net/i/rthk31_1@167495/index_2052_av-b.m3u8"},
    {"name": "港台電視32 (官方)", "url": "https://rthklive2-lh.akamaihd.net/i/rthk32_1@168450/index_2052_av-b.m3u8"}
]

# --- 邏輯區 ---

def check_url(url, retries=2, timeout=5):
    """檢測鏈接是否有效 - 增強版
    1. 多次重試處理暫時性錯誤
    2. 驗證 Content-Type 是否為視頻/串流格式
    3. 讀取實際數據確認不是錯誤頁面
    4. 檢查回應體大小是否合理
    """
    valid_content_types = [
        'video/', 'application/x-mpegurl', 'application/vnd.apple.mpegurl',
        'application/octet-stream', 'binary/octet-stream', 'application/dash+xml'
    ]
    
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, timeout=timeout, stream=True)
            
            if response.status_code != 200:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return False
            
            # 檢查 Content-Type
            content_type = response.headers.get('Content-Type', '').lower()
            is_valid_type = any(ct in content_type for ct in valid_content_types)
            
            # 讀取前 10KB 數據驗證
            data = b''
            for chunk in response.iter_content(chunk_size=1024):
                data += chunk
                if len(data) >= 10240:  # 讀取 10KB
                    break
            
            response.close()
            
            # 如果沒有數據，嘗試重試
            if len(data) == 0:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return False
            
            # 檢查是否為有效串流格式
            data_str = data[:4096].decode('utf-8', errors='ignore').strip()
            
            # 有效 M3U8 格式檢查
            if data_str.startswith('#EXTM3U') or data_str.startswith('#EXT-X-'):
                return True
            
            # 有效 M3U 格式檢查
            if data_str.startswith('#EXTINF'):
                return True
            
            # 有效視頻數據檢查 (檢查常見的視頻文件頭)
            if data[:4] in [b'\x00\x00\x00\x18', b'\x00\x00\x00\x1c', b'\x00\x00\x00\x20',
                           b'\x1a\x45\xdf\xa3',  # WebM/Matroska
                           b'\x52\x49\x46\x46',  # RIFF (AVI)
                           ]:
                return True
            
            # 如果 Content-Type 是視頻相關且有數據
            if is_valid_type and len(data) > 0:
                return True
            
            # 如果嘗試次數用盡仍無有效數據
            if attempt < retries:
                time.sleep(1)
                continue
            return False
            
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(1)
                continue
            return False
        except requests.exceptions.ConnectionError:
            if attempt < retries:
                time.sleep(1)
                continue
            return False
        except Exception:
            return False
    
    return False


def check_url_concurrent(channels, max_workers=10):
    """並行檢測多個頻道的有效性"""
    results = {}
    
    def check_single(ch):
        return ch['url'], check_url(ch['url'])
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_single, ch): ch for ch in channels}
        
        for future in as_completed(futures):
            url, is_valid = future.result()
            results[url] = is_valid
    
    return results

def get_sort_key(item):
    """計算頻道的排序權重"""
    name = item["name"]
    for index, keyword in enumerate(ORDER_KEYWORDS):
        if keyword in name:
            return index
    return 999

def fetch_and_parse():
    found_channels = []
    
    print("🚀 任務開始！正在抓取網路源...", flush=True)
    
    for index, source in enumerate(SOURCE_URLS):
        print(f"  [{index+1}/{len(SOURCE_URLS)}] 正在讀取: {source}", flush=True)
        try:
            r = requests.get(source, timeout=15)
            r.encoding = 'utf-8'
            
            if r.status_code != 200:
                print(f"    ⚠️ 無法讀取 (Status: {r.status_code})", flush=True)
                continue
            
            lines = r.text.split('\n')
            current_name = ""
            count_added = 0
            is_m3u = any(line.startswith('#EXTM3U') or line.startswith('#EXTINF') for line in lines[:10])
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if is_m3u:
                    # M3U 格式解析
                    if line.startswith("#EXTINF"):
                        match = re.search(r',(.+)$', line)
                        if match:
                            raw_name = match.group(1).strip()
                            converted_name = cc.convert(raw_name)
                            current_name = converted_name.replace('臺', '台')
                    elif line.startswith("http") and current_name:
                        if any(b.lower() in current_name.lower() for b in BLOCK_KEYWORDS):
                            current_name = ""
                            continue
                        if any(cc.convert(k).replace('臺', '台').lower() in current_name.lower() for k in KEYWORDS):
                            if not any(c['url'] == line for c in found_channels):
                                found_channels.append({"name": current_name, "url": line})
                                count_added += 1
                        current_name = ""
                else:
                    # TXT 格式解析 (名稱,URL 或 名稱@URL)
                    if ',' in line and line.startswith('http') == False:
                        parts = line.split(',', 1)
                        if len(parts) == 2:
                            name_part = parts[0].strip()
                            url_part = parts[1].strip()
                            if url_part.startswith('http'):
                                converted_name = cc.convert(name_part).replace('臺', '台')
                                if any(b.lower() in converted_name.lower() for b in BLOCK_KEYWORDS):
                                    continue
                                if any(cc.convert(k).replace('臺', '台').lower() in converted_name.lower() for k in KEYWORDS):
                                    if not any(c['url'] == url_part for c in found_channels):
                                        found_channels.append({"name": converted_name, "url": url_part})
                                        count_added += 1
                    elif line.startswith('http'):
                        # 純 URL，嘗試從 URL 推斷名稱
                        url_part = line.strip()
                        if url_part.startswith('http'):
                            for kw in KEYWORDS:
                                if cc.convert(kw).replace('臺', '台').lower() in url_part.lower():
                                    converted_name = cc.convert(kw).replace('臺', '台')
                                    if not any(c['url'] == url_part for c in found_channels):
                                        found_channels.append({"name": converted_name, "url": url_part})
                                        count_added += 1
                                    break
            
            print(f"    ✅ 抓取成功，新增 {count_added} 個頻道", flush=True)
            
        except Exception as e:
            print(f"    ❌ 抓取錯誤: {e}", flush=True)

    return found_channels

def generate_m3u(channels):
    total = len(channels)
    print(f"\n🔍 共找到 {total} 個潛在頻道，開始並行檢測有效性...", flush=True)
    
    final_list = []
    
    # 1. 加入靜態源
    for static in STATIC_CHANNELS:
        final_list.append(static)
        
    # 2. 並行檢測網路源
    validity_map = check_url_concurrent(channels, max_workers=10)
    
    for ch in channels:
        if validity_map.get(ch['url'], False):
            final_list.append(ch)
            print(f"  🟢 {ch['name']} - 有效", flush=True)
        else:
            print(f"  🔴 {ch['name']} - 失效", flush=True)

    # 3. 排序
    print("\n🔄 正在進行排序...", flush=True)
    final_list.sort(key=get_sort_key)

    # 4. 寫入文件
    content = '#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"\n'
    content += f'# Update: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
    
    for item in final_list:
        final_name = item["name"].replace('臺', '台')
        content += f'#EXTINF:-1 group-title="Hong Kong" logo="https://epg.112114.xyz/logo/{final_name}.png",{final_name}\n'
        content += f'{item["url"]}\n'

    with open("hk_live.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n🎉 全部完成！共收錄 {len(final_list)} 個有效頻道。", flush=True)

if __name__ == "__main__":
    candidates = fetch_and_parse()
    generate_m3u(candidates)
