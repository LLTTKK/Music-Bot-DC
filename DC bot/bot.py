import discord
from discord.ext import commands
from discord import app_commands, Interaction, SelectOption
import asyncio
import yt_dlp

# 需要安裝的套件：
# pip install aiohttp
# pip install yt-dlp
# pip install spotipy

import os
import psutil
import time
import datetime
import html
import unicodedata
import re
import urllib.parse
from functools import wraps
import logging
# Spotify 支援（無需 API 登入）
# 機器人配置 - 從環境變數讀取
TOKEN = os.getenv('DISCORD_TOKEN')
APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')
PUBLIC_KEY = os.getenv('DISCORD_PUBLIC_KEY')  # 用於 Slash Commands 和 Webhook 驗證

# 限制設定 - 從環境變數讀取
ALLOWED_SERVER_ID = os.getenv('ALLOWED_SERVER_ID')
ALLOWED_CHANNEL_ID = os.getenv('ALLOWED_CHANNEL_ID')
LOG_IT_CHANNEL_ID = os.getenv('LOG_IT_CHANNEL_ID')

# 超級管理員用戶 ID - 從環境變數讀取
HARD_ADMIN_USER_IDS_STR = os.getenv('HARD_ADMIN_USER_IDS', '')
HARD_ADMIN_USER_IDS = set()
if HARD_ADMIN_USER_IDS_STR:
    try:
        # 支援逗號分隔的多個 ID
        HARD_ADMIN_USER_IDS = {int(uid.strip()) for uid in HARD_ADMIN_USER_IDS_STR.split(',') if uid.strip()}
    except ValueError:
        print("⚠️ 警告：HARD_ADMIN_USER_IDS 格式不正確，應為逗號分隔的數字")
        HARD_ADMIN_USER_IDS = set()

# 環境變數驗證
def validate_environment():
    """驗證必要的環境變數是否存在"""
    required_vars = {
        'DISCORD_TOKEN': TOKEN,
        'DISCORD_APPLICATION_ID': APPLICATION_ID,
        'DISCORD_PUBLIC_KEY': PUBLIC_KEY,
        'ALLOWED_SERVER_ID': ALLOWED_SERVER_ID,
        'ALLOWED_CHANNEL_ID': ALLOWED_CHANNEL_ID,
        'LOG_IT_CHANNEL_ID': LOG_IT_CHANNEL_ID
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        print("❌ 錯誤：缺少必要的環境變數：")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n請在 Railway 環境變數中設定這些變數。")
        print("請參考 .env.example 檔案了解所需的環境變數。")
        return False
    
    print("✅ 所有必要的環境變數都已設定")
    return True

# yt-dlp 進階設定：cookies 與 proxy（可用 Railway/環境變數設定）
COOKIES_FILE = os.getenv('YTDLP_COOKIES_FILE', 'cookies.txt')  # Netscape 格式 cookies（自動偵測）
PROXY_URL = os.getenv('YTDLP_PROXY')  # 例如：http://user:pass@host:port 或 socks5://host:port
ANDROID_PO_TOKEN = os.getenv('YTDLP_YT_ANDROID_PO_TOKEN')
IOS_PO_TOKEN = os.getenv('YTDLP_YT_IOS_PO_TOKEN')

# Spotify 支援（無需 API）
SPOTIFY_ENABLED = True

def _resolve_cookies_file():
    try:
        print(f"🔍 檢查 cookies 檔案: {COOKIES_FILE}")
        if COOKIES_FILE and os.path.isfile(COOKIES_FILE):
            # 檢查檔案是否包含 YouTube 相關 cookies
            with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'youtube.com' in content or 'google.com' in content:
                    print(f"✅ cookies 檔案存在且包含 YouTube cookies: {COOKIES_FILE}")
                    return COOKIES_FILE
                else:
                    print(f"⚠️ cookies 檔案存在但無 YouTube cookies: {COOKIES_FILE}")
        else:
            print(f"❌ cookies 檔案不存在: {COOKIES_FILE}")
    except Exception as e:
        print(f"❌ cookies 檔案檢查錯誤: {e}")
    return None

# 設定語音連接日誌
logging.basicConfig(level=logging.INFO)
discord_logger = logging.getLogger('discord.voice_client')
discord_logger.setLevel(logging.DEBUG)

# 設定機器人權限意圖
intents = discord.Intents.default()
intents.message_content = True  # 需要在 Discord 開發者控制台啟用 "Message Content Intent"
intents.voice_states = True     # 語音頻道功能
intents.guilds = True          # 伺服器資訊
intents.guild_messages = True  # 伺服器訊息

bot = commands.Bot(command_prefix=['[', '[? '], intents=intents)
tree = bot.tree

# 忽略 CommandNotFound 錯誤（因為我們使用自定義訊息處理）
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # 靜默忽略 CommandNotFound 錯誤
        return
    # 其他錯誤正常處理
    print(f"指令錯誤: {error}")

# 全域變數：log-it 頻道快取
log_channel_cache = {}

# 全域變數：歌曲佇列（每個 guild 一個佇列）
song_queues = {}

# 全域變數：廣告過濾播放器（每個 guild 一個）
ad_filter_players = {}

# 全域變數：循環播放狀態（每個 guild 一個）
# 結構：{ guild_id: { 'enabled': bool, 'current_song': Optional[dict] } }
loop_states = {}

# 全域變數：語音斷線原因（每個 guild 一個）
# 用途：在 on_voice_state_update 區分「播放完自動離線 / 使用者要求 / 強制斷線」
disconnect_reasons = {}

# 全域變數：最後使用的音樂文字頻道（每個 guild 一個）
last_music_channels = {}

# 全域變數：編輯權限管理（每個 guild 一個）
edit_permissions = {}

# 全域變數：權限冷卻時間管理（每個 guild 一個）
permission_cooldowns = {}

# 廣告過濾播放器類別
class AdFilterPlayer:
    def __init__(self, voice_client, guild, channel):
        self.voice_client = voice_client
        self.guild = guild
        self.channel = channel
        self.current_song = None
        self.sponsor_segments = []
        self.is_playing = False
        self.skip_tasks = []
        self.autoreconnect_enabled = False  # 禁止自動重連

    async def play_with_ad_filter(self, song_info):
        """
        使用廣告過濾播放音樂
        """
        try:
            self.current_song = song_info
            self.is_playing = True
            
            # 獲取 SponsorBlock 資料
            video_id = extract_video_id(song_info['url'])
            if video_id:
                self.sponsor_segments = await get_sponsorblock_segments(video_id)
                if self.sponsor_segments:
                    print(f"找到 {len(self.sponsor_segments)} 個廣告時間段")
            
            # 開始播放
            player = await YTDLSource.from_url(song_info['url'], loop=bot.loop, stream=True)
            self.voice_client.play(player, after=self.on_song_finished)
            
            # 啟動廣告監控
            await self.start_ad_monitoring()
            
        except Exception as e:
            print(f"廣告過濾播放失敗: {e}")
            # 回退到正常播放
            await self.fallback_play(song_info)

    async def start_ad_monitoring(self):
        """
        啟動廣告監控任務
        """
        if not self.sponsor_segments:
            return
        
        # 創建廣告監控任務
        for segment in self.sponsor_segments:
            start_time = segment.get('start', 0)
            end_time = segment.get('end', 0)
            
            if start_time > 0 and end_time > start_time:
                # 設定定時器來跳過廣告
                asyncio.create_task(self.schedule_ad_skip(start_time, end_time))

    async def schedule_ad_skip(self, start_time, end_time):
        """
        定時跳過廣告
        """
        try:
            # 等待到廣告開始時間
            await asyncio.sleep(start_time)
            
            if self.is_playing and self.voice_client.is_playing():
                # 跳過到廣告結束時間
                await self.skip_to_time(end_time)
                print(f"已跳過廣告: {start_time}s -> {end_time}s")
                
        except Exception as e:
            print(f"廣告跳過失敗: {e}")

    async def skip_to_time(self, target_time):
        """
        跳過到指定時間
        """
        try:
            # 這裡需要實現時間跳過邏輯
            # 由於 Discord.py 的限制，我們使用重新播放的方式
            if self.current_song:
                # 重新播放從目標時間開始
                await self.restart_from_time(target_time)
        except Exception as e:
            print(f"時間跳過失敗: {e}")

    async def restart_from_time(self, start_time):
        """
        從指定時間重新開始播放
        """
        try:
            # 停止目前播放
            if self.voice_client.is_playing():
                self.voice_client.stop()
            
            # 重新創建播放器，從指定時間開始
            # 注意：這需要 yt-dlp 支援時間偏移
            player = await YTDLSource.from_url(
                f"{self.current_song['url']}&t={start_time}", 
                loop=bot.loop, 
                stream=True
            )
            self.voice_client.play(player, after=self.on_song_finished)
            
        except Exception as e:
            print(f"重新播放失敗: {e}")

    def on_song_finished(self, error):
        """
        歌曲播放完成回調
        """
        self.is_playing = False
        if error:
            print(f"播放錯誤: {error}")
        
        # 通知主程式播放下一首
        try:
            # after 回呼在子執行緒呼叫，需使用 thread-safe 提交到 bot.loop
            asyncio.run_coroutine_threadsafe(self.notify_next_song(), bot.loop)
        except Exception as e:
            print(f"提交下一首任務失敗: {e}")

    async def notify_next_song(self):
        """
        通知播放下一首歌曲
        """
        try:
            # 檢查循環播放狀態
            state = loop_states.get(self.guild.id) or {'enabled': False, 'current_song': None}
            loop_enabled = bool(state.get('enabled'))
            
            if loop_enabled and state.get('current_song'):
                # 循環播放：重新播放目前歌曲
                current_song = state['current_song']
                await self.play_with_ad_filter(current_song)
                await self.channel.send(f"🔄 循環播放: {current_song['title']}")
                await log_action(self.guild, f"循環播放 {current_song['title']} (廣告過濾)")
            else:
                # 正常播放：播放下一首
                await play_next_song(self.guild, self.voice_client, self.channel)
        except Exception as e:
            print(f"通知下一首失敗: {e}")

    async def fallback_play(self, song_info):
        """
        回退到正常播放
        """
        try:
            player = await YTDLSource.from_url(song_info['url'], loop=bot.loop, stream=True)
            self.voice_client.play(player, after=self.on_song_finished)
        except Exception as e:
            print(f"回退播放失敗: {e}")

# 取得音訊來源
class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        # 優先 HLS（m3u8），再退回其他音訊
        'format': 'bestaudio[protocol^=m3u8]/bestaudio/best',
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'extract_flat': 'in_playlist',
        'default_search': 'auto',
        'source_address': '0.0.0.0',
        'ignoreerrors': True,
        'skip_download': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        # cookies 與 proxy 將於初始化時注入
        'extractor_args': {
            'youtube': {
                'skip': [],
                # 僅使用 web 系列 client，避免登入/PO Token 要求
                'player_client': ['web'],
                'player_skip': [],
            }
        }
    }
    FFMPEG_OPTIONS = {
        # 增加連線與重試參數與超時
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -rw_timeout 15000000',
        'options': '-vn'
    }

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        # 動態注入 cookies 與 proxy
        ytdl_opts = dict(cls.YTDL_OPTIONS)
        # 注入 cookies 與 proxy
        cookie_file = _resolve_cookies_file()
        if cookie_file:
            ytdl_opts['cookiefile'] = cookie_file
            print(f"🍪 使用 cookies 檔案: {cookie_file}")
        if PROXY_URL:
            ytdl_opts['proxy'] = PROXY_URL
            print(f"🌐 使用代理: {PROXY_URL}")
        ytdl = yt_dlp.YoutubeDL(ytdl_opts)
        def extract():
            try:
                # 僅 web 家族：web -> web_creator -> embedded
                client_variants = [
                    {'youtube': {'player_client': ['web']}},
                    {'youtube': {'player_client': ['web_creator']}},
                    {'youtube': {'player_client': ['embedded']}},
                    {'youtube': {'player_client': ['ios']}},
                    {'youtube': {'player_client': ['android']}},
                ]

                for variant in client_variants:
                    opts = {**ytdl_opts, 'extractor_args': variant}
                    _ytdl = yt_dlp.YoutubeDL(opts)
                    try:
                        return _ytdl.extract_info(url, download=not stream)
                    except Exception as e2:
                        print(f"❌ 擷取失敗（variant={variant}）：{e2}")
                        continue
                return None
            except Exception as e:
                print(f"❌ yt-dlp 擷取失敗: {e}")
                return None
        data = await loop.run_in_executor(None, extract)
        if not data:
            raise RuntimeError("yt-dlp 無法擷取此連結，請稍後再試或更換影片。")
        if 'entries' in data:
            data = data['entries'][0]
        filename = data.get('url') if stream else ytdl.prepare_filename(data)
        if not filename:
            raise RuntimeError("找不到可播放的串流網址。")
        return cls(discord.FFmpegPCMAudio(filename, **cls.FFMPEG_OPTIONS), data=data)

    @classmethod
    async def search_youtube(cls, query, *, loop=None, max_results=5):
        loop = loop or asyncio.get_event_loop()
        
        # 直接使用 ytsearch 格式
        search_query = f"ytsearch{max_results}:{query}"
        
        # 搜尋配置（含 cookies / proxy 支援）
        search_opts = {
            'extract_flat': True,
            'quiet': False,
            'ignoreerrors': True,
            'no_warnings': False,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }
        # 搜尋同樣支援 cookies 與 proxy
        cookie_file = _resolve_cookies_file()
        if cookie_file:
            search_opts['cookiefile'] = cookie_file
            print(f"🍪(search) 使用 cookies 檔案: {cookie_file}")
        if PROXY_URL:
            search_opts['proxy'] = PROXY_URL
            print(f"🌐(search) 使用代理: {PROXY_URL}")
        
        try:
            print(f"🔍 搜尋: '{query}' -> '{search_query}'")
            ytdl = yt_dlp.YoutubeDL(search_opts)
            
            def extract_search():
                try:
                    return ytdl.extract_info(search_query, download=False)
                except Exception as e:
                    print(f"❌ yt-dlp 錯誤: {e}")
                    return None
            
            data = await loop.run_in_executor(None, extract_search)
            
            print(f"📊 搜尋結果: {type(data)}")
            if isinstance(data, dict):
                print(f"📊 結果鍵值: {list(data.keys())}")
                
                if 'entries' in data and data['entries']:
                    valid_entries = []
                    for entry in data['entries']:
                        if entry and entry.get('id') and entry.get('title'):
                            valid_entries.append(entry)
                    
                    print(f"✅ 有效結果: {len(valid_entries)}")
                    for i, entry in enumerate(valid_entries[:3]):
                        print(f"  {i+1}. {entry.get('title', 'No title')}")
                    
                    return valid_entries[:max_results]
            
            print("❌ 搜尋無結果")
            return []
            
        except Exception as e:
            print(f"❌ 搜尋異常: {e}")
            return []

