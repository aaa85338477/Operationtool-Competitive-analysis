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
import plotly.express as px
import pandas as pd

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

# ================= 1.5 图片加载与前端动态渲染模块 =================

def load_image_from_url(url):
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"图片加载失败 {url}: {e}")
        return None

def render_dynamic_content(text):
    """动态解析 Markdown，遇到 Mermaid 画流程图，遇到 JSON 画雷达图和饼图"""
    blocks = re.split(r'(
