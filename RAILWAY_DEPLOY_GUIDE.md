# 🚀 Railway 部署指南

## 📋 前置準備

### 1. 確保您有以下帳號：
- ✅ GitHub 帳號（已完成 - 您的代碼已在 GitHub 上）
- ⚠️ Railway 帳號（需要註冊）

### 2. 檔案檢查清單：
- ✅ `Bot.py` - 主要機器人程式
- ✅ `requirements.txt` - Python 套件依賴
- ✅ `Procfile` - Railway 啟動指令
- ✅ `railway.json` - Railway 配置
- ✅ `runtime.txt` - Python 版本指定
- ✅ `CONFIG_SETUP.md` - 配置說明

## 🎯 步驟 1：註冊 Railway 帳號

1. 前往 [Railway.app](https://railway.app/)
2. 點擊 **"Start a New Project"** 或 **"Login"**
3. 選擇 **"Login with GitHub"**
4. 授權 Railway 存取您的 GitHub 帳號

## 🔗 步驟 2：連接 GitHub 儲存庫

1. 在 Railway 控制台中，點擊 **"New Project"**
2. 選擇 **"Deploy from GitHub repo"**
3. 找到並選擇您的儲存庫：`LLTTKK/dc-bot-new`
4. 點擊 **"Deploy Now"**

## ⚙️ 步驟 3：配置環境變數（必需）

機器人現在使用環境變數進行配置，您必須設定以下環境變數：

1. 在 Railway 專案中，點擊 **"Variables"** 標籤
2. 添加以下必要的環境變數：
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   DISCORD_APPLICATION_ID=your_application_id_here
   DISCORD_PUBLIC_KEY=your_public_key_here
   ALLOWED_SERVER_ID=your_server_id_here
   ALLOWED_CHANNEL_ID=your_channel_id_here
   LOG_IT_CHANNEL_ID=your_log_channel_id_here
   HARD_ADMIN_USER_IDS=123456789012345678,987654321098765432
   ```

3. YouTube 播放（Railway 幾乎必設）：
   ```
   # 把本機匯出的 Netscape cookies.txt 全文貼上（推薦）
   YTDLP_COOKIES=
   # 或 base64 編碼後貼上
   YTDLP_COOKIES_BASE64=
   # 可選：住宅代理（cookies 仍被擋時）
   YTDLP_PROXY=
   ```
   若日誌出現 `Sign in to confirm you’re not a bot` / `cookies.txt 不存在`，代表雲端 IP 被 YouTube bot-check，沒有 cookies 就無法播放。

**詳細設定說明請參考 [Railway 環境變數設定指南](RAILWAY_ENV_SETUP.md)**

## 🚀 步驟 4：部署

1. Railway 會自動開始部署
2. 您可以在 **"Deployments"** 標籤中查看部署進度
3. 查看 **"Logs"** 標籤確認機器人是否成功啟動

## 📊 步驟 5：監控和管理

### 查看日誌：
- 點擊 **"Logs"** 標籤
- 確認看到類似以下訊息：
  ```
  ✅ 所有必要的環境變數都已設定
  已登入為 YourBotName#1234
  Application ID: your_application_id
  ✅ 已連接到指定伺服器: YourServerName (ID: your_server_id)
  ✅ 已找到指定頻道: #your-channel 在 YourServerName
  ```

### 重啟機器人：
- 在 **"Deployments"** 標籤中點擊 **"Redeploy"**

### 查看資源使用：
- 在 **"Metrics"** 標籤中查看 CPU 和記憶體使用情況

## 💰 費用說明

### Railway 定價：
- **免費方案**：每月 $5 USD 的免費額度
- **Pro 方案**：$20 USD/月（無限制使用）

### 預估使用量：
- 您的機器人預計每月使用 $1-3 USD（在免費額度內）
- 主要消耗：CPU 時間和記憶體使用

## 🔧 故障排除

### 常見問題：

#### 1. 部署失敗
**解決方案：**
- 檢查 `requirements.txt` 是否正確
- 確認 `Bot.py` 檔案名稱正確（注意大小寫）
- 查看部署日誌中的錯誤訊息

#### 2. 機器人離線
**解決方案：**
- 檢查 Discord Token 是否正確
- 確認機器人有足夠的權限
- 查看 Railway 日誌中的錯誤訊息

#### 3. 機器人不回應指令
**解決方案：**
- 確認您在正確的伺服器和頻道中測試
- 檢查伺服器 ID 和頻道 ID 是否正確設定
- 確認機器人已加入您的 Discord 伺服器

## 🔄 更新機器人

當您修改代碼後：

1. **提交到 GitHub：**
   ```bash
   git add .
   git commit -m "Update bot features"
   git push
   ```

2. **Railway 自動部署：**
   - Railway 會自動檢測 GitHub 更新
   - 自動重新部署最新版本

## 🎯 機器人邀請連結

使用以下格式的連結邀請機器人到您的伺服器：
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=8&scope=bot
```

將 `YOUR_APPLICATION_ID` 替換為您的實際應用程式 ID。

## 📞 支援

如果遇到問題：
1. 檢查 Railway 日誌
2. 確認 Discord 機器人設定
3. 查看 `CONFIG_SETUP.md` 中的詳細說明

---

## 🎉 完成！

您的 Discord 機器人現在應該在 Railway 上運行了！

測試指令：
- 在指定頻道中輸入：`[? youtube never gonna give you up`
- 機器人應該會回應並開始搜尋音樂

**祝您使用愉快！** 🎵🤖
