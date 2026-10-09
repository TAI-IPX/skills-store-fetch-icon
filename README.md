# skills-store-fetch-icon（真实应用图标填充）

用真实的应用图标填充设计稿占位：从 Apple 官方接口按真实应用取官方方图，随机抽一批**真实存在**的应用，产出图标文件，并把真实的应用名和一句拟真的描述写进 Figma 槽位的文本层。

图标是真的，名字是真的，描述按应用定位拟真，应用是随机抽的。

## 仓库结构

    skills/
      skills-store-fetch-icon/
        SKILL.md              技能说明（英文 frontmatter，正文中文）
        scripts/fetch_icons.py 取图脚本（Python 3 标准库）
        data/app_pool.json     精选应用池

## 安装

把下面这段话发给你的智能体就行：

    请从 https://github.com/TAI-IPX/skills-store-fetch-icon 安装技能，技能在仓库里的路径是 skills/skills-store-fetch-icon

智能体会自己把技能装到你的技能目录，下一轮对话它就会出现在可用技能列表里，之后你直接说需求就能用。

## 用法

### 一、只下载到本地文件夹

不需要 Figma。

    python3 <skill>/scripts/fetch_icons.py --count 24 --out ~/Desktop/app-icons

产出 01.png、02.png…… 按抽取顺序编号，外加一份 manifest.json。不指定 --out 时写到系统临时目录，不污染任何仓库。

| 参数 | 作用 | 默认 |
| --- | --- | --- |
| --count N / -n N | 要几个图标，必填 | 无 |
| --size | 256 / 512 / 1024 | 512 |
| --out DIR | 输出目录 | 系统临时目录 |
| --pool FILE | 自定义应用池 JSON | 自带 data/app_pool.json |
| --seed S | 固定随机种子，结果可复现 | 无 |

### 二、填入 Figma 槽位

在 Figma 里选中要填充的槽位，然后让 agent 填。技能会按阅读顺序排序槽位、取等量图标、上传填充，并把真实应用名和描述写进槽位内的文本层。槽位数即取图数量。

前提是已连接 Figma，且账号对目标文件有权限。

## 应用池

data/app_pool.json 是一份以国内应用为主的池子，126 条，覆盖社交、音乐、视频、购物、出行、金融、办公、工具、游戏、AI 等类目。每条：

    { "id": "414478124", "name": "微信", "desc": "随时联系，分享生活", "category": "social", "country": "cn" }

- id 是 iTunes trackId，country 决定去哪个地区的商店查。
- name 是人工维护的简短品牌名，直接写进设计稿。
- desc 是一句话拟真文案，写进槽位的描述层。
- 想换成自己的应用：复制这份 JSON 改，再用 --pool 指过去。

脚本每次运行都会校验整份池子。有 id 查不到时直接报错退出，不会静默跳过；池子可用数少于请求数时也会报错并说明实际可用数。

## 依赖

Python 3 标准库，无第三方依赖。需要访问 Apple 的公开 lookup 接口。跨平台，不调用 sips 等平台专有命令。

## 可移植性

技能内不含任何个人路径、账号或连接 ID。运行时从当前环境解析 Figma 连接：恰好一个可用连接直接用；多个则询问使用者；一个都没有时退化为只下载图标，不中断任务。

## 边界

- 图标是 Apple 及各家开发者的商标，只能做指示性展示（例如「支持某应用」这类界面），不能当成自己的品牌标识，也不能暗示对方背书。
- 池子里的文案是按应用定位撰写的拟真占位内容，用于 mockup 展示，不等于各应用官方的宣传语。
