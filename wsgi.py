"""
生产环境 WSGI 入口 — 用于 gunicorn / uwsgi / PythonAnywhere / 云函数等部署。

本地开发仍然直接运行：
    python server.py

生产部署示例 (gunicorn + 4 workers，适合 2C4G 以上的 VPS)：
    # 先在启动终端预加载 YOLO 模型 (workers=1 避免多进程重复加载 GB 级模型)
    gunicorn --workers=1 --threads=4 --timeout=3600 --bind=0.0.0.0:5000 wsgi:app

注意：YOLO 推理和视频解码是计算密集型，多 workers 会把显存/内存吃爆，
      生产建议使用 --workers=1 + --threads=多 即可，或走 GPU 实例。
"""

import os
import sys

# 保证 wsgi.py 被任何位置启动时都能 import 到 backend/server 模块
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 先让 server.py 的模块级代码 (CORS 配置 / history 目录创建) 执行
from server import app as application  # noqa: E402

# 兼容有的平台找 `application` 有的找 `app`
app = application

if __name__ == "__main__":
    # 兜底：直接运行 wsgi.py 时等价于 server.py
    from server import preload_model
    print("=" * 50)
    print("  Sprint Analytics AI - Production WSGI Entry")
    print("  (建议生产使用 gunicorn 调用本文件)")
    print("=" * 50)
    preload_model()
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
