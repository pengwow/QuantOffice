# deploy/

直接拷贝即用的 nginx / supervisor 部署文件。

## 目录

| 子目录        | 用途                                                |
| ------------- | --------------------------------------------------- |
| `nginx/`      | 反向代理 + 静态前端（监听 80，转发 8765）           |
| `supervisor/` | 后端 uvicorn **+ 前端 Vite dev** 进程托管           |

| 文件                                        | 角色                                          |
| ------------------------------------------- | --------------------------------------------- |
| `supervisor/quantoffice.conf`               | 后端 uvicorn（监听 127.0.0.1:8765）           |
| `supervisor/quantoffice-frontend.conf`      | 前端 Vite dev（监听 0.0.0.0:5173，可选）      |
| `nginx/quantoffice.conf`                    | 反代 + 静态文件 / dev 模式反代 Vite           |

## 一次性部署（生产模式：nginx serve 静态前端）

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
| `/var/log/supervisor/quantoffice-frontend.out.log` | Vite dev stdout      |
| `/var/log/supervisor/quantoffice-frontend.err.log` | Vite dev stderr      |

## 进程管理

```bash
sudo supervisorctl status                           # 全部状态
sudo supervisorctl restart quantoffice              # 重启后端
sudo supervisorctl restart quantoffice-frontend     # 重启前端 dev
sudo supervisorctl tail -f quantoffice              # 后端日志
sudo supervisorctl tail -f quantoffice-frontend     # 前端日志
```

## Dev 模式（Vite HMR 热重载）

适合改前端代码要即时看效果，或者 1H1G 机器跑不动 `bun run build`。

```bash
# 1. 装一次（拿到 node_modules，不构建）
cd /workspace/frontend && bun install
cd /workspace

# 2. 启前端 dev（supervisor 托管，崩溃自愈）
sudo cp deploy/supervisor/quantoffice-frontend.conf \
        /etc/supervisor/conf.d/
sudo supervisorctl reread && sudo supervisorctl update
sudo supervisorctl start quantoffice-frontend

# 3. 让 nginx 把 / 反代到 Vite（关键！覆盖掉原来的 try_files 静态文件）
#    编辑 /etc/nginx/conf.d/quantoffice.conf，把 location / 块替换为：
#
#    location / {
#        proxy_pass http://127.0.0.1:5173;
#        proxy_http_version 1.1;
#        proxy_set_header Host              $host;
#        proxy_set_header X-Real-IP         $remote_addr;
#        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
#        proxy_set_header X-Forwarded-Proto $scheme;
#    }
#
sudo nginx -t && sudo systemctl reload nginx
```

dev 模式下，`/api` 和 `/ws` 由 Vite 自己代理到后端 8765（见 `vite.config.ts`），不经过 nginx。

## 和 `./deploy.sh` 互斥

`./deploy.sh start` 用 PID 文件管后端；supervisor 接管后两者会冲突，**只用一个**。
建议：

- **裸机 / VM（生产）** → `supervisor quantoffice.conf` + `nginx`（本文档）
- **裸机 / VM（改前端）** → 加 `supervisor quantoffice-frontend.conf`，nginx `/` 改 proxy
- **临时本地 / 调试** → `./deploy.sh all`（一键起）
- **容器化** → `docker/Dockerfile`（已有）
