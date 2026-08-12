[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$ArticleDir = (Get-Location).Path,
    [string]$Markdown = "",
    [ValidateSet("olive-journal", "moyu-green", "red-white", "graphite-minimal", "zen-whitespace", "moyu-ticket")]
    [string]$Theme = "olive-journal",
    [string]$SectionLabels = "",
    [switch]$ListThemes,
    [switch]$OpenPreview
)

$ErrorActionPreference = "Stop"
$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$renderer = Join-Path $toolDir "render_wechat.py"
$sanitizer = Join-Path $toolDir "sanitize_public_output.py"
$capturer = Join-Path $toolDir "capture_mobile_screenshot.py"
$gzhSkill = Join-Path $env:USERPROFILE ".codex\skills\gzh-design"
$validator = Join-Path $gzhSkill "scripts\validate_gzh_html.py"
$componentLint = Join-Path $gzhSkill "scripts\component_lint.py"
$previewWrapper = Join-Path $gzhSkill "scripts\wrap_preview.py"
$python = (Get-Command python -ErrorAction Stop).Source

function Write-StepLog {
    # Tee-Object 在 Windows PowerShell 5.1 下默认写 UTF-16LE，
    # 会让后续的隐私清理读成乱码、漏掉本机绝对路径，所以显式写 UTF-8。
    param([Parameter(ValueFromPipeline = $true)]$InputObject, [string]$Path)
    begin { $collected = New-Object System.Collections.ArrayList }
    process { [void]$collected.Add($InputObject) }
    end {
        ($collected | Out-String) | Set-Content -LiteralPath $Path -Encoding UTF8
        $collected
    }
}


if ($ListThemes) {
    & $python $renderer --list-themes
    exit $LASTEXITCODE
}

$articlePath = (Resolve-Path -LiteralPath $ArticleDir).Path
if ([string]::IsNullOrWhiteSpace($Markdown)) {
    $preferred = Join-Path $articlePath "终稿.md"
    if (Test-Path -LiteralPath $preferred) {
        $markdownPath = $preferred
    } else {
        $candidates = @(Get-ChildItem -LiteralPath $articlePath -Filter "*.md" -File |
            Where-Object { $_.Name -notin @("排版任务卡.md", "图片证据表.md", "手机端结构脚本.md") })
        if ($candidates.Count -ne 1) {
            throw "未找到唯一Markdown。请用-Markdown指定文件。"
        }
        $markdownPath = $candidates[0].FullName
    }
} else {
    $markdownPath = if ([IO.Path]::IsPathRooted($Markdown)) {
        (Resolve-Path -LiteralPath $Markdown).Path
    } else {
        (Resolve-Path -LiteralPath (Join-Path $articlePath $Markdown)).Path
    }
}

foreach ($required in @($renderer, $sanitizer, $capturer, $validator, $componentLint, $previewWrapper)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "缺少必需文件：$required"
    }
}

$sourceHashBefore = (Get-FileHash -LiteralPath $markdownPath -Algorithm SHA256).Hash
$layoutRoot = Join-Path $articlePath "公众号排版"
$outputDir = Join-Path $layoutRoot "output"
$logDir = Join-Path $layoutRoot "validation"
New-Item -ItemType Directory -Force -Path $layoutRoot, $outputDir, $logDir | Out-Null

Write-Host "[1/8] 检查图片并生成正文HTML（主题：$Theme）..."
$renderArgs = @("--markdown", $markdownPath, "--output-root", $layoutRoot, "--theme", $Theme)
if (-not [string]::IsNullOrWhiteSpace($SectionLabels)) {
    $renderArgs += @("--section-labels", $SectionLabels)
}
& $python $renderer @renderArgs
if ($LASTEXITCODE -ne 0) { throw "Markdown排版失败，退出码$LASTEXITCODE" }

# 文件名由渲染器按主题决定，这里直接读取完整性报告。
$integrity = Get-Content -LiteralPath (Join-Path $layoutRoot "source-integrity.json") -Raw -Encoding UTF8 |
    ConvertFrom-Json
