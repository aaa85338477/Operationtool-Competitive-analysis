import streamlit as st
import streamlit.components.v1 as components
import re
import requests
import json
from datetime import datetime
from io import BytesIO
from PIL import Image
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
            "内购价格区间": result.get('inAppProductPrice', '无数据'),
            "截图": result.get('screenshots', [])[:3] 
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
            "主分类": result.get('primaryGenreName'),
            "截图": result.get('screenshotUrls', [])[:3]
        }
    except Exception as e:
        return {"error": f"App Store 抓取失败: {str(e)}"}

# ================= 1.5 图片加载与前端渲染模块 =================

def load_image_from_url(url):
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"图片加载失败 {url}: {e}")
        return None

def render_markdown_with_mermaid(text):
    """解析包含 Mermaid 代码块的 Markdown 文本并混合渲染"""
    parts = re.split(r'```mermaid(.*?)```', text, flags=re.DOTALL)
    
    for i, part in enumerate(parts):
        if i % 2 == 0:
            if part.strip():
                st.markdown(part)
        else:
            mermaid_code = part.strip()
            # 注入 HTML 和官方 Mermaid.js 渲染器
            mermaid_html = f"""
            <div class="mermaid" style="display: flex; justify-content: center;">
                {mermaid_code}
            </div>
            <script type="module">
                import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
            </script>
            """
            components.html(mermaid_html, height=450, scrolling=True)

# ================= 2. AI 核心分析模块 =================

def analyze_game_with_ai(game_data, api_key):
    client = genai.Client(api_key=api_key)
    
    text_data_for_ai = {}
    image_objects = []
    
    for platform, data in game_data.items():
        text_data_for_ai[platform] = {k: v for k, v in data.items() if k != "截图"}
        if "截图" in data:
            for img_url in data["截图"]:
                img = load_image_from_url(img_url)
                if img:
                    image_objects.append(img)
                    
    # 【修复1】ensure_ascii=True 确保中文字符串能正常编码传输，防止报错
    data_str = json.dumps(text_data_for_ai, indent=2, ensure_ascii=True)
    
    system_instruction = """
    你现在是一位拥有10年经验的海外手游制作人兼发行总监。
    我为你提供了该游戏的【商店文案数据】以及【真实的商店游戏截图】。
    请深度拆解该游戏，以专业、简练的行业术语输出。
    严格按照以下 Markdown 格式输出：
    
    ### 1. 市场定位
    (结合文本推断受众人群画像、核心差异化卖点)
    
    ### 2. 游戏画风（视觉拆解）
    (⚠️ 务必直接观察提供的真实截图，详细分析其色彩饱和度、2D/3D表现、UI排版风格、美术题材等视觉特征。切勿盲目相信商店文案的自吹自擂！)
    
    ### 3. 玩法类型
    (核心玩法、是否融合了副玩法)
    
    ### 4. 核心循环推测 (Core Loop)
    请先用一段简练的文字概括玩家的单局或中长线行为闭环。
    然后，**必须**使用 Mermaid 流程图代码来可视化这个核心循环。
    要求：
    - 使用方向从左到右 (graph LR) 或从上到下 (graph TD) 的流程图。
    - 节点文案必须精简（如：局内战斗、获取资源、局外养成）。
    - 确保代码包裹在 ```mermaid 和 ``` 之间。
    
    ### 5. 成长与付费系统推测
    (可能的养成维度，以及根据内购/价格反推的商业化设计)
    
    ### 6. LiveOps 设计推测
    (分析更新频率和日志内容，推测其长线运营节奏)
    """

    try:
        contents_list = [f"以下是抓取到的游戏商店基础数据：\n{data_str}\n\n同时附上真实的商店截图。请结合图文开始你的拆解分析。"]
        contents_list.extend(image_objects)

        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=contents_list,
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
st.markdown("输入竞品的应用商店链接，AI将结合**商店数据与真实截图**，一键生成结构化拆解报告（含可视化核心循环图）。")

with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("输入你的 Gemini API Key", type="password")
    st.markdown("[获取 Gemini API Key](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.caption("注：本工具不会存储您的 API Key。")

col1, col2 = st.columns(2)
with col1:
    gp_url = st.text_input("Google Play 商店链接")
with col2:
    ios_url = st.text_input("App Store 商店链接")

if st.button("🚀 一键提取并分析", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ 请先在左侧栏输入您的 Gemini API Key！")
        st.stop()
        
    if not gp_url and not ios_url:
        st.warning("⚠️ 请至少输入一个商店的链接！")
        st.stop()

    game_data = {}
    status_container = st.empty()
    
    with status_container.container():
        if gp_url:
            with st.spinner("正在抓取 Google Play 数据与截图..."):
                gp_result = get_google_play_info(gp_url)
                if "error" in gp_result:
                    st.error(gp_result["error"])
                else:
                    game_data["Google Play"] = gp_result
                    st.success("✅ Google Play 数据抓取成功！")
                    
        if ios_url:
            with st.spinner("正在抓取 App Store 数据与截图..."):
                ios_result = get_app_store_info(ios_url)
                if "error" in ios_result:
                    st.error(ios_result["error"])
                else:
                    game_data["App Store"] = ios_result
                    st.success("✅ App Store 数据抓取成功！")
                    
    if game_data:
        st.divider()
        st.subheader("🤖 AI 制作人图文联合拆解报告")
        
        st.markdown("**🔍 分析所参考的真实截图：**")
        img_cols = st.columns(6)
        col_idx = 0
        for p, d in game_data.items():
            if "截图" in d:
                for url in d["截图"]:
                    img_cols[col_idx % 6].image(url, use_container_width=True)
                    col_idx += 1
        
        with st.spinner("AI 正在观察游戏截图并深度解码系统设计，请稍候..."):
            report = analyze_game_with_ai(game_data, api_key)
            
        # 【修复2】调用自定义的混合渲染函数，代替原来的 st.markdown(report)
        render_markdown_with_mermaid(report)
        
        with st.expander("查看抓取到的原始商店文本数据"):
            clean_data = {p: {k: v for k, v in d.items() if k != "截图"} for p, d in game_data.items()}
            st.json(clean_data)
