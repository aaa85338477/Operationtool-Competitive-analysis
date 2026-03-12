import streamlit as st
import streamlit.components.v1 as components
import re
import requests
import json
import tempfile
import os
from datetime import datetime
from io import BytesIO
from PIL import Image
from google_play_scraper import app as play_app
from google import genai
from google.genai import types
import plotly.express as px
import pandas as pd

# 尝试导入高级媒体处理库
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    import cv2
except ImportError:
    cv2 = None

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
        url = f"[https://itunes.apple.com/lookup?id=](https://itunes.apple.com/lookup?id=){app_id}&country=us"
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

def extract_keyframes(video_path, num_frames=5):
    """
    智能切帧引擎：从视频中均匀提取关键帧，绕过代理服务器的大文件上传限制
    """
    frames = []
    if not cv2:
        st.warning("缺少 opencv-python-headless 库，无法提取视频帧。")
        return frames
        
    try:
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            return frames
            
        # 等距采样，避开极端的片头片尾 (例如 1/6, 2/6, ..., 5/6 处)
        step = max(1, total_frames // (num_frames + 1))
        
        for i in range(1, num_frames + 1):
            frame_idx = i * step
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                # BGR 转 RGB 并化为 PIL Image
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                # 压缩尺寸，防代理中转请求体过大
                pil_img.thumbnail((800, 800))
                frames.append(pil_img)
        cap.release()
    except Exception as e:
        print(f"切帧失败: {e}")
        
    return frames

def render_dynamic_content(text):
    """动态解析 Markdown，渲染 Mermaid 流程图及 JSON 驱动的高级图表"""
    marker = "\x60\x60\x60"
    
    # 【修复重点 1】：增强型正则，兼容 AI 输出时附带的空格、换行及大小写差异
    pattern = r'(' + marker + r'\s*(?:mermaid|json)[\s\S]*?' + marker + r')'
    blocks = re.split(pattern, text, flags=re.IGNORECASE)
    
    for block in blocks:
        stripped_block = block.strip()
        
        # 匹配 mermaid
        if re.match(r'^' + marker + r'\s*mermaid', stripped_block, re.IGNORECASE):
            # 精准剥离代码块外壳
            mermaid_code = re.sub(r'^' + marker + r'\s*mermaid\s*', '', stripped_block, flags=re.IGNORECASE)
            mermaid_code = re.sub(r'\s*' + marker + r'$', '', mermaid_code).strip()
            
            mermaid_html = f"""
            <div class="mermaid" style="display: flex; justify-content: center;">
                {mermaid_code}
            </div>
            <script type="module">
                import mermaid from '[https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs](https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs)';
                mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
            </script>
            """
            components.html(mermaid_html, height=450, scrolling=True)
            
        # 匹配 json
        elif re.match(r'^' + marker + r'\s*json', stripped_block, re.IGNORECASE):
            json_str = re.sub(r'^' + marker + r'\s*json\s*', '', stripped_block, flags=re.IGNORECASE)
            json_str = re.sub(r'\s*' + marker + r'$', '', json_str).strip()
            
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
                
                if "ua_features_radar" in data and any(v > 0 for v in data["ua_features_radar"].values()):
                    has_visuals = True
                    st.write("---")
                    col_ua, _ = st.columns([1, 1]) 
                    with col_ua:
                        ua_data = data["ua_features_radar"]
                        df_ua = pd.DataFrame(dict(r=list(ua_data.values()), theta=list(ua_data.keys())))
                        df_ua = pd.concat([df_ua, df_ua.iloc[[0]]], ignore_index=True)
                        fig_ua = px.line_polar(df_ua, r='r', theta='theta', line_close=True, title="🎬 UA买量特征画像 (提炼自上传素材)")
                        fig_ua.update_traces(fill='toself', line_color='#FF0055') 
                        fig_ua.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])))
                        st.plotly_chart(fig_ua, use_container_width=True)
                
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
            if stripped_block:
                st.markdown(block)

# ================= 2. 中转站 SDK 核心分析模块 =================

def get_gemini_client(api_key):
    return genai.Client(
        api_key=api_key,
        http_options={'base_url': '[https://api.bltcy.ai](https://api.bltcy.ai)'}
    )

