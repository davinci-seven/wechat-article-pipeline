# 公开前脱敏检查

公众号文章本身可能没有隐私问题，但排版报告、终端截图和示例输出经常会顺手带出本机信息。

这套工作流会自动清理JSON、Markdown和日志中的常见绝对路径，并输出`privacy-audit.json`。HTML只扫描、不改写正文；公开到GitHub前，仍建议手动看一遍下面这些位置。

## 重点检查

- Windows路径：`C:\Users\用户名\...`、`F:\项目目录\...`
- macOS和Linux用户目录：`/Users/用户名/...`、`/home/用户名/...`
- 邮箱、手机号、家庭地址
- GitHub Token、OpenAI Key、公众号AppSecret
- SSH私钥、证书、`.env`、`config.json`
- 电脑序列号、UUID、资产编号
- 截图里的真实用户名、主机名、IP、浏览器标签页和通知
- 发布稳定版HTML中的Base64图片内容

## 自动检查结果

每次运行后查看：

```text
公众号排版\privacy-audit.json
```

其中：

- `errors`：高风险内容，公开前必须处理
- `warnings`：可能是示例数据，也可能是真实信息，需要人工判断
- `changed_files`：本次自动替换过本机路径的报告文件

## 提交GitHub前

```powershell
git status
git diff --cached
```

不要只看文件名。尤其要打开JSON、日志、HTML和截图确认一次。

仓库的`.gitignore`会拦住常见密钥文件，但已经被Git跟踪过的文件不会因为后来加入忽略规则而自动消失。
