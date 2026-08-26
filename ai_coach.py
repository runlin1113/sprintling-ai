import json
import os
import requests

# --- 1. DeepSeek API 配置 ---
# 警告：为了账号安全，后续请尽量通过环境变量读取 API Key。
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


def generate_training_prescription(payload_path, output_md_path, athlete_info=None):
    """
    调用百炼知识库应用，基于降维 JSON 生成带有力学映射的训练计划
    """
    # 默认加载专属运动员档案
    if athlete_info is None:
        athlete_info = {
            "name": "凌润林",
            "event": "100m",
            "pb": "11.75s",
            "goal": "11.40s"
        }

    def save_and_return(content):
        """将内容（含错误信息）写入 Markdown 文件并返回"""
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(content)
        return content

    # 1. 加载视觉引擎提取的降维数据载荷
    try:
        with open(payload_path, 'r', encoding='utf-8') as f:
            payload_dict = json.load(f)
            payload_json = json.dumps(payload_dict, ensure_ascii=False, indent=2)
    except Exception as e:
        return save_and_return(f"# AI 教练分析错误\n\n**System Error**: Loading payload failed. {e}")

    # 2. 动态探测当前数据包含了哪些阶段 (防止大模型幻觉)
    available_phases = []
    if "phase_1_start_acceleration" in payload_dict:
        available_phases.append("起跑加速段 (Start Phase)")
    if "phase_2_maximum_velocity" in payload_dict:
        available_phases.append("途中跑极速段 (Max Velocity Phase)")

    if not available_phases:
        return save_and_return("# AI 教练分析错误\n\n数据载荷为空，无法进行生物力学诊断。")

    phase_context_str = " 与 ".join(available_phases)

    # 3. 动态拼接运动员信息
    athlete_context = f"""
    【Athlete Profile | 运动员档案】:
    - 姓名: {athlete_info.get('name')}
    - 专项: {athlete_info.get('event')}
    - 当前成绩 (PB): {athlete_info.get('pb')}
    - 突破目标: {athlete_info.get('goal')}
    请在调取知识库时，务必结合该运动员从 {athlete_info.get('pb')} 冲击 {athlete_info.get('goal')} 的技术痛点进行深度诊断。
    """

    # 4. 构建触发 RAG 检索的超级提示词 (Prompt)
    # 对于 DashScope Application API，推荐将 System Prompt 和 User Prompt 融合成一个结构严谨的指令文本
    prompt = f"""
    # 角色与核心任务
    你是一位具备丰富实战经验与深厚学术造诣的顶级短跑生物力学教练。
    你的任务是通过分析计算机视觉提取的【运动学 JSON 载荷】，结合前沿神经科学，为田径运动员提供精准的技术诊断与训练处方。
    【最高强制指令】：在进行技术机理分析时，**你必须优先检索并明确引用你挂载的知识库（如《短跑与跨栏力学》）中的标准参数与底层力学公式**，拒绝泛泛而谈的体能建议。

    {athlete_context}

    # 数据处理范围警告
    本次传入的数据仅包含：【{phase_context_str}】。请只针对提供的数据阶段进行分析，绝不可凭空捏造未提供阶段的数据！

    # 视觉引擎数据载荷 (JSON)
    {payload_json}

    # 输出格式限制 (必须严格按照以下 Markdown 结构输出，以配合系统后端的 Word 导出模块)

    ## 一、 动力学数据诊断报告
    - **核心数据抓取**：(精准抓取 JSON 中异常的运动学指标，如膝角速度异常、躯干倾角不足等)
    - **对称性与稳定性判定**：(结合数据深入分析双侧发力协同能力与中枢神经募集状态)

    ## 二、 知识库理论映射
    - (在此强制引用知识库理论！解释上述异常数据是如何导致水平推进力流失的，指出力学模型的本质缺陷)

    ## 三、 专项干预处方
    - (针对核心瓶颈，开出至少3个具体的专项训练动作。必须包含：动作名称、执行要点、组数与间歇时间、配速要求，以及该动作旨在解决哪一项具体的数据异常)
    """

    print("🚀 正在连接 DeepSeek AI 引擎，请求专家诊断...")

    # 5. 调用 DeepSeek Chat Completions API
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位具备丰富实战经验与深厚学术造诣的顶级短跑生物力学教练，精通《短跑与跨栏力学》领域的专业知识。你擅长将复杂的生物力学数据转化为可执行的训练处方。请严格按照用户要求的Markdown格式输出。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 4096
        }

        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        # 6. 处理返回结果并写入 Markdown
        if response.status_code != 200:
            error_msg = f"# AI 教练分析错误\n\n**API Error**: `{response.status_code}` - {response.text}\n\n> 请检查 DeepSeek API Key 是否有效。"
            print(error_msg)
            return save_and_return(error_msg)

        response_data = response.json()
        if "choices" not in response_data or len(response_data["choices"]) == 0:
            error_msg = f"# AI 教练分析错误\n\n**API Error**: 响应格式异常，未找到 choices 字段\n\n```\n{json.dumps(response_data, ensure_ascii=False, indent=2)}\n```"
            print(error_msg)
            return save_and_return(error_msg)

        report = response_data["choices"][0]["message"]["content"]
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(report)

        print("\n✅ 诊断报告生成成功！已保存至:", output_md_path)
        return report

    except Exception as e:
        import traceback as _tb
        error_detail = _tb.format_exc()
        error_msg = f"# AI 教练分析错误\n\n**API Connection Failed**: {str(e)}\n\n```\n{error_detail}\n```\n\n> 可能原因：\n> 1. DeepSeek API Key 无效或已过期\n> 2. 网络连接问题\n> 3. 请求超时，请稍后重试"
        print(error_msg)
        return save_and_return(error_msg)


# --- 本地测试入口 ---
if __name__ == '__main__':
    # 模拟输入路径与输出路径
    test_payload_path = 'sprint_timeseries_data.json'
    test_output_md = 'coach_prescription.md'

    # 如果本地没有测试用的 JSON，代码会自动生成一个伪造的数据用来测试联通性
    if not os.path.exists(test_payload_path):
        dummy_data = {
            "phase_2_maximum_velocity": True,
            "metrics": {"cv_index": 0.08, "right_knee_velocity_drop": 15}
        }
        with open(test_payload_path, 'w', encoding='utf-8') as f:
            json.dump(dummy_data, f, ensure_ascii=False)
            print(f"🔧 创建了临时测试载荷: {test_payload_path}")

    # 执行诊断
    result = generate_training_prescription(test_payload_path, test_output_md)
    print("\n--- 诊断结果预览 ---\n")
    print(result)