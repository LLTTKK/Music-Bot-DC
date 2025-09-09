# Discord Music Bot 🎵

一個功能豐富且安全的 Discord 音樂機器人，支援多平台音樂播放、進階播放清單管理和企業級安全功能。

## ✨ 功能特色

### 🎵 音樂播放
- **YouTube 搜尋與播放** - 支援關鍵字搜尋和直接 URL 播放
- **多平台支援** - YouTube, Spotify, Apple Music, SoundCloud
- **串流偏好 HLS** - 優先 `m3u8`（較穩定），並使用 `tv → web` client 流程
- **可選 PO Token** - 只有在提供 PO Token 時，才會嘗試 `android/ios` client
- **自動廣告過濾** - 整合 SponsorBlock API，已加入 UA、精簡分類；API 400 僅記錄不影響播放
- **智能播放佇列** - 最多支援 50 首歌曲的播放佇列
- **互動式選單** - 搜尋結果的視覺化選擇介面

### 🎛️ 播放控制
- **靈活的播放控制** - 播放、暫停、跳過、繼續
- **預設不循環** - 預設 `not loop`，使用者啟用後才會單曲循環（不影響佇列）
- **批量跳過** - 可一次跳過多首歌曲
- **即時狀態顯示** - 實時播放狀態和佇列資訊
- **斷線行為** -
  - 佇列播畢：自動離線並清空佇列，於 `log-it` 與最後使用的音樂頻道提示
  - 使用者斷線：清空佇列並提示離線
  - 強制斷線：不自動重連，提示警告並清空佇列

### 🔐 進階權限系統
- **分級權限管理** - 1-5 級權限控制
- **智能冷卻機制** - 一般權限 10 分鐘，高權限 1 小時冷卻
- **管理員特權** - 無限制編輯權限和專屬指令
- **權限自動過期** - 10 分鐘自動過期，防止濫用

### 🛡️ 企業級安全功能
- **輸入驗證與過濾** - 長度限制、字符白名單、惡意模式檢測
- **內容安全過濾** - URL 域名驗證、敏感關鍵字過濾
- **輸入清理與轉義** - HTML 轉義、Unicode 正規化
- **增強錯誤處理** - 安全錯誤訊息、詳細安全日誌
- **攻擊防護** - 防止 XSS、腳本注入、路徑遍歷等攻擊

### 🌐 雙語支援
- **完整雙語介面** - 繁體中文 / English 雙語支援
- **本地化錯誤訊息** - 所有錯誤和提示都有雙語版本

### 📊 系統監控
- **即時服務器狀態** - CPU、記憶體、磁碟、網路使用率監控
- **詳細運行日誌** - 所有操作都記錄到 log-it 頻道
- **管理員專用統計** - 服務器狀態查詢和 Bot 重啟功能

## 🚀 雲端部署

### Railway 部署 (推薦)

機器人現在使用環境變數進行配置，提供更好的安全性和靈活性。

#### 快速部署步驟

