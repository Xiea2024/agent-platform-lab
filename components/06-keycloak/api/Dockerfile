FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
# 宿主网络对 pypi.org 不可达，使用镜像站（D-10/D-12 网络约束）
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
COPY main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
