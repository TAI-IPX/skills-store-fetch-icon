---
name: app-icon-filler
description: >-
  Fill design mockups with real, correctly named App Store app icons. Use when
  someone needs a realistic app icon wall, an integration or marketplace grid,
  an "as seen on" strip, or placeholder icons with genuine app names — for
  Figma slots they already drew, or downloaded to a local folder. Pulls official
  artwork from Apple's public lookup API, so icons are real rather than invented
  or hand-sourced.
---

# App Icon Filler（真实应用图标填充）

从 Apple 官方接口按真实应用取图标，用来给设计稿填位。**图标是真的，名字是真的，一句话文案按应用定位拟真，应用是随机抽的。**

两种用法，互不依赖：

1. **只下载到本地文件夹** —— 不需要 Figma，产出一批图标文件。
2. **填入 Figma 选中的槽位** —— 同时把真实应用名和一句拟真描述写进槽位里的文本层。

## 先确认一件事

用户是否有 Figma 可用。没有 Figma，或用户只说"给我找一批真实应用图标"，直接走用法 1，不要因为 Figma 不可用就中断。

---

## 用法 1：只下载到本地文件夹

```bash
python3 <skill>/scripts/fetch_icons.py --count 24
```

参数：

| 参数 | 作用 | 默认 |
| --- | --- | --- |
| `--count N` / `-n N` | 要几个图标，必填 | 无 |
| `--size` | `256` / `512` / `1024` | `512` |
| `--out DIR` | 输出目录 | 新建临时目录 |
| `--pool FILE` | 自定义应用池 JSON | skill 自带 `data/app_pool.json` |
| `--seed S` | 固定随机种子，同种子同结果 | 无 |

输出：`01.png`、`02.png`……按抽取顺序编号，外加一份 `manifest.json`。脚本会在 stdout 打印图标目录和 manifest 的**绝对路径**，把这两个路径原样告诉用户。

`manifest.json` 里 `items` 的顺序就是槽位填充顺序，每条含 `index`、`file`、`app_id`、`name`、`desc`、`category`、`country`、`store_title`、`source_url`。

默认输出到临时目录，不污染任何仓库。用户明确说要放哪，才传 `--out`。

---

## 用法 2：填入 Figma 槽位

### 步骤 0 — 解析 Figma 连接

**永远不要硬编码 link_id 或账号。** 每个用户有自己的一套连接。

- 环境里恰好一个可用连接 → 直接用。
- 多个可用连接 → 问用户用哪个，不要替他挑。
- 一个可用连接都没有 → 不要中断任务，退化为用法 1 只下载，并告诉用户连接 Figma 后可以重跑填充。
- 连接存在却返回 `UNAUTHORIZED` / 要求重新认证 → 明确让用户去重新连接 Figma。不要重试，也不要改用别的连接。

同样不要假设 `fileKey`。用户得给 Figma 链接，或从当前选中的文件/页面推断。

### 步骤 1 — 识别槽位（只读）

用 `use_figma` 只读地读 `figma.currentPage.selection`，把选中项展开成可填充的槽位：

- 算槽位的类型：FRAME、RECTANGLE、ELLIPSE、COMPONENT、INSTANCE 等有 fill 的节点。
- TEXT 和 GROUP 不算槽位。
- 按**阅读顺序**排序：先按 `absoluteBoundingBox.y` 分行（行容差 = 槽位高度中位数 × 0.5），行内再按 `x` 升序。
- 顺带记下每个槽位内部的两类文本层 nodeId。**名称层**：优先取名为 `name` / `应用名` 的 TEXT，否则取第一个 TEXT。**描述层**：优先取名为 `一句话描述` 或字符里含「描述」的 TEXT，否则取第二个 TEXT。设计文件里图层名经常是被复制后留下的旧应用名（例如名称层叫「QQ音乐」而内容是「微信」），所以**不要靠图层名判断，按上面顺序回退到位置**。

选中为空 → 停下来告诉用户去 Figma 里选中槽位，不要瞎猜一个节点填。

**槽位数就是取图数量，不要另外问用户要几个。** 若用户报的数与槽位数不一致，以槽位为准并说明。

### 步骤 2 — 取图

```bash
python3 <skill>/scripts/fetch_icons.py --count <槽位数>
```

### 步骤 3 — 上传

调 `figma_upload_assets`，一次拿到 N 个一次性上传地址：

- `count = N`
- `nodeIds = 有序槽位列表`（顺序必须与槽位顺序一致）
- `scaleMode = "FILL"`
- 带上 `fileKey`、`currentPageId`、解析出的 `link_id`

一次最多 60 个。超过 60 就按 60 分批，**先 POST 完当前批再申请下一批**。

### 步骤 4 — POST 本地文件

