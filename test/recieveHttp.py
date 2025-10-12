from fastapi import FastAPI, Request
from datetime import datetime
import os
from pathlib import Path

# 创建 FastAPI 应用实例
app = FastAPI()

# 确保存储请求日志的目录存在
LOG_DIR = Path(__file__).parent / "request_logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
)
async def log_all_requests(request: Request, path: str):
    """捕获所有路径和方法的请求，并将请求信息写入文件"""

    # 生成当前日期时间作为文件名（精确到微秒，确保唯一性）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = LOG_DIR / f"{timestamp}.json"

    # 收集请求信息
    # request_data = {
    #     "timestamp": datetime.now().isoformat(),
    #     "method": request.method,
    #     "path": f"/{path}",
    #     "query_parameters": dict(request.query_params),
    #     "headers": dict(request.headers),
    #     "client": f"{request.client.host}:{request.client.port}" if request.client else "unknown"
    # }

    # # 尝试获取请求体（对于有请求体的方法）
    # try:
    #     if request.method in ["POST", "PUT", "PATCH"]:
    #         body = await request.body()
    #         request_data["body"] = body.decode("utf-8", errors="replace")
    # except Exception as e:
    #     request_data["body_error"] = f"无法获取请求体: {str(e)}"

    # 将请求信息写入文件
    with open(filename, "w", encoding="utf-8") as f:
        f.write((await request.body()).decode("utf-8", errors="replace"))

    return {"message": f"请求已记录到文件: {filename}"}


if __name__ == "__main__":
    import uvicorn

    # 启动服务器，监听 8000 端口，允许来自任何 IP 的连接
    uvicorn.run(app, host="0.0.0.0", port=8000)
