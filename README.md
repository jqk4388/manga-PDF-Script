# manga-PDF-2-txt
**日文漫画PDF文字提取器** 通过字号字体过滤掉不需要的假名标注。有LP文本和普通文本两种导出模式。

    pip install pdfplumber

![日文漫画PDF文字提取器](img\QQ20250426-030756.png)

**PDF自动生成注释** 把PDF中的原文右上角添加注释，显示字体字号信息。

    pip install pdfplumber pymupdf

![PDF自动生成注释](img\QQ20250426-031013.png)

**PDF注释导出：** Acrobat导出PDF注释内容，加粗部分用【】括号包裹。

**PDF注释导出-info：** 导出基础上加上注释的作者和主题，配合自动生成注释脚本可以获取原文字体和字号信息。配合导入脚本&样式可以实现全自动嵌字。

## 安装方法

![安装方法](img\QQ20250426-031130.png)

1. Adobe Acrobat Pro
- 更多工具中找到指引式操作（旧版本叫动作向导）
- 管理自定义命令
- 导入XML命令文件
- 打开PDF文件，在动作向导工具中点击命令PDF注释导出LPtxt运行，弹出窗口保存LPtxt
2. Python
- Windows10以上版本，exe直接运行
- MAC系统，脚本运行需要配置Python环境，pip安装需要的库

    pip install PyMuPDF

- 运行后弹出窗口选择一个带注释的PDF，在PDF目录下导出同名TXT文件。
**注意：python不能获取注释中加粗的字，建议使用Acrobat Pro JS 脚本导出。**

**一键合并PDF** 批量合并PDF，自动排序。放在PDF文件夹下运行或者运行后选择PDF文件夹。

    pip install pypdf