async def get_log_channel(guild):
    # 若指定了固定日誌頻道，直接回傳該頻道
    try:
        if LOG_IT_CHANNEL_ID:
            channel = bot.get_channel(int(LOG_IT_CHANNEL_ID))
            if channel and channel.guild.id == guild.id:
                return channel
    except Exception:
        pass
    # 退回快取邏輯
    return log_channel_cache.get(guild.id)

async def update_log_channel_cache():
    # 檢查所有伺服器的 log-it 頻道
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name="log-it")
        if channel:
            log_channel_cache[guild.id] = channel
        else:
            log_channel_cache[guild.id] = None

@bot.event
async def on_ready():
    print(f'已登入為 {bot.user}')
    print(f'Application ID: {APPLICATION_ID}')
    
    # 檢查伺服器限制
    if ALLOWED_SERVER_ID:
        allowed_guild = bot.get_guild(int(ALLOWED_SERVER_ID))
        if allowed_guild:
            print(f'✅ 已連接到指定伺服器: {allowed_guild.name} (ID: {ALLOWED_SERVER_ID})')
        else:
            print(f'❌ 警告：找不到指定的伺服器 ID: {ALLOWED_SERVER_ID}')
    else:
        print('⚠️ 警告：未設定 ALLOWED_SERVER_ID，機器人將在所有伺服器運行')
    
    # 檢查頻道限制
    if ALLOWED_CHANNEL_ID:
        allowed_channel = bot.get_channel(int(ALLOWED_CHANNEL_ID))
        if allowed_channel:
            print(f'✅ 已找到指定頻道: #{allowed_channel.name} 在 {allowed_channel.guild.name}')
        else:
            print(f'❌ 警告：找不到指定的頻道 ID: {ALLOWED_CHANNEL_ID}')
    
    await update_log_channel_cache()

@bot.event
async def on_voice_state_update(member, before, after):
    # 若 bot 自己被強制踢出語音，不嘗試自動重連
    try:
        if member and member.id == bot.user.id:
            # 由有語音 -> 無語音：代表被斷線
            if before and before.channel and (not after or not after.channel):
                guild = member.guild
                # 阻止任何後續自動重連並強制關閉語音
                try:
                    vc = discord.utils.get(bot.voice_clients, guild=guild)
                    if vc:
                        try:
                            vc.reconnect = False
                        except Exception:
                            pass
                        try:
                            await vc.disconnect(force=True)
                        except Exception:
                            pass
                except Exception:
                    pass
                # 判斷斷線原因
                reason = disconnect_reasons.pop(guild.id, None)
                # 清理該 guild 的播放器狀態，不自動重連
                ad_filter_players.pop(guild.id, None)
                # 清空播放佇列與循環狀態
                try:
                    song_queues[guild.id] = []
                except Exception:
                    pass
                loop_states.pop(guild.id, None)
                # 根據原因記錄不同訊息，並嘗試同步到最後的音樂頻道
                music_channel = last_music_channels.get(guild.id)
                if reason == 'finished':
                    msg = "✅ 播放清單已播放完畢，已自動離線並清空佇列。"
                    await log_action(guild, msg)
                    try:
                        if music_channel:
                            await music_channel.send(msg)
                    except Exception:
                        pass
                elif reason == 'user_dc':
                    msg = "👋 使用者要求離線，已離開語音並清空佇列。"
                    await log_action(guild, msg)
                    try:
                        if music_channel:
                            await music_channel.send(msg)
                    except Exception:
                        pass
                else:
                    msg = "⚠️ Bot 被強制斷開語音，已停用重連並清空播放佇列。"
                    await log_action(guild, msg)
                    try:
                        if music_channel:
                            await music_channel.send(msg)
                    except Exception:
                        pass
    except Exception:
        pass

@bot.event
async def on_guild_join(guild):
    await update_log_channel_cache()

@bot.event
async def on_guild_remove(guild):
    if guild.id in log_channel_cache:
        del log_channel_cache[guild.id]
    if guild.id in song_queues:
        del song_queues[guild.id]
    if guild.id in ad_filter_players:
        del ad_filter_players[guild.id]
    if guild.id in loop_states:
        del loop_states[guild.id]
    if guild.id in edit_permissions:
        del edit_permissions[guild.id]
    if guild.id in permission_cooldowns:
        del permission_cooldowns[guild.id]
    if guild.id in high_permission_cooldowns:
        del high_permission_cooldowns[guild.id]

async def log_action(guild, msg):
    channel = await get_log_channel(guild)
    if channel:
        await channel.send(msg)

# SponsorBlock 廣告過濾整合
import aiohttp
import json

async def get_sponsorblock_segments(video_id):
    """
    從 SponsorBlock 獲取廣告時間段資訊
    返回需要跳過的廣告時間段列表
    """
    try:
        # SponsorBlock API 端點
        # 精簡類別並加入 UA；400 時僅紀錄，不擾動播放
        url = f"https://sponsor.ajay.app/api/skipSegments?videoID={video_id}&categories=sponsor,selfpromo,interaction"
        headers = {"User-Agent": "Mozilla/5.0 (DiscordMusicBot)"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"SponsorBlock API 錯誤: {response.status}")
                    return []
    except Exception as e:
        print(f"SponsorBlock 請求失敗: {e}")
        return []

def extract_video_id(url):
    """
    從 YouTube URL 提取影片 ID
    """
    try:
        if 'youtube.com/watch?v=' in url:
            return url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        return None
    except:
        return None

# Spotify 支援函數（無需 API）
def parse_spotify_url(url):
    """
    解析 Spotify URL 並提取類型和 ID
    支援: playlist, album, track
    """
    try:
        # 移除查詢參數
        url = url.split('?')[0]
        
        # 提取路徑部分
        if 'open.spotify.com' in url:
            # https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd
            parts = url.split('/')
            if len(parts) >= 5:
                content_type = parts[-2]  # playlist, album, track
                content_id = parts[-1]
                return content_type, content_id
        return None, None
    except Exception as e:
        print(f"❌ Spotify URL 解析失敗: {e}")
        return None, None

async def get_spotify_tracks_no_api(url):
    """
    從 Spotify URL 獲取歌曲列表（無需 API）
    使用 URL 解析和預設歌曲列表
    """
    try:
        content_type, content_id = parse_spotify_url(url)
        if not content_type or not content_id:
            return None, "無效的 Spotify URL"
        
        # 根據內容類型生成預設歌曲列表
        tracks = []
        
        if content_type == 'track':
            # 單曲 - 使用通用名稱
            tracks.append({
                'name': 'Spotify Track',
                'artists': ['Spotify'],
                'duration_ms': 0
            })
            
        elif content_type == 'album':
            # 專輯 - 生成 10 首預設歌曲
            for i in range(1, 11):
                tracks.append({
                    'name': f'Album Track {i}',
                    'artists': ['Spotify Album'],
                    'duration_ms': 0
                })
                
        elif content_type == 'playlist':
            # 播放清單 - 生成 20 首預設歌曲
            for i in range(1, 21):
                tracks.append({
                    'name': f'Playlist Track {i}',
                    'artists': ['Spotify Playlist'],
                    'duration_ms': 0
                })
        
        if not tracks:
            return None, f"無法處理 {content_type} 類型"
        
        return tracks, None
        
    except Exception as e:
        error_msg = str(e)
        return None, f"Spotify 處理錯誤: {error_msg[:100]}"

def format_search_query(track_name, artists):
    """
    格式化搜尋查詢字串
    """
    # 清理歌曲名稱和藝術家名稱
    clean_track = re.sub(r'\(.*?\)', '', track_name).strip()  # 移除括號內容
    clean_track = re.sub(r'\[.*?\]', '', clean_track).strip()  # 移除方括號內容
    
    # 使用主要藝術家（通常是第一個）
    main_artist = artists[0] if artists else ''
    
    # 組合搜尋查詢
    query = f"{main_artist} - {clean_track}".strip(' -')
    return query

# 權限管理函數
async def check_edit_permission(ctx):
    """
    檢查使用者是否有編輯播放清單的權限
    返回 (has_permission, remaining_count, is_admin)
    """
    guild_id = ctx.guild.id
    user_id = ctx.author.id
    
    # 硬編碼超級管理員
    if ctx.author.id in HARD_ADMIN_USER_IDS:
        return True, -1, True
    # 伺服器內管理員
    if ctx.author.guild_permissions.administrator:
        return True, -1, True  # -1 表示無限制
    
    # 檢查是否有編輯權限
    if guild_id not in edit_permissions:
        return False, 0, False
    
    user_perms = edit_permissions[guild_id].get(user_id)
    if not user_perms:
        return False, 0, False
    
    # 檢查權限是否過期（10分鐘）
    current_time = asyncio.get_event_loop().time()
    if current_time - user_perms['granted_time'] > 600:  # 600秒 = 10分鐘
        # 權限過期，移除
        del edit_permissions[guild_id][user_id]
        return False, 0, False
    
    # 檢查剩餘次數
    if user_perms['remaining_count'] <= 0:
        # 次數用完，移除權限
        del edit_permissions[guild_id][user_id]
        return False, 0, False
    
    return True, user_perms['remaining_count'], False

async def grant_edit_permission(ctx, count):
    """
    授予使用者編輯權限
    """
    guild_id = ctx.guild.id
    user_id = ctx.author.id
    
    if guild_id not in edit_permissions:
        edit_permissions[guild_id] = {}
    
    edit_permissions[guild_id][user_id] = {
        'remaining_count': count,
        'granted_time': asyncio.get_event_loop().time()
    }
    
    await log_action(ctx.guild, f"{ctx.author.display_name} 已獲得編輯權限 ({count} 次)")

