# Discord 機器人配置說明

## 🤖 環境變數配置

機器人現在使用環境變數進行配置，不再在代碼中硬編碼敏感資訊。

## 📋 必要的環境變數

### 1. Discord 機器人設定

從 [Discord Developer Portal](https://discord.com/developers/applications) 獲取：

- **DISCORD_TOKEN**: 機器人 Token
- **DISCORD_APPLICATION_ID**: 應用程式 ID
- **DISCORD_PUBLIC_KEY**: 公開金鑰（用於 Slash Commands 和 Webhook 驗證）

### 2. 伺服器限制設定

- **ALLOWED_SERVER_ID**: 允許機器人運行的伺服器 ID
- **ALLOWED_CHANNEL_ID**: 機器人監聽的頻道 ID
- **LOG_IT_CHANNEL_ID**: 日誌頻道 ID

### 3. 管理員設定（可選）

- **HARD_ADMIN_USER_IDS**: 超級管理員用戶 ID（多個用逗號分隔）

## ⚙️ Railway 環境變數設定

### 1. 在 Railway 中設定環境變數

1. 登入 [Railway](https://railway.app)
2. 選擇您的專案
3. 進入 Variables 頁面
4. 添加以下環境變數：

```
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_APPLICATION_ID=your_application_id_here
DISCORD_PUBLIC_KEY=your_public_key_here
ALLOWED_SERVER_ID=your_server_id_here
ALLOWED_CHANNEL_ID=your_channel_id_here
LOG_IT_CHANNEL_ID=your_log_channel_id_here
HARD_ADMIN_USER_IDS=123456789012345678,987654321098765432
```

### 2. 如何獲取 Discord 資訊

#### 獲取伺服器 ID
1. 在 Discord 中，右鍵點擊您的伺服器名稱
2. 選擇「複製伺服器 ID」
3. 如果看不到這個選項，請先啟用開發者模式：
   - 設定 → 進階 → 開發者模式 → 開啟

#### 獲取頻道 ID
1. 右鍵點擊頻道名稱
2. 選擇「複製頻道 ID」

#### 獲取用戶 ID
1. 右鍵點擊用戶名稱
2. 選擇「複製用戶 ID」

### 3. 機器人邀請連結

使用以下格式邀請機器人到您的伺服器：
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=8&scope=bot
```

將 `YOUR_APPLICATION_ID` 替換為您的實際應用程式 ID。

## 🔒 安全限制

機器人現在已設定為：
- ✅ 只在指定的伺服器運行
- ✅ 只監聽指定的頻道
- ✅ 忽略其他伺服器和頻道的所有指令和訊息
- ✅ 所有敏感資訊都通過環境變數管理

## 🎵 支援的指令

機器人只會在指定頻道中回應以下指令：

### 音樂播放
- `[? youtube <URL或關鍵字>` - 搜尋並播放 YouTube 音樂
- `[? list` 或 `[? show` - 顯示播放佇列
- `[stop` - 停止播放
- `[K` 或 `[k` - 繼續播放
- `[skip <數量>` - 跳過歌曲
- `[loop` - 啟用循環播放
- `[notloop` - 停用循環播放
- `[dc` - 離開語音頻道並清空佇列

### 權限管理
- `[permission <次數>` - 請求編輯權限
- `[editlist <操作>` - 編輯播放清單
- `[empy` - 清空佇列（需要權限等級 5）

### 管理員指令
- `[serverstats` 或 `[mo` - 查看伺服器狀態
- `[reboot` - 重啟機器人

## 🚀 部署步驟

### Railway 部署

1. 將代碼推送到 GitHub 倉庫
2. 在 Railway 中連接 GitHub 倉庫
3. 設定所有必要的環境變數（參考上面的環境變數列表）
4. 部署機器人

### 本地開發

1. 複製 `env.example` 為 `.env` 並填入實際值：
   ```bash
   cp env.example .env
   ```

2. 安裝依賴：
   ```bash
   pip install -r requirements.txt
   ```

3. 運行機器人：
   ```bash
   python bot.py
   ```

4. 檢查控制台輸出，確認：
   - ✅ 所有環境變數都已設定
   - ✅ 機器人成功登入
   - ✅ 找到指定的伺服器
   - ✅ 找到指定的頻道

## ⚠️ 注意事項

- **安全性**：所有敏感資訊現在都通過環境變數管理，不再硬編碼在代碼中
- **環境變數**：確保在 Railway 中正確設定所有必要的環境變數
- **權限**：機器人只會在指定的頻道中工作，其他地方的指令會被忽略
- **管理員**：超級管理員用戶 ID 可以通過 `HARD_ADMIN_USER_IDS` 環境變數設定
