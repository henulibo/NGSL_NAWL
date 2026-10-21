# 部署与本地运行

文档统一使用示例域名 `study.example.com`。项目不提供公共服务、可用账号或默认密码。

## Docker Compose 部署

需要 Docker Engine、Compose 和有 HTTPS 域名的服务器。把域名指向服务器，放行 TCP 80 / 443；如使用 HTTP/3，也可自行配置 UDP 443。`deploy/install-docker.sh` 仅供 Ubuntu 使用，运行前先检查脚本。

```sh
cp .env.example .env
```

编辑 `.env`：`SITE_ADDRESS` 为自己的域名，`APP_ORIGIN` 为对应的 HTTPS 来源，不带末尾斜杠。镜像名和依赖版本可按部署环境调整；正式使用时应固定已验证的镜像标签或摘要。

```sh
docker compose config --quiet
docker compose up -d --build --wait
```

Dockerfile 自动构建离线 HTML、服务器页面并安装 `server/requirements.txt` 中锁定的依赖。首次构建需要访问 Python 镜像仓库和 PyPI，不再要求下载离线 wheel。仅 app 与 edge 之间开放 8000，宿主机通过 Caddy 的 80 / 443 对外提供服务。Caddy 自动申请和续期域名证书，需持久保存其数据卷。

### 初始化管理员

以下命令在 Bash 中执行，密码 12–128 字符，经标准输入传入容器，不写进命令参数或仓库：

```bash
read -r -s -p 'Initial admin password (12–128 characters): ' ADMIN_PASSWORD
printf '\n'
printf '%s' "$ADMIN_PASSWORD" | docker compose exec -T app \
  python -m server.manage create-admin --username admin --password-stdin
unset ADMIN_PASSWORD
```

打开自己的 HTTPS 域名登录，在「我的账号」创建学习账号、停用账号或重置密码。用户可修改自己的密码。修改或重置密码、停用账号会撤销原登录。

### 数据、备份和恢复

Compose 项目名保留为 `ielts`；账号、会话和学习进度在 `ielts_study_data`，Caddy 状态在 `ielts_caddy_data` 与 `ielts_caddy_config`。已有部署更新时应保持项目名和卷不变。

```sh
docker compose ps
docker compose logs --tail=100 app edge
sh deploy/backup.sh
```

备份通过 SQLite 在线 API 生成，保存于项目忽略目录 `backups/`，并在卷内 `/data/backups/` 留存。包含用户账号散列、会话和进度，应限制权限、另存到服务器之外，不可上传公开仓库。长期运行时应自行安排备份周期和保留策略。

更新前备份数据库、`.env` 和旧镜像，随后运行 `docker compose up -d --build --wait`。回滚使用旧版本代码及镜像；涉及数据结构变化时，先核对兼容性。`docker compose down -v` 会删除账号、进度及证书卷。

恢复时先备份当前状态并停止应用，再把选定的在线备份恢复到数据卷的 `/data/study.db`；清理旧 WAL/SHM，确保属于 UID/GID 10001、权限 0600。备份中的有效会话也可能恢复，需要撤销登录时应在停机期间清理 sessions 表，随后启动验证。

## 本地 HTTP 开发

使用 Python 3.12 或 3.13。先按 [贡献指南](../../CONTRIBUTING.md) 安装依赖，再构建：

```sh
python vocab-data/build.py
python server/build_web.py
mkdir -p .local
```

用隐藏输入读取密码并创建本地账号：

```sh
python -c 'import getpass, subprocess, sys; subprocess.run([sys.executable, "-m", "server.manage", "--db", ".local/study.db", "create-admin", "--username", "admin", "--password-stdin"], input=getpass.getpass("Admin password: "), text=True, check=True)'
```

启动仅监听本机的开发服务：

```sh
APP_ORIGIN=http://localhost:8000 COOKIE_SECURE=false DATABASE_PATH=.local/study.db \
  python -m uvicorn server.app:application --factory --host 127.0.0.1 --port 8000
```

打开 `http://localhost:8000`，不要混用不同主机名或端口。正式部署保留 Secure cookie 并使用 HTTPS。本地数据库也不能提交。

## 离线与同步

首次在每台设备联网登录，等待「离线资源已就绪」后，可在同一浏览器离线刷新、查看释义、查词和记录学习状态。恢复联网后自动同步；关闭页面期间的操作在下次打开后续传。待同步时不要清除网站数据。

每个账号独立存储本机进度。不同设备修改不同单词会合并；同一单词以服务器最后收到的有效操作为准。登录、账号管理、改密码及完整 JSON 导入需要联网。旧独立 HTML 的进度可先备份，再在登录后导入；导入替换该账号的云端进度。

浏览器的 Service Worker 和存储支持会影响离线能力。独立 HTML 无账号、无服务端同步；服务器版需要首次联网登录，两种使用方式的进度通过手动备份导入迁移。