把 `manifest.json` 里的第 i 个文件 POST 到第 i 个上传地址，顺序不能错。已有 fill 会被覆盖，这正是我们要的。

```bash
curl -sS -X POST --data-binary @01.png -H "Content-Type: image/png" "<upload-url-1>"
```

Content-Type 按实际文件后缀给：`image/png`、`image/jpeg`、`image/webp`。目标环境没有 `curl` 时，用 Python 标准库 POST 同样的字节。

**槽位在组件实例内部时（设计稿里很常见）。** `figma_upload_assets` 的 `nodeIds` 只接受 `123:456` 这种简单 ID；设计系统里的图标常嵌在实例内部，ID 形如 `I123:456;789:012;...`，会被 schema 直接拒绝。这时改用两步：

1. 调 `figma_upload_assets` 只给 `count`、**不给 `nodeIds`**，POST 后从每个响应里取 `imageHash`。注意这会在当前页生成同名临时图层（通常叫 `01`、`02`……），填完后必须删掉。
2. 用 `use_figma` + `getNodeByIdAsync` 把 `node.fills = [{ type: 'IMAGE', imageHash, scaleMode: 'FILL' }]` 写进目标图标节点。

读、写实例内部的任意节点都用 `use_figma` + `getNodeByIdAsync` 传完整 ID，`metadata` 里的简写 ID 不要直接拿去回填。

### 步骤 5 — 写名字与描述

用 `use_figma` 按顺序写回 `manifest.json` 的第 i 条：

- **名称层**写 `name`。
- **描述层**写 `desc`。`desc` 是应用池里人工维护的一句话（如微信「随时联系，分享生活」）。池里没带 `desc`（自定义池常常没有）时，按应用的真实定位现场拟一句：8–14 个中文字，两个短句用逗号相连，说清它能做什么；不要复述应用名，不要写「这是一个…」，也不要抄商店标题或应用介绍原文。
- 两类文本都要先 `await figma.loadFontAsync(...)` 再设 `characters`，字体没加载就赋值会抛错。字体名从该节点自己的 `getStyledTextSegments(['fontName'])` 取，不要猜。
- 槽位里没有对应的文本层 → 跳过那一项，最后如实报告哪些槽位没写名称、哪些没写描述。
- 字体加载失败 → 跳过那条并报告，不影响图标已经填好这件事。

---

## 图的真实形态（很重要）

`bb` 原始方图是**满幅不透明的正方形，没有透明通道**。微信的左上角就是微信绿，美团就是美团黄。所以：

- 槽位要做成**方形画框 + 圆角 + 开启 clip content**，圆角半径由设计稿控制。这样灌进去就是标准的真实商店图标外观。
- 需要透明背景的官方圆角图，就把 URL 尾段换成 `{size}x{size}ia.png`。注意这是 Apple 的遮罩，圆角比例固定，不好微调。

尺寸上限以源图为准：多数应用 256/512/1024 都有；少数只上到 1024。默认 512 对 mockup 足够（约 70–160KB）。

## 应用池

自带 `data/app_pool.json` 是一份以国内应用为主的池子，覆盖社交、音乐、视频、购物、出行、金融、办公、工具、游戏、AI 等类目。每条：

```json
{ "id": "414478124", "name": "微信", "desc": "随时联系，分享生活", "category": "social", "country": "cn" }
```

- `id` 是 iTunes trackId，`country` 决定去哪个地区的商店查。
- `name` 是人工维护的**简短品牌名**，直接写进设计稿。**不要用 Apple 返回的商店标题**（那些带营销后缀，如「网易云音乐-数亿音乐畅听」），`store_title` 只作为核对用的参考留在 manifest 里。
- `desc` 是人工维护的**一句话拟真文案**，写进槽位的描述层，让 mockup 看起来像真的商店列表。同样不要抄商店标题或应用介绍原文；不需要就留空字符串。
- 加应用：在 App Store 里搜到目标应用，从其链接 `.../id6758482875` 里取数字，或直接拿裸 ID。
- 想完全换成自己的应用：复制这份 JSON 改，然后 `--pool 你的文件.json`。

脚本每次都会校验整份池子。**有 id 查不到时直接报错退出，不会静默跳过**；池子可用数少于请求数时也会报错并说明实际可用数。

## 边界

- 图标是 Apple 及各家开发者的商标，**只能做指示性展示**（"支持某应用"这类），不能当成自己的品牌标识，也不能暗示对方背书。
- 一次最多 60 个槽位。更大批量按 60 分批。
- 读不到实时选中时，退化方案：让用户复制 Figma 链接里的 `node-id` 指定容器，填充该容器下所有可填充子节点，同样按阅读顺序排。
- 只做图标获取与填充。不在本地生成 HTML 预览页，不做网格排版。
