import streamlit as st
import streamlit.components.v1 as components
import re
import requests
import json
import tempfile
import os
import time
from datetime import datetime
from io import BytesIO
from PIL import Image
from google_play_scraper import app as play_app
from google import genai
from google.genai import types
import plotly.express as px
import pandas as pd

# 尝试导入 yt_dlp，如果失败会在前端报错提示
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

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

# ================= 1.5 图片/视频处理与前端渲染模块 =================

def load_image_from_url(url):
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        clean_img = Image.new('RGB', img.size)
        clean_img.paste(img.convert('RGB'))
        return clean_img
    except Exception as e:
        print(f"图片加载失败 {url}: {e}")
        return None

def render_dynamic_content(text):
    """动态解析 Markdown，遇到 Mermaid 画流程图，遇到 JSON 画雷达图、饼图和甘特图"""
    marker = "\x60\x60\x60"
    pattern = r'(' + marker + r'(?:mermaid|json).*?' + marker + r')'
    blocks = re.split(pattern, text, flags=re.DOTALL)
    
    for block in blocks:
        if block.startswith(marker + 'mermaid'):
            mermaid_code = block.replace(marker + 'mermaid', '').replace(marker, '').strip()
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
            
        elif block.startswith(marker + 'json'):
            json_str = block.replace(marker + 'json', '').replace(marker, '').strip()
            try:
                data = json.loads(json_str)
                has_visuals = False
                
                if "progression_radar" in data and "monetization_pie" in data:
                    has_visuals = True
                    st.write("---") 
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        radar_data = data["progression_radar"]
                        df_radar = pd.DataFrame(dict(r=list(radar_data.values()), theta=list(radar_data.keys())))
                        df_radar = pd.concat([df_radar, df_radar.iloc[[0]]], ignore_index=True)
                        fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, title="⚔️ 养成模块深度评估 (1-10分)")
                        fig_radar.update_traces(fill='toself', line_color='#00F0FF')
                        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])))
                        st.plotly_chart(fig_radar, use_container_width=True)
                        
                    with col2:
                        pie_data = data["monetization_pie"]
                        df_pie = pd.DataFrame(dict(value=list(pie_data.values()), name=list(pie_data.keys())))
                        fig_pie = px.pie(df_pie, values='value', names='name', title="💰 核心商业化模式占比")
                        fig_pie.update_traces(hole=.4, hoverinfo="label+percent") 
                        st.plotly_chart(fig_pie, use_container_width=True)
                
                if "liveops_timeline" in data:
                    has_visuals = True
                    timeline_data = data["liveops_timeline"]
                    df_timeline = pd.DataFrame(timeline_data)
                    
                    if not df_timeline.empty and all(col in df_timeline.columns for col in ["Event", "Start", "Finish", "Type"]):
                        df_timeline["Start"] = pd.to_datetime(df_timeline["Start"])
                        df_timeline["Finish"] = pd.to_datetime(df_timeline["Finish"])
                        mask = df_timeline["Start"] == df_timeline["Finish"]
                        df_timeline.loc[mask, "Finish"] += pd.Timedelta(days=1)
                        
                        st.write("---") 
                        fig_timeline = px.timeline(
                            df_timeline, x_start="Start", x_end="Finish", y="Event", color="Type",
                            title="📅 LiveOps 长线运营推演排期表 (未来3个月模拟)"
                        )
                        fig_timeline.update_yaxes(autorange="reversed")
                        st.plotly_chart(fig_timeline, use_container_width=True)
                        
                if not has_visuals:
                    st.json(data)
                    
            except Exception as e:
                st.error(f"图表解析失败，AI 输出的 JSON 格式可能有误: {e}")
                st.code(json_str, language='json')
                
        else:
            if block.strip():
                st.markdown(block)

# ================= 2. AI 核心分析模块 =================

