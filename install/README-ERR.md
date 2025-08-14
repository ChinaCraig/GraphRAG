当直接执行下载脚本报错时，需要调整镜像源

```
下载paraphrase-MiniLM-L6-v2+2.7.0模型可使用这个命令
eg：
cd /Users/craig-macmini/Documents/my_workspace/py_workspace/GraphRAG/install && export HF_ENDPOINT=https://hf-mirror.com && export HUGGINGFACE_HUB_DEFAULT_ENDPOINT=https://hf-mirror.com && export HF_HUB_DISABLE_PROGRESS_BARS=false && ./paraphrase-MiniLM-L6-v2+2.7.0.sh
```

```
下载paraphrase-multilingual-mpnet-base-v2+2.7.0模型可使用这个命令
eg：
cd /Users/craig-macmini/Documents/my_workspace/py_workspace/GraphRAG/install && export HF_ENDPOINT=https://hf-mirror.com && export HUGGINGFACE_HUB_DEFAULT_ENDPOINT=https://hf-mirror.com && export HF_HUB_DISABLE_PROGRESS_BARS=false && ./paraphrase-multilingual-mpnet-base-v2+2.7.0.sh
```