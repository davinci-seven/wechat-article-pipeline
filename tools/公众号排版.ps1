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
$gzhSkill = Join-Path $env:USERPROFILE ".codex\skills\gzh-design"
$validator = Join-Path $gzhSkill "scripts\validate_gzh_html.py"
$componentLint = Join-Path $gzhSkill "scripts\component_lint.py"
$previewWrapper = Join-Path $gzhSkill "scripts\wrap_preview.py"
$python = (Get-Command python -ErrorAction Stop).Source

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

foreach ($required in @($renderer, $sanitizer, $validator, $componentLint, $previewWrapper)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "缺少必需文件：$required"
    }
}

$sourceHashBefore = (Get-FileHash -LiteralPath $markdownPath -Algorithm SHA256).Hash
$layoutRoot = Join-Path $articlePath "公众号排版"
$outputDir = Join-Path $layoutRoot "output"
$logDir = Join-Path $layoutRoot "validation"
New-Item -ItemType Directory -Force -Path $layoutRoot, $outputDir, $logDir | Out-Null

Write-Host "[1/7] 检查图片并生成正文HTML（主题：$Theme）..."
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

Write-Host "[2/7] 检查主题组件..."
& $python $componentLint $gzhSkill 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir "component-lint.txt")
if ($LASTEXITCODE -ne 0) { throw "主题组件校验存在ERROR" }

Write-Host "[3/7] 校验干净正文HTML..."
& $python $validator $cleanHtml 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir "clean-html-validation.txt")
if ($LASTEXITCODE -ne 0) { throw "干净正文HTML校验存在ERROR" }

Write-Host "[4/7] 校验发布稳定版HTML..."
& $python $validator $stableHtml 2>&1 |
    Tee-Object -FilePath (Join-Path $logDir "stable-html-validation.txt")
if ($LASTEXITCODE -ne 0) { throw "发布稳定版HTML校验存在ERROR" }

Write-Host "[5/7] 生成带复制按钮的预览页..."
& $python $previewWrapper $stableHtml $previewHtml
if ($LASTEXITCODE -ne 0) { throw "预览页生成失败" }

Write-Host "[6/7] 确认原始Markdown未被覆盖..."
$sourceHashAfter = (Get-FileHash -LiteralPath $markdownPath -Algorithm SHA256).Hash
if ($sourceHashBefore -ne $sourceHashAfter) {
    throw "安全检查失败：原始Markdown内容发生变化。"
}

$screenshotPath = Join-Path $outputDir "$([IO.Path]::GetFileNameWithoutExtension($markdownPath))_390px_手机长截图.png"
$screenshotGenerated = Test-Path -LiteralPath $screenshotPath

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

Write-Host "[7/7] 清理本机路径并检查敏感信息..."
& $python $sanitizer --article-dir $articlePath --layout-root $layoutRoot
if ($LASTEXITCODE -ne 0) { throw "隐私检查未通过，请查看privacy-audit.json" }

$summary | ConvertTo-Json -Depth 4

if ($OpenPreview) {
    Start-Process -FilePath $mobilePage
}
