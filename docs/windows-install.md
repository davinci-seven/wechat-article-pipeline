# Windows安装

## 1. 准备基础环境

需要：

- Windows 10或Windows 11
- Python 3.10+
- PowerShell 5.1或PowerShell 7
- Git

先确认命令可用：

```powershell
python --version
git --version
$PSVersionTable.PSVersion
```

## 2. 安装Python依赖

在仓库根目录运行：

```powershell
pip install -r requirements.txt
```

Pillow用于图片处理，Playwright用于生成390px手机端长截图。

Playwright还需要下载一次浏览器内核：

```powershell
python -m playwright install chromium
```

不装Playwright也能跑完整条流水线，只是长截图那一步会告警并标记为“未运行”。

## 3. 安装gzh-design

本流程会调用gzh-design提供的HTML校验、组件检查和复制预览脚本，默认从这里读取：

```text
%USERPROFILE%\.codex\skills\gzh-design\
```

安装命令：

```powershell
git clone https://github.com/isjiamu/gzh-design-skill "$env:USERPROFILE\.codex\skills\gzh-design"
```

安装后确认下面3个文件存在：

```text
%USERPROFILE%\.codex\skills\gzh-design\scripts\validate_gzh_html.py
%USERPROFILE%\.codex\skills\gzh-design\scripts\component_lint.py
%USERPROFILE%\.codex\skills\gzh-design\scripts\wrap_preview.py
```

Windows环境不要运行仓库里仅适用于macOS的`install.command`。

gzh-design在这套流程里负责什么，见[致谢与项目边界](credits.md)。

## 4. 跑一次示例

```powershell
.\tools\公众号排版.ps1 -ArticleDir .\examples\demo-article -OpenPreview
```

正常情况下会看到8个步骤依次完成，并打开手机端预览页。

输出目录位于：

```text
examples\demo-article\公众号排版\
```

## 5. 可选：安装md2wechat

只有需要上传公众号素材或创建草稿时才需要安装：

```powershell
npm install -g @geekjourneyx/md2wechat
md2wechat doctor --json
```

不要把公众号AppID、AppSecret或其他凭据写进仓库。只放在本地环境变量或安全配置中。

## 常见问题

### 未找到唯一Markdown

文章目录里有多个`.md`文件。

把定稿命名为`终稿.md`，或者通过`-Markdown`指定：

```powershell
.\tools\公众号排版.ps1 -ArticleDir .\我的文章 -Markdown 文章终稿.md
```

### 缺少必需文件

通常是gzh-design没有安装，或者实际目录和默认路径不一致。回到第3步检查3个脚本是否存在。

### 原始Markdown内容发生变化

完整性检查发现排版前后的文件哈希不一致。先确认是否有编辑器、同步软件或其他脚本在运行期间改动了原稿，再重新执行。

### 长截图未生成

第6步会打印退出码：`3`是没装Playwright，`4`是浏览器执行失败。

```powershell
pip install playwright
python -m playwright install chromium
```

详细输出见`公众号排版alidation\screenshot.txt`。这一步失败不会中断流水线，其余产物照常生成。

### 隐私检查失败

生成目录里发现未清理的绝对路径、Token、私钥或其他高风险内容。查看：

```text
公众号排版\privacy-audit.json
```

清理后再公开或提交到GitHub。
