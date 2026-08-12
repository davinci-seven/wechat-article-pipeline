---
name: wechat-article-pipeline
description: 把定稿Markdown和本地配图生成公众号兼容内联HTML、图片内嵌稳定版、复制预览、390px手机长截图及完整性和隐私报告。适用于公众号文章定稿后的排版、检查和交付；不负责改稿，也不会在未经确认时创建公众号草稿。
---

# 公众号文章排版

把已经定稿的Markdown和本地配图交给本仓库现有脚本处理，输出可复制到公众号的HTML、手机预览和可核对的报告。

## 输入

- 一份定稿Markdown
- Markdown引用的全部本地图片
- 可选主题；未指定时使用`olive-journal`
- 可选输出目录；不得把产物写回或覆盖原稿

如果文章目录里有多份Markdown，先请用户明确指定。不得自行猜测哪份是定稿。

## 必守规则

- 不改正文，不改写、缩写、合并或重排任何段落。
- 不调整图片顺序和图注。
- 不覆盖原稿。运行前后计算原稿SHA256；不一致立即停止。
- 先检查全部本地图片。缺少任意一张，立即停止并列出缺失项，不继续生成残缺结果。
- 只有实际执行过且拿到结果的检查才能写“通过”。无法运行的检查标为“未运行”，并说明原因。
- HTML正文只扫描隐私，不自动改写。JSON、Markdown和日志可用现有清理脚本处理本机路径。
- 未经用户明确确认，不创建公众号草稿，不调用发布接口。
- 不调用`md2wechat convert`二次渲染已经生成的HTML。

## 执行

先定位仓库根目录、定稿Markdown和图片，再选择当前系统对应的入口。

### Windows

优先调用仓库现有的一键脚本：

```powershell
.\tools\公众号排版.ps1 -ArticleDir "F:\文章\我的文章" -Markdown "终稿.md" -OpenPreview
```

路径必须加引号。中文目录、空格和括号在不加引号时会被拆开，`<`和`>`在PowerShell里还是重定向符，直接写占位尖括号会报语法错误。

只有用户指定主题时才追加`-Theme moyu-green`（可选值用`-ListThemes`查看）。脚本失败后保留真实错误，不绕过图片、HTML或隐私检查。

该脚本已包含全部8个步骤，含长截图。未安装Playwright时第6步会告警并把`screenshot_status`标为“未运行”，其余步骤照常完成。

### 非Windows或ChatGPT代码执行环境

调用仓库现有脚本完成同一条流水线，不另写一套渲染器：

1. 计算原稿SHA256，并解析Markdown中的本地图片引用。
2. 确认图片全部存在；缺图立即停止。
3. 调用`tools/render_wechat.py`生成公众号兼容内联HTML、图片内嵌发布稳定版、390px手机截图页、图片证据表和完整性数据。
4. 使用已安装的gzh-design脚本校验组件和HTML，并用其`wrap_preview.py`生成带一键复制按钮的预览页。
5. 在390px视口实际打开手机截图页并分段截图，再调用`tools/stitch_screenshot.py`拼成长图。没有浏览器或截图能力时，把长截图标为“未运行”，不得用截图页代替并声称完成。
6. 再次计算原稿SHA256，确认原稿未变化。
7. 调用`tools/sanitize_public_output.py`生成隐私报告。HTML只扫描，不改写；报告里的警告需要人工判断。

完整命令如下。把`ARTICLE`、`LAYOUT`、`GZH`三个变量换成实际路径即可，其余原样执行：

```bash
ARTICLE="/path/to/我的文章"            # 文章目录
LAYOUT="$ARTICLE/公众号排版"            # 产物目录，不要写回原稿目录之外
GZH="$HOME/.codex/skills/gzh-design"   # 已安装的gzh-design

# 1. 渲染：正文HTML、发布稳定版、手机截图页、图片证据表、完整性数据
python tools/render_wechat.py \
  --markdown "$ARTICLE/终稿.md" \
  --output-root "$LAYOUT" \
  --theme olive-journal

# 渲染器按主题决定文件名，从报告里读，不要自己拼。
# 路径通过sys.argv传入，不要拼进Python字符串，否则Windows路径的反斜杠会被当转义符。
read_field() {
  python -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))[sys.argv[2]])" \
    "$LAYOUT/source-integrity.json" "$1"
}
CLEAN=$(read_field clean_html)
STABLE=$(read_field stable_html)
MOBILE=$(read_field mobile_screenshot_page)
PREVIEW="${STABLE/_发布稳定版.html/_预览.html}"

# 2. 组件与HTML校验，退出码非0即为不合规
python "$GZH/scripts/component_lint.py" "$GZH"
python "$GZH/scripts/validate_gzh_html.py" "$CLEAN"
python "$GZH/scripts/validate_gzh_html.py" "$STABLE"

# 3. 带一键复制按钮的预览页
python "$GZH/scripts/wrap_preview.py" "$STABLE" "$PREVIEW"

# 4. 390px手机端完整长截图（需要Playwright）
python tools/capture_mobile_screenshot.py \
  --page "$MOBILE" \
  --output "$LAYOUT/output/终稿_390px_手机长截图.png"

# 5. 清理本机路径并检查敏感信息
python tools/sanitize_public_output.py \
  --article-dir "$ARTICLE" \
  --layout-root "$LAYOUT"
```

