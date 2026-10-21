# 参与贡献

欢迎修正词表、改进离线体验、补充测试或完善文档。较大的功能调整请先开 Issue 说明目标和方案；普通修复可以直接提交 Pull Request。

## 本地环境

使用 Python 3.12 或 3.13、Node.js 22 和 npm。Node.js 只用于测试。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r server/requirements-dev.txt
npm --prefix tests ci
make build
make test
make check-release
```

Windows 可用 `.venv\Scripts\activate` 激活环境，并执行 [README](README.md) 中对应的 Python / Node 命令，不要求安装 Make。

## 变更约定

- 每个 PR 聚焦一个问题，说明行为变化和验证结果；涉及行为的修复应有能复现问题的测试。
- 修改 `vocab-data/page-template.html`、脚本或公开数据后重新构建。生成的 HTML、`examples-data.json` 和 `server/web/` 不提交。
- 服务端涉及账号、会话或学习进度时，检查用户隔离、离线同步和旧进度兼容性。
- Python 测试位于 `tests/test_*.py`，JavaScript 测试使用 Node 自带的测试运行器。不要为运行服务增加 Node 依赖。
- 文档中的域名使用 `study.example.com`；测试账号只在临时数据库中创建。不要提交真实配置、访问日志、进度导出、密码或个人邮箱。

## 数据贡献

请先阅读 [数据来源与许可](docs/data.md)。数据改动须说明来源、许可及加工步骤；NGSL / NAWL 派生数据保留 CC BY-SA 4.0，ECDICT 保留 MIT 声明。不要上传没有分发授权的词典抓取结果、截图或付费数据。代码贡献按项目 MIT 许可提供，第三方数据仍遵守原许可。

## 提交 Pull Request

运行上述构建、测试与发布检查，在 PR 中填写变更目的和实际执行的检查。不要勾选未执行的检查。遵守 [行为准则](CODE_OF_CONDUCT.md)，安全问题按 [安全政策](SECURITY.md) 私下报告。