def analyze_game_with_ai(game_data, gemini_video_file, api_key):
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
                    
    data_str = json.dumps(text_data_for_ai, indent=2, ensure_ascii=True)
    
    system_instruction = """
    你现在是一位拥有10年经验的海外手游制作人兼高级发行总监。
    我为你提供了该游戏的【商店文案数据】以及【真实的商店游戏截图】。同时，用户可能还提供了【买量视频(UA Video)】。
    请深度拆解该游戏，以专业、简练的行业术语输出。
    严格按照以下 Markdown 格式输出：
    
    ### 1. 市场定位
    (请【分点列出】：目标受众人群画像、核心差异化卖点)
    
    ### 2. 游戏画风（视觉拆解）
    (⚠️ 务必直接观察提供的真实截图，请【分点列出】详细分析：色彩饱和度、2D/3D表现、UI排版风格、美术题材等特征)
    
    ### 3. 玩法类型
    (请简要概括：核心玩法、是否融合了副玩法)
    
    ### 4. 核心循环推测 (Core Loop)
    请先用一段简练的文字概括玩家的单局或中长线行为闭环。
    然后，**必须**使用 Mermaid 流程图代码来可视化这个核心循环。
    要求：代码必须包裹在 \x60\x60\x60mermaid 和 \x60\x60\x60 之间。
    
    ### 5. 成长与付费系统推测
    (仅提供文字分析，请【分点推测】可能的养成维度与商业化设计)
    
    ### 6. LiveOps 设计推测
    (仅提供文字分析，分析更新频率和日志内容，推测其长线运营节奏)
    
    ### 7. 买量素材深度诊断 (UA Video Analysis)
    (⚠️ 务必检查输入内容中是否包含了买量视频。
    - **如果包含了 UA 视频**：请重点发挥你的视听觉多模态能力，深度分析该视频的：【前3秒黄金Hook (视觉与听觉刺激)】、【视频剧情走向与节奏】、【BGM与音效的作用】以及【与真实玩法的差异度(Fake Ad / 擦边球判断)】。
    - **如果没有提供视频**：请直接输出“未上传买量视频，跳过此环节的深度分析”。)
    
    ---
    ### 📊 结构化可视化数据
    在所有的文字分析结束后，**必须**附带唯一一段纯 JSON 代码（使用 \x60\x60\x60json 和 \x60\x60\x60 包裹），用于生成图表。
    JSON 必须严格包含以下结构：
    {
      "progression_radar": {"等级与基础属性": 8, "装备与词条": 9, "技能与流派拓展": 5, "外观收集": 3, "其他养成": 6}, 
      "monetization_pie": {"抽卡/开箱": 40, "战令/通行证": 30, "破冰/限时礼包": 20, "资源直购": 10},
      "liveops_timeline": [
        {"Event": "当前版本更新", "Start": "2023-10-01", "Finish": "2023-10-01", "Type": "版本更新"},
        {"Event": "S1 赛季战令开启", "Start": "2023-10-05", "Finish": "2023-11-05", "Type": "赛季更新"}
      ]
    }
    注意：
    - progression_radar 代表养成深度打分（满分10分），正好5个维度。
    - monetization_pie 代表核心付费点占比，各项数值相加必须为 100。
    - liveops_timeline 请根据抓取到的"最近更新时间"，向后合理推演未来 3 个月的模拟排期！包含 Event(事件名)、Start(开始时间 YYYY-MM-DD)、Finish(结束时间 YYYY-MM-DD)、Type(事件类型)。
    """

    try:
        contents_list = [f"以下是抓取到的游戏商店基础数据：\n{data_str}\n\n同时附带了一些真实的商店截图，请先阅读。"]
        contents_list.extend(image_objects)
        
        # 将视频文件追加给大模型
        if gemini_video_file:
            contents_list.append("\n\n---\n以下是用户提供的该游戏【核心买量视频】。请务必结合视频画面和声音完成分析：")
            contents_list.append(gemini_video_file)

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
st.markdown("输入竞品商店链接并**提供买量视频**，AI将生成包含图文/视频解析的全案结构化拆解报告。")

