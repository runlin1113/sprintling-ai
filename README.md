# SprintLing AI — 一切为了更快

基于机器学习（YOLOv8 姿态估计）与大模型的短跑力学分析与应用。

> 🏃 短跑视频 → 姿态关键点检测 → 运动学指标分析 → AI 教练训练处方

## 功能特性

- **YOLOv8-Pose 姿态估计**：自动识别起跑加速段与途中跑极速段
- **运动学分析**：关节角度、躯干前倾、速度曲线、步频步幅、对称性等指标
- **可视化仪表盘**：一键生成动力学图表
- **AI 教练报告**：DeepSeek 大模型基于力学数据生成个性化训练处方（可导出 Word）
- **本地运行**：Flask Web 界面，视频数据不出本机

## 快速开始（源码运行）

```bash
pip install -r requirements.txt
python server.py
# 浏览器访问 http://localhost:5000
```

> ⚠️ 首次运行会自动下载 YOLOv8-Pose 模型文件（`yolov8n-pose.pt`，约 6.6MB），请保持网络连接。
> ⚠️ 本机无 NVIDIA GPU 时，视频分析走 CPU，速度较慢（5 秒视频约 3~8 分钟）。

### AI 教练功能配置

`ai_coach.py` 通过环境变量读取 DeepSeek API Key：

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="sk-你的key"
python server.py

# Linux / macOS
export DEEPSEEK_API_KEY="sk-你的key"
python server.py
```

Key 获取：https://platform.deepseek.com （免费注册）

## 下载桌面版（免配置，Windows）

不想折腾环境？直接下载打包好的 Windows 软件包：

👉 [**SprintLing AI 下载中心**](https://runlin1113.github.io/sprintling-ai/)

- 解压即用，无需安装 Python
- 内置 50 次 AI 报告免费额度，用完后在 `config.ini` 填自己的 Key 即可

## 部署到 Hugging Face Spaces（免费在线版）

项目包含一套完整的 Docker 部署方案，见 [`hf_space/`](hf_space/)：

```bash
python hf_space/deploy_hf.py --token hf_你的token
```

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | HTML / CSS / JavaScript（`web/`） |
| 后端 | Flask + Flask-CORS（`server.py`） |
| 视觉 | Ultralytics YOLOv8-Pose + OpenCV + PyTorch |
| 分析 | NumPy / SciPy / Matplotlib |
| AI 教练 | DeepSeek Chat Completions API |
| 报告 | python-docx（Word 导出） |

## 项目结构

```
├── server.py            # Flask Web 服务（一体化部署，含 web/ 静态前端）
├── backend.py           # 运动学分析核心（YOLO 推理 + 指标计算 + 图表）
├── ai_coach.py          # AI 教练报告（DeepSeek API）
├── feature_extractor.py # 特征提取
├── vision_core2.py      # 视觉核心（备选姿态管线）
├── visualizer.py        # 数据可视化
├── web/                 # 前端页面
├── hf_space/            # Hugging Face Spaces 免费部署方案
└── main.py              # Streamlit 版入口
```

## 说明

- 本项目为机器学习课程设计作品，仅供学习与科研交流
- 部署/打包详情见 [`DEPLOY_NOTES.md`](DEPLOY_NOTES.md)