1. **Fork 此倉庫** 到您的 GitHub 帳號
2. **連接 Railway**：
   - 前往 [Railway](https://railway.app)
   - 點擊 "New Project" → "Deploy from GitHub repo"
   - 選擇您的倉庫

3. **設定環境變數**：
   - 在 Railway 專案中，前往 "Variables" 頁面
   - 添加以下必要的環境變數：

   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   DISCORD_APPLICATION_ID=your_application_id_here
   DISCORD_PUBLIC_KEY=your_public_key_here
   ALLOWED_SERVER_ID=your_server_id_here
   ALLOWED_CHANNEL_ID=your_channel_id_here
   LOG_IT_CHANNEL_ID=your_log_channel_id_here
   HARD_ADMIN_USER_IDS=123456789012345678,987654321098765432
   ```

4. **部署完成**：Railway 會自動構建和部署您的機器人

#### 詳細設定指南

請參考以下文件了解詳細的設定步驟：
- [Railway 環境變數設定指南](RAILWAY_ENV_SETUP.md)
- [Discord 機器人配置說明](CONFIG_SETUP.md)

本專案已 **Docker 化**，Railway 以 Dockerfile 建置，依賴安裝在映像層，重建更快。

### Render 部署

1. Fork 此 repository
2. 前往 [Render](https://render.com/)
3. 點擊 "New" → "Web Service"
4. 連接您的 GitHub repository
5. 配置：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
6. 添加環境變數：
   - `DISCORD_TOKEN`: 您的 Discord Bot Token
7. 部署！

### Heroku 部署

1. 安裝 Heroku CLI
2. 登入 Heroku: `heroku login`
3. 創建應用: `heroku create your-bot-name`
4. 設定環境變數: `heroku config:set DISCORD_TOKEN=your_token_here`
5. 部署: `git push heroku main`

## 🔧 本地開發

### 安裝依賴
```bash
pip install -r requirements.txt
```

### 設定環境變數
1. 複製環境變數範例文件：
   ```bash
   cp env.example .env
   ```

2. 編輯 `.env` 文件並填入實際值：
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   DISCORD_APPLICATION_ID=your_application_id_here
   DISCORD_PUBLIC_KEY=your_public_key_here
   ALLOWED_SERVER_ID=your_server_id_here
   ALLOWED_CHANNEL_ID=your_channel_id_here
   LOG_IT_CHANNEL_ID=your_log_channel_id_here
   HARD_ADMIN_USER_IDS=123456789012345678,987654321098765432
   ```

### 運行機器人
```bash
python bot.py
```

## 📋 完整指令列表（支援前綴 `[?` 與 `[`）

### 🎵 音樂播放指令
- `[? youtube <關鍵字/網址>` - 搜尋並播放 YouTube 音樂，支援互動式選單
- `[? yt <關鍵字/網址>` - YouTube 搜尋播放（`[? youtube` 的簡短版本）
- `[yt <關鍵字/網址>` - YouTube 搜尋播放（更簡短的版本）
- `[? url <音樂連結>` - 播放多平台音樂 (YouTube, Spotify, Apple Music, SoundCloud)

### 📋 播放清單管理
- `[? list` / `[list` - 顯示當前播放佇列
- `[? show` / `[show` - 顯示播放佇列 (list 的別名)
- `[? empy` - 清空播放佇列 (需權限等級 5，觸發 1 小時冷卻)

### ⏯️ 播放控制指令
- `[? stop` / `[stop` - 停止當前播放 (保留佇列)
- `[? K` / `[? k` - 繼續播放佇列中的音樂
- `[? skip [數量]` / `[skip [數量]` - 跳過歌曲 (預設 1 首，可指定數量)
- `[? loop` - 啟用單曲循環播放（預設關閉）
- `[? notloop` - 停止循環播放（播放完將繼續下一首）
- `[? dc` / `[dc` - 離開語音頻道並清空佇列

### 🔐 權限管理系統
- `[? permission <1-5>` - 請求編輯權限 (1-5 次使用權限)
  - 一般權限冷卻：10 分鐘
  - 高權限冷卻：1 小時 (使用 empy 後)
  - 管理員：無限制權限

### ✏️ 播放清單編輯指令 (需權限)
- `[? editlist move <從位置> <到位置>` - 移動歌曲位置
- `[? editlist play <位置>` - 立即播放指定位置的歌曲
- `[? editlist remove <位置>` - 從佇列中移除歌曲
- `[? editlist swap <位置1> <位置2>` - 交換兩個位置的歌曲

### ⚙️ 管理員專用指令
- `[? reboot` - 重啟機器人（管理員與硬編碼超管可用）
- `[? serverstats` - 查看服務器即時狀態（發送到 `log-it` 頻道；在其他頻道會提示已發送至 `log-it`）
- `[? mo` - 服務器狀態查詢（`serverstats` 的簡短別名）

### 🛡️ 安全功能
- **自動輸入驗證** - 所有指令都經過安全檢查
- **惡意內容過濾** - 自動阻止可疑輸入和 URL
- **詳細安全日誌** - 所有安全事件記錄到 log-it 頻道
- **攻擊防護** - 防止腳本注入、XSS 等攻擊

### 📊 使用範例
```
# 搜尋並播放音樂
[? youtube 周杰倫 青花瓷
[? yt Maroon 5 Love is Like
[yt 五月天 擁抱

# 直接播放 YouTube 連結
[? url https://www.youtube.com/watch?v=xxxxxx
[? yt https://youtu.be/xxxxxx
[yt https://www.youtube.com/watch?v=xxxxxx

# 請求 3 次編輯權限
[? permission 3

# 將第 2 首歌移動到第 5 位
[? editlist move 2 5

# 立即播放第 3 首歌
[? editlist play 3

# 跳過 2 首歌曲
[? skip 2
```

## 🛠️ 技術棧與架構

### 核心技術
- **Python 3.11+** - 現代 Python 版本支援
- **discord.py 2.3.2** - Discord API 官方包裝器
- **yt-dlp** - YouTube 和多平台音頻提取
- **aiohttp** - 異步 HTTP 客戶端
- **psutil** - 系統資源監控

### 外部 API 整合
- **SponsorBlock API** - 自動廣告過濾
- **YouTube Data API** - 音樂搜尋與播放
- **FFmpeg** - 音頻處理和串流

### 安全架構
- **輸入驗證層** - 多層次安全檢查
- **權限管理系統** - 分級權限控制
- **日誌監控** - 完整的操作記錄
- **錯誤處理** - 安全的錯誤回應機制

## 📁 專案結構

```
dc-bot-new/
├── bot.py              # 主要 Bot 程式
├── requirements.txt    # Python 依賴套件
├── runtime.txt         # Python 版本指定
├── Procfile           # 部署配置 (Railway/Heroku)
├── .gitignore         # Git 忽略文件
└── README.md          # 專案說明文檔
```

## ⚙️ 環境需求

### 必要環境變數
- `DISCORD_TOKEN` - Discord Bot Token (必須)

### 系統需求
- Python 3.11 或更高版本
- FFmpeg (音頻處理)
- 穩定的網路連線

### Discord 設定需求
- 創建 Discord Application
- 建立 Bot 並獲取 Token
- 在伺服器中創建 `log-it` 頻道 (用於日誌記錄)

## 🔧 本地開發與測試


## 🚨 故障排除

### 常見問題
1. **Bot 無法加入語音頻道**
   - 檢查 Bot 是否有 `Connect` 和 `Speak` 權限
   - 確認使用者在語音頻道中

2. **音樂無法播放**
   - 檢查 FFmpeg 是否正確安裝
   - 確認網路連線穩定

3. **指令無回應**
   - 檢查 Bot 是否有 `Read Messages` 權限
   - 確認 `log-it` 頻道是否存在

4. **權限系統錯誤**
   - 檢查使用者是否在冷卻時間中
   - 確認權限等級是否足夠

## 📈 效能優化

- **異步處理** - 所有 I/O 操作都使用異步處理
- **記憶體管理** - 自動清理過期的權限和狀態
- **網路優化** - 使用連接池和請求重試機制
- **資源監控** - 即時監控系統資源使用情況

## 🔐 安全特性

### 輸入安全
- 長度限制檢查
- 字符白名單過濾
- 惡意模式檢測
- URL 域名驗證

### 權限安全
- 分級權限控制
- 自動權限過期
- 冷卻時間機制
- 管理員權限分離

### 日誌安全
- 詳細的操作記錄
- 安全事件警告
- 敏感資訊過濾
- 自動威脅檢測

## 📝 版權與授權

MIT License - 詳見 LICENSE 文件



## 🎯 未來規劃

- [ ] Spotify 完整整合
- [ ] 播放清單匯入/匯出
- [ ] 網頁控制介面
- [ ] 多語言支援擴展
- [ ] AI 音樂推薦
- [ ] 語音識別控制

---

**⭐ 如果這個專案對您有幫助，請給我們一個 Star！**