def analyze_game_with_ai(game_data, extracted_video_frames, api_key):
    client = get_gemini_client(api_key)
    
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
    
    # 【修复重点 2】：强化 Prompt 中的格式约束，防止挤成一团
    system_instruction = """
    你现在是一位拥有10年经验的海外手游制作人兼高级发行总监。
    我为你提供了该游戏的【商店文案数据】以及【真实的商店游戏截图】。同时，用户可能还提供了从【买量视频(UA Videos)中抽取的核心关键帧】。
    请深度拆解该游戏，以专业、简练的行业术语输出。
    严格按照以下 Markdown 格式输出：
    
    ### 1. 市场定位
    (请严格按照以下格式【分点列出】：
    - **目标受众人群**：...
    - **核心差异化卖点**：...)
    
    ### 2. 游戏画风（视觉拆解）
    (⚠️ 务必直接观察提供的真实截图，必须严格按照以下格式【分点列出】详细分析：
    - **色彩饱和度**：...
    - **2D/3D表现**：...
    - **UI排版风格**：...
    - **美术题材特征**：...)
    
    ### 3. 玩法类型
    (请简要概括：核心玩法、是否融合了副玩法)
    
    ### 4. 核心循环推测 (Core Loop)
    请先用一段简练的文字概括玩家的单局或中长线行为闭环。
    然后，**必须**使用 Mermaid 流程图代码来可视化这个核心循环。
    要求：代码必须包裹在 \x60\x60\x60mermaid 和 \x60\x60\x60 之间。
    
    ### 5. 成长与付费系统推测
    (仅提供文字分析，请按照以下格式【分点推测】：
    - **核心养成维度**：...
    - **主要商业化设计**：...)
    
    ### 6. LiveOps 设计推测
    (仅提供文字分析，分析更新频率和日志内容，推测其长线运营节奏)
    
    ### 7. 买量素材批量拆解 (UA Creative Batch Analysis)
    (⚠️ 务必检查输入内容中是否包含了从买量视频抽取的关键帧图像。
    - **如果包含了 UA 关键帧**：请按连环画逻辑推理其剧情，交叉比对提炼“起量公式”。重点分析：【推演的前3秒视觉Hook】、【共同刺激的受众情绪痛点(如：强迫症、同情弱者)】、【素材包装套路与真实玩法的差异(Fake Ad诊断)】。
    - **如果没有提供图像**：请直接输出“未上传买量视频，跳过此环节深度分析”。)
    
    ---
    ### 📊 结构化可视化数据
    在所有的文字分析结束后，**必须**附带唯一一段纯 JSON 代码（使用 \x60\x60\x60json 和 \x60\x60\x60 包裹），用于生成图表。
    JSON 必须严格包含以下结构：
    {
      "progression_radar": {"等级与基础属性": 8, "装备与词条": 9, "技能与流派拓展": 5, "外观收集": 3, "其他养成": 6}, 
      "monetization_pie": {"抽卡/开箱": 40, "战令/通行证": 30, "破冰/限时礼包": 20, "资源直购": 10},
      "ua_features_radar": {"解压ASMR (Satisfying)": 8, "故意失败 (Fail Ad)": 9, "剧情反转 (Drama)": 4, "智商碾压 (IQ Test)": 7, "擦边/猎奇 (Bizarre)": 3},
      "liveops_timeline": [
        {"Event": "当前版本更新", "Start": "2023-10-01", "Finish": "2023-10-01", "Type": "版本更新"}
      ]
    }
    注意：
    - progression_radar 代表养成深度打分（满分10分），正好5个维度。
    - monetization_pie 代表核心付费点占比，各项数值相加必须为 100。
    - ua_features_radar 代表这批买量素材的吸睛特征强度（满分10分），必须正好5个维度。**如果没有关键帧，请将此项的5个值全部填 0！**
    - liveops_timeline 请根据抓取到的"最近更新时间"，向后合理推演未来 3 个月的模拟排期！包含 Event, Start(YYYY-MM-DD), Finish(YYYY-MM-DD), Type。
    """

    try:
        contents_list = [f"以下是抓取到的游戏商店基础数据：\n{data_str}\n\n同时附带了一些真实的商店截图，请先阅读。"]
        contents_list.extend(image_objects)
        
        # 将抽取的视频帧批量追加给大模型（模拟看视频）
        if extracted_video_frames:
            contents_list.append("\n\n---\n以下是从用户提供的【多条核心买量视频】中按时间轴抽取的黄金关键帧。请像看连环画一样推理素材剧情和起量共性：")
            contents_list.extend(extracted_video_frames)

        response = client.models.generate_content(
            model='gemini-3.1-flash-lite-preview-thinking-high',
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
st.markdown("输入竞品商店链接并**批量提供买量视频**，AI将生成包含图文解析、买量套路拆解及图表全景的深度报告。")

with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("输入你的中转站 API Key", type="password")
    st.markdown("💡 已配置为 bltcy.ai 中转节点，并调用 **gemini-3.1-flash-lite-preview-thinking-high** 模型")
    st.divider()
    st.caption("注：本工具不会存储您的 API Key。")

# --- 商店链接输入区 ---
st.subheader("🛒 1. 基础商店信息获取")
col1, col2 = st.columns(2)
with col1:
    gp_url = st.text_input("Google Play 商店链接")
with col2:
    ios_url = st.text_input("App Store 商店链接")

# --- UA 视频批量输入区 ---
st.subheader("📺 2. 附加：买量视频批量解析 (UA Videos Pattern Analysis)")
st.info("💡 强力升级：支持同时分析多条视频！系统将自动抽取关键帧进行推演，完美绕过代理商大文件拦截。")

ua_video_option = st.radio("选择提供视频的方式：", ["⬆️ 上传本地视频 (推荐，支持批量)", "🔗 输入 YouTube 视频链接 (批量)"])
ua_video_uploads = []
yt_url_text = ""

if "上传" in ua_video_option:
    ua_video_uploads = st.file_uploader("上传竞品买量视频 (最多建议 3-5 个，单视频 <50MB)", type=['mp4', 'mov'], accept_multiple_files=True)
else:
    yt_url_text = st.text_area("YouTube 视频链接 (支持多行批量输入，每行粘贴一个链接，最多建议 3-5 个)")
    st.caption("⚠️ 注：部分 YouTube 视频可能会被云端节点拦截抓取。若报错，请改用本地上传。")

if st.button("🚀 一键提取并分析", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ 请先在左侧栏输入您的 API Key！")
        st.stop()
        
    if not gp_url and not ios_url:
        st.warning("⚠️ 请至少输入一个商店的链接！")
        st.stop()

    game_data = {}
    gemini_video_frames = [] # 改为存储从视频中抽取的 PIL Image 关键帧
    video_paths_to_delete = []
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
        
        # 2. 批量下载并切分视频帧 (完美避开 File API 封锁)
        if ua_video_uploads or yt_url_text.strip():
            with st.spinner("⏳ 正在并发预处理多批买量视频 (此步骤会自动提取黄金关键帧，约 10~40 秒)..."):
                try:
                    # 2.1 本地批量保存
                    if "上传" in ua_video_option and ua_video_uploads:
                        for vid_file in ua_video_uploads[:5]: 
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                                tmp.write(vid_file.read())
                                video_paths_to_delete.append(tmp.name)
                                
                    # 2.2 YouTube 批量下载
                    elif "YouTube" in ua_video_option and yt_url_text.strip():
                        if not yt_dlp:
                            st.error("未安装 yt-dlp 依赖，无法解析 YouTube 链接。请检查 requirements.txt")
                        else:
                            st.info("⬇️ 正在循环提取 YouTube 视频流...")
                            urls = [u.strip() for u in yt_url_text.split('\n') if u.strip()][:5]
                            
                            ydl_opts = {
                                'format': 'b[ext=mp4]/best', 
                                'outtmpl': '%(id)s.%(ext)s',
                                'quiet': True,
                                'noplaylist': True,
                                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                                'http_headers': {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                                }
                            }
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                for url in urls:
                                    try:
                                        info = ydl.extract_info(url, download=True)
                                        video_paths_to_delete.append(ydl.prepare_filename(info))
                                    except Exception as e:
                                        st.warning(f"视频 {url} 提取失败，已跳过: {e}")
                    
                    # 2.3 提取关键帧并准备发给大模型
                    if video_paths_to_delete:
                        st.info(f"🎞️ 正在从 {len(video_paths_to_delete)} 个视频中提取黄金关键帧(避开代理大文件限制)...")
                        for path in video_paths_to_delete:
                            # 每个视频抽取 5 张代表性截图
                            frames = extract_keyframes(path, num_frames=5)
                            if frames:
                                gemini_video_frames.extend(frames)
                                
                        if gemini_video_frames:
                            st.success(f"✅ 成功从视频中提取 {len(gemini_video_frames)} 张核心帧供 AI 分析！")
                        else:
                            st.error("❌ 视频切帧失败，请确保要求库已安装。")
                            
                except Exception as e:
                    st.error(f"❌ 视频获取或处理发生异常: {e}")
                    
    # 3. 开始 AI 聚合分析
    if game_data:
        st.divider()
        st.subheader("🤖 AI 制作人全案拆解报告 (含 UA 共性提炼)")
        
        store_img_urls = []
        for p, d in game_data.items():
            if "截图" in d:
                store_img_urls.extend(d["截图"])
        if store_img_urls:
            st.markdown("**🔍 基础分析参考素材 (商店真实截图)：**")
            img_cols = st.columns(min(len(store_img_urls), 6))
            for idx, url in enumerate(store_img_urls[:6]):
                img_cols[idx].image(url, use_container_width=True)
                
        # 展示抽取的视频帧缩略图
        if gemini_video_frames:
            st.markdown("**🎬 自动提取的买量素材关键帧：**")
            frame_cols = st.columns(min(len(gemini_video_frames), 6))
            for idx, frame in enumerate(gemini_video_frames[:6]):
                frame_cols[idx].image(frame, use_container_width=True)
                
        with st.spinner(f"🧠 终极推演中：调用 gemini-3.1-flash-lite-preview-thinking-high 提取爆款公式，请稍候..."):
            report = analyze_game_with_ai(game_data, gemini_video_frames, api_key)
            
        render_dynamic_content(report)
        
        with st.expander("查看抓取到的原始商店文本数据"):
            clean_data = {p: {k: v for k, v in d.items() if k != "截图"} for p, d in game_data.items()}
            st.json(clean_data)
            
    # 彻底清理所有服务器临时视频文件
    for path in video_paths_to_delete:
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
