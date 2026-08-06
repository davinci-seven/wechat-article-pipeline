# 安装成Skill

安装后，可以把定稿Markdown和配图交给Codex或其他支持本地Skill的代码执行环境，让它按仓库里的固定规则完成排版、预览、截图和检查。

## 装到Codex

需要先有Git和Python 3.10+。Windows还需要PowerShell 5.1或PowerShell 7。

在终端运行：

```bash
git clone https://github.com/davinci-seven/wechat-article-pipeline.git ~/.codex/skills/wechat-article-pipeline
```

如果这个目录已经存在，用下面的命令更新：

```bash
git -C ~/.codex/skills/wechat-article-pipeline pull --ff-only
```

重启Codex或新开一个会话，让它重新读取Skill。

Windows PowerShell也可以安装到Codex默认目录：

```powershell
git clone https://github.com/davinci-seven/wechat-article-pipeline.git "$env:USERPROFILE\.codex\skills\wechat-article-pipeline"
```

## 依赖

安装Python依赖：

```bash
python -m pip install Pillow
```

这套流水线还会调用gzh-design提供的HTML校验、组件检查和复制预览包装脚本。按[gzh-design仓库](https://github.com/isjiamu/gzh-design-skill)的说明，把它安装为`gzh-design`Skill。

Windows一键入口会从`%USERPROFILE%\.codex\skills\gzh-design`读取这些脚本：

- `scripts/validate_gzh_html.py`
- `scripts/component_lint.py`
- `scripts/wrap_preview.py`

非Windows或ChatGPT代码执行环境可以按实际安装位置调用相同脚本，不要为了省一步跳过校验。

## 怎么叫它干活

把定稿Markdown和所有本地配图放在同一个文章目录中，然后说：

```text
使用wechat-article-pipeline处理这份定稿Markdown和配图。
正文、图片顺序和图注都不要改。生成公众号内联HTML、图片内嵌稳定版、复制预览、390px长截图以及完整性和隐私报告。
```

也可以补充主题，例如：

```text
使用red-white主题。
```

Windows环境会优先执行`tools/公众号排版.ps1`。非Windows或ChatGPT代码执行环境会调用`tools/render_wechat.py`、`tools/stitch_screenshot.py`、`tools/sanitize_public_output.py`和现有校验脚本完成相同步骤。

## 第一次验收

可以先用仓库自带示例确认环境：

```powershell
.\tools\公众号排版.ps1 -ArticleDir .\examples\demo-article -OpenPreview
```

完成后检查`examples/demo-article/公众号排版`。应该能看到正文HTML、发布稳定版、复制预览页、手机截图页、图片证据表、`source-integrity.json`、`workflow-result.json`和`privacy-audit.json`。

390px完整长截图需要实际浏览器截图。只生成手机截图页，不等于已经生成长截图。

## 这套Skill不会做什么

- 不改正文
- 不调整图片顺序和图注
- 不覆盖原稿
- 缺图时不继续
- 没运行的检查不声称通过
- HTML正文只扫描隐私，不自动改写
- 未经明确确认不创建公众号草稿
- 不调用`md2wechat convert`二次渲染

这些规则写在仓库根目录的`SKILL.md`里。修改Skill时，不要删掉或弱化它们。
