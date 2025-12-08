# Railway 環境變數設定指南

## 🚀 快速設定

### 1. 登入 Railway
前往 [Railway](https://railway.app) 並登入您的帳號。

### 2. 選擇專案
選擇您要部署 Discord 機器人的專案。

### 3. 進入環境變數設定
1. 點擊專案名稱
2. 選擇 "Variables" 標籤
3. 點擊 "New Variable" 按鈕

### 4. 設定必要的環境變數

#### Discord 機器人設定
```
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_APPLICATION_ID=your_application_id_here
DISCORD_PUBLIC_KEY=your_public_key_here
```

#### 伺服器限制設定
```
ALLOWED_SERVER_ID=your_server_id_here
ALLOWED_CHANNEL_ID=your_channel_id_here
LOG_IT_CHANNEL_ID=your_log_channel_id_here
```

#### 管理員設定（可選）
```
HARD_ADMIN_USER_IDS=123456789012345678,987654321098765432
```

#### yt-dlp 進階設定（可選）
```
YTDLP_COOKIES_FILE=cookies.txt
YTDLP_PROXY=
YTDLP_YT_ANDROID_PO_TOKEN=
YTDLP_YT_IOS_PO_TOKEN=
```

## 📋 如何獲取 Discord 資訊

### 獲取機器人 Token
1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 選擇您的應用程式
3. 前往 "Bot" 頁面
4. 在 "Token" 部分點擊 "Copy"

### 獲取應用程式 ID
1. 在 Discord Developer Portal 中
2. 前往 "General Information" 頁面
3. 複製 "Application ID"

### 獲取公開金鑰
1. 在 Discord Developer Portal 中
2. 前往 "General Information" 頁面
3. 複製 "Public Key"

### 獲取伺服器 ID
1. 在 Discord 中，右鍵點擊伺服器名稱
2. 選擇 "複製伺服器 ID"
3. 如果看不到選項，請啟用開發者模式：
   - 設定 → 進階 → 開發者模式 → 開啟

### 獲取頻道 ID
1. 右鍵點擊頻道名稱
2. 選擇 "複製頻道 ID"

### 獲取用戶 ID
1. 右鍵點擊用戶名稱
2. 選擇 "複製用戶 ID"

## ✅ 驗證設定

設定完成後，機器人會在啟動時自動驗證環境變數。如果缺少必要的變數，機器人會顯示錯誤訊息並停止運行。

### 成功訊息
```
✅ 所有必要的環境變數都已設定
已登入為 YourBot#1234
✅ 已連接到指定伺服器: Your Server (ID: 123456789)
✅ 已找到指定頻道: #music 在 Your Server
```

### 錯誤訊息
```
❌ 錯誤：缺少必要的環境變數：
   - DISCORD_TOKEN
   - ALLOWED_SERVER_ID

請在 Railway 環境變數中設定這些變數。
請參考 .env.example 檔案了解所需的環境變數。
```

## 🔧 疑難排解

### 問題：機器人無法啟動
**解決方案**：檢查所有必要的環境變數是否都已設定。

### 問題：機器人無法連接到伺服器
**解決方案**：確認 `ALLOWED_SERVER_ID` 設定正確。

### 問題：機器人無法監聽頻道
**解決方案**：確認 `ALLOWED_CHANNEL_ID` 設定正確。

### 問題：管理員權限不工作
**解決方案**：確認 `HARD_ADMIN_USER_IDS` 格式正確（逗號分隔的數字）。

## 📝 注意事項

- 環境變數設定後，機器人會自動重新部署
- 敏感資訊（如 Token）不會在日誌中顯示
- 建議定期更新機器人 Token 以確保安全性
- 如果更改環境變數，請等待幾分鐘讓部署完成