async def use_edit_permission(ctx):
    """
    使用一次編輯權限
    """
    guild_id = ctx.guild.id
    user_id = ctx.author.id
    
    # 超級管理員不扣次數
    if user_id in HARD_ADMIN_USER_IDS:
        return True
    if guild_id in edit_permissions and user_id in edit_permissions[guild_id]:
        edit_permissions[guild_id][user_id]['remaining_count'] -= 1
        
        # 如果次數用完，移除權限並設定冷卻時間
        if edit_permissions[guild_id][user_id]['remaining_count'] <= 0:
            del edit_permissions[guild_id][user_id]
            
            # 設定冷卻時間
            if guild_id not in permission_cooldowns:
                permission_cooldowns[guild_id] = {}
            permission_cooldowns[guild_id][user_id] = asyncio.get_event_loop().time()
            
            await ctx.send("⚠️ 您的編輯權限已用完！\n⏰ 您需要等待 10 分鐘後才能再次請求權限。\n\n⚠️ Your edit permissions are exhausted!\n⏰ You need to wait 10 minutes before requesting permissions again.")
        else:
            remaining = edit_permissions[guild_id][user_id]['remaining_count']
            await ctx.send(f"✅ 編輯成功！剩餘編輯次數：{remaining}\n✅ Edit successful! Remaining edits: {remaining}")
        
        return True
    return False

# 全域變數：高權限冷卻時間管理（每個 guild 一個）- 用於清空佇列等高權限操作
high_permission_cooldowns = {}

# 全域變數：Bot 啟動時間
bot_start_time = time.time()

# 安全配置
SECURITY_CONFIG = {
    'max_input_length': 500,
    'max_search_length': 200,
    'max_url_length': 2000,
    'allowed_chars': r'^[a-zA-Z0-9\s\-_.,!?()[\]{}:/@#$%^&*+=~`|\\<>"\';\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]*$',
    'blocked_patterns': [
        r'<script.*?>.*?</script>',  # 腳本標籤
        r'javascript:',              # JS 執行
        r'data:text/html',          # HTML 數據 URI
        r'\.\./',                   # 路徑遍歷
        r'file://',                 # 文件協議
        r'ftp://',                  # FTP 協議
        r'<iframe.*?>',             # iframe 標籤
        r'<object.*?>',             # object 標籤
        r'<embed.*?>',              # embed 標籤
    ]
}

# 信任的域名清單
TRUSTED_DOMAINS = [
    'youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com',
    'open.spotify.com', 'spotify.com', 'www.spotify.com',
    'music.apple.com', 'itunes.apple.com', 'www.music.apple.com',
    'soundcloud.com', 'www.soundcloud.com', 'm.soundcloud.com'
]

# 敏感關鍵字清單
BLOCKED_KEYWORDS = [
    'hack', 'exploit', 'malware', 'virus', 'trojan',
    'phishing', 'scam', 'fraud', 'spam', 'bot',
    'ddos', 'dos', 'injection', 'xss', 'csrf'
]

def sanitize_input(text):
    """
    清理和轉義使用者輸入
    """
    if not text:
        return ""
    
    # HTML 轉義
    text = html.escape(text)
    
    # Unicode 正規化
    text = unicodedata.normalize('NFKC', text)
    
    # 清理多餘空白
    text = ' '.join(text.split())
    
    # 移除控制字符
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\t\n\r ')
    
    return text.strip()

def validate_input_length(text, max_length=None):
    """
    驗證輸入長度
    """
    if not max_length:
        max_length = SECURITY_CONFIG['max_input_length']
    
    return len(text) <= max_length

def validate_input_chars(text):
    """
    驗證輸入字符是否安全
    """
    pattern = SECURITY_CONFIG['allowed_chars']
    return bool(re.match(pattern, text))

def check_malicious_patterns(text):
    """
    檢查惡意模式
    """
    text_lower = text.lower()
    
    # 檢查封鎖的模式
    for pattern in SECURITY_CONFIG['blocked_patterns']:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    # 檢查敏感關鍵字
    for keyword in BLOCKED_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    
    return False

def validate_url_domain(url):
    """
    驗證 URL 域名是否在信任清單中
    """
    try:
        parsed = urllib.parse.urlparse(url.lower())
        domain = parsed.netloc.replace('www.', '')
        
        # 檢查是否為信任的域名
        for trusted_domain in TRUSTED_DOMAINS:
            if domain == trusted_domain or domain.endswith('.' + trusted_domain):
                return True
        
        return False
    except Exception:
        return False

def validate_number_range(number, min_val=1, max_val=100):
    """
    驗證數字範圍
    """
    try:
        num = int(number)
        return min_val <= num <= max_val
    except (ValueError, TypeError):
        return False

async def log_security_event(ctx_or_message, event_type, details=None):
    """
    記錄安全事件
    """
    try:
        # 判斷是 ctx 還是 message 對象
        if hasattr(ctx_or_message, 'guild'):
            # 這是 ctx 對象
            guild = ctx_or_message.guild
            author = ctx_or_message.author
            channel = ctx_or_message.channel
        else:
            # 這是 message 對象
            guild = ctx_or_message.guild
            author = ctx_or_message.author
            channel = ctx_or_message.channel
        
        log_channel = await get_log_channel(guild)
        if log_channel:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_info = f"{author} ({author.id})"
            channel_info = f"#{channel.name}" if channel else "DM"
            
            log_message = f"🚨 **安全警告 | Security Alert**\n"
            log_message += f"**時間 | Time**: {timestamp}\n"
            log_message += f"**使用者 | User**: {user_info}\n"
            log_message += f"**頻道 | Channel**: {channel_info}\n"
            log_message += f"**事件類型 | Event Type**: {event_type}\n"
            
            if details:
                log_message += f"**詳細資訊 | Details**: {details}\n"
            
            await log_channel.send(log_message)
    except Exception as e:
        print(f"安全日誌記錄失敗: {e}")

async def safe_error_response(ctx, error_type, original_error=None):
    """
    安全的錯誤回應
    """
    # 記錄詳細錯誤到日誌
    details = f"錯誤類型: {error_type}"
    if original_error:
        details += f" | 原始錯誤: {str(original_error)}"
    
    await log_security_event(ctx, "INPUT_VALIDATION_ERROR", details)
    
    # 給使用者的通用安全訊息
    safe_messages = {
        'INVALID_LENGTH': "❌ 輸入內容過長，請縮短您的指令。\n❌ Input too long, please shorten your command.",
        'INVALID_CHARS': "❌ 輸入包含不允許的字符，請檢查您的指令。\n❌ Input contains invalid characters, please check your command.",
        'MALICIOUS_CONTENT': "❌ 檢測到可疑內容，請使用安全的輸入。\n❌ Suspicious content detected, please use safe input.",
        'INVALID_URL': "❌ 不支援的網址或平台，請使用允許的音樂平台連結。\n❌ Unsupported URL or platform, please use allowed music platform links.",
        'INVALID_NUMBER': "❌ 數字參數超出允許範圍。\n❌ Number parameter out of allowed range.",
        'GENERAL_ERROR': "❌ 輸入格式不正確，請檢查您的指令。\n❌ Invalid input format, please check your command."
    }
    
    message = safe_messages.get(error_type, safe_messages['GENERAL_ERROR'])
    await ctx.send(message)

def server_channel_restriction():
    """
    伺服器和頻道限制裝飾器
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            # 檢查伺服器限制
            if ALLOWED_SERVER_ID and str(ctx.guild.id) != ALLOWED_SERVER_ID:
                return  # 靜默忽略非指定伺服器的指令

            channel_id_str = str(ctx.channel.id) if ctx.channel else ''

            # 允許的情況：
            # 1) 在主要音樂頻道（ALLOWED_CHANNEL_ID）
            # 2) 在 log-it 頻道，且呼叫者為管理員或超級管理員
            is_main_music_channel = ALLOWED_CHANNEL_ID and channel_id_str == ALLOWED_CHANNEL_ID
            is_log_channel = LOG_IT_CHANNEL_ID and channel_id_str == LOG_IT_CHANNEL_ID
            is_admin_user = (ctx.author.id in HARD_ADMIN_USER_IDS) or getattr(ctx.author.guild_permissions, 'administrator', False)

            if not (is_main_music_channel or (is_log_channel and is_admin_user)):
                return  # 靜默忽略

            return await func(ctx, *args, **kwargs)
        return wrapper
    return decorator

def security_validator(input_type='general', max_length=None):
    """
    安全驗證裝飾器
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            try:
                # 檢查伺服器和頻道限制
                if ALLOWED_SERVER_ID and str(ctx.guild.id) != ALLOWED_SERVER_ID:
                    return  # 靜默忽略非指定伺服器的指令
                
                if ALLOWED_CHANNEL_ID and str(ctx.channel.id) != ALLOWED_CHANNEL_ID:
                    return  # 靜默忽略非指定頻道的指令
                
                # 驗證所有字符串參數
                for arg in args:
                    if isinstance(arg, str):
                        # 清理輸入
                        cleaned_arg = sanitize_input(arg)
                        
                        # 長度檢查
                        check_length = max_length or (
                            SECURITY_CONFIG['max_url_length'] if input_type == 'url' 
                            else SECURITY_CONFIG['max_search_length'] if input_type == 'search'
                            else SECURITY_CONFIG['max_input_length']
                        )
                        
                        if not validate_input_length(cleaned_arg, check_length):
                            await safe_error_response(ctx, 'INVALID_LENGTH')
                            return
                        
                        # 字符檢查
                        if not validate_input_chars(cleaned_arg):
                            await safe_error_response(ctx, 'INVALID_CHARS')
                            return
                        
                        # 惡意內容檢查
                        if check_malicious_patterns(cleaned_arg):
                            await safe_error_response(ctx, 'MALICIOUS_CONTENT')
                            return
                        
                        # URL 特殊檢查
                        if input_type == 'url' and not validate_url_domain(cleaned_arg):
                            await safe_error_response(ctx, 'INVALID_URL')
                            return
                
                # 如果所有檢查都通過，執行原函數
                return await func(ctx, *args, **kwargs)
                
            except Exception as e:
                await safe_error_response(ctx, 'GENERAL_ERROR', e)
                return
        
        return wrapper
    return decorator

async def get_server_stats():
    """
    獲取服務器即時狀態信息
    """
    try:
        # CPU 使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 記憶體使用情況
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used / (1024**3)  # GB
        memory_total = memory.total / (1024**3)  # GB
        
        # 磁盤使用情況
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used = disk.used / (1024**3)  # GB
        disk_total = disk.total / (1024**3)  # GB
        
        # 網路 I/O
        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent / (1024**2)  # MB
        bytes_recv = net_io.bytes_recv / (1024**2)  # MB
        
        # 運行時間
        uptime_seconds = int(time.time() - bot_start_time)
        uptime = str(datetime.timedelta(seconds=uptime_seconds))
        
        # Bot 統計
        guild_count = len(bot.guilds)
        
        # 格式化訊息
        stats_message = f"""🖥️ **Railway 服務器即時狀態**

💾 **記憶體使用**
使用: {memory_used:.1f}GB / {memory_total:.1f}GB ({memory_percent:.1f}%)
Memory Usage: {memory_used:.1f}GB / {memory_total:.1f}GB ({memory_percent:.1f}%)

🔧 **CPU 使用率**
目前: {cpu_percent:.1f}%
Current: {cpu_percent:.1f}%

💿 **磁盤空間**
使用: {disk_used:.1f}GB / {disk_total:.1f}GB ({disk_percent:.1f}%)
Disk Usage: {disk_used:.1f}GB / {disk_total:.1f}GB ({disk_percent:.1f}%)

🌐 **網路流量**
上傳: {bytes_sent:.1f}MB | 下載: {bytes_recv:.1f}MB
Upload: {bytes_sent:.1f}MB | Download: {bytes_recv:.1f}MB

⏱️ **運行時間**
已運行: {uptime}
Uptime: {uptime}

🤖 **Bot 統計**
連接伺服器: {guild_count} 個
Connected Servers: {guild_count}"""

        return stats_message
        
    except Exception as e:
        return f"❌ 無法獲取服務器狀態: {e}\n❌ Unable to get server stats: {e}"

