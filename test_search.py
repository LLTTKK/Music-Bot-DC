#!/usr/bin/env python3
"""
測試 YouTube 搜尋功能的獨立腳本
"""
import asyncio
import yt_dlp

async def test_search():
    query = "never gonna give you up"
    search_query = f"ytsearch5:{query}"
    
    search_opts = {
        'extract_flat': True,
        'quiet': False,
        'ignoreerrors': True,
        'skip_download': True,
    }
    
    print(f"🔍 測試搜尋: {search_query}")
    
    ytdl = yt_dlp.YoutubeDL(search_opts)
    
    try:
        result = ytdl.extract_info(search_query, download=False)
        print(f"📊 結果類型: {type(result)}")
        
        if result and isinstance(result, dict):
            print(f"📊 鍵值: {list(result.keys())}")
            
            if 'entries' in result and result['entries']:
                print(f"✅ 找到 {len(result['entries'])} 個結果:")
                for i, entry in enumerate(result['entries'][:3]):
                    if entry:
                        title = entry.get('title', 'Unknown')
                        video_id = entry.get('id', 'No ID')
                        print(f"  {i+1}. {title} (ID: {video_id})")
            else:
                print("❌ 沒有 entries 或為空")
        else:
            print("❌ 結果不是字典或為空")
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
