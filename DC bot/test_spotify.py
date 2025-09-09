#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試無 API Spotify 支援功能
"""

import asyncio
import yt_dlp

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

async def test_spotify_extraction(url):
    """
    測試 Spotify 內容提取
    """
    print(f"🔍 測試 URL: {url}")
    
    content_type, content_id = parse_spotify_url(url)
    print(f"📊 解析結果: 類型={content_type}, ID={content_id}")
    
    if not content_type or not content_id:
        print("❌ URL 解析失敗")
        return
    
    try:
        # 使用 yt-dlp 提取 Spotify 內容
        ytdl_opts = {
            'extract_flat': True,
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': True,
        }
        
        ytdl = yt_dlp.YoutubeDL(ytdl_opts)
        
        print("🔄 正在提取 Spotify 內容...")
        data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: ytdl.extract_info(url, download=False)
        )
        
        if not data:
            print("❌ 無法提取內容")
            return
        
        print(f"✅ 提取成功！")
        print(f"📊 標題: {data.get('title', 'N/A')}")
        print(f"📊 類型: {data.get('_type', 'N/A')}")
        
        if 'entries' in data and data['entries']:
            print(f"📊 歌曲數量: {len(data['entries'])}")
            print("🎵 前 3 首歌曲:")
            for i, entry in enumerate(data['entries'][:3]):
                if entry and isinstance(entry, dict):
                    title = entry.get('title', 'Unknown')
                    artist = entry.get('uploader', entry.get('channel', 'Unknown'))
                    print(f"  {i+1}. {title} - {artist}")
        else:
            print("📊 單曲或無法提取播放清單")
            
    except Exception as e:
        print(f"❌ 提取失敗: {e}")

async def main():
    """
    主測試函數
    """
    print("🎵 測試無 API Spotify 支援")
    print("=" * 50)
    
    # 測試不同的 Spotify URL
    test_urls = [
        "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh",  # 單曲
        "https://open.spotify.com/album/7G1LFDr4XyDOmn8bdkvojJ",  # 專輯
        "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd",  # 播放清單
    ]
    
    for url in test_urls:
        print("\n" + "=" * 50)
        await test_spotify_extraction(url)
        await asyncio.sleep(1)  # 避免請求過於頻繁
    
    print("\n" + "=" * 50)
    print("✅ 測試完成！")

if __name__ == "__main__":
    asyncio.run(main())
