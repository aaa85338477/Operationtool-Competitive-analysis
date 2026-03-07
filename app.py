import streamlit as st
import re
import requests
import json
from datetime import datetime
from google_play_scraper import app as play_app
from google import genai
from google.genai import types

# ================= 1. 数据清洗与抓取模块 =================

def clean_date(date_obj_or_str):
    if not date_obj_or_str:
        return "未知时间"
    try:
        if isinstance(date_obj_or_str, datetime):
            return date_obj_or_str.strftime('%Y-%m-%d')
        elif isinstance(date_obj_or_str, str):
            dt = datetime.strptime(date_obj_or_str, "%Y-%m-%dT%H:%M:%SZ")
            return dt.strftime('%Y-%m-%d')
    except Exception:
        return str(date_obj_or_str)

def get_google_play_info(play_url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', play_url)
    if not match:
        return {"error": "无法从链接中提取 Google Play 包名"}
    app_id = match.group(1)
    try:
        result = play_app(app_id, lang='en', country='us')
        return {
            "平台": "Google Play",
            "游戏名称": result.get('title'),
            "最近更新时间": clean_date(result.get('updated')),
            "更新日志": result.get('recentChanges', '无'),
            "应用描述": result.get('description', '无')[:1500],
            "内购价格区间": result.get('inAppProductPrice', '无数据')
        }
    except Exception as e:
        return {"error": f"Google Play 抓取失败: {str(e)}"}

def get_app_store_info(apple_url):
    match = re.search(r'id(\d+)', apple_url)
    if not match:
        return {"error": "无法从链接中提取 App Store ID"}
    app_id = match.group(1)
    try:
        url = f"https://itunes.apple.com/lookup?id={app_id}&country=us"
        response = requests.get(url)
        data = response.json()
        if data['resultCount'] == 0:
            return {"error": "App Store 未找到该应用"}
        result = data['results'][0]
        return {
            "平台": "App Store",
            "游戏名称": result.get('trackName'),
            "最近更新时间": clean_date(result.get('currentVersionReleaseDate')),
            "更新日志": result.get('releaseNotes', '无'),
            "应用描述": result.get('description', '无')[:1500],
            "价格": result.get('price', 0.0),
            "主分类": result.get('primaryGenreName')
        }
    except Exception as e:
        return {"error": f"App Store 抓取失败: {str(e)}"}

# ================= 2. AI 核心分析模块 =================

def analyze_game_with_ai(game_data, api_key):
    client = genai.Client(api_key=api_key)
    data_str = json.dumps(game_data, indent=2, ensure_ascii=False)
    
    system_instruction = """
    你现在是一位拥有10年经验的海外手游制作人兼发行总监。
    请根据提供的竞品应用商店数据（包含描述、内购项、更新日志等），深度拆解该游戏。
    请以专业、简练的行业术语输出，不要说废话。
    严格按照以下 Markdown 格式输出：
    
    ### 1. 市场定位
    (受众人群画像、核心差异化卖点)
    
    ### 2. 游戏画风
    (结合描述推测视觉风格，以及对目标市场的适配度)
    
    ### 3. 玩法类型
    (核心玩法、是否融合了副玩法)
    
    ### 4. 核心循环推测 (Core Loop)
    (玩家单局或中长线的行为闭环)
    
    ### 5. 成长与付费系统推测
    (可能的养成维度，以及根据内购/价格反推的商业化设计)
    
    ### 6. LiveOps 设计推测
    (分析更新频率和日志内容，推测其长线运营节奏)
    """

    try:
        # 使用 Gemini 2.5 Flash-Lite 保证响应速度与接口权限匹配
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=f"以下是抓取到的游戏商店数据：\n{data_str}\n\n请开始你的拆解分析。",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3, 
            )
        )
        return response.text
    except Exception as e:
        return f"AI 分析出错: {str(e)}"

# ================= 3. Streamlit 前端界面 =================

st.set_page_config(page_title="竞品智能拆解工具", page_icon="🎮", layout="wide")

st.title("🎮 海外竞品智能拆解工具")
st.markdown("输入竞品的应用商店链接，一键生成包含核心玩法、商业化及 LiveOps 推测的结构化报告。")

# 侧边栏：配置 API Key
with st.sidebar:
    st.header("⚙️ 设置")
    # 提供密码输入框，保护隐私
    api_key = st.text_input("输入你的 Gemini API Key", type="password")
    st.markdown("[获取 Gemini API Key](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.caption("注：本工具不会存储您的 API Key，刷新页面后需重新输入。")

# 主界面：输入框
col1, col2 = st.columns(2)
with col1:
    gp_url = st.text_input("Google Play 商店链接", placeholder="例如: https://play.google.com/store/apps/details?id=com.supercell.brawlstars")
with col2:
    ios_url = st.text_input("App Store 商店链接", placeholder="例如: https://apps.apple.com/us/app/brawl-stars/id1229016807")

# 触发按钮
if st.button("🚀 一键提取并分析", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ 请先在左侧栏输入您的 Gemini API Key！")
        st.stop()
        
    if not gp_url and not ios_url:
        st.warning("⚠️ 请至少输入一个商店的链接！")
        st.stop()

    game_data = {}
    
    # 状态展示区域
    status_container = st.empty()
    
    with status_container.container():
        # 抓取数据
        if gp_url:
            with st.spinner("正在抓取 Google Play 数据..."):
                gp_result = get_google_play_info(gp_url)
                if "error" in gp_result:
                    st.error(gp_result["error"])
                else:
                    game_data["Google Play"] = gp_result
                    st.success("✅ Google Play 数据抓取成功！")
                    
        if ios_url:
            with st.spinner("正在抓取 App Store 数据..."):
                ios_result = get_app_store_info(ios_url)
                if "error" in ios_result:
                    st.error(ios_result["error"])
                else:
                    game_data["App Store"] = ios_result
                    st.success("✅ App Store 数据抓取成功！")
                    
    # 如果成功抓取到任何数据，开始 AI 分析
    if game_data:
        st.divider()
        st.subheader("🤖 AI 制作人深度拆解报告")
        
        with st.spinner("AI 正在深度解码系统设计与商业化逻辑，请稍候..."):
            report = analyze_game_with_ai(game_data, api_key)
            
        # 渲染最终报告
        st.markdown(report)
        
        # 折叠面板：查看原始抓取数据（方便 Debug 和对齐数据）
        with st.expander("查看抓取到的原始商店数据"):
            st.json(game_data)
