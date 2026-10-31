# V12外部运行依赖

V12已经内聚项目内源码依赖，但不会复制第三方包、环境、凭据或ALFWorld数据。

必需的直接第三方Python包为：

- `openai`：Qwen/DeepSeek的OpenAI兼容客户端；
- `alfworld`：文本环境与任务类型；
- `langgraph`：Client A的Planner→Executor状态机。

ALFWorld还会带入TextWorld等传递依赖。不要根据本机Windows诊断环境猜测正式版本；正式运行前应从原V10使用的WSL `stage3-alfworld`环境导出锁文件，并在V12 preflight中记录Python与包版本。当前Windows `.venv-stage3-alfworld`可运行离线协议测试，但并未安装完整`alfworld`和`langgraph`，不能据此启动正式任务。

运行时还必须显式提供：

- `--data-root`指向现有ALFWorld数据；
- DashScope任务执行凭据；
- DeepSeek官方Teacher/聚合凭据；
- V12之外的全新输出目录或`stage2_local_v12/runs/`下的新运行目录。

凭据不得写入本目录、日志、来源清单或Git。
