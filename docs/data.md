# 数据来源与许可

代码与数据分别授权：根目录 [LICENSE](../LICENSE) 的 MIT 用于代码和原创文档；[NOTICE](../NOTICE) 列出第三方数据的署名、许可链接和加工内容。

| 文件 | 来源及范围 | 许可 |
| --- | --- | --- |
| `vocab-data/ngsl-official.csv` | NGSL 1.2 原始统计表，2,809 个词 | CC BY-SA 4.0 |
| `vocab-data/nawl-stats.csv` | NAWL 1.2 原始统计表，957 个词 | CC BY-SA 4.0 |
| `vocab-data/supplementary.csv` | NGSL 补充词表，52 个词 | CC BY-SA 4.0 |
| `vocab-data/study-data.json` | 词头、表内排名与分日编排；不含私有词典内容 | CC BY-SA 4.0 |
| `vocab-data/learner-definitions.json` | NGSL / NAWL 官方英文释义，转换为 JSON 并统一空格 | CC BY-SA 4.0 |
| `vocab-data/lookup-data.json` | ECDICT 释义与音标子集，保留词形还原信息 | MIT |

NGSL / NAWL 作者：Charles Browne、Brent Culligan、Joseph Phillips（2013），New General Service List Project。

来源与许可核对日期：2026-10-21。

- [NGSL 官方来源及许可](https://www.newgeneralservicelist.com/new-general-service-list)
- [NAWL 官方来源及许可](https://www.newgeneralservicelist.com/new-academic-word-list)
- [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- [ECDICT 原仓库](https://github.com/skywind3000/ECDICT)、[上游 MIT 许可](https://github.com/skywind3000/ECDICT/blob/master/LICENSE)、[本地许可副本](../vocab-data/ecdict-license.txt)

## 默认构建

`python3 vocab-data/build.py` 从上述 JSON 读取词表、官方英文释义和 ECDICT 数据，生成弹框语料及独立 HTML；构建不联网。英文释义保留原文，中文释义不声称是官方译本。部分英美拼写通过明确映射查找 ECDICT，并在弹框标注参考词头。

公开数据未提供双语例句或 CEFR 等级；页面不推测这些信息。官方英文释义覆盖 NGSL 2,809 个词、NAWL 954 个词；cheer、descendent 缺失，distribution 的原表错误值被略去。补充词无官方英文释义。ECDICT 未覆盖的条目显示「暂无离线中文释义」，而不是用其他来源的文本填补。

`examples-data.json`、独立 HTML 和 `server/web/` 是生成文件，不提交到 Git。输出 HTML 内嵌数据署名及 ECDICT 许可；分发 HTML 或容器时应同时保留根目录 LICENSE、NOTICE，以及数据各自的许可和署名。

## 本地旧数据与导入工具

首次整理时，旧 HTML 和旧词典 JSON 已保存在本机忽略目录 `private-release-notes/legacy-vocabulary/`，它们不属于公开源码、CI 或发布包。旧的 `cambridge-senses.json`、`core-senses.json`、`senses-extra.json`、`examples-extra.json` 也被显式排除。

`cambridge.py`、`merge_examples.py` 和 `learner.load_core_senses` 是保留的本地导入工具，仅用合成测试数据验证解析逻辑；默认构建不调用它们。若自行导入第三方内容，应先取得对应使用及分发授权。剑桥针对离线存储和嵌入提供单独授权途径，参见 [官方 API FAQ](https://dictionary-api.cambridge.org/api/faq)。导入内容不会因为项目使用 MIT 就自动获得分发许可。

## 更新数据

修改数据时在 PR 中附上原始版本、下载地址、许可和转换步骤，保留 NOTICE 中的署名。词表与分日元数据更新后运行构建和测试，核对总数、重复词、缺失释义及旧进度 ID 的兼容性。

`prepare_lookup.py` 接受三个显式路径：ECDICT CSV、含 `examples` 数组的语料 JSON、输出 JSON。它只做本地转换，不会下载词典。不要为了补全缺失项混入许可不明的内容。
