# deploy/

直接拷贝即用的 nginx / supervisor 部署文件。

## 目录

| 子目录        | 用途                                       |
| ------------- | ------------------------------------------ |
| `nginx/`      | 反向代理 + 静态前端（监听 80，转发 8765）  |
| `supervisor/` | 后端 uvicorn 进程托管                       |

## 一次性部署（root 权限）

```bash
# 0. 准备项目（必须先跑过 uv sync，前端 dist 必须存在）
./deploy.sh install

# 1. nginx
sudo cp deploy/nginx/quantoffice.conf   /etc/nginx/conf.d/quantoffice.conf
sudo nginx -t && sudo systemctl reload nginx

# 2. supervisor
sudo mkdir -p /var/log/supervisor
sudo cp deploy/supervisor/quantoffice.conf /etc/supervisor/conf.d/quantoffice.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start quantoffice

# 3. 验证
curl http://127.0.0.1/healthz        # 后端健康检查
curl http://127.0.0.1/                # 前端 SPA 入口
sudo supervisorctl status quantoffice
```

## 端口约定

| 服务     | 监听地址            | 暴露方式                  |
| -------- | ------------------- | ------------------------- |
| 后端     | `127.0.0.1:8765`    | **不**对外，nginx 转 `80` |
| 前端     | `/workspace/frontend/dist` | nginx 直接 serve    |
| nginx    | `:80`               | 对外                      |

## 改域名 / 上 HTTPS

编辑 `deploy/nginx/quantoffice.conf`：

- `server_name _;` → `server_name api.example.com;`
- 加一段 `server { listen 443 ssl; ... }`（或用 certbot `--nginx` 自动签）

改后端监听地址：同步改 `deploy/nginx/quantoffice.conf` 里的 `upstream` 块和 `deploy/supervisor/quantoffice.conf` 里的 `--port` / `--host`。

## 日志位置

| 文件                                            | 内容                     |
| ----------------------------------------------- | ------------------------ |
| `/var/log/nginx/quantoffice.access.log`         | nginx 访问日志           |
| `/var/log/nginx/quantoffice.error.log`          | nginx 错误日志           |
| `/var/log/supervisor/quantoffice.out.log`       | uvicorn stdout           |
| `/var/log/supervisor/quantoffice.err.log`       | uvicorn stderr / 异常    |

## 进程管理

```bash
sudo supervisorctl status quantoffice     # 状态
sudo supervisorctl restart quantoffice    # 重启
sudo supervisorctl tail -f quantoffice    # 实时日志
sudo supervisorctl stop quantoffice       # 停止
```

## 和 `./deploy.sh` 互斥

`./deploy.sh start` 用 PID 文件管后端；supervisor 接管后两者会冲突，**只用一个**。
建议：

- **裸机 / VM** → `supervisor` + `nginx`（本文档）
- **临时本地 / 调试** → `./deploy.sh all`（一键起）
- **容器化** → `docker/Dockerfile`（已有）
