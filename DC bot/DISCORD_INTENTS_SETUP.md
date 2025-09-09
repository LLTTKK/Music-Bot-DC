# 🔐 Discord Privileged Intents 設定指南

## ❌ 錯誤訊息
```
discord.errors.PrivilegedIntentsRequired: Shard ID None is requesting privileged intents that have not been explicitly enabled in the developer portal.
```

## 🎯 解決方案

### 方法 1：啟用 Privileged Intents（推薦）

#### 步驟 1：前往 Discord 開發者控制台
1. 訪問：[https://discord.com/developers/applications/](https://discord.com/developers/applications/)
2. 使用您的 Discord 帳號登入

#### 步驟 2：選擇您的機器人應用程式
1. 找到並點擊您的應用程式
2. **Application ID**: 您的應用程式 ID（從環境變數 `DISCORD_APPLICATION_ID` 獲取）

#### 步驟 3：前往 Bot 設定
1. 在左側選單中點擊 **"Bot"**
2. 向下滾動找到 **"Privileged Gateway Intents"** 區域

#### 步驟 4：啟用必要的 Intents
啟用以下選項：

- ✅ **Message Content Intent** ⭐ **必須啟用**
  - 允許機器人讀取訊息內容
  - 您的機器人需要這個來處理 `[? youtube` 等指令

- ✅ **Server Members Intent** （可選）
  - 允許機器人存取伺服器成員資訊
  - 用於權限檢查和日誌功能

- ✅ **Presence Intent** （可選）
  - 允許機器人查看使用者狀態
  - 不是必須的，但建議啟用

#### 步驟 5：儲存變更
1. 點擊 **"Save Changes"**
2. 等待幾分鐘讓變更生效

### 方法 2：修改機器人權限（如果無法啟用 Intents）

如果您無法啟用 Privileged Intents，可以使用受限版本：

```python
# 受限版本 - 不需要 Privileged Intents
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.guild_messages = True
# 移除 intents.message_content = True
```

⚠️ **注意**：受限版本將無法讀取訊息內容，機器人功能會受到限制。

## 🔄 重新部署

完成 Discord 設定後：

### 自動重新部署（推薦）
Railway 會在檢測到代碼更改後自動重新部署。

### 手動重新部署
1. 在 Railway 控制台中
2. 前往 **"Deployments"** 標籤
3. 點擊 **"Redeploy"**

## ✅ 驗證成功

成功啟動後，您應該在 Railway 日誌中看到：

```
✅ 所有必要的環境變數都已設定
已登入為 [您的機器人名稱]#1234
Application ID: your_application_id
✅ 已連接到指定伺服器: [伺服器名稱] (ID: your_server_id)
✅ 已找到指定頻道: #[頻道名稱] 在 [伺服器名稱]
```

## 🎵 測試機器人

在您的 Discord 頻道中測試：
```
[? youtube never gonna give you up
```

## 🚨 常見問題

### Q: 我啟用了 Intents 但還是出錯？
**A**: 等待 5-10 分鐘讓 Discord 的變更生效，然後重新部署機器人。

### Q: 我找不到 "Privileged Gateway Intents" 選項？
**A**: 確保您在正確的應用程式頁面，並且在 "Bot" 標籤中。

### Q: 啟用 Intents 有什麼限制嗎？
**A**: 如果您的機器人在 100+ 個伺服器中，需要通過 Discord 的驗證程序。

### Q: 機器人可以在沒有 Message Content Intent 的情況下工作嗎？
**A**: 不行，您的機器人需要讀取訊息內容來處理指令。

## 📞 需要幫助？

如果問題持續存在：
1. 檢查 Discord 開發者控制台的設定
2. 確認機器人 Token 正確
3. 查看 Railway 的完整日誌
4. 確保機器人已被邀請到您的伺服器

---

**記住**：Message Content Intent 是您的機器人正常工作的必要條件！
