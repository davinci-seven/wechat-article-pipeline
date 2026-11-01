# 主题

主题决定一篇文章贴进公众号后的样子。同一个账号的每一篇都用同一个主题，版式不要跟着文章变。

内置六套在 `tools/render_wechat.py` 的 `THEMES` 里，布局都是 `standard`。五个账号主题是仓库根目录 `themes/*.json`，各用自己的布局。两边用同一套字段。

```powershell
python tools\paste_wechat.py --list-themes
python tools\render_wechat.py --list-themes
```

## 现有布局

| layout | 用在 | 固定骨架 |
| --- | --- | --- |
| `standard` | 橄榄手记等六套 | 原有的章节序号结构，只换颜色和字号 |
| `diary` | 小满日记 | 居中刊头，宋体标题，段首缩进，行距松，引用是「旁注」 |
| `gazette` | 老陈跑社保 | 正文约 18px，海军蓝标题条，无序列表是黄底「划重点」，有序列表是大号序号，引用是「记住」，粗体铺黄底 |
| `memo` | 科室备忘 | 双横线刊头，条款下划线，列表紧，代码块是浅底 |
| `archive` | 旧纸堆 | 旧纸色，正文宋体，印章字，引用是双边「原文」框 |
| `kitchen` | 节气小灶 | 绿色标题加橙色短线，图片圆角橙框，无序列表是「用料」，有序列表是「做法」步骤卡 |

写稿时可以按这个习惯用 Markdown，主题会固定成上面的样子：

| 写法 | 小满日记 | 老陈跑社保 | 科室老周 | 旧纸堆 | 节气小灶 |
| --- | --- | --- | --- | --- | --- |
| `#` 标题 | 居中 | 蓝底白字 | 公文标题 | 居中宋体 | 绿字，下面一条橙线 |
| `##` 章节 | 小号序号 | 整条蓝底 | 条款，底下一道线 | 居中 | 绿字加橙线 |
| `-` 列表 | 疏朗圆点 | 黄框「划重点」 | 「事项」 | 疏朗圆点 | 「用料」 |
| `1.` 列表 | 疏朗序号 | 「按顺序看」 | 「步骤」 | 疏朗序号 | 「做法」步骤卡 |
| `>` 引用 | 旁注 | 记住，字重一些 | 说明 | 原文框 | 小记 |
| `**粗体**` | 加粗 | 黄底，用来标金额、年限、比例 | 加粗 | 加粗 | 加粗 |

刊头上的账号名（例如「小满的第八年」）来自主题定义，每篇都会带上，不写进 Markdown。

## 新增一个账号主题

只换颜色、沿用上面某种骨架时，复制一份 JSON 即可，不用改 Python。

1. 复制 `themes/xiaoman-diary.json` 为 `themes/你的-key.json`。
2. `key` 必须和文件名一致，只用小写字母、数字和连字符。
3. `layout` 填上表里的一个名字。
4. 改 `account`、`tagline`、颜色和字号。颜色用 `#RRGGBB`。字号写成 `16px` 这种字符串，不要写成数字。
5. 运行 `--list-themes` 确认能被读到。

`key` 不能和内置六套重名。多出来的字段会直接报错，避免打错字还静默套成别的主题。

PowerShell 入口不再写死主题名单，新 JSON 可以被 `-Theme` 用到。

### 字段

必填：

`key` `name_cn` `page_bg` `text` `heading` `accent` `accent_soft` `h1_bg` `h1_text` `h2_number` `h2_label` `h3_bg` `h3_text` `list_bg` `list_border` `list_text` `code_bg` `code_text` `code_lang` `inline_code_text` `inline_code_bg` `image_border` `caption` `hr` `strong` `font_size` `line_height` `letter_spacing` `para_gap` `chapter_gap`

可选，不写就用默认值：

| 字段 | 默认 | 作用 |
| --- | --- | --- |
| `layout` | `standard` | 上表里的骨架 |
| `account` | 空 | 每篇都出现的账号名。空则不画刊头和文末署名 |
| `tagline` | 空 | 刊头第二行 |
| `description` | 空 | 给人看的一句说明，不进正文 |
| `body_font` | 系统黑体 | 正文字体。只写本机就有的字体，不要链到网上 |
| `heading_font` | 跟正文 | 标题字体。旧纸堆、小满日记的标题用宋体 |
| `list_label` | 空 | 无序列表上的小标题，如「划重点」「用料」 |
| `step_label` | 空 | 有序列表上的小标题，如「做法」 |
| `takeaway_label` | 空 | 老陈跑社保引用框上的字，如「记住」 |
| `quote_label` | 空 | 引用框上的字，如「原文」「旁注」 |
| `seal` | 空 | 标题上方的印章字，旧纸堆用「旧」 |
| `image_radius` | `4px` | 图片圆角 |
| `image_border_width` | `1px` | 图片边框粗细。旧纸堆用宽边当衬纸 |

字体示例（注意用单引号，样式属性本身是双引号）：

```json
"body_font": "'Songti SC','STSong','SimSun',serif",
"heading_font": "'Songti SC','STSong','SimSun',serif"
```

某个布局未必把每个颜色都用上。字段仍然要求写全，这样以后只改 `layout` 不用补数据。

## 再加一种骨架

现有五种账号骨架都不够用时，在 `tools/layouts.py` 里加一个函数，并把它登记进 `SPECS` 和 `render_wechat.py` 的 `LAYOUTS`。JSON 只负责配色和刊头文字，骨架放在 Python 里，避免每篇文章各写一套 HTML。

公众号正文里只使用内联样式，标签用 `section`、`p`、`span`、`table`。不要外链字体和 CSS，不要 `<script>`，不要 `display:flex`、`display:grid`、`position:fixed`。这些限制对粘贴进编辑器的那一段生效；页面上的复制按钮可以有脚本，按钮本身不会被复制进去。