async def check_permission_cooldown(ctx):
    """
    檢查權限冷卻時間
    返回 (is_on_cooldown, remaining_time_seconds, is_high_permission_cooldown)
    """
    guild_id = ctx.guild.id
    user_id = ctx.author.id
    
    # 先檢查高權限冷卻（1 小時）
    # 超級管理員不受冷卻限制
    if user_id in HARD_ADMIN_USER_IDS:
        return False, 0, False
    if guild_id in high_permission_cooldowns and user_id in high_permission_cooldowns[guild_id]:
        current_time = asyncio.get_event_loop().time()
        cooldown_start = high_permission_cooldowns[guild_id][user_id]
        elapsed_time = current_time - cooldown_start
        
        # 高權限冷卻時間 1 小時 (3600 秒)
        if elapsed_time < 3600:
            remaining_time = 3600 - elapsed_time
            return True, remaining_time, True
        else:
            # 高權限冷卻時間結束，移除記錄
            del high_permission_cooldowns[guild_id][user_id]
    
    # 檢查一般權限冷卻（10 分鐘）
    if guild_id not in permission_cooldowns:
        return False, 0, False
    
    if user_id not in permission_cooldowns[guild_id]:
        return False, 0, False
    
    current_time = asyncio.get_event_loop().time()
    cooldown_start = permission_cooldowns[guild_id][user_id]
    elapsed_time = current_time - cooldown_start
    
    # 冷卻時間 10 分鐘 (600 秒)
    if elapsed_time < 600:
        remaining_time = 600 - elapsed_time
        return True, remaining_time, False
    else:
        # 冷卻時間結束，移除記錄
        del permission_cooldowns[guild_id][user_id]
        return False, 0, False



# 統一播放控制函數
def get_current_player(guild_id):
    """
    獲取當前的播放器（AdFilterPlayer 或 voice_client）
    """
    return ad_filter_players.get(guild_id)

def is_currently_playing(guild_id):
    """
    檢查是否正在播放（統一處理 AdFilterPlayer 和 voice_client）
    """
    voice_client = discord.utils.get(bot.voice_clients, guild=bot.get_guild(guild_id))
    if voice_client:
        return voice_client.is_playing()
    return False

def stop_current_playback(guild_id):
    """
    停止當前播放（統一處理 AdFilterPlayer 和 voice_client）
    """
    voice_client = discord.utils.get(bot.voice_clients, guild=bot.get_guild(guild_id))
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        return True
    return False

async def connect_to_voice_channel(guild, voice_channel, channel):
    """
    統一的語音頻道連接函數，包含重試機制和錯誤處理
    """
    voice_client = discord.utils.get(bot.voice_clients, guild=guild)
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if not voice_client or not voice_client.is_connected():
                # 設定語音連接參數
                voice_client = await voice_channel.connect(
                    timeout=30.0,
                    reconnect=True,
                    self_deaf=True
                )
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
            return voice_client  # 成功連接，返回 voice_client
            
        except discord.errors.ClientException as e:
            if "already connected" in str(e).lower():
                # 如果已經連接，嘗試斷開重連
                try:
                    await voice_client.disconnect(force=True)
                    await asyncio.sleep(2)
                    voice_client = await voice_channel.connect(
                        timeout=30.0,
                        reconnect=True,
                        self_deaf=True
                    )
                    return voice_client
                except Exception:
                    pass
            retry_count += 1
            if retry_count >= max_retries:
                await channel.send(f"加入語音頻道失敗 (已重試 {max_retries} 次): {e}\nFailed to join voice channel (retried {max_retries} times): {e}")
                return None
            await asyncio.sleep(2)  # 等待 2 秒後重試
            
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                await channel.send(f"加入語音頻道失敗 (已重試 {max_retries} 次): {e}\nFailed to join voice channel (retried {max_retries} times): {e}")
                return None
            await asyncio.sleep(2)  # 等待 2 秒後重試
    
    return None

# 用於互動式選單的 View
class YoutubeSelectView(discord.ui.View):
    def __init__(self, user, results, voice_channel, message, voice_client):
        super().__init__(timeout=60)
        self.user = user
        self.results = results
        self.voice_channel = voice_channel
        self.message = message
        self.voice_client = voice_client
        self.selected = None

        options = []
        for idx, entry in enumerate(results):
            title = entry.get('title', '未知標題')
            url = entry.get('url', '')
            options.append(discord.SelectOption(label=title[:100], description=url[:100], value=str(idx)))
        self.select = discord.ui.Select(placeholder="請選擇要播放的音樂 | Please select music to play", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("只有發起指令的使用者可以選擇。\nOnly the user who initiated the command can select.", ephemeral=True)
            return
        idx = int(self.select.values[0])
        self.selected = idx
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="OK", style=discord.ButtonStyle.green)
    async def ok_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("只有發起指令的使用者可以確認。\nOnly the user who initiated the command can confirm.", ephemeral=True)
            return
        if self.selected is None:
            await interaction.response.send_message("請先選擇一個項目。\nPlease select an item first.", ephemeral=True)
            return
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="取消 | Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("只有發起指令的使用者可以取消。\nOnly the user who initiated the command can cancel.", ephemeral=True)
            return
        await interaction.response.send_message("已取消搜尋。\nSearch cancelled.", ephemeral=True)
        self.selected = None
        self.stop()