第4步的退出码含义：`0`成功，`2`手机截图页不存在，`3`未安装Playwright，`4`浏览器执行失败。返回`3`时先尝试`pip install playwright && python -m playwright install chromium`；仍然不行就把长截图标为“未运行”，不得用手机截图页HTML冒充长截图。

`tools/stitch_screenshot.py`用于已经手动分段截好图、需要拼接的场合；走上面第4步时不需要它，脚本内部会自行处理超高页面的分段拼接。

后续校验、预览包装和截图必须依据当前环境中的实际脚本位置执行，不得伪造命令输出。

## 验收

至少核对并如实汇报：

- 公众号兼容内联HTML
- 图片内嵌的发布稳定版HTML
- 带一键复制按钮的预览页
- 390px手机端预览和完整长截图
- 图片证据表，且顺序、路径和图注与原稿一致
- 原稿运行前后SHA256及`source_unchanged`结果
- HTML校验的实际结果
- `privacy-audit.json`中的错误和警告
- 未运行的检查及原因
- ChatGPT环境中的轻量Preview和完整一键复制HTML是否都已交付，并且身份标注清楚

任何必需检查失败时，不把整套任务写成“已完成”。先返回失败位置、真实输出和可执行的下一步。

## ChatGPT双交付

当执行环境是ChatGPT，并且已经生成带“一键复制到公众号”按钮的完整预览HTML时，最终必须同时交付以下两份HTML，不能互相替代。

### ChatGPT截图预览

在最终回复中额外提供一个HTML代码块，供ChatGPT直接切换Preview、小窗或全屏查看和截图。

- 输出完整可运行的HTML文档，包括`<!doctype html>`、顶部工具栏、预览容器和复制按钮。
- 视觉主题与正式预览保持一致，至少展示标题、开头正文和代表性内容。
- 为控制回复体积，可以只保留代表性图片、缩略图或少量内容；不要把数MB的data URI塞进聊天回复。
- 在页面工具栏和回复说明中明确标记“轻量预览，非全文”。复制按钮也要提示复制的是预览片段，不能让用户误以为已经复制完整文章。
- 不得把这份轻量HTML记作完整文章、发布稳定版或公众号终审文件。
- 如果当前客户端没有HTML Preview入口，仍保留这份代码块，并以完整HTML附件作为可用回退。

### 公众号一键复制HTML

同时提供可下载的完整预览HTML，作为真实复制到公众号编辑器和发布前终审的唯一来源。

- 保留全部正文、图片顺序、alt文本和图注。
- 使用已经校验的发布稳定版正文；图片优先内嵌为data URI，避免依赖本地路径。
- 保留顶部工具栏和“一键复制到公众号”按钮，按钮只复制完整正文容器，不复制工具栏或提示文字。
- 不得为了生成轻量Preview而删减或覆盖这份完整HTML。
- 没有实际测试复制按钮时，标为“未测试”，不能声称复制成功。

最终回复必须用这两个固定名称区分产物：

- `ChatGPT截图预览`：聊天内轻量Preview，用于查看和截图，不是全文。
- `公众号一键复制HTML`：完整文章，用于真实复制和发布前终审。

不要因为已经提供完整HTML下载附件，就省略ChatGPT环境中的轻量Preview代码块；也不要只给轻量Preview而漏掉完整HTML附件。

## 发布边界

默认只生成本地文件，不登录公众号、不上传素材、不创建草稿。只有用户在看到本次产物后明确要求创建公众号草稿，才进入单独的发布步骤；即使进入发布步骤，也直接使用已生成HTML，不调用`md2wechat convert`。

安装方法见[docs/skill-install.md](docs/skill-install.md)，日常参数和输出说明见[README.md](README.md)。
