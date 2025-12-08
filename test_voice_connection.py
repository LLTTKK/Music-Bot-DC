#!/usr/bin/env python3
"""
語音連接測試腳本
用於測試 Discord 機器人的語音連接功能
"""

import discord
from discord.ext import commands
import asyncio
import os
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
discord_logger = logging.getLogger('discord.voice_client')
discord_logger.setLevel(logging.DEBUG)

# 設定機器人權限意圖
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='!test', intents=intents)

async def test_voice_connection(guild, voice_channel, channel):
    """
    測試語音連接功能
    """
    voice_client = discord.utils.get(bot.voice_clients, guild=guild)
    max_retries = 3
    retry_count = 0
    
    print(f"開始測試語音連接到 {voice_channel.name}")
    
    while retry_count < max_retries:
        try:
            if not voice_client or not voice_client.is_connected():
                print(f"嘗試連接 (第 {retry_count + 1} 次)...")
                voice_client = await voice_channel.connect(
                    timeout=30.0,
                    reconnect=True,
                    self_deaf=True
                )
                print("✅ 語音連接成功！")
            elif voice_client.channel != voice_channel:
                print("移動到新的語音頻道...")
                await voice_client.move_to(voice_channel)
                print("✅ 成功移動到新頻道！")
            
            # 測試連接狀態
            if voice_client.is_connected():
                print(f"✅ 連接狀態: 已連接到 {voice_client.channel.name}")
                print(f"✅ 延遲: {voice_client.latency * 1000:.2f}ms")
                return voice_client
            else:
                print("❌ 連接失敗")
                return None
                
        except discord.errors.ClientException as e:
            if "already connected" in str(e).lower():
                print("檢測到重複連接，嘗試重新連接...")
                try:
                    await voice_client.disconnect(force=True)
                    await asyncio.sleep(2)
                    voice_client = await voice_channel.connect(
                        timeout=30.0,
                        reconnect=True,
                        self_deaf=True
                    )
                    print("✅ 重新連接成功！")
                    return voice_client
                except Exception as reconnect_error:
                    print(f"❌ 重新連接失敗: {reconnect_error}")
                    
            retry_count += 1
            if retry_count >= max_retries:
                print(f"❌ 連接失敗 (已重試 {max_retries} 次): {e}")
                return None
            print(f"等待 2 秒後重試...")
            await asyncio.sleep(2)
            
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                print(f"❌ 連接失敗 (已重試 {max_retries} 次): {e}")
                return None
            print(f"發生錯誤: {e}")
            print(f"等待 2 秒後重試...")
            await asyncio.sleep(2)
    
    return None

@bot.event
async def on_ready():
    print(f'測試機器人已登入: {bot.user}')
    print('語音連接測試腳本已準備就緒')

@bot.command(name='voice_test')
async def voice_test(ctx):
    """測試語音連接"""
    if not ctx.author.voice:
        await ctx.send("❌ 請先加入一個語音頻道")
        return
    
    voice_channel = ctx.author.voice.channel
    await ctx.send(f"🔄 開始測試連接到 {voice_channel.name}...")
    
    voice_client = await test_voice_connection(ctx.guild, voice_channel, ctx.channel)
    
    if voice_client:
        await ctx.send("✅ 語音連接測試成功！")
        # 等待 5 秒後斷開
        await asyncio.sleep(5)
        await voice_client.disconnect()
        await ctx.send("✅ 測試完成，已斷開連接")
    else:
        await ctx.send("❌ 語音連接測試失敗")

if __name__ == "__main__":
    # 從環境變數讀取 Token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ 請設定 DISCORD_TOKEN 環境變數")
        exit(1)
    
    print("啟動語音連接測試...")
    bot.run(token)
