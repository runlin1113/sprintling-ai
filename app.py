import streamlit as st
import os
import shutil
import json
from datetime import datetime
import backend

st.set_page_config(page_title="Sprint Analytics AI", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @keyframes fadeIn { 0% { opacity: 0; transform: translateY(15px); } 100% { opacity: 1; transform: translateY(0); } }
    .stApp { background-color: #F8F9FA; animation: fadeIn 0.8s cubic-bezier(0.2, 0.8, 0.2, 1); }
    [data-testid="stSidebar"] { background-color: #D32F2F; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    h1, h2, h3, h4 { color: #B71C1C !important; font-family: 'Helvetica Neue', Arial, sans-serif; }
    .stButton>button { background-color: #B71C1C; color: white; border: none; border-radius: 2px; font-weight: 600; text-transform: uppercase; transition: all 0.3s ease; }
    .stButton>button:hover { background-color: #D32F2F; color: white; box-shadow: 0 4px 12px rgba(211, 47, 47, 0.3); }
    .explanation-box { background-color: #FFFFFF; border-left: 4px solid #D32F2F; padding: 15px; margin-top: 15px; color: #424242; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .notice-box { background-color: #FFF3E0; border-left: 4px solid #FF9800; padding: 15px; margin-bottom: 20px; color: #424242; border-radius: 4px;}
    hr { border-top: 1px solid #E0E0E0; }
    .stTabs [data-baseweb="tab-list"] { gap: 32px; border-bottom: 2px solid #EEEEEE; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; font-size: 16px; color: #757575;}
    .stTabs [aria-selected="true"] { color: #B71C1C !important; border-bottom: 3px solid #B71C1C !important;}
</style>
""", unsafe_allow_html=True)

HISTORY_DIR = "history_data"
if not os.path.exists(HISTORY_DIR):
    os.makedirs(HISTORY_DIR)

if "app_state" not in st.session_state:
    st.session_state.app_state = "REGISTRATION"
if "athlete_info" not in st.session_state:
    st.session_state.athlete_info = {}
if "selected_record" not in st.session_state:
    st.session_state.selected_record = None

# --- 前置页面：运动员注册 ---
if st.session_state.app_state == "REGISTRATION":
    st.title("Athlete Profile | 运动员注册")
    st.markdown(
        "Create a profile to generate a highly personalized technical training plan. You can also skip this step.")

    with st.form("registration_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name | 姓名", placeholder="e.g. 凌润林")
            event = st.selectbox("Event | 专项", ["100m", "200m", "400m", "110m Hurdles"])
        with col2:
            pb = st.text_input("Personal Best | 个人纪录 (s)", placeholder="e.g. 11.75")

        submitted = st.form_submit_button("Register & Enter System | 注册并进入")

    if st.button("Skip Registration | 直接跳过"):
        st.session_state.athlete_info = {}
        st.session_state.app_state = "MAIN_APP"
        st.rerun()

    if submitted:
        if name:
            st.session_state.athlete_info = {"name": name, "event": event, "pb": pb}
            st.session_state.app_state = "MAIN_APP"
            st.rerun()
        else:
            st.warning("Please enter a name or choose to skip. | 请输入姓名或选择跳过。")

# --- 主系统页面 ---
elif st.session_state.app_state == "MAIN_APP":

    st.sidebar.title("Data Archives | 数据档案")
    if st.sidebar.button("Back to Registration | 返回重新注册"):
        st.session_state.app_state = "REGISTRATION"
        st.rerun()

    records = sorted(os.listdir(HISTORY_DIR), reverse=True)
    st.sidebar.write("History Records | 历史分析记录:")
    for record in records:
        if st.sidebar.button(f"RECORD: {record}", key=f"btn_{record}"):
            st.session_state.selected_record = record

    if st.session_state.selected_record:
        st.sidebar.markdown("---")
        st.sidebar.write(f"Selected | 当前选中:\n{st.session_state.selected_record}")
        if st.sidebar.button("Delete Record | 删除记录"):
            shutil.rmtree(os.path.join(HISTORY_DIR, st.session_state.selected_record))
            st.session_state.selected_record = None
            st.rerun()

    if st.session_state.athlete_info.get("name"):
        st.title(f"前进吧！ {st.session_state.athlete_info['name']}! 🏃")
        st.markdown(
            f"Current Target: {st.session_state.athlete_info['event']} | PB: {st.session_state.athlete_info['pb']}s")
    else:
        st.title("Sprint Analytics AI | 短跨力学分析系统")

    # --- 注意事项 ---
    st.markdown("""
    <div class="notice-box">
        <strong>拍摄与上传须知 | Recording & Uploading Guidelines:</strong><br>
        1. <strong>机位稳定 (Stable Camera)</strong>: 拍摄机位请保持绝对稳定，避免跟随晃动。<br>
        2. <strong>单人入镜 (Single Subject)</strong>: 画面中尽量只包含目标运动员，避免背景中有其他移动人员干扰模型锁定。<br>
        3. <strong>原速原片 (Original Speed)</strong>: 请直接上传原速视频（推荐相机自带的 60fps/120fps 慢动作格式），<strong>切勿使用剪辑软件自行放慢倍速</strong>，后期慢放会导致抽帧或重复帧，直接摧毁动力学求导的准确率。
    </div>
    """, unsafe_allow_html=True)

    st.markdown("Please upload **at least one** video phase (Start or Max Velocity) for analysis.")

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        start_video = st.file_uploader("1. Start Phase Video | 起跑段视频 (Optional)", type=['mp4', 'mov'])
    with col_v2:
        maxvel_video = st.file_uploader("2. Max Velocity Video | 途中跑段视频 (Optional)", type=['mp4', 'mov'])

    if start_video or maxvel_video:
        if st.button("Initialize Biomechanical Engine | 启动分析"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            work_dir = os.path.join(HISTORY_DIR, timestamp)
            os.makedirs(work_dir)

            raw_start = os.path.join(work_dir, "raw_start.mp4")
            raw_maxvel = os.path.join(work_dir, "raw_maxvel.mp4")
            proc_start = os.path.join(work_dir, "proc_start.webm")
            proc_maxvel = os.path.join(work_dir, "proc_maxvel.webm")
            json_start = os.path.join(work_dir, "data_start.json")
            json_maxvel = os.path.join(work_dir, "data_maxvel.json")

            payload_path = os.path.join(work_dir, "payload.json")
            img_path = os.path.join(work_dir, "chart.png")
            report_md = os.path.join(work_dir, "report.md")
            report_docx = os.path.join(work_dir, "report.docx")

            # 动态独立处理存在的视频
            if start_video:
                with open(raw_start, "wb") as f: f.write(start_video.getbuffer())
                with st.spinner("Processing Start Phase Dynamics | 解析起跑..."):
                    backend.process_full_kinematics(raw_start, proc_start, json_start)

            if maxvel_video:
                with open(raw_maxvel, "wb") as f: f.write(maxvel_video.getbuffer())
                with st.spinner("Processing Maximum Velocity Kinematics | 解析途中跑..."):
                    backend.process_full_kinematics(raw_maxvel, proc_maxvel, json_maxvel)

            with st.spinner("Fusing Data & Generating Dashboard | 融合数据与图表..."):
                backend.extract_combined_features(json_start, json_maxvel, payload_path)
                backend.plot_combined_dashboard(json_start, json_maxvel, img_path)

            with st.spinner("AI Generating Actionable Protocol | 教练分析并制定计划..."):
                backend.generate_training_report(payload_path, report_md, st.session_state.athlete_info)
                backend.create_docx_report(report_md, report_docx)

            st.session_state.selected_record = timestamp
            st.rerun()

    # 展示区
    if st.session_state.selected_record:
        work_dir = os.path.join(HISTORY_DIR, st.session_state.selected_record)
        proc_start = os.path.join(work_dir, "proc_start.webm")
        proc_maxvel = os.path.join(work_dir, "proc_maxvel.webm")
        report_md = os.path.join(work_dir, "report.md")
        report_docx = os.path.join(work_dir, "report.docx")
        img_path = os.path.join(work_dir, "chart.png")
        payload_path = os.path.join(work_dir, "payload.json")

        st.markdown("---")

        if os.path.exists(report_docx):
            with open(report_docx, "rb") as file:
                st.download_button(
                    label="Download Word Document | 一键导出 Word 版训练计划",
                    data=file,
                    file_name=f"Training_Plan_{st.session_state.selected_record}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary"
                )

        tab1, tab2, tab3 = st.tabs([
            "Phase Tracking | 动作追踪",
            "Dynamics Dashboard | 动力学数据",
            "AI Protocol | 教练分析"
        ])

        with tab1:
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                # 动态回放起跑段视频及提供下载
                if os.path.exists(proc_start):
                    st.markdown("#### Phase 1: Start (起跑段)")
                    st.video(proc_start, format="video/webm")
                    with open(proc_start, "rb") as f:
                        st.download_button(
                            label=" Download Start Phase Video | 下载起跑追踪视频",
                            data=f,
                            file_name=f"Start_Phase_{st.session_state.selected_record}.webm",
                            mime="video/webm"
                        )
            with col_t2:
                # 动态回放极速段视频及提供下载
                if os.path.exists(proc_maxvel):
                    st.markdown("#### Phase 2: Max Velocity (途中跑段)")
                    st.video(proc_maxvel, format="video/webm")
                    with open(proc_maxvel, "rb") as f:
                        st.download_button(
                            label="Download Max Velocity Video | 下载途中跑阶段追踪视频",
                            data=f,
                            file_name=f"Max_Velocity_{st.session_state.selected_record}.webm",
                            mime="video/webm"
                        )

            # 在视频下方直观渲染给 AI 的数据载荷
            if os.path.exists(payload_path):
                st.markdown("---")
                st.markdown("### 降维后的数据 | Reduced Biomechanical Payload")
                st.markdown(
                    "以下为系统自动剥离环境噪音后，输入给 AI 教练的核心运动学指标 | Core kinematic metrics extracted and fed to the AI coach:")
                with open(payload_path, "r", encoding="utf-8") as f:
                    payload_data = json.load(f)
                    st.json(payload_data)

        with tab2:
            if os.path.exists(img_path):
                st.image(img_path, use_container_width=True)
                st.markdown("""
                <div class="explanation-box">
                    <strong>图表释义 (Chart Explanations)：</strong><br>
                    <strong>1. Torso Lean Dynamics (起跑躯干倾角)</strong> (如提供起跑视频)：监控加速阶段身体重心的压制能力。过早抬升会导致水平推进力向垂直方向泄露，降低加速效率。<br>
                    <strong>2. Knee Flexion Symmetry (途中跑阶段期膝关节对称性)</strong> (如提供途中跑视频)：通过追踪步态周期中的左右膝关节折叠峰值角度，量化双侧发力平衡。不对称不仅暗示中枢神经(CNS)单侧疲劳或代偿，也是拉伤的潜在预警。
                </div>
                """, unsafe_allow_html=True)

        with tab3:
            if os.path.exists(report_md):
                with open(report_md, "r", encoding="utf-8") as f:
                    st.markdown(f.read())