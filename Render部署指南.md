# Render 部署指南（替换阿里云 FC）

> 为什么换 Render：阿里云 FC 默认域名（fcapp.run）已被安全策略拦截，百炼调用会 403。
> Render 给的是正常可用的 HTTPS 公网地址，无此限制，且零依赖版本连 pip 都不用装。

## 准备文件（本地已有）
- `tushare_quote_service.py`（零依赖新浪版，已实测）
- `render.yaml`（上面已生成）
- 如想后续加 Tushare，再补 `requirements.txt`

## 部署步骤

### 1. 把代码传到 GitHub（Render 从 GitHub 拉取）
1. 打开 github.com 注册/登录
2. 右上角 + → New repository，名字随便（如 `tushare-quote`）
3. 仓库里上传两个文件：
   - `tushare_quote_service.py`
   - `render.yaml`
4. 提交

### 2. 在 Render 创建服务
1. 打开 render.com 注册（用 GitHub 账号登录最方便）
2. 右上角 New → Blueprint
3. 连接你的 GitHub 仓库，选 `tushare-quote`
4. Render 会自动读取 `render.yaml`，显示服务配置
5. 点 Create Web Service

### 3. 等待部署
- 部署完成（约 1-2 分钟）后，Render 给你一个地址：
  `https://tushare-quote-xxx.onrender.com`
- 注意：免费版有**冷启动**（15 分钟无请求会休眠，下次唤醒约 30 秒）

### 4. 验证
浏览器访问：
```
https://你的地址.onrender.com/
```
看到 `{"status":"ok","service":"quote","port":...}` 即成功。

实时行情：
```
https://你的地址.onrender.com/quote/realtime
```
（GET 会提示用 POST；POST 需带 body，浏览器不方便，用百炼测）

### 5. 填回百炼
插件 URL 改成 Render 地址（不要路径，只要域名）：
```
https://tushare-quote-xxx.onrender.com
```
然后测试两个工具（实时 / 日线）。

## 注意事项
- 免费版 Sleep：15 分钟无访问会休眠，百炼第一次调用会慢一点（等待唤醒），之后正常。
- 跨境延迟：Render 在境外，调新浪行情源约 100-300ms，对查询类场景完全可接受。
- 以后想用 Tushare 专业数据：把服务迁回阿里云 FC + API 网关（国内网络），或给 Render 版加 `requirements.txt` 引入 tushare（接受跨境延迟）。

## 备选：不用 GitHub，手动粘贴
Render 也支持「New → Web Service → 手动填写」：
- Runtime: Python 3
- Build Command: 空
- Start Command: `python tushare_quote_service.py`
- 在代码编辑器里把 `tushare_quote_service.py` 内容粘贴进去
