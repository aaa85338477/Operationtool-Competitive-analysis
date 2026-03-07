import re
import requests
import json
from datetime import datetime
from google_play_scraper import app as play_app
from google import genai
from google.genai import types

# ================= 1. 数据清洗与抓取模块 =================

def clean_date(date_obj_or_str):
    """把时间统一格式化为 YYYY-MM-DD，去掉多余的时分秒"""
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
    """提取 Google Play 商店信息"""
    match = re.search(r'id=([a-zA-Z0-9._]+)', play_url)
    if not match:
        return {"error": "无法从链接中提取包名"}
    app_id = match.group(1)
    try:
        result = play_app(app_id, lang='en', country='us')
        return {
            "平台": "Google Play",
            "游戏名称": result.get('title'),
            "最近更新时间": clean_date(result.get('updated')),
            "更新日志": result.get('recentChanges', '无'),
            "应用描述": result.get('description', '无')[:1500], # 截取前1500字符
            "内购价格区间": result.get('inAppProductPrice', '无数据')
        }
    except Exception as e:
        return {"error": f"Google Play 抓取失败: {str(e)}"}

# ================= 2. AI 核心分析模块 =================

def analyze_game_with_ai(game_data, api_key):
    """调用 Gemini 2.5 Flash-Lite 对抓取的数据进行结构化拆解"""
    print("正在呼叫 AI 制作人进行深度拆解...")
    
    # 初始化客户端
    client = genai.Client(api_key=api_key)
    
    # 将抓取到的字典数据转成漂亮的 JSON 字符串，方便 AI 阅读
    data_str = json.dumps(game_data, indent=2, ensure_ascii=False)
    
    # 核心 System Prompt (系统提示词)
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
    (可能的养成维度，以及根据内购价格反推的商业化设计)
    
    ### 6. LiveOps 设计推测
    (分析更新频率和日志内容，推测其长线运营节奏，如通行证、周期活动等)
    """

    try:
        # 调用 Gemini 2.5 Flash-Lite 模型
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=f"以下是抓取到的游戏商店数据：\n{data_str}\n\n请开始你的拆解分析。",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3, # 稍微调低温度，让输出更严谨、更具结构性
            )
        )
        return response.text
    except Exception as e:
        return f"AI 分析出错: {str(e)}"

# ================= 测试运行区 =================
if __name__ == "__main__":
    # 替换成你申请的 Gemini API Key
    YOUR_API_KEY = "这里填入你的_API_KEY" 
    
    test_play_url = "https://play.google.com/store/apps/details?id=com.playrix.gardenscapes" # 以梦幻花园为例
    
    # 1. 抓取数据
    raw_data = get_google_play_info(test_play_url)
    
    if "error" in raw_data:
        print(raw_data["error"])
    else:
        print(f"成功抓取基础数据: {raw_data['游戏名称']}")
        
        # 2. 调用 AI 分析
        if YOUR_API_KEY != "这里填入你的_API_KEY":
            analysis_report = analyze_game_with_ai(raw_data, YOUR_API_KEY)
            print("\n" + "="*20 + " AI 竞品拆解报告 " + "="*20)
            print(analysis_report)
        else:
            print("\n请先在代码中填入你的 API Key，即可看到 AI 生成的报告！")
