# 旧手机一体部署手册（Termux + Cloudflare Tunnel）

> 目标：把「AI家办」整体（前端 + 后端）跑在一台闲置安卓手机上，通过 Cloudflare Tunnel 一个域名对外。零服务器成本、零代码改动、无需单独部署前端。

## 为什么前端不用单独部署

后端 `app/main.py` 已把前端静态资源一起托管：

```python
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")  # 静态资源
@app.get("/")                                                             # 首页
def index():
    return FileResponse(str(_STATIC / "index.html"))
```

前端 `static/api.js` 与 `static/index.html` 全部用**根相对路径**（`/api/...`、`/static/...`），因此前后端同域、无跨域、零改动。**不需要 Cloudflare Pages、不需要 github 部署、不需要改 api.js 的 API_BASE。**

## 总览（最终链路）

```text
用户浏览器
    │ ① 访问 https://ai.example.com/（你的域名）
    ▼
Cloudflare Tunnel（公网入口，转发到手机本地）
    │ ② 127.0.0.1:8000
    ▼
安卓手机 · Termux · FastAPI（一体：serve 前端 + /api + SQLite 落盘本地）
    │ ③ advisor 调大模型
    ▼
DeepSeek API（key 只存在手机 .env，不进 git）
```

---

## 0. 前置清单

| 项 | 说明 |
|---|---|
| 安卓手机 | Android 7+，已解锁，可装 F-Droid 应用 |
| 供电/网络 | 常插充电器 + 稳定 WiFi（手机 = 24h 服务器，唯一风险点） |
| Cloudflare 账号 | 免费即可 |
| 域名（Tunnel 必需） | DNS 托管在 Cloudflare 的域名；**没有域名看 §4-B 临时隧道** |
| GitHub（可选） | 仅作代码同步/备份用，非部署必需；也可用 scp 传代码 |

> ⚠️ 铁律：`.env`（含 DeepSeek key）与 `data.db`（含用户数据）**绝不进 github**。本项目 `.gitignore` 已排除两者。

---

## 1. 代码同步到手机（二选一）

**方式 A：git 私有仓库（推荐，兼做版本控制 + 备份）**

```bash
# 在 Windows 开发机（仅一次性）
cd /d/Claude_Code/ai-jia-ban
git init && git add . && git commit -m "chore: 内测部署基线"
git remote add origin https://github.com/<用户名>/ai-jia-ban.git
git push -u origin main

# 在手机 Termux
git clone https://github.com/<用户名>/ai-jia-ban.git
```

**方式 B：scp 直接传（无 github）**

```bash
# 在 Windows 开发机（需手机已开 sshd：Termux 里 `pkg install openssh && sshd`）
scp -r -P 8022 /d/Claude_Code/ai-jia-ban <手机用户>@<手机IP>:~/
```

---

## 2. 手机装 Termux + Python

1. **装 Termux**：从 [F-Droid](https://f-droid.org/packages/com.termux/) 下载（**不要用 Play 商店版**，已停更）。
2. 再装两个插件（F-Droid 同源）：
   - **Termux:Boot**（开机自启）
   - **Termux:API**（`termux-wake-lock` 保活）
3. 打开 Termux：

```bash
pkg update && pkg upgrade -y
pkg install -y python git
```

---

## 3. 装依赖 + 配 key + 起服务

```bash
cd ~/ai-jia-ban

# 3.1 装依赖（纯 uvicorn，避开 uvloop 在 Termux 的编译坑）
pip install fastapi uvicorn pydantic httpx

# 3.2 手写 .env（key 只在这台手机，不进 git）
cat > .env <<'EOF'
LLM_API_KEY=sk-你的deepseek密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
EOF

# 3.3 起服务（127.0.0.1 即可，Tunnel 本地回连；无需暴露局域网）
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

本机冒烟：Termux 另开窗口 `curl http://127.0.0.1:8000/api/health`，应返回 JSON。

---

## 4. Cloudflare Tunnel 打通

### 4-A. 有域名（正式内测推荐）

```bash
pkg install -y cloudflared

cloudflared tunnel login                          # 弹 URL，浏览器点授权
cloudflared tunnel create ai-jia-ban              # 记下返回的 <uuid>

mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml <<'EOF'
tunnel: <uuid>
credentials-file: /data/data/com.termux/files/home/.cloudflared/<uuid>.json

ingress:
  - hostname: ai.example.com
    service: http://localhost:8000
  - service: http_status:404
EOF

cloudflared tunnel route dns ai-jia-ban ai.example.com   # 域名须已托管在 Cloudflare
cloudflared tunnel run ai-jia-ban
```

此时手机浏览器开 `https://ai.example.com/` 应直接看到登录页（前端 + 后端已一体上线）。

### 4-B. 没有域名（临时试跑，域名会变）

```bash
pkg install -y cloudflared
cloudflared tunnel --url http://localhost:8000
```

返回 `https://xxxx.trycloudflare.com` 随机域名，**重启即变**，只适合临时试跑，不适合长期内测。

---

## 5. 开机自启 + 保活（手机当服务器必须做）

```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-backend.sh <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd ~/ai-jia-ban
nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > /dev/null 2>&1 &
nohup cloudflared tunnel run ai-jia-ban > /dev/null 2>&1 &
EOF
chmod +x ~/.termux/boot/start-backend.sh
```

- 首次授予 Termux:Boot 开机自启权限（系统设置允许）。
- 关掉「电池优化」对 Termux 的限制（应用设置 → 电池 → 无限制），允许后台运行。

---

## 6. 端到端验证清单

| 验证项 | 操作 | 通过标准 |
|---|---|---|
| 前端加载 | 开 `https://ai.example.com/` | 登录/注册页正常，出现内测告知文案 |
| 后端健康 | 开 `https://ai.example.com/api/health` | 返回 JSON |
| 注册/登录 | 注册测试号 | 拿 token 进驾驶舱 |
| 三件套①rate limit | 连续对话刷到上限 | 第 51 次返回 429（默认 50/日） |
| 三件套②删除账号 | 顶栏「删除账号」 | 确认后退出，数据清空 |
| 三件套③告知 | 登录页 | 显示「数据会发给大模型」文案 |
| 铁律兜底 | 手机断网/拔 key | 规则兜底不 500，数字仍确定性 |

---

## 7. 已知坑点

1. **uvloop 编译失败**：`uvicorn[standard]` 在 Termux 可能编译不过，改纯 `uvicorn`（§3 已用）。
2. **trycloudflare 域名漂移**：无域名临时隧道重启即变——正式内测务必绑自己的域名（§4-A）。
3. **手机深度休眠**：忘 `termux-wake-lock` 后台被杀，服务悄悄下线。
4. **数据在手机本地**：手机损坏/丢失即数据丢失（内测可接受，已列入「数据安全基线·暂缓」）。
5. **key 泄露风险**：`.env` 只存在手机与本地开发机，绝不进 git；github 私有仓库也别误加。
