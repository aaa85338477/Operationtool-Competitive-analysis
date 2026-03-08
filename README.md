🎮 海外竞品智能拆解工具 (Smart Competitor Analysis Tool)

📖 项目简介

作为海外游戏发行与制作人的得力助手，本工具旨在通过“极简输入”实现“极深洞察”。
只需输入竞品的 Google Play 或 App Store 链接，并选择性提供其买量广告素材（UA Video），工具即可自动抓取商店的多维度数据（文本与截图），并调用 Google 最新的 Gemini 2.5 Flash-Lite 多模态大模型，一键生成包含图文解析、商业化图表、长线运营推演在内的主策划级全案拆解报告。

✨ 核心功能

🛍️ 商店情报自动抓取：无需手动查阅，自动提取应用的文字描述、最新更新日志、内购价格区间及商店高清截图。

👀 多模态视觉拆解：不仅看文本，更通过清洗后的真实商店截图，从美术渲染、色彩饱和度、UI 布局进行深度的画风推断。

📊 数据图表原生可视化：AI 的推演不再是枯燥的文字。工具会自动将分析结果转译为动态图表：

核心循环图：自动渲染 Mermaid 交互式流程图（Core Loop）。

养成深度分析：Plotly 原生渲染“赛博朋克风”雷达图。

商业化结构：饼图直观展示抽卡、战令、直购的推测占比。

LiveOps 排期推演：时间轴甘特图推演未来 3 个月的长线运营节奏。

📺 买量素材 (UA Video) 深度诊断：支持直接输入 YouTube 链接或本地上传 MP4 视频，AI 直接读取音视频轨，拆解“前 3 秒黄金 Hook”、诊断是否为 Fake Ad（虚假宣传）。

⚙️ 运行逻辑全景图

以下为系统从接收用户输入到最终渲染报告的完整工作流架构：

graph TD
    %% 核心节点定义
    UI[🖥️ 前端界面 Streamlit]
    Data_Scraper[🕸️ 商店爬虫引擎]
    Img_Process[🖼️ 图像清洗模块 Pillow]
    Video_Process[🎬 视频预处理模块 yt-dlp]
    AI_Engine((🧠 Gemini 2.5 Flash-Lite))
    Renderer{🎨 动态解析渲染器}

    %% 用户输入流
    UI -->|1. 配置鉴权| Auth(Gemini API Key)
    UI -->|2. 输入商店链接| GP_iOS_URL(GP/iOS URL)
    UI -->|3. 提供买量视频| UA_Media(YouTube 链接 / 本地 MP4)

    %% 数据抓取与预处理
    GP_iOS_URL --> Data_Scraper
    Data_Scraper -->|提取文本| Raw_Text(应用描述, 版本日志, 价格区间)
    Data_Scraper -->|提取图床URL| Raw_Imgs(前3张商店截图)
    Raw_Imgs --> Img_Process
    Img_Process -->|剥离 EXIF 避免编码崩溃| Clean_Imgs(纯净 RGB 图像数组)

    UA_Media --> Video_Process
    Video_Process -->|解析与下载| Tmp_Video(服务器临时 MP4)
    Tmp_Video -->|调用 File API 上传| Gemini_Cloud_Video(云端待解析视频流)

    %% 多模态合流与分析
    Auth -.-> AI_Engine
    Raw_Text -->|构建 System Prompt| AI_Engine
    Clean_Imgs -->|注入多模态视觉上下文| AI_Engine
    Gemini_Cloud_Video -->|注入音视频上下文| AI_Engine

    %% AI 返回结果与解析
    AI_Engine -->|输出混合文本 Markdown+JSON+Mermaid| Renderer

    %% 前端动态可视化
    Renderer -->|正则提取纯文本| MarkDown[📝 文本洞察: 市场/画风/买量诊断]
    Renderer -->|拦截 ```mermaid| Mermaid_View[🔄 渲染 Core Loop 流程图]
    Renderer -->|拦截 ```json| Plotly_Engine[📊 交由 Plotly 绘制高级图表]

    Plotly_Engine --> Chart1[🕸️ 养成深度雷达图]
    Plotly_Engine --> Chart2[🍩 付费占比结构饼图]
    Plotly_Engine --> Chart3[📅 LiveOps 运营甘特图]


🛠️ 技术栈说明

前端框架：Streamlit (极速构建数据可视化交互界面)

数据抓取：google-play-scraper (GP 商店数据), requests (调用 Apple iTunes 官方接口)

多模态处理：

Pillow (实时处理与清洗网络图片 EXIF/Metadata)

yt-dlp (解析并下载 YouTube 流媒体)

大模型引擎：google-genai (调用 Gemini 2.5 Flash-Lite)

动态可视化：Plotly Express (雷达图/饼图/甘特图), Mermaid.js (嵌入式流程图渲染)

📦 部署与安装指南

1. 依赖文件 (requirements.txt)

确保项目根目录包含以下依赖：

streamlit>=1.30.0
requests>=2.31.0
google-play-scraper>=1.2.4
google-genai>=0.3.0
Pillow>=10.0.0
plotly>=5.18.0
pandas>=2.1.0
yt-dlp>=2024.03.10


2. 本地运行环境测试

安装 Python 3.9 或以上版本。

终端执行命令安装依赖：pip install -r requirements.txt

启动应用：streamlit run app.py

3. Streamlit Community Cloud 一键部署

将 app.py 与 requirements.txt 上传至您的 GitHub 仓库。

登录 Streamlit Cloud，点击 New app。

绑定该仓库及主文件路径（app.py），点击 Deploy。

部署成功后即可获得公网访问链接，随时随地进行竞品拆解。

💡 使用注意事项

API Key 隐私保护：本工具运行需要个人的 Google Gemini API Key，工具采用了安全输入框设计（不会缓存在服务器），请放心使用。

YouTube 抓取限制：部分海外节点可能会触发 YouTube 的反爬验证码拦截，如遇视频解析报错，建议使用本地上传功能上传轻量级 MP4 视频。

语言设置：目前抓取接口默认使用美区（country='us'）及英语（lang='en'），AI 输出为中文。如需针对特定区域，可自行在代码的 play_app() 及 iTunes API URL 中调整区域代码。
