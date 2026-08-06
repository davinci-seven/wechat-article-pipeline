# 致谢与项目边界

这套工作流建立在三个公开项目之上。

本仓库没有重新实现它们的核心能力，而是把这些能力接成一条适合Windows日常使用的文章排版流程，并补充原稿完整性、图片检查和手机端QA。

## gzh-design

作者：[@isjiamu](https://github.com/isjiamu)  
项目：<https://github.com/isjiamu/gzh-design-skill>

gzh-design提供了公众号兼容HTML的基础能力，包括内联样式组件、公众号限制检查和一键复制预览。

本项目会调用：

- `scripts/validate_gzh_html.py`
- `scripts/component_lint.py`
- `scripts/wrap_preview.py`

本仓库的六套主题配色和排印参数也参考了gzh-design各主题的设计变量。这里实现的是统一文章结构下的参数化主题切换，不包含gzh-design每套主题的全部专属组件。

## xiaowan-wechat-layout

作者：[@cyberxiaowan](https://github.com/cyberxiaowan)  
项目：<https://github.com/cyberxiaowan/xiaowan-wechat-layout-skill>

本项目的手机端结构检查、图片证据表和排版检查思路参考了该项目。

生成的`手机端结构脚本.md`和`图片证据表.md`，用于在排版完成后检查文章结构、图片顺序和移动端阅读效果。

## md2wechat

作者：[@geekjourneyx](https://github.com/geekjourneyx)  
项目：<https://github.com/geekjourneyx/md2wechat-skill>

md2wechat提供公众号素材上传和草稿创建能力。

本项目不会调用`md2wechat convert`重新渲染已经排好的HTML。需要发布时，只应使用其图片上传和草稿接口，并且必须由用户明确确认。

## 本仓库增加的部分

本项目主要补充了：

- Windows PowerShell一键脚本
- BAT拖拽入口
- Markdown渲染和多主题参数
- 原稿SHA256校验
- 正文顺序完整性检查
- 图片路径检查、图片证据表和图片映射
- 图片内嵌的发布稳定版HTML
- 390px手机端预览和长截图拼接
- “不覆盖、不自动发布、不二次渲染”的安全边界

简单说，基础项目提供关键能力，这个仓库负责把它们组织成一条可以反复使用的Windows工作流。

## 许可说明

本仓库自有代码采用MIT License。

gzh-design、xiaowan-wechat-layout和md2wechat的许可证及使用范围，以各自仓库当前说明为准。本仓库仅通过安装和调用方式使用它们，不复制或重新分发其完整源码。

对引用方式或项目边界有疑问，可以直接提交issue。