with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("输入你的 Gemini API Key", type="password")
    st.markdown("[获取 Gemini API Key](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.caption("注：本工具不会存储您的 API Key。")

# --- 商店链接输入区 ---
st.subheader("🛒 1. 基础商店信息获取")
col1, col2 = st.columns(2)
with col1:
    gp_url = st.text_input("Google Play 商店链接")
with col2:
    ios_url = st.text_input("App Store 商店链接")

# --- UA 视频输入区 ---
st.subheader("📺 2. 附加：买量视频 (UA Video) 深度视听觉分析")
st.info("💡 视频包含比截图丰富百倍的信息！AI 能够读取视频画面和配乐，帮你一针见血地诊断 Fake Ad 套路和前 3 秒黄金 Hook。")

ua_video_option = st.radio("选择提供视频的方式：", ["⬆️ 上传本地视频 (推荐，更稳定)", "🔗 输入 YouTube 视频链接"])
ua_video_upload = None
yt_url = ""

if "上传" in ua_video_option:
    ua_video_upload = st.file_uploader("上传竞品买量视频 (支持 mp4/mov，建议小于 50MB)", type=['mp4', 'mov'])
else:
    yt_url = st.text_input("YouTube 视频链接 (例如: https://www.youtube.com/watch?v=...)")
    st.caption("⚠️ 注：由于云服务器 IP 限制，部分 YouTube 视频可能会被拦截抓取。若报错，请改用本地上传。")

if st.button("🚀 一键提取并分析", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ 请先在左侧栏输入您的 Gemini API Key！")
        st.stop()
        
    if not gp_url and not ios_url:
        st.warning("⚠️ 请至少输入一个商店的链接！")
        st.stop()

    game_data = {}
    gemini_video_file = None
    video_path_to_delete = None
    status_container = st.empty()
    
    with status_container.container():
        # 1. 抓取商店数据
        if gp_url:
            with st.spinner("正在抓取 Google Play 数据与商店截图..."):
                gp_result = get_google_play_info(gp_url)
                if "error" in gp_result:
                    st.error(gp_result["error"])
                else:
                    game_data["Google Play"] = gp_result
                    st.success("✅ Google Play 数据就绪！")
                    
        if ios_url:
            with st.spinner("正在抓取 App Store 数据与商店截图..."):
                ios_result = get_app_store_info(ios_url)
                if "error" in ios_result:
                    st.error(ios_result["error"])
                else:
                    game_data["App Store"] = ios_result
                    st.success("✅ App Store 数据就绪！")
        
        # 2. 处理视频并上传给 Gemini
        if ua_video_upload or yt_url:
            with st.spinner("⏳ 正在预处理买量视频 (视频处理耗时较长，请耐心等待 10~30 秒)..."):
                try:
                    client = genai.Client(api_key=api_key)
                    
                    if "上传" in ua_video_option and ua_video_upload:
                        # 本地上传：保存为临时文件
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                            tmp.write(ua_video_upload.read())
                            video_path_to_delete = tmp.name
                            
                    elif "YouTube" in ua_video_option and yt_url:
                        if not yt_dlp:
                            st.error("未安装 yt-dlp 依赖，无法解析 YouTube 链接。请检查 requirements.txt")
                        else:
                            st.info("⬇️ 正在从 YouTube 提取视频流...")
                            # 仅下载预合并的 MP4 格式，避免需要 ffmpeg 环境
                            ydl_opts = {
                                'format': 'b[ext=mp4]/best', 
                                'outtmpl': '%(id)s.%(ext)s',
                                'quiet': True,
                                'noplaylist': True
                            }
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                info = ydl.extract_info(yt_url, download=True)
                                video_path_to_delete = ydl.prepare_filename(info)
                    
                    # 将临时视频上传至 Gemini 引擎并轮询状态
                    if video_path_to_delete and os.path.exists(video_path_to_delete):
                        st.info("⬆️ 正在将视频传输至 AI 视觉核心引擎处理...")
                        gemini_video_file = client.files.upload(file=video_path_to_delete)
                        
                        # Gemini 处理视频需要时间，必须轮询等待状态变为 ACTIVE
                        while gemini_video_file.state.name == "PROCESSING":
                            time.sleep(2)
                            gemini_video_file = client.files.get(name=gemini_video_file.name)
                            
                        if gemini_video_file.state.name == "FAILED":
                            st.error("❌ AI 引擎解析视频失败。")
                            gemini_video_file = None
                        else:
                            st.success("✅ 视频视觉与音频特征提取完毕！")
                            
                except Exception as e:
                    st.error(f"❌ 视频获取或处理发生异常: {e}")
                    
    # 3. 开始 AI 聚合分析
    if game_data:
        st.divider()
        st.subheader("🤖 AI 制作人全案拆解报告")
        
        # 展示商店截图预览
        store_img_urls = []
        for p, d in game_data.items():
            if "截图" in d:
                store_img_urls.extend(d["截图"])
        if store_img_urls:
            st.markdown("**🔍 分析所参考的商店视觉素材：**")
            img_cols = st.columns(min(len(store_img_urls), 6))
            for idx, url in enumerate(store_img_urls[:6]):
                img_cols[idx].image(url, use_container_width=True)
                
        with st.spinner("🧠 最终数据汇总中：AI 正在深度解码系统设计与 UA 策略，请稍候..."):
            report = analyze_game_with_ai(game_data, gemini_video_file, api_key)
            
        render_dynamic_content(report)
        
        with st.expander("查看抓取到的原始商店文本数据"):
            clean_data = {p: {k: v for k, v in d.items() if k != "截图"} for p, d in game_data.items()}
            st.json(clean_data)
            
    # 最后清理占用云服务器空间的临时视频文件
    if video_path_to_delete and os.path.exists(video_path_to_delete):
        try:
            os.remove(video_path_to_delete)
        except:
            pass
