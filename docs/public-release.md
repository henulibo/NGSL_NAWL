# 公开发布指南

## 发布内容

代码与原创文档采用 MIT，词表和官方英文释义采用 CC BY-SA 4.0，ECDICT 采用 MIT。适用文件及署名见 [NOTICE](../NOTICE) 和 [数据说明](data.md)。公开仓库和默认生成页面不包含剑桥词典数据。

`private-release-notes/`、`.env`、本机工具配置、账号数据库、备份、日志和生成文件均被忽略。旧词典材料保存在本机 `private-release-notes/legacy-vocabulary/`，不可随源码上传。

## 发布检查和源码包

```sh
python3 scripts/package_public_release.py --check
python3 scripts/package_public_release.py
```

发布脚本直接枚举明确允许的文件，不依赖 Git，也不遍历本机私有目录；从 GitHub 下载源码 ZIP 后仍可使用。输出为 `public-release/ielts-source.zip`，顶层目录 `ielts-source/`。仅包含公开清单中的代码、公开数据、测试、文档和 GitHub 配置；不含原有 Git 元数据、旧词典 JSON、生成 HTML 或运行数据。新增文件类型需要审查后更新允许清单。

检查内容包括常见服务商令牌、私钥标记、JWT、带密码的连接地址、个人主目录路径、邮箱、公网 IPv4 及部分源码硬编码凭据。存在 Git 时，还拒绝已跟踪但不在公开清单内的文件。失败时仅输出文件名和问题类型，不输出凭据原文；缺少必要文件同样会中止。

**此脚本不扫描 Git 历史，也不能发现所有编码或自定义凭据。** 测试中的固定密码用于临时账号，服务端的无效用户占位散列不是可登录账号。

## 发布前验证

```sh
make build
make test
make check-release
make release
```

把生成 ZIP 解压到项目之外的空目录，再在其中执行：

```sh
python3 vocab-data/build.py
python3 server/build_web.py
python3 scripts/package_public_release.py --check
```

确认无 `.git` 也能构建，页面词表总数正确，来源与许可随包保留。所有源码包内路径和时间戳固定；相同文件内容及执行位在同一压缩工具环境下生成相同 ZIP。

## 首次公开到 GitHub

当前工作目录以干净快照初始化新历史。推送前核对 `git log --format=fuller` 中的作者姓名、邮箱和待推送提交内容；本仓库可使用匿名作者或自己的 GitHub noreply 邮箱。不要把旧仓库的分支或标签直接合并进来，也不要使用 mirror 推送。

在 GitHub 创建空仓库后关联所需远程，再推送已经审查的 `main` 分支。CI 配置随首次提交生效；本地检查通过不代表 GitHub Actions 已实际运行。首次推送后查看 CI 结果，并在仓库设置中启用私密漏洞报告、依赖告警，以及要求 CI 通过的主分支保护。仓库尚未创建时，这些 GitHub 设置无法在本地提前完成。

若必须保留旧仓库历史，应在公开前单独扫描全部相关分支、标签及历史对象。`.gitignore` 不会清除已跟踪文件或旧提交。真实凭据若曾公开，先撤销或轮换，再处理历史。