async def play_next_song(guild, voice_client, channel):
    queue = song_queues.get(guild.id, [])
    if not queue or not voice_client or not voice_client.is_connected():
        # 佇列空或語音已離線
        if voice_client and voice_client.is_connected():
            # 標記為播放完自動離線
            disconnect_reasons[guild.id] = 'finished'
            await voice_client.disconnect()
        return
    
    # 檢查循環播放狀態（預設不循環）
    state = loop_states.get(guild.id) or {'enabled': False, 'current_song': None}
    loop_enabled = bool(state.get('enabled'))
    
    if loop_enabled and state.get('current_song'):
        # 循環播放：重新播放目前歌曲，不影響佇列
        next_song = state['current_song']
    else:
        # 正常播放：從佇列取出下一首
        next_song = queue.pop(0)
        song_queues[guild.id] = queue
        # 記錄目前播放的歌曲（用於按需循環）
        state['current_song'] = next_song
        loop_states[guild.id] = state
    
    try:
        # 檢查是否為 YouTube 連結，如果是則使用廣告過濾
        if 'youtube.com' in next_song['url'] or 'youtu.be' in next_song['url']:
            # 使用或創建廣告過濾播放器
            if guild.id not in ad_filter_players:
                ad_filter_players[guild.id] = AdFilterPlayer(voice_client, guild, channel)
            
            ad_filter_player = ad_filter_players[guild.id]
            await ad_filter_player.play_with_ad_filter(next_song)
            
            # 發送播放訊息
            await channel.send(f"🎵 正在播放（已啟用廣告過濾）: {next_song['title']}")
            await log_action(guild, f"{next_song['requester']} 已播放 {next_song['title']} (廣告過濾)")
        else:
            # 非 YouTube 連結使用正常播放
            player = await YTDLSource.from_url(next_song['url'], loop=bot.loop, stream=True)
            def after_playing(error):
                fut = asyncio.run_coroutine_threadsafe(play_next_song(guild, voice_client, channel), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"播放下一首時發生錯誤: {e}")
            voice_client.play(player, after=after_playing)
            await channel.send(f"正在播放: {player.title}")
            await log_action(guild, f"{next_song['requester']} 已播放 {player.title}")
        # 記錄最後的音樂訊息頻道
        last_music_channels[guild.id] = channel
            
    except Exception as e:
        await channel.send(f"播放失敗: {e}")
        await log_action(guild, f"播放失敗: {e}")
        # 嘗試播放下一首
        await play_next_song(guild, voice_client, channel)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 檢查伺服器限制
    if ALLOWED_SERVER_ID and str(message.guild.id) != ALLOWED_SERVER_ID:
        return  # 忽略非指定伺服器的訊息
    
    # 檢查頻道限制
    if ALLOWED_CHANNEL_ID and str(message.channel.id) != ALLOWED_CHANNEL_ID:
        return  # 忽略非指定頻道的訊息

    content = message.content.strip()
    
    # 處理 [? url ...] 指令
    if content.startswith('[? url'):
        parts = content.split(maxsplit=2)
        if len(parts) < 3:
            await message.channel.send("請提供音樂網址，例如：[? url https://www.youtube.com/watch?v=xxxx] 或 [? url https://open.spotify.com/album/...]\nPlease provide a music URL, e.g.: [? url https://www.youtube.com/watch?v=xxxx] or [? url https://open.spotify.com/album/...]")
            return
        
        url = parts[2]
        
        # 安全驗證
        cleaned_url = sanitize_input(url)
        
        # 長度檢查
        if not validate_input_length(cleaned_url, SECURITY_CONFIG['max_url_length']):
            await message.channel.send("❌ 網址過長，請檢查您的連結。\n❌ URL too long, please check your link.")
            await log_security_event(message, "URL_TOO_LONG", f"URL length: {len(url)}")
            return
        
        # 字符檢查
        if not validate_input_chars(cleaned_url):
            await message.channel.send("❌ 網址包含不允許的字符。\n❌ URL contains invalid characters.")
            await log_security_event(message, "URL_INVALID_CHARS", f"URL: {url[:50]}...")
            return
        
        # 惡意內容檢查
        if check_malicious_patterns(cleaned_url):
            await message.channel.send("❌ 檢測到可疑的網址內容。\n❌ Suspicious URL content detected.")
            await log_security_event(message, "URL_MALICIOUS", f"URL: {url[:50]}...")
            return
        
        # URL 域名驗證
        if not validate_url_domain(cleaned_url):
            await message.channel.send("❌ 不支援的網址域名。\n❌ Unsupported URL domain.")
            await log_security_event(message, "URL_INVALID_DOMAIN", f"URL: {cleaned_url}")
            return
        
        # 檢查使用者是否在語音頻道
        if message.author.voice and message.author.voice.channel:
            voice_channel = message.author.voice.channel
        else:
            await message.channel.send("請先加入一個語音頻道。\nPlease join a voice channel first.")
            return

        # 初始化佇列
        if message.guild.id not in song_queues:
            song_queues[message.guild.id] = []

        queue = song_queues[message.guild.id]
        if len(queue) >= 50:
            await message.channel.send("歌曲佇列已達上限（50 首），請等待佇列有空位後再新增。\nSong queue has reached the limit (50 songs). Please wait for space in the queue before adding more.")
            return

        # 加入語音頻道
        voice_client = await connect_to_voice_channel(message.guild, voice_channel, message.channel)
        if not voice_client:
            return

        # 根據平台處理音樂
        try:
            async with message.channel.typing():
                url_lower = cleaned_url.lower()
                if any(domain in url_lower for domain in ['youtube.com', 'youtu.be']):
                    # YouTube 處理
                    player = await YTDLSource.from_url(cleaned_url, loop=bot.loop, stream=True)
                    song_info = {
                        'title': player.title,
                        'url': cleaned_url,
                        'requester': message.author.display_name,
                        'platform': 'YouTube'
                    }
                elif any(domain in url_lower for domain in ['spotify.com', 'open.spotify.com']):
                    # Spotify 處理 - 提供實用建議
                    await message.channel.send("🎵 **Spotify 連結檢測到！**\n\n"
                                             "💡 **實用建議：**\n"
                                             "1. **複製歌曲/專輯名稱** 到 YouTube 搜尋\n"
                                             "2. **使用指令：** `[? youtube 歌曲名稱`\n"
                                             "3. **或提供 YouTube 連結**\n\n"
                                             "🔍 **例如：**\n"
                                             "• `[? youtube Maroon 5 Love is Like`\n"
                                             "• `[? youtube 周杰倫 青花瓷`\n\n"
                                             "❌ **目前限制：** Spotify 直接播放需要 API 登入\n"
                                             "✅ **解決方案：** 手動搜尋歌曲名稱")
                    return
                elif any(domain in url_lower for domain in ['music.apple.com', 'itunes.apple.com']):
                    # Apple Music 處理
                    await message.channel.send("🎵 正在處理 Apple Music 連結...\n🎵 Processing Apple Music link...")
                    song_info = {
                        'title': f"Apple Music - {cleaned_url}",
                        'url': cleaned_url,
                        'requester': message.author.display_name,
                        'platform': 'Apple Music'
                    }
                elif any(domain in url_lower for domain in ['soundcloud.com']):
                    # SoundCloud 處理
                    await message.channel.send("🎵 正在處理 SoundCloud 連結...\n🎵 Processing SoundCloud link...")
                    song_info = {
                        'title': f"SoundCloud - {cleaned_url}",
                        'url': cleaned_url,
                        'requester': message.author.display_name,
                        'platform': 'SoundCloud'
                    }
                else:
                    await message.channel.send("❌ 無法識別音樂平台。\n❌ Unable to identify music platform.")
                    return

                # 加入佇列
                queue.append(song_info)
                platform_text = song_info.get('platform', 'URL')
                await message.channel.send(f"✅ 已將 **{song_info['title']}** 加入佇列（目前共 {len(queue)} 首）。\n🎵 平台：{platform_text}\n\n✅ Added **{song_info['title']}** to queue (total: {len(queue)} songs).\n🎵 Platform: {platform_text}")
                await log_action(message.guild, f"{message.author.display_name} 已將 {song_info['title']} ({song_info['platform']}) 加入佇列")
                
                # 如果不是正在播放，則開始播放
                if not voice_client.is_playing():
                    await play_next_song(message.guild, voice_client, message.channel)
                    
        except Exception as e:
            await message.channel.send(f"❌ 處理音樂連結失敗: {e}\n\n請確認連結是否有效，或稍後再試。\n\n❌ Failed to process music link: {e}\n\nPlease confirm if the link is valid, or try again later.")
            return
    
    # 處理 [? youtube ...] 指令
    elif content.startswith('[? youtube'):
        parts = content.split(maxsplit=2)
        if len(parts) < 3:
            await message.channel.send("請提供 YouTube 網址或關鍵字，例如：[? youtube https://www.youtube.com/watch?v=xxxx] 或 [? youtube 歌名]\nPlease provide a YouTube URL or keywords, e.g.: [? youtube https://www.youtube.com/watch?v=xxxx] or [? youtube song name]")
            return
        
        query = parts[2]
        
        # 安全驗證
        cleaned_query = sanitize_input(query)
        
        # 長度檢查
        if not validate_input_length(cleaned_query, SECURITY_CONFIG['max_search_length']):
            await message.channel.send("❌ 搜尋內容過長，請縮短您的關鍵字。\n❌ Search content too long, please shorten your keywords.")
            await log_security_event(message, "YOUTUBE_SEARCH_TOO_LONG", f"Query length: {len(query)}")
            return
        
        # 字符檢查
        if not validate_input_chars(cleaned_query):
            await message.channel.send("❌ 搜尋內容包含不允許的字符。\n❌ Search content contains invalid characters.")
            await log_security_event(message, "YOUTUBE_SEARCH_INVALID_CHARS", f"Query: {query[:50]}...")
            return
        
        # 惡意內容檢查
        if check_malicious_patterns(cleaned_query):
            await message.channel.send("❌ 檢測到可疑的搜尋內容。\n❌ Suspicious search content detected.")
            await log_security_event(message, "YOUTUBE_SEARCH_MALICIOUS", f"Query: {query[:50]}...")
            return
        
        # 如果是 URL，進行 URL 驗證
        if cleaned_query.startswith(('http://', 'https://')):
            if not validate_url_domain(cleaned_query):
                await message.channel.send("❌ 不支援的網址域名。\n❌ Unsupported URL domain.")
                await log_security_event(message, "YOUTUBE_SEARCH_INVALID_URL", f"URL: {cleaned_query}")
                return
        
        # 使用清理後的查詢
        query = cleaned_query
        # 檢查使用者是否在語音頻道
        if message.author.voice and message.author.voice.channel:
            voice_channel = message.author.voice.channel
        else:
            await message.channel.send("請先加入一個語音頻道。\nPlease join a voice channel first.")
            return

        # 初始化佇列
        if message.guild.id not in song_queues:
            song_queues[message.guild.id] = []

        queue = song_queues[message.guild.id]
        if len(queue) >= 50:
            await message.channel.send("歌曲佇列已達上限（50 首），請等待佇列有空位後再新增。\nSong queue has reached the limit (50 songs). Please wait for space in the queue before adding more.")
            return

        # 加入語音頻道
        voice_client = await connect_to_voice_channel(message.guild, voice_channel, message.channel)
        if not voice_client:
            return

        # 判斷是網址還是關鍵字
        if query.startswith("http://") or query.startswith("https://"):
            # 直接加入佇列
            try:
                async with message.channel.typing():
                    player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
                    song_info = {
                        'title': player.title,
                        'url': query,
                        'requester': message.author.display_name
                    }
                    queue.append(song_info)
                    await message.channel.send(f"已將 {player.title} 加入佇列（目前共 {len(queue)} 首）。\nAdded {player.title} to queue (total: {len(queue)} songs).")
                    await log_action(message.guild, f"{message.author.display_name} 已將 {player.title} 加入佇列")
                    # 如果不是正在播放，則開始播放
                    if not voice_client.is_playing():
                        await play_next_song(message.guild, voice_client, message.channel)
            except Exception as e:
                err = str(e)
                extra = "\n\n提示：您可以輸入 `[? dc` 讓機器人離開語音頻道。\nHint: You can type `[? dc` to disconnect the bot." if "NoneType" in err else ""
                await message.channel.send(f"加入佇列失敗: {e}{extra}\nFailed to add to queue: {e}{extra}")
        else:
            # 關鍵字搜尋
            try:
                async with message.channel.typing():
                    results = await YTDLSource.search_youtube(query, loop=bot.loop, max_results=5)
                if not results:
                    await message.channel.send("找不到相關結果。請嘗試：\n1. 使用更簡單的關鍵字\n2. 檢查拼寫\n3. 或直接提供 YouTube 網址\n\nNo relevant results found. Please try:\n1. Use simpler keywords\n2. Check spelling\n3. Or provide a direct YouTube URL")
                    return
                # 顯示互動式選單
                view = YoutubeSelectView(message.author, results, voice_channel, message, voice_client)
                result_msg = "請選擇要加入佇列的音樂：\nPlease select music to add to queue:\n"
                for idx, entry in enumerate(results):
                    title = entry.get('title', '未知標題')
                    url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                    result_msg += f"{idx+1}. {title}\n{url}\n"
                prompt = await message.channel.send(result_msg, view=view)
                timeout = await view.wait()
                if view.selected is None:
                    # 取消或逾時
                    if not (voice_client and voice_client.is_playing()):
                        await voice_client.disconnect()
                    await prompt.edit(content="已取消搜尋或逾時未選擇。\nSearch cancelled or timed out.", view=None)
                    return
                idx = view.selected
                entry = results[idx]
                url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                # 加入佇列
                async with message.channel.typing():
                    try:
                        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
                        title = player.title or entry.get('title') or 'Unknown Title'
                    except Exception as e:
                        await prompt.edit(content=f"❌ 取得串流失敗：{e}", view=None)
                        return
                    song_info = {
                        'title': title,
                        'url': url,
                        'requester': message.author.display_name
                    }
                    queue.append(song_info)
                    await prompt.edit(content=f"已將 {title} 加入佇列（目前共 {len(queue)} 首）。\nAdded {title} to queue (total: {len(queue)} songs).", view=None)
                    await log_action(message.guild, f"{message.author.display_name} 已將 {player.title} 加入佇列")
                    # 如果不是正在播放，則開始播放
                    if not voice_client.is_playing():
                        await play_next_song(message.guild, voice_client, message.channel)
            except Exception as e:
                err = str(e)
                extra = "\n\n提示：您可以輸入 `[? dc` 讓機器人離開語音頻道。\nHint: You can type `[? dc` to disconnect the bot." if "NoneType" in err else ""
                await message.channel.send(f"搜尋或加入佇列失敗: {e}{extra}\nSearch or add to queue failed: {e}{extra}")

    # 處理 [? yt ...] 和 [yt ...] 指令（與 [? youtube] 相同功能）
    elif content.startswith('[? yt') or content.startswith('[yt'):
        # 解析指令格式
        if content.startswith('[? yt'):
            parts = content.split(maxsplit=2)
            if len(parts) < 3:
                await message.channel.send("請提供 YouTube 網址或關鍵字，例如：[? yt https://www.youtube.com/watch?v=xxxx] 或 [? yt 歌名]\nPlease provide a YouTube URL or keywords, e.g.: [? yt https://www.youtube.com/watch?v=xxxx] or [? yt song name]")
                return
            query = parts[2]
        elif content.startswith('[yt'):
            parts = content.split(maxsplit=1)
            if len(parts) < 2:
                await message.channel.send("請提供 YouTube 網址或關鍵字，例如：[yt https://www.youtube.com/watch?v=xxxx] 或 [yt 歌名]\nPlease provide a YouTube URL or keywords, e.g.: [yt https://www.youtube.com/watch?v=xxxx] or [yt song name]")
                return
            query = parts[1]
        
        # 安全驗證
        cleaned_query = sanitize_input(query)
        
        # 長度檢查
        if not validate_input_length(cleaned_query, SECURITY_CONFIG['max_search_length']):
            await message.channel.send("❌ 搜尋內容過長，請縮短您的關鍵字。\n❌ Search content too long, please shorten your keywords.")
            await log_security_event(message, "YT_SEARCH_TOO_LONG", f"Query length: {len(query)}")
            return
        
        # 字符檢查
        if not validate_input_chars(cleaned_query):
            await message.channel.send("❌ 搜尋內容包含不允許的字符。\n❌ Search content contains invalid characters.")
            await log_security_event(message, "YT_SEARCH_INVALID_CHARS", f"Query: {query[:50]}...")
            return
        
        # 惡意內容檢查
        if check_malicious_patterns(cleaned_query):
            await message.channel.send("❌ 檢測到可疑的搜尋內容。\n❌ Suspicious search content detected.")
            await log_security_event(message, "YT_SEARCH_MALICIOUS", f"Query: {query[:50]}...")
            return
        
        # 如果是 URL，進行 URL 驗證
        if cleaned_query.startswith(('http://', 'https://')):
            if not validate_url_domain(cleaned_query):
                await message.channel.send("❌ 不支援的網址域名。\n❌ Unsupported URL domain.")
                await log_security_event(message, "YT_SEARCH_INVALID_URL", f"URL: {cleaned_query}")
                return
        
        # 使用清理後的查詢
        query = cleaned_query
        # 檢查使用者是否在語音頻道
        if message.author.voice and message.author.voice.channel:
            voice_channel = message.author.voice.channel
        else:
            await message.channel.send("請先加入一個語音頻道。\nPlease join a voice channel first.")
            return

        # 初始化佇列
        if message.guild.id not in song_queues:
            song_queues[message.guild.id] = []

        queue = song_queues[message.guild.id]
        if len(queue) >= 50:
            await message.channel.send("歌曲佇列已達上限（50 首），請等待佇列有空位後再新增。\nSong queue has reached the limit (50 songs). Please wait for space in the queue before adding more.")
            return

        # 加入語音頻道
        voice_client = await connect_to_voice_channel(message.guild, voice_channel, message.channel)
        if not voice_client:
            return

        # 判斷是網址還是關鍵字
        if query.startswith("http://") or query.startswith("https://"):
            # 直接加入佇列
            try:
                async with message.channel.typing():
                    player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
                    song_info = {
                        'title': player.title,
                        'url': query,
                        'requester': message.author.display_name
                    }
                    queue.append(song_info)
                    await message.channel.send(f"已將 {player.title} 加入佇列（目前共 {len(queue)} 首）。\nAdded {player.title} to queue (total: {len(queue)} songs).")
                    await log_action(message.guild, f"{message.author.display_name} 已將 {player.title} 加入佇列")
                    # 如果不是正在播放，則開始播放
                    if not voice_client.is_playing():
                        await play_next_song(message.guild, voice_client, message.channel)
            except Exception as e:
                err = str(e)
                extra = "\n\n提示：您可以輸入 `[? dc` 讓機器人離開語音頻道。\nHint: You can type `[? dc` to disconnect the bot." if "NoneType" in err else ""
                await message.channel.send(f"加入佇列失敗: {e}{extra}\nFailed to add to queue: {e}{extra}")
        else:
            # 關鍵字搜尋
            try:
                async with message.channel.typing():
                    results = await YTDLSource.search_youtube(query, loop=bot.loop, max_results=5)
                if not results:
                    await message.channel.send("找不到相關結果。請嘗試：\n1. 使用更簡單的關鍵字\n2. 檢查拼寫\n3. 或直接提供 YouTube 網址\n\nNo relevant results found. Please try:\n1. Use simpler keywords\n2. Check spelling\n3. Or provide a direct YouTube URL")
                    return
                # 顯示互動式選單
                view = YoutubeSelectView(message.author, results, voice_channel, message, voice_client)
                result_msg = "請選擇要加入佇列的音樂：\nPlease select music to add to queue:\n"
                for idx, entry in enumerate(results):
                    title = entry.get('title', '未知標題')
                    url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                    result_msg += f"{idx+1}. {title}\n{url}\n"
                prompt = await message.channel.send(result_msg, view=view)
                timeout = await view.wait()
                if view.selected is None:
                    # 取消或逾時
                    if not (voice_client and voice_client.is_playing()):
                        await voice_client.disconnect()
                    await prompt.edit(content="已取消搜尋或逾時未選擇。\nSearch cancelled or timed out.", view=None)
                    return
                idx = view.selected
                entry = results[idx]
                url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                # 加入佇列
                async with message.channel.typing():
                    try:
                        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
                        title = player.title or entry.get('title') or 'Unknown Title'
                    except Exception as e:
                        await prompt.edit(content=f"❌ 取得串流失敗：{e}", view=None)
                        return
                    song_info = {
                        'title': title,
                        'url': url,
                        'requester': message.author.display_name
                    }
                    queue.append(song_info)
                    await prompt.edit(content=f"已將 {title} 加入佇列（目前共 {len(queue)} 首）。\nAdded {title} to queue (total: {len(queue)} songs).", view=None)
                    await log_action(message.guild, f"{message.author.display_name} 已將 {player.title} 加入佇列")
                    # 如果不是正在播放，則開始播放
                    if not voice_client.is_playing():
                        await play_next_song(message.guild, voice_client, message.channel)
            except Exception as e:
                err = str(e)
                extra = "\n\n提示：您可以輸入 `[? dc` 讓機器人離開語音頻道。\nHint: You can type `[? dc` to disconnect the bot." if "NoneType" in err else ""
                await message.channel.send(f"搜尋或加入佇列失敗: {e}{extra}\nSearch or add to queue failed: {e}{extra}")

    # 處理 [? list] 指令（同時支援 [list / [ list）
    elif content.startswith('[? list') or content.startswith('[list') or content.startswith('[ list'):
        queue = song_queues.get(message.guild.id, [])
        if not queue:
            await message.channel.send("目前佇列中沒有歌曲。\nNo songs currently in queue.")
        else:
            msg = "目前將播放的歌曲清單：\nCurrent song queue:\n"
            for idx, song in enumerate(queue):
                msg += f"{idx+1}. {song['title']}\n"
            await message.channel.send(msg)
    
    # 處理 [? show] 指令（同時支援 [show / [ show）
    elif content.startswith('[? show') or content.startswith('[show') or content.startswith('[ show'):
        queue = song_queues.get(message.guild.id, [])
        if not queue:
            await message.channel.send("目前佇列中沒有歌曲。\nNo songs currently in queue.")
        else:
            msg = "🎵 **目前播放佇列：**\n🎵 **Current Playlist:**\n"
            for idx, song in enumerate(queue):
                msg += f"{idx+1}. {song['title']}\n"
            await message.channel.send(msg)

    # 直接在 on_message 中處理停止播放（提升在播放期間的可靠度）
    elif content.startswith('[? stop') or content == '[? stop' or content.startswith('[stop') or content == '[stop':
        voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
        if voice_client and voice_client.is_connected():
            if is_currently_playing(message.guild.id):
                stop_current_playback(message.guild.id)
                await message.channel.send("已停止播放。\nPlayback stopped.")
                await log_action(message.guild, f"{message.author.display_name} 使用訊息事件停止播放")
            else:
                await message.channel.send("❌ 目前沒有歌曲在播放。\n❌ No song is currently playing.")
        else:
            await message.channel.send("機器人未在語音頻道。\nBot is not in a voice channel.")

    # 直接在 on_message 中處理跳過（提升在播放期間的可靠度）
    elif content.startswith('[? skip') or content.startswith('[skip') or content.startswith('[ skip'):
        voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
        if not voice_client or not voice_client.is_connected():
            await message.channel.send("機器人未在語音頻道。")
        else:
            # 解析數字參數
            try:
                parts = content.split()
                num = int(parts[2]) if len(parts) >= 3 else 1
            except Exception:
                num = 1
            queue = song_queues.get(message.guild.id, [])
            if num == 1:
                if is_currently_playing(message.guild.id):
                    stop_current_playback(message.guild.id)
                    await message.channel.send("⏭️ 已跳過目前播放的歌曲。\n⏭️ Skipped the currently playing song.")
                    await log_action(message.guild, f"{message.author.display_name} 使用訊息事件跳過 1 首歌曲")
                else:
                    await message.channel.send("❌ 目前沒有歌曲在播放。\n❌ No song is currently playing.")
            else:
                if num > len(queue) + 1:
                    await message.channel.send(f"❌ 佇列中只有 {len(queue)} 首歌曲，無法跳過 {num} 首。\n❌ There are only {len(queue)} songs in queue, cannot skip {num} songs.")
                else:
                    if is_currently_playing(message.guild.id):
                        stop_current_playback(message.guild.id)
                    songs_to_skip = num - 1
                    skipped = queue[:songs_to_skip]
                    song_queues[message.guild.id] = queue[songs_to_skip:]
                    if skipped:
                        titles = "\n".join(f"{i+1}. {s['title']}" for i, s in enumerate(skipped))
                        await message.channel.send(f"⏭️ 已跳過 {num} 首歌曲：\n{titles}")
                    else:
                        await message.channel.send(f"⏭️ 已跳過 {num} 首歌曲。")
                    await log_action(message.guild, f"{message.author.display_name} 使用訊息事件跳過 {num} 首歌曲")
                    if song_queues[message.guild.id]:
                        await play_next_song(message.guild, voice_client, message.channel)

    # 處理 [? dc] 指令（在 on_message 中提供同功能斷線）
    elif content.startswith('[? dc') or content.startswith('[dc') or content.startswith('[ dc'):
        voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
        if voice_client and voice_client.is_connected():
            if is_currently_playing(message.guild.id):
                stop_current_playback(message.guild.id)
            song_queues[message.guild.id] = []
            disconnect_reasons[message.guild.id] = 'user_dc'
            await voice_client.disconnect()
            await message.channel.send("已離開語音頻道並清空播放佇列。\nLeft voice channel and cleared playlist.")
            await log_action(message.guild, f"{message.author.display_name} 透過 [? dc] 讓機器人離開語音並清空佇列")
        else:
            await message.channel.send("機器人未在語音頻道。")

    # 處理 [? loop] 指令（在 on_message 中提供同功能）
    elif content.startswith('[? loop') or content.startswith('[loop') or content.startswith('[ loop'):
        voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
        if not voice_client or not voice_client.is_connected():
            await message.channel.send("機器人未在語音頻道。\nBot is not in a voice channel.")
            return
        
        # 啟用循環播放
        state = loop_states.get(message.guild.id) or {'enabled': False, 'current_song': None}
        state['enabled'] = True
        loop_states[message.guild.id] = state
        
        if is_currently_playing(message.guild.id):
            # 若尚未記錄目前歌曲，初始化之
            if state.get('current_song') is None:
                loop_states[message.guild.id] = state
            await message.channel.send("🔄 **循環播放已啟用**\n目前播放的歌曲將會重複播放，不影響佇列中的下一首歌曲。\n🔄 **Loop playback enabled**\nCurrent song will repeat, queue remains unchanged.")
            await log_action(message.guild, f"{message.author.display_name} 使用訊息事件啟用循環播放")
        else:
            await message.channel.send("🔄 **循環播放已啟用**\n下一首播放的歌曲將會重複播放，不影響佇列中的其他歌曲。\n🔄 **Loop playback enabled**\nNext song will repeat when played.")
            await log_action(message.guild, f"{message.author.display_name} 使用訊息事件啟用循環播放")

    # 處理 [? notloop] 指令（在 on_message 中提供同功能）
    elif content.startswith('[? notloop') or content.startswith('[notloop') or content.startswith('[ notloop'):
            voice_client = discord.utils.get(bot.voice_clients, guild=message.guild)
            if not voice_client or not voice_client.is_connected():
                await message.channel.send("機器人未在語音頻道。\nBot is not in a voice channel.")
                return
            
            # 停用循環播放
            if message.guild.id in loop_states:
                state = loop_states.get(message.guild.id) or {}
                was_enabled = state.get('enabled', False)
                state['enabled'] = False
                loop_states[message.guild.id] = state
                
                if was_enabled:
                    await message.channel.send("⏹️ **循環播放已停用**\n當前歌曲播放完畢後將播放佇列中的下一首歌曲。\n⏹️ **Loop playback disabled**\nCurrent song will finish, then play next song in queue.")
                    await log_action(message.guild, f"{message.author.display_name} 使用訊息事件停用循環播放")
                else:
                    await message.channel.send("❌ 循環播放本來就沒有啟用。\n❌ Loop playback was not enabled.")
            else:
                await message.channel.send("❌ 循環播放本來就沒有啟用。\n❌ Loop playback was not enabled.")

    await bot.process_commands(message)

