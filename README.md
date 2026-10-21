# NGSL × NAWL 词汇学习手册

离线优先的英语词汇学习工具：每天一页，标记生词，用自己的节奏完成一轮复习。

An offline-first vocabulary workbook with NGSL / NAWL word lists, local progress, speech synthesis, and optional self-hosted account sync.

[快速开始](#快速开始) · [部署指南](docs/deployment/README.md) · [数据与许可](docs/data.md) · [参与贡献](CONTRIBUTING.md) · [安全政策](SECURITY.md)

## 能做什么

- **按日学习**：NGSL 1.2 的 2,809 个词和 NAWL 1.2 的 957 个词各分 5 天，附 52 个补充词；可跨天搜索或按 50 词分组。
- **离线复习**：中文释义、官方英文释义、音标和查词数据嵌入单个 HTML，打开后无需服务或网络。
- **记录进度**：标记已掌握、需复习，隐藏释义自测；支持 JSON 备份与导入、CSV 导出、打印 / PDF。
- **适配设备**：移动端布局、深浅色模式、键盘关闭弹框和浏览器语音朗读。
- **可选同步**：自行部署 Python 服务，为多个账号独立保存进度；支持离线修改后恢复同步。

公开版本采用 NGSL / NAWL 官方词表及英文释义（CC BY-SA 4.0）和 ECDICT 中文释义与音标（MIT）。**不包含剑桥词典内容、双语例句或 CEFR 等级。** 缺失释义会直接提示，完整来源与加工说明见 [docs/data.md](docs/data.md)。

## 快速开始

仅构建离线页面需要 Python 3.9 或更高版本，无第三方依赖：

```sh
python3 vocab-data/build.py
```

用浏览器打开生成的 `NGSL_NAWL_10天学习词表.html`。首次构建不联网，也不需要账号。该 HTML 是生成文件，不进入 Git；下载源码 ZIP 的用户同样运行上述命令。

进度存在当前浏览器。移动 HTML、换浏览器或清理网站数据可能影响进度，建议定期使用「备份进度」。朗读效果取决于系统已安装的英语语音和浏览器支持；若需要完全离线朗读，请安装本地英语语音。

## 本地开发

完整服务与测试使用 **Python 3.12 / 3.13**；JavaScript 测试使用 **Node.js 22**。运行 Python 服务不需要 Node.js。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r server/requirements-dev.txt
npm --prefix tests ci
make build
make test
make check-release
```

没有 Make 时，依次运行：

```sh
python vocab-data/build.py
python server/build_web.py
python -m pytest -q
node --test tests/*.test.js
python scripts/package_public_release.py --check
```

Windows 使用 `.venv\Scripts\activate` 激活虚拟环境。Python 测试检查数据、构建、登录权限和用户进度隔离；JavaScript 测试检查查词、朗读、浏览器存储和离线同步。GitHub Actions 也执行构建、测试与发布检查。

## 多用户服务器版

服务器版需自行部署，用户账号由管理员创建，没有默认密码或公共服务地址。Docker 构建会自动生成前端并安装锁定版本的 Python 依赖，不需要预先准备 wheel 文件。

```sh
cp .env.example .env
# 编辑 .env，把两个示例域名替换为自己的 HTTPS 域名。
docker compose up -d --build --wait
```

随后按 [部署指南](docs/deployment/README.md) 通过标准输入初始化管理员。账号、会话及进度保存在 SQLite 持久卷；Caddy 提供 HTTPS。首次联网登录并等待离线资源就绪后，同一浏览器可以离线学习，恢复联网后续传修改。

本地 HTTP 开发、备份恢复和更新回滚也见部署指南。不要把运行数据库、备份、进度导出或实际 `.env` 提交到仓库。

## 项目结构

```text
vocab-data/       公开数据、页面模板、查词 / 朗读逻辑和构建脚本
server/          FastAPI / SQLite 服务及登录、账号、离线同步脚本
tests/           Python 与 Node.js 测试
deploy/          Caddy 配置、备份和 Ubuntu Docker 安装脚本
scripts/         发布包构建与敏感信息检查
docs/            部署、数据来源和公开发布说明
.github/         CI、依赖更新配置及 Issue / PR 模板
```

生成的独立 HTML、`vocab-data/examples-data.json` 和 `server/web/` 均被忽略。源码不含第三方词典的抓取或导入工具；构建只读取仓库内的公开数据，也不会下载词典。

## 打包与发布

```sh
python3 scripts/package_public_release.py --check
python3 scripts/package_public_release.py
```

第二条命令生成 `public-release/ielts-source.zip`，只包含公开清单内的源码、数据、许可与文档；不带 `.git`、本机配置、旧词典内容或账号数据。不依赖 Git 命令，因此解压后的源码仍可重新打包。发布前的检查范围与 GitHub 设置见 [公开发布指南](docs/public-release.md)。

## 贡献与许可

问题报告和改进建议请使用仓库的 Issue 模板。提交代码前阅读 [贡献指南](CONTRIBUTING.md) 和 [行为准则](CODE_OF_CONDUCT.md)；安全问题按 [安全政策](SECURITY.md) 私下报告。版本变化记录于 [CHANGELOG](CHANGELOG.md)。

**代码及原创文档采用 [MIT](LICENSE)。** 词表和官方英文释义保留 **CC BY-SA 4.0**，ECDICT 数据保留其 **MIT** 许可；这些数据不因根目录 LICENSE 改为其他许可。署名、加工记录和适用文件见 [NOTICE](NOTICE) 与 [数据说明](docs/data.md)。