$cleanHtml = $integrity.clean_html
$stableHtml = $integrity.stable_html
$mobilePage = $integrity.mobile_screenshot_page
$previewHtml = [IO.Path]::Combine(
    $outputDir,
    [IO.Path]::GetFileNameWithoutExtension($stableHtml).Replace("_发布稳定版", "") + "_预览.html"
)

Write-Host "[2/8] 检查主题组件..."
& $python $componentLint $gzhSkill 2>&1 |
    Write-StepLog -Path (Join-Path $logDir "component-lint.txt")
if ($LASTEXITCODE -ne 0) { throw "主题组件校验存在ERROR" }

Write-Host "[3/8] 校验干净正文HTML..."
& $python $validator $cleanHtml 2>&1 |
    Write-StepLog -Path (Join-Path $logDir "clean-html-validation.txt")
if ($LASTEXITCODE -ne 0) { throw "干净正文HTML校验存在ERROR" }

Write-Host "[4/8] 校验发布稳定版HTML..."
& $python $validator $stableHtml 2>&1 |
    Write-StepLog -Path (Join-Path $logDir "stable-html-validation.txt")
if ($LASTEXITCODE -ne 0) { throw "发布稳定版HTML校验存在ERROR" }

Write-Host "[5/8] 生成带复制按钮的预览页..."
& $python $previewWrapper $stableHtml $previewHtml
if ($LASTEXITCODE -ne 0) { throw "预览页生成失败" }

Write-Host "[6/8] 生成390px手机端完整长截图..."
$screenshotPath = Join-Path $outputDir "$([IO.Path]::GetFileNameWithoutExtension($markdownPath))_390px_手机长截图.png"
# 截图依赖Playwright，属于可选能力：装了就真截，没装就如实标"未运行"，
# 但不能因此让整条流水线失败，也不能拿截图页冒充长截图。
# $ErrorActionPreference=Stop 会把原生命令写到stderr的提示也当成终止性错误，
# 这一步允许失败，所以先临时放开，拿到退出码再恢复。
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $python $capturer --page $mobilePage --output $screenshotPath 2>&1 |
    Write-StepLog -Path (Join-Path $logDir "screenshot.txt")
$screenshotExit = $LASTEXITCODE
$ErrorActionPreference = $previousErrorAction
$screenshotGenerated = ($screenshotExit -eq 0) -and (Test-Path -LiteralPath $screenshotPath)
if (-not $screenshotGenerated) {
    Write-Warning "长截图未生成（退出码$screenshotExit），结果中标记为「未运行」。安装方法：pip install playwright; python -m playwright install chromium"
}

Write-Host "[7/8] 确认原始Markdown未被覆盖..."
$sourceHashAfter = (Get-FileHash -LiteralPath $markdownPath -Algorithm SHA256).Hash
if ($sourceHashBefore -ne $sourceHashAfter) {
    throw "安全检查失败：原始Markdown内容发生变化。"
}

$summary = [ordered]@{
    ok = $true
    markdown = [IO.Path]::GetFileName($markdownPath)
    theme = $Theme
    source_unchanged = $true
    clean_html = "output\$([IO.Path]::GetFileName($cleanHtml))"
    stable_html = "output\$([IO.Path]::GetFileName($stableHtml))"
    preview_html = "output\$([IO.Path]::GetFileName($previewHtml))"
    mobile_screenshot_page = "output\$([IO.Path]::GetFileName($mobilePage))"
    screenshot = if ($screenshotGenerated) { "output\$([IO.Path]::GetFileName($screenshotPath))" } else { $null }
    screenshot_status = if ($screenshotGenerated) { "已生成" } else { "未运行" }
    published = $false
}
$summary | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path $layoutRoot "workflow-result.json") -Encoding UTF8

Write-Host "[8/8] 清理本机路径并检查敏感信息..."
& $python $sanitizer --article-dir $articlePath --layout-root $layoutRoot
if ($LASTEXITCODE -ne 0) { throw "隐私检查未通过，请查看privacy-audit.json" }

$summary | ConvertTo-Json -Depth 4

if ($OpenPreview) {
    Start-Process -FilePath $mobilePage
}