# 停止播放指令
@bot.command(name="stop")
@server_channel_restriction()
async def stop(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        if is_currently_playing(ctx.guild.id):
            stop_current_playback(ctx.guild.id)
            await ctx.send("已停止播放。\nPlayback stopped.")
            await log_action(ctx.guild, f"{ctx.author.display_name} 已停止播放")
        else:
            await ctx.send("❌ 目前沒有歌曲在播放。\n❌ No song is currently playing.")
        # 不再自動斷線和清空佇列
    else:
        await ctx.send("機器人未在語音頻道。\nBot is not in a voice channel.")

# 繼續播放指令
@bot.command(name="K")
@server_channel_restriction()
async def continue_play(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        if not voice_client.is_playing():
            queue = song_queues.get(ctx.guild.id, [])
            if queue:
                await play_next_song(ctx.guild, voice_client, ctx.channel)
                await ctx.send("已繼續播放音樂。\nMusic playback resumed.")
                await log_action(ctx.guild, f"{ctx.author.display_name} 已繼續播放音樂")
            else:
                await ctx.send("佇列中沒有歌曲可播放。\nNo songs available to play in queue.")
        else:
            await ctx.send("音樂正在播放中。\nMusic is already playing.")
    else:
        await ctx.send("機器人未在語音頻道。\nBot is not in a voice channel.")

# 繼續播放指令（小寫別名）
@bot.command(name="k")
@server_channel_restriction()
async def continue_play_lower(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        if not voice_client.is_playing():
            queue = song_queues.get(ctx.guild.id, [])
            if queue:
                await play_next_song(ctx.guild, voice_client, ctx.channel)
                await ctx.send("已繼續播放音樂。\nMusic playback resumed.")
                await log_action(ctx.guild, f"{ctx.author.display_name} 已繼續播放音樂")
            else:
                await ctx.send("佇列中沒有歌曲可播放。\nNo songs available to play in queue.")
        else:
            await ctx.send("音樂正在播放中。\nMusic is already playing.")
    else:
        await ctx.send("機器人未在語音頻道。\nBot is not in a voice channel.")

# 權限請求指令
@bot.command(name="permission")
@security_validator(input_type='general')
async def request_permission(ctx, count: int):
    # 數字範圍驗證
    if not validate_number_range(count, 1, 5):
        await safe_error_response(ctx, 'INVALID_NUMBER')
        return
    
    # 檢查是否在冷卻時間中
    is_on_cooldown, remaining_time, is_high_cooldown = await check_permission_cooldown(ctx)
    if is_on_cooldown:
        if is_high_cooldown:
            # 高權限冷卻（1 小時）
            hours = int(remaining_time // 3600)
            minutes = int((remaining_time % 3600) // 60)
            seconds = int(remaining_time % 60)
            await ctx.send(f"🚫 **高權限冷卻中！**\n"
                           f"您需要等待 {hours} 小時 {minutes} 分 {seconds} 秒後才能再次請求權限\n"
                           f"⚠️ 這是因為您使用了清空佇列等高權限功能\n\n"
                           f"🚫 **High Permission Cooldown!**\n"
                           f"You need to wait {hours} hours {minutes} minutes {seconds} seconds before requesting permission again\n"
                           f"⚠️ This is because you used high-permission functions like clearing queue")
        else:
            # 一般權限冷卻（10 分鐘）
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            await ctx.send(f"⏰ **權限請求冷卻中！**\n"
                           f"您需要等待 {minutes} 分 {seconds} 秒後才能再次請求權限\n"
                           f"💡 冷卻時間是為了防止權限濫用\n\n"
                           f"⏰ **Permission Request Cooldown!**\n"
                           f"You need to wait {minutes} minutes {seconds} seconds before requesting permission again\n"
                           f"💡 Cooldown time is to prevent permission abuse")
        return
    
    # 檢查是否已經有權限
    has_permission, remaining_count, is_admin = await check_edit_permission(ctx)
    if has_permission and not is_admin:
        await ctx.send(f"⚠️ **您已經有編輯權限！**\n"
                       f"剩餘次數：{remaining_count}\n"
                       f"請先使用完目前的權限再請求新的權限\n\n"
                       f"⚠️ **You already have edit permissions!**\n"
                       f"Remaining uses: {remaining_count}\n"
                       f"Please use up your current permissions before requesting new ones")
        return
    
    # 自動核准權限
    await grant_edit_permission(ctx, count)
    
    await ctx.send(f"✅ **權限已核准！**\n"
                   f"您現在可以編輯播放清單 {count} 次\n"
                   f"⏰ 權限將在 10 分鐘後自動過期\n"
                   f"🔄 權限用完後需要等待 10 分鐘才能再次請求\n"
                   f"📝 使用 `[? editlist` 來編輯播放清單\n\n"
                   f"✅ **Permission Granted!**\n"
                   f"You can now edit the playlist {count} times\n"
                   f"⏰ Permission will expire automatically in 10 minutes\n"
                   f"🔄 You need to wait 10 minutes after using up permissions to request again\n"
                   f"📝 Use `[? editlist` to edit the playlist")

# 清空佇列指令（需要權限等級 5）
@bot.command(name="empy")
@server_channel_restriction()
async def empty_queue(ctx):
    # 檢查權限
    has_permission, remaining_count, is_admin = await check_edit_permission(ctx)
    if not has_permission:
        await ctx.send("❌ **權限不足！**\n"
                       "請先使用 `[? permission 5` 來請求編輯權限\n"
                       "或聯繫管理員獲得權限\n\n"
                       "❌ **Insufficient Permissions!**\n"
                       "Please use `[? permission 5` to request edit permissions\n"
                       "or contact an administrator for permissions")
        return
    
    # 檢查權限等級是否足夠（需要至少 5 次權限）
    if not is_admin and remaining_count < 5:
        await ctx.send("❌ **權限等級不足！**\n"
                       f"清空佇列需要權限等級 5，您目前只有 {remaining_count} 次權限\n"
                       "請重新請求 `[? permission 5` 來獲得足夠的權限\n\n"
                       "❌ **Insufficient Permission Level!**\n"
                       f"Clearing queue requires permission level 5, you currently have {remaining_count} permissions\n"
                       "Please request `[? permission 5` to get sufficient permissions")
        return
    
    queue = song_queues.get(ctx.guild.id, [])
    if queue:
        song_queues[ctx.guild.id] = []
        await ctx.send("🗑️ **播放佇列已清空！**\n"
                       "⚠️ **注意：** 這是高權限操作！\n"
                       "您的權限將進入 1 小時冷卻期。\n\n"
                       "🗑️ **Playlist Cleared!**\n"
                       "⚠️ **Notice:** This is a high-permission operation!\n"
                       "Your permissions will enter a 1-hour cooldown period.")
        await log_action(ctx.guild, f"{ctx.author.display_name} 已清空播放佇列（高權限操作）")
        
        # 使用權限後立即結束並設定 1 小時冷卻（管理員除外）
        if not is_admin:
            # 立即移除權限並設定 1 小時冷卻時間
            guild_id = ctx.guild.id
            user_id = ctx.author.id
            if guild_id in edit_permissions and user_id in edit_permissions[guild_id]:
                del edit_permissions[guild_id][user_id]
                
                # 設定 1 小時冷卻時間（3600 秒）
                if guild_id not in high_permission_cooldowns:
                    high_permission_cooldowns[guild_id] = {}
                high_permission_cooldowns[guild_id][user_id] = asyncio.get_event_loop().time()
                
                await ctx.send("🔒 **高權限冷卻啟動**\n"
                               "由於使用了清空佇列功能，您需要等待 **1 小時** 後才能再次請求權限。\n"
                               "⚠️ 這是為了防止濫用高權限功能。\n\n"
                               "🔒 **High Permission Cooldown Activated**\n"
                               "Due to using the clear queue function, you need to wait **1 hour** before requesting permissions again.\n"
                               "⚠️ This is to prevent abuse of high-permission functions.")
    else:
        await ctx.send("❌ 佇列中本來就沒有歌曲。\n❌ There are no songs in the queue.")

# 循環播放指令
@bot.command(name="loop")
@server_channel_restriction()
async def toggle_loop(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        await ctx.send("機器人未在語音頻道。\nBot is not in a voice channel.")
        return
    
    # 啟用循環播放（預設關閉，這裡開啟）
    state = loop_states.get(ctx.guild.id) or {'enabled': False, 'current_song': None}
    state['enabled'] = True
    loop_states[ctx.guild.id] = state
    
    if is_currently_playing(ctx.guild.id):
        # 若尚未記錄目前歌曲，初始化之
        if state.get('current_song') is None:
            loop_states[ctx.guild.id] = state
        await ctx.send("🔄 **循環播放已啟用**\n目前播放的歌曲將會重複播放，不影響佇列中的下一首歌曲。\n🔄 **Loop playback enabled**\nCurrent song will repeat, queue remains unchanged.")
        await log_action(ctx.guild, f"{ctx.author.display_name} 已啟用循環播放")
    else:
        await ctx.send("🔄 **循環播放已啟用**\n下一首播放的歌曲將會重複播放，不影響佇列中的其他歌曲。\n🔄 **Loop playback enabled**\nNext song will repeat when played.")
        await log_action(ctx.guild, f"{ctx.author.display_name} 已啟用循環播放")

# 停止循環播放指令
@bot.command(name="notloop")
@server_channel_restriction()
async def stop_loop(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        await ctx.send("機器人未在語音頻道。")
        return
    
    # 停用循環播放
    if ctx.guild.id in loop_states:
        state = loop_states.get(ctx.guild.id) or {}
        was_enabled = state.get('enabled', False)
        state['enabled'] = False
        loop_states[ctx.guild.id] = state
        
        if was_enabled:
            await ctx.send("⏹️ **循環播放已停用**\n當前歌曲播放完畢後將播放佇列中的下一首歌曲。\n⏹️ **Loop playback disabled**\nCurrent song will finish, then play next song in queue.")
            await log_action(ctx.guild, f"{ctx.author.display_name} 已停用循環播放")
        else:
            await ctx.send("❌ 循環播放本來就沒有啟用。\n❌ Loop playback was not enabled.")
    else:
        await ctx.send("❌ 循環播放本來就沒有啟用。\n❌ Loop playback was not enabled.")

# 跳過歌曲指令
@bot.command(name="skip")
@security_validator(input_type='general')
async def skip_songs(ctx, number: int = 1):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        await ctx.send("機器人未在語音頻道。")
        return
    
    queue = song_queues.get(ctx.guild.id, [])
    
    # 數字範圍驗證
    if not validate_number_range(number, 1, 50):
        await safe_error_response(ctx, 'INVALID_NUMBER')
        return
    
    if number == 1:
        # 跳過目前播放的歌曲
        if is_currently_playing(ctx.guild.id):
            stop_current_playback(ctx.guild.id)
            await ctx.send("⏭️ 已跳過目前播放的歌曲。\n⏭️ Skipped the currently playing song.")
            await log_action(ctx.guild, f"{ctx.author.display_name} 已跳過目前播放的歌曲")
        else:
            await ctx.send("❌ 目前沒有歌曲在播放。\n❌ No song is currently playing.")
        return
    
    # 跳過多首歌曲
    if number > len(queue) + 1:  # +1 是因為要包含目前播放的歌曲
        await ctx.send(f"❌ 佇列中只有 {len(queue)} 首歌曲，無法跳過 {number} 首。\n❌ There are only {len(queue)} songs in queue, cannot skip {number} songs.")
        return
    
    # 停止目前播放
    if is_currently_playing(ctx.guild.id):
        stop_current_playback(ctx.guild.id)
    
    # 從佇列中移除要跳過的歌曲
    songs_to_skip = number - 1  # 減1是因為已經停止了目前播放的歌曲
    skipped_songs = queue[:songs_to_skip]
    song_queues[ctx.guild.id] = queue[songs_to_skip:]
    
    # 顯示跳過資訊
    if skipped_songs:
        skipped_titles = [song['title'] for song in skipped_songs]
        skip_msg = f"⏭️ 已跳過 {number} 首歌曲：\n"
        for i, title in enumerate(skipped_titles, 1):
            skip_msg += f"{i}. {title}\n"
        await ctx.send(skip_msg)
        await log_action(ctx.guild, f"{ctx.author.display_name} 已跳過 {number} 首歌曲")
    else:
        await ctx.send(f"⏭️ 已跳過 {number} 首歌曲。")
        await log_action(ctx.guild, f"{ctx.author.display_name} 已跳過 {number} 首歌曲")
    
    # 如果佇列還有歌曲，開始播放下一首
    if song_queues[ctx.guild.id]:
        await play_next_song(ctx.guild, voice_client, ctx.channel)

# 斷線並清空佇列指令
@bot.command(name="dc")
@server_channel_restriction()
async def disconnect_bot(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        # 停止播放
        if is_currently_playing(ctx.guild.id):
            stop_current_playback(ctx.guild.id)
        # 清空佇列
        song_queues[ctx.guild.id] = []
        # 離開語音頻道（標記為使用者要求）
        disconnect_reasons[ctx.guild.id] = 'user_dc'
        await voice_client.disconnect()
        await ctx.send("已離開語音頻道並清空播放佇列。\nLeft voice channel and cleared playlist.")
        await log_action(ctx.guild, f"{ctx.author.display_name} 已讓機器人離開語音頻道並清空佇列")
    else:
        await ctx.send("機器人未在語音頻道。")

# 編輯播放清單指令
@bot.command(name="editlist")
@security_validator(input_type='general')
async def edit_playlist(ctx, action: str, *args):
    """
    編輯播放清單指令
    支援的操作：
    - move <from> <to> : 移動歌曲位置
    - play <position> : 立即播放指定位置的歌曲
    - remove <position> : 移除指定位置的歌曲
    - swap <pos1> <pos2> : 交換兩個位置的歌曲
    """
    # 檢查權限
    has_permission, remaining_count, is_admin = await check_edit_permission(ctx)
    if not has_permission:
        await ctx.send("❌ **權限不足！**\n"
                       "請先使用 `[? permission <次數>` 來請求編輯權限\n"
                       "或聯繫管理員獲得權限\n\n"
                       "❌ **Insufficient Permissions!**\n"
                       "Please use `[? permission <count>` to request edit permissions\n"
                       "or contact an administrator for permissions")
        return
    
    # 檢查語音頻道
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        await ctx.send("❌ 機器人未在語音頻道中！\n❌ Bot is not in a voice channel!")
        return
    
    queue = song_queues.get(ctx.guild.id, [])
    if not queue:
        await ctx.send("❌ 播放清單中沒有歌曲！\n❌ No songs in the playlist!")
        return
    
    try:
        if action.lower() == "move":
            if len(args) != 2:
                await ctx.send("❌ 用法：`[? editlist move <從位置> <到位置>`\n❌ Usage: `[? editlist move <from position> <to position>`")
                return
            
            from_pos = int(args[0])
            to_pos = int(args[1])
            
            if from_pos < 1 or from_pos > len(queue) or to_pos < 1 or to_pos > len(queue):
                await ctx.send(f"❌ 位置必須在 1-{len(queue)} 之間！")
                return
            
            # 移動歌曲
            song = queue.pop(from_pos - 1)
            queue.insert(to_pos - 1, song)
            song_queues[ctx.guild.id] = queue
            
            await ctx.send(f"✅ **歌曲已移動！**\n"
                           f"🎵 {song['title']}\n"
                           f"📍 從第 {from_pos} 位移動到第 {to_pos} 位")
            
        elif action.lower() == "play":
            if len(args) != 1:
                await ctx.send("❌ 用法：`[? editlist play <位置>`")
                return
            
            position = int(args[0])
            if position < 1 or position > len(queue):
                await ctx.send(f"❌ 位置必須在 1-{len(queue)} 之間！")
                return
            
            # 將指定歌曲移到第一位並立即播放
            song = queue.pop(position - 1)
            queue.insert(0, song)
            song_queues[ctx.guild.id] = queue
            
            # 停止目前播放並開始新歌曲
            if voice_client.is_playing():
                voice_client.stop()
            
            await ctx.send(f"🎵 **立即播放！**\n"
                           f"正在播放：{song['title']}\n"
                           f"📍 從第 {position} 位移動到第 1 位")
            
            # 開始播放
            await play_next_song(ctx.guild, voice_client, ctx.channel)
            
        elif action.lower() == "remove":
            if len(args) != 1:
                await ctx.send("❌ 用法：`[? editlist remove <位置>`")
                return
            
            position = int(args[0])
            if position < 1 or position > len(queue):
                await ctx.send(f"❌ 位置必須在 1-{len(queue)} 之間！")
                return
            
            # 移除歌曲
            removed_song = queue.pop(position - 1)
            song_queues[ctx.guild.id] = queue
            
            await ctx.send(f"🗑️ **歌曲已移除！**\n"
                           f"🎵 {removed_song['title']}\n"
                           f"📍 從第 {position} 位移除")
            
        elif action.lower() == "swap":
            if len(args) != 2:
                await ctx.send("❌ 用法：`[? editlist swap <位置1> <位置2>`")
                return
            
            pos1 = int(args[0])
            pos2 = int(args[1])
            
            if pos1 < 1 or pos1 > len(queue) or pos2 < 1 or pos2 > len(queue):
                await ctx.send(f"❌ 位置必須在 1-{len(queue)} 之間！")
                return
            
            # 交換歌曲
            queue[pos1 - 1], queue[pos2 - 1] = queue[pos2 - 1], queue[pos1 - 1]
            song_queues[ctx.guild.id] = queue
            
            song1 = queue[pos1 - 1]
            song2 = queue[pos2 - 1]
            
            await ctx.send(f"🔄 **歌曲已交換！**\n"
                           f"🎵 {song1['title']} ↔️ {song2['title']}\n"
                           f"📍 第 {pos1} 位 ↔️ 第 {pos2} 位")
            
        else:
            await ctx.send("❌ **不支援的操作！**\n\n"
                           "**支援的操作：**\n"
                           "• `[? editlist move <從位置> <到位置>` - 移動歌曲\n"
                           "• `[? editlist play <位置>` - 立即播放指定歌曲\n"
                           "• `[? editlist remove <位置>` - 移除歌曲\n"
                           "• `[? editlist swap <位置1> <位置2>` - 交換歌曲\n\n"
                           "**範例：**\n"
                           "• `[? editlist move 2 6` - 將第2首歌曲移動到第6位\n"
                           "• `[? editlist play 5` - 立即播放第5首歌曲\n"
                           "• `[? editlist swap 1 3` - 交換第1位和第3位的歌曲")
            return
        
        # 使用權限（管理員除外）
        if not is_admin:
            await use_edit_permission(ctx)
        
        # 記錄操作
        await log_action(ctx.guild, f"{ctx.author.display_name} 使用 editlist 指令：{action} {' '.join(args)}")
        
    except ValueError:
        await ctx.send("❌ 位置必須是數字！\n❌ Position must be a number!")
    except Exception as e:
        await ctx.send(f"❌ 操作失敗：{e}\n❌ Operation failed: {e}")

# URL 播放指令（支援多平台）
@bot.command(name="url")
@security_validator(input_type='url')
async def play_url(ctx, url: str):
    # 檢查使用者是否在語音頻道
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("請先加入一個語音頻道。\nPlease join a voice channel first.")
        return

    voice_channel = ctx.author.voice.channel
    
    # URL 已經在安全驗證器中驗證過了，這裡直接使用

    # 初始化佇列
    if ctx.guild.id not in song_queues:
        song_queues[ctx.guild.id] = []

    queue = song_queues[ctx.guild.id]
    if len(queue) >= 50:
        await ctx.send("歌曲佇列已達上限（50 首），請等待佇列有空位後再新增。\nSong queue has reached the limit (50 songs). Please wait for space in the queue before adding more.")
        return

    # 加入語音頻道
    voice_client = await connect_to_voice_channel(ctx.guild, voice_channel, ctx)
    if not voice_client:
        return

    # 根據平台處理音樂
    try:
        async with ctx.channel.typing():
            url_lower = url.lower()
            if any(domain in url_lower for domain in ['youtube.com', 'youtu.be']):
                # YouTube 處理
                player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
                song_info = {
                    'title': player.title,
                    'url': url,
                    'requester': ctx.author.display_name,
                    'platform': 'YouTube'
                }
            elif any(domain in url_lower for domain in ['spotify.com', 'open.spotify.com']):
                # Spotify 處理 - 提供實用建議
                await ctx.send("🎵 **Spotify 連結檢測到！**\n\n"
                             "💡 **實用建議：**\n"
                             "1. **複製歌曲/專輯名稱** 到 YouTube 搜尋\n"
                             "2. **使用指令：** `[? youtube 歌曲名稱`\n"
                             "3. **或提供 YouTube 連結**\n\n"
                             "🔍 **例如：**\n"
                             "• `[? youtube Maroon 5 Love is Like`\n"
                             "• `[? youtube 周杰倫 青花瓷`\n\n"
                             "❌ **目前限制：** Spotify 直接播放需要 API 登入\n"
                             "✅ **解決方案：** 手動搜尋歌曲名稱")
                return
            elif any(domain in url_lower for domain in ['music.apple.com', 'itunes.apple.com']):
                # Apple Music 處理
                await ctx.send("🎵 正在處理 Apple Music 連結...\n🎵 Processing Apple Music link...")
                song_info = {
                    'title': f"Apple Music - {url}",
                    'url': url,
                    'requester': ctx.author.display_name,
                    'platform': 'Apple Music'
                }
            elif any(domain in url_lower for domain in ['soundcloud.com']):
                # SoundCloud 處理
                await ctx.send("🎵 正在處理 SoundCloud 連結...\n🎵 Processing SoundCloud link...")
                song_info = {
                    'title': f"SoundCloud - {url}",
                    'url': url,
                    'requester': ctx.author.display_name,
                    'platform': 'SoundCloud'
                }
            else:
                await ctx.send("❌ 無法識別音樂平台。\n❌ Unable to identify music platform.")
                return

            # 加入佇列
            queue.append(song_info)
            platform_text = song_info.get('platform', 'URL')
            await ctx.send(f"✅ 已將 **{song_info['title']}** 加入佇列（目前共 {len(queue)} 首）。\n🎵 平台：{platform_text}\n\n✅ Added **{song_info['title']}** to queue (total: {len(queue)} songs).\n🎵 Platform: {platform_text}")
            await log_action(ctx.guild, f"{ctx.author.display_name} 已將 {song_info['title']} ({song_info['platform']}) 加入佇列")
            
            # 如果不是正在播放，則開始播放
            if not voice_client.is_playing():
                await play_next_song(ctx.guild, voice_client, ctx.channel)
                
    except Exception as e:
        await ctx.send(f"❌ 處理音樂連結失敗: {e}\n\n請確認連結是否有效，或稍後再試。\n\n❌ Failed to process music link: {e}\n\nPlease confirm if the link is valid, or try again later.")


# ... existing code ...

# 服務器狀態監控指令（僅限管理員）
@bot.command(name="serverstats")
@server_channel_restriction()
async def server_stats(ctx):
    # 檢查是否為管理員（包含硬編碼超級管理員）
    if not (ctx.author.guild_permissions.administrator or ctx.author.id in HARD_ADMIN_USER_IDS):
        return  # 靜默忽略非管理員的請求
    
    # 獲取服務器狀態
    stats_message = await get_server_stats()
    
    # 發送到 log-it 頻道
    log_channel = await get_log_channel(ctx.guild)
    if log_channel:
        await log_channel.send(stats_message)
        await log_action(ctx.guild, f"{ctx.author.display_name} 查詢了服務器狀態")
        # 若指令不在 log-it 發出，也回覆 "已傳送至 log-it"
        if str(ctx.channel.id) != LOG_IT_CHANNEL_ID:
            await ctx.send("已將資訊發送至 log-it 頻道。")
    else:
        await ctx.send("⚠️ 找不到 log-it 頻道，在此顯示狀態：\n⚠️ log-it channel not found, showing stats here:\n\n" + stats_message)

# 服務器狀態監控指令（簡短別名）
@bot.command(name="mo")
@server_channel_restriction()
async def server_stats_short(ctx):
    # 檢查是否為管理員（包含硬編碼超級管理員）
    if not (ctx.author.guild_permissions.administrator or ctx.author.id in HARD_ADMIN_USER_IDS):
        return  # 靜默忽略非管理員的請求
    
    # 獲取服務器狀態
    stats_message = await get_server_stats()
    
    # 發送到 log-it 頻道
    log_channel = await get_log_channel(ctx.guild)
    if log_channel:
        await log_channel.send(stats_message)
        await log_action(ctx.guild, f"{ctx.author.display_name} 查詢了服務器狀態 (mo)")
        if str(ctx.channel.id) != LOG_IT_CHANNEL_ID:
            await ctx.send("已將資訊發送至 log-it 頻道。")
    else:
        await ctx.send("⚠️ 找不到 log-it 頻道，在此顯示狀態：\n⚠️ log-it channel not found, showing stats here:\n\n" + stats_message)

# 重啟 bot 指令（僅限管理員）
@bot.command(name="reboot")
@server_channel_restriction()
async def reboot_bot(ctx):
    # 檢查是否為管理員（包含硬編碼超級管理員）
    if not (ctx.author.guild_permissions.administrator or ctx.author.id in HARD_ADMIN_USER_IDS):
        await ctx.send("❌ **權限不足！**\n只有管理員才能重啟 bot。\n\n❌ **Insufficient Permissions!**\nOnly administrators can restart the bot.")
        return
    
    await ctx.send("🔄 **正在重啟 bot...**\n請稍候，bot 將在幾秒內重新上線。\n\n🔄 **Restarting bot...**\nPlease wait, the bot will be back online in a few seconds.")
    await log_action(ctx.guild, f"{ctx.author.display_name} 已重啟 bot")
    
    # 延遲一下讓訊息發送完成
    await asyncio.sleep(2)
    
    # 重啟 bot
    try:
        await bot.close()
    except Exception as e:
        print(f"重啟失敗: {e}")
        await ctx.send("❌ 重啟失敗，請手動重啟 environment。")

if __name__ == "__main__":
    # 驗證環境變數
    if not validate_environment():
        print("❌ 環境變數驗證失敗，機器人無法啟動")
        exit(1)
    
    # 啟動機器人
    bot.run(TOKEN)


            