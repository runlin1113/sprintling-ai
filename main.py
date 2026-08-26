import sys
import os
from streamlit.web import cli


def main():
    # 获取当前运行目录下的 app.py 绝对路径
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')

    # 模拟命令行参数执行 Streamlit
    sys.argv = ["streamlit", "run", app_path]

    print("正在启动 Sprint Analytics AI 桌面服务...")
    sys.exit(cli.main())


if __name__ == '__main__':
    main()