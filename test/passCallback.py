from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import hashlib
import json
import os

# 创建FastAPI应用
app = FastAPI(title="QQ机器人回调验证服务", version="1.0")

# QQ机器人AppSecret - 请在此处设置您的密钥
# 获取位置：QQ机器人管理后台 → 开发 → 开发设置 → AppSecret
BOT_SECRET = "Tfr3FRer4HUhu8Mao2GUjyDShwBRhxDT"  # 请将此值替换为您的实际AppSecret

@app.post("/")
async def qqbot_verification(request: Request):
    """
    QQ机器人回调验证接口
    仅处理验证请求(op=13)，不处理其他消息事件
    """
    
    # 检查AppSecret是否配置
    if not BOT_SECRET:
        raise HTTPException(
            status_code=500, 
            detail="BOT_SECRET未配置，请在代码中设置您的QQ机器人AppSecret"
        )
    
    try:
        # 获取并解析请求体
        body = await request.body()
        request_data = json.loads(body.decode("utf-8"))
        
        # 记录请求日志
        print(f"收到回调请求: {request_data}")
        
        # 检查是否为验证请求
        if request_data.get("op") != 13 or "d" not in request_data:
            print(f"非验证请求，忽略处理")
            return JSONResponse(content={"status": "ignored"})
        
        # 提取验证数据
        verification_data = request_data["d"]
        plain_token = verification_data.get("plain_token")
        event_ts = verification_data.get("event_ts")
        
        if not plain_token or not event_ts:
            raise ValueError("验证数据不完整，缺少plain_token或event_ts")
        
        # 生成签名
        signature = generate_ed25519_signature(event_ts, plain_token, BOT_SECRET)
        
        # 构造验证响应
        response = {
            "plain_token": plain_token,
            "signature": signature
        }
        
        print(f"验证响应: {response}")
        return JSONResponse(content=response)
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="请求体不是有效的JSON格式")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"验证失败: {str(ve)}")
    except Exception as e:
        print(f"处理验证请求时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

def generate_ed25519_signature(event_ts: str, plain_token: str, secret: str) -> str:
    """
    生成QQ机器人验证所需的Ed25519签名
    """
    try:
        
        seed = BOT_SECRET
        while len(seed) < 32:
            seed+= BOT_SECRET[2:]
        print(f"生成的种子: {seed}")
        # 使用派生的种子创建私钥并生成签名
        private_key = Ed25519PrivateKey.from_private_bytes(seed.encode('utf-8')[:32])
        message = f"{event_ts}{plain_token}".encode('utf-8')
        signature_bytes = private_key.sign(message)

        # 返回十六进制编码的签名
        return signature_bytes.hex()
        
    except Exception as e:
        raise ValueError(f"签名生成失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    # 配置服务
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "0.0.0.0")
    
    # 启动前检查
    if BOT_SECRET:
        print("=" * 60)
        print("QQ机器人回调验证服务")
        print("=" * 60)
        print(f"服务地址: http://{HOST}:{PORT}")
        print(f"验证接口: http://{HOST}:{PORT}/callback")
        print(f"健康检查: http://{HOST}:{PORT}/health")
        print(f"AppSecret已配置: {'是' if BOT_SECRET else '否'}")
        print("=" * 60)
    else:
        print("警告: BOT_SECRET未配置，请在代码中设置您的QQ机器人AppSecret")
        print(f"服务仍将启动，但无法通过验证")
    
    # 启动服务
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")