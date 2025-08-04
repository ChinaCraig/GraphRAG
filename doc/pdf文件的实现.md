## 重要
项目的前置要求，参照：项目说明.md
## pdf类型的文件相关实现
1.所有内容都放在app/service/pdf目录下
2.在PdfExtractService.py这个文件中实现pdf文件内容的提取，使用Unstructured架构，该文件只有一个入口，入参为文件绝对路径，返参为json，例如：
```
[
  {
    "type": "text",
    "content": "本试验旨在探究药物A与药物B在不同剂量下的反应。",
    "embedding_model": "mpnet",
    "position": { "page": 1, "x": 50, "y": 100 }
  }
]
```
3.内容提取完以后，需要将这个json以当前的pdf文件名称命名，保存进/upload/json目录下
4.在PdfVectorService.py这个文件中实现对提取内容的向量化和保存，使用768纬向量模型paraphrase-multilingual-mpnet-base-v2，这个模型的下载脚本放在install目录下，只要执行这个脚本即可下载部署这个嵌入模型，该文件只有一个入口，入参为json字符串（上个步骤产生的结果），然后对该内容做向量化处理，并保存进向量数据库