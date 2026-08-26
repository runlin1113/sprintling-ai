# SprintLing AI — Hugging Face Spaces 免费部署指南

把短跑力学分析应用免费部署到公网，任何人有链接即可访问。

## 为什么选 Hugging Face Spaces

| 项目 | 说明 |
|---|---|
| 费用 | 完全免费，无需信用卡 |
| 资源 | 免费 CPU 实例（2 vCPU / 16GB 内存 / 50GB 存储） |
| 域名 | 获得 `https://<用户名>-sprintling-ai.hf.space` 公网地址 |
| 在线状态 | 长期在线；约 48 小时无人访问会休眠，有人打开即自动唤醒 |

## 部署步骤（约 15 分钟，大部分时间在等构建）

### 第 1 步：注册 Hugging Face 账号
打开 https://huggingface.co/join 注册（邮箱即可）。

### 第 2 步：创建 Access Token
1. 打开 https://huggingface.co/settings/tokens
2. 点 **Create new token** → 名称随意（如 `sprintling-deploy`）
3. Token type 选 **Write**（必须，脚本需要写仓库权限）
4. 复制生成的 `hf_xxxx...`，妥善保存

### 第 3 步：轮换你的 DeepSeek API Key（安全必做！）
> ⚠️ 原 `ai_coach.py` 中硬编码了你的 DeepSeek Key（`sk-9b08...`）。
> 虽然部署脚本会自动脱敏、不上传真实 Key，但该 Key 已在本地代码中出现过，
> 强烈建议去 https://platform.deepseek.com 开放平台**删除/重置**这个 Key，
> 拿到新 Key 用于部署（新 Key 只配置在 Space 的 Secrets 里，不进入代码）。

### 第 4 步：运行部署脚本
```bash
cd "D:\大二下学习资料\机器学习\机器学习大作业\202400601015_凌润林_基于机器学习方法与大模型的短跨力学分析与应用\代码\hf_space"
python deploy_hf.py --token hf_你的token
```
脚本会自动：
- 安装 `huggingface_hub`
- 在 `hf_space/build/` 准备部署文件（**自动把 ai_coach.py 中的硬编码 Key 替换为环境变量读取**，你的原文件不会被改动）
- 创建名为 `sprintling-ai` 的 Docker Space 并上传全部文件

> 若你的 HF 用户名下已存在同名 Space，可用 `--space-name 其它名字` 换一个。

### 第 5 步：配置 DeepSeek Key（Space Secrets）
1. 打开 Space 主页 https://huggingface.co/spaces/<用户名>/sprintling-ai
2. **Settings → Variables and secrets**
3. 添加：变量名 `DEEPSEEK_API_KEY`，值 = 第 3 步的新 Key

### 第 6 步：等待构建并访问
1. Space 主页下方 **Build logs** 查看构建进度（首次约 10~20 分钟）
2. 构建完成后打开应用直达地址：
   `https://<用户名>-sprintling-ai.hf.space`

## 使用注意事项

- **视频尽量短**（≤10 秒）：免费 CPU 实例上 5 秒视频约需 3~8 分钟分析，长视频会非常慢
- **首次访问慢**：模型加载约需 1~2 分钟，属正常现象
- **历史数据不保留**：实例重启后 `history_data/` 会被清空，属免费实例的正常限制
- **报告生成**：AI 教练报告依赖 DeepSeek API，若 Secrets 未配置或 Key 无效，报告会显示错误信息，力学指标图表不受影响

## 常见问题

| 问题 | 处理 |
|---|---|
| 构建失败 | 打开 Build logs 看报错，常见是网络问题，点 Restart 重试 |
| 访问一直转圈 | 实例正在冷启动/唤醒，刷新等待 1~2 分钟 |
| 想删掉 Space | Space 主页 → Settings → Danger zone → Delete Space |
| 想换硬件加速 | 免费用户可把 Space 设为 Sleep=0 的 Pro（付费），或申请 org 的 zeroGPU 额度 |

## 部署文件说明（hf_space/ 目录）

| 文件 | 作用 |
|---|---|
| `deploy_hf.py` | 一键部署脚本（打包 + 脱敏 + 上传） |
| `Dockerfile` | 镜像定义：CPU 版 PyTorch、7860 端口、gunicorn 启动 |
| `README.md` | Space 展示页内容 |
| `build/` | 脚本生成的待上传快照（可随时删除重建） |

原项目代码保持零修改，部署后本地 `python server.py` 照常使用。
