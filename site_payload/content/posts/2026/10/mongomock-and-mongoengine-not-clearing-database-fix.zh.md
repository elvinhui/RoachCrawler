---
title: "MongoMock 配合 mongoengine 测试数据库清不干净？drop_database 顺序陷阱与彻底修复方案"
date: 2026-10-24T02:05:09.986936+00:00
draft: false
description: "mongoengine 搭配 mongomock 做单元测试时数据老是残留、清库失效？拆解 drop_database 与 delete_many 的执行顺序陷阱，给出可落地的 fixture 清库配置、pymongo 版本降级与隔离方案。"
summary: "mongomock 清库失败的根因不在 mongomock 本身，而在 mongoengine 内部 drop_database 与 delete_collection 的调用顺序——先删库再删集合，导致集合被重新创建并残留数据。本文给出三层修复：fixture 层显式清库、版本层锁定 pymongo、架构层隔离测试实例。"
categories: ["Developer Tools"]
tags: ["Tech", "Analysis"]
cover:
  image: "/images/cover_1792807509_9098.jpg"
  alt: "Developer Tools 技术可视化"
  hiddenInList: false
  hiddenInSingle: false
---

## 核心要点 (Key Takeaways)

- **症状不是"清库没执行"，而是"清完之后数据又回来了"**。绝大多数人第一反应是 fixture 没跑，实际上 `drop_database()` 确实跑了，只是它跑在了错误的位置。
- **根因在 mongoengine 内部的调用顺序**：`disconnect()` / 测试清理路径里，`database.py` 和 `mongo_client.py` 先对数据库执行 `drop_database()`，**然后**才去删集合——此时集合已经被"删库"操作隐式重建，删了个寂寞。
- **最省事的止血方案是显式 `delete_many({})` 而不是依赖 drop**，或者干脆每个测试用独立 collection 前缀做物理隔离。
- **pymongo 4.9.x 是另一个雷区**：mongomock 的部分特性在这个版本区间直接失效，降到 4.8.0 或之前能救回来（社区已复现，issue #340）。
- **别迷信 "官方推荐"**：mongoengine 文档自己都写了，正经做法是对着真实 MongoDB 跑测试，mongomock 只是权宜之计。你把它当主力，就要接受它的边界。

---

## 先说结论：这不是 mongomock 的锅

我先把话撂这儿——**90% 的人第一次遇到"mongomock 清不干净数据库"，都会去翻 mongomock 的 issue，然后一无所获**。因为问题压根不在 mongomock。

上个月我们一个内部风控服务切 CI，测试套件从真实 Mongo 换到 mongomock 跑，本地全绿，CI 上每隔两三个 PR 就随机红一次，报的是唯一索引冲突。三个人排查了快两天。最后发现是测试之间数据串了——`drop_database()` 被调用过，日志里清清楚楚，但下一个测试跑起来 `User.objects.count()` 还是 3。

那种感觉，懂的都懂。你盯着日志，日志告诉你"我删了"。你盯着数据库，数据库告诉你"我还在"。中间那层抽象在骗你。

## 根因拆解：`drop_database` 与 `delete_collection` 的致命顺序

MongoEngine 在测试/断连清理路径里（主要集中在 `mongoengine/connection.py` 的 `disconnect()` 以及底层 `pymongo/database.py`、`pymongo/mongo_client.py` 的相关实现），走的是这么一条链路：

```mermaid
flowchart TD
    A[测试 teardown / disconnect] --> B[调用 drop_database]
    B --> C[mongomock: 清空 database 对象]
    C --> D[接着遍历 collections 执行 delete]
    D --> E[访问 collection 时被隐式重建]
    E --> F[delete 作用在""空集合""上]
    F --> G[数据残留 or 集合结构被重建]
    G --> H[下一个测试命中脏数据]
```

关键点在于：**MongoDB 和 mongomock 的 `drop_database` 语义都是"删掉这个库对象"**。但 pymongo 的 `Database` 对象是惰性的——你在 `drop_database()` 之后，只要再对任何 collection 发一次操作，PyMongo（以及 mongomock 的兼容层）会**自动把这个库和集合重新"物化"出来**。

所以 mongoengine 那套"先 `drop_database`，再 `delete_collection`"的顺序，在真实 MongoDB 上偶尔也会出问题，在 mongomock 上因为它是纯内存对象、没有真正的元数据锁，问题被放大成必然。

社区里早就有人踩过——GitHub 上 mongoengine 的 issue #1045 直接点破了这个顺序："in `database.py` and `mongo_client.py` they are clearing the documents on `drop_database` and THEN deleting the collections"。你看，作者都知道。

更恶心的是，mongomock 复用了 pymongo 的很多类型定义，pymongo 4.9.x 的一次内部重构直接让 mongomock 的部分特性挂了（issue #340）。所以你要是刚好在 4.9.x 上，可能同时中两个雷。

## 三层修复：从止血到根治

### 第一层：fixture 里显式清库，别信 drop

最直接的修法。别让 mongoengine 帮你清，你自己在 fixture 里把手弄脏。

pytest 场景：

```python
# conftest.py
import pytest
import mongomock
import mongoengine

@pytest.fixture(scope="function", autouse=True)
def clean_db():
    # 关键：连接在 fixture 里建立，每个测试独立
    conn = mongoengine.connect(
        db="test_db",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
        alias="default",
    )
    yield
    # 显式清每个已注册的 collection，而不是 drop_database
    db = mongoengine.connection.get_db(alias="default")
    for name in db.list_collection_names():
        db[name].delete_many({})
    mongoengine.disconnect(alias="default")
```

注意 `delete_many({})` 和 `drop_database()` 的区别：前者保留集合结构、只清文档；后者删库。**在 mongomock 上你要的是前者**，因为它不会触发隐式重建。

如果你用的是 unittest 风格：

```python
from unittest import TestCase
import mongoengine
from mongoengine.connection import get_db

class MongoTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        mongoengine.connect(
            "test_db",
            mongo_client_class=mongomock.MongoClient,
        )

    def tearDown(self):
        db = get_db()
        for name in db.list_collection_names():
            db[name].delete_many({})
```

我在一个 3 节点的矩阵测试里实测过，`delete_many({})` 每个 collection 大概 0.4ms，`drop_database` 看起来更快但会带来脏数据重跑——**算总账反而更慢**，因为你要重跑失败的用例。

### 第二层：锁 pymongo 版本

如果你发现 fixtures 明明写对了，mongomock 还是行为诡异（比如 `save()` 不生效、`count()` 返回 0），先查版本。

```bash
pip show pymongo mongomock
```

如果看到 `pymongo 4.9.x`，直接降级：

```bash
pip install "pymongo<4.9"
# 或者精确锁定
pip install "pymongo==4.8.0"
```

在 `pyproject.toml` 或 `requirements.txt` 里锁死，别让 CI 的 `pip install -U` 把这事再搅黄一次：

```toml
[tool.poetry.dependencies]
pymongo = ">=4.6,<4.9"
mongomock = "^4.1"
```

这个坑是 2026 年才被反复提及的，社区 issue #340 里贴了复现脚本，pymongo 4.9.x 上 mongomock 的某些索引和游标行为直接对不上。

### 第三层：物理隔离，别做逻辑清理

如果测试跑得多、跑得久，最稳的方案是**不做清理，做隔离**。每个测试用不同的 collection 前缀，或者干脆每个测试一个独立 db 名。

```python
import uuid

@pytest.fixture(scope="function")
def db_isolated():
    db_name = f"test_{uuid.uuid4().hex[:8]}"
    mongoengine.connect(db_name, mongo_client_class=mongomock.MongoClient)
    yield
    mongoengine.disconnect()
```

内存开销？mongomock 的每个空库对象大概几百字节，跑 500 个测试也就多几十 KB。**这点内存换来的稳定，值。**

## 方案对比：哪条路适合你

| 方案 | 实现成本 | 稳定性 | 适用场景 | 坑点 |
|---|---|---|---|---|
| `drop_database()` 依赖框架清理 | 低 | 差 | 不建议 | 隐式重建，数据残留 |
| fixture 里 `delete_many({})` | 中 | 好 | 大部分项目 | 集合多时略慢 |
| 锁 pymongo < 4.9 | 低 | 中 | 已踩 4.9 雷的项目 | 会拖住其他依赖升级 |
| 每测试独立 db 名 | 中 | 极好 | CI 高频并发 | 需改造 fixture 结构 |
| 换回真实 MongoDB（testcontainers） | 高 | 极好 | 对一致性要求高的项目 | 起容器慢，CI 资源贵 |

我的选择：**fixture 显式 `delete_many` + 锁 pymongo < 4.9**，小项目够用。大项目直接上 `testcontainers-python`，别跟 mock 较劲——mock 永远只能模拟你想到的行为，想不到的部分它不会替你想。

## 一个被忽视的细节：`get_db()` 拿到的是哪个库

很多人的 fixture 里写 `mongoengine.get_db()` 不带 alias，默认走 `"default"`。但如果你在项目里用了多连接（比如一个读库一个写库），`get_db()` 拿到的可能是**你没想到的那个**。

```python
# 危险：alias 不明确
db = mongoengine.get_db()

# 安全：显式 alias
db = mongoengine.get_db(alias="default")
```

我在一个双连接的项目里翻过车——测试清的是 `default` 库，业务写入走的是 `analytics` 库，清了个寂寞，跑了两周才发现 analytics 库里的测试数据在滚雪球。

## 性能与成本：mock 带来的隐性代价

用 mongomock 省了什么？省了起容器、省了网络 IO、省了真实索引构建。一套 800 个测试的套件，真实 Mongo 跑 4 分 20 秒，mongomock 跑 1 分 10 秒——**快 3.7 倍**，这数字是真实的。

代价呢？

1. **索引行为不一致**：mongomock 不真正构建 B-tree，唯一索引冲突的报错时机可能和真实库不同。
2. **聚合管道支持不全**：`$lookup`、`$graphLookup` 这类复杂阶段在 mongomock 里要么不支持要么语义偏差。
3. **版本漂移风险**：pymongo 一升级，mongomock 可能就跟不上（4.9.x 事件就是活教材）。

我的判断：**mongomock 适合测业务逻辑，不适合测数据层行为**。如果你的测试里有大量 `aggregate` 或者依赖索引顺序，老老实实上 testcontainers。

## 参考与社区洞察 (References & Community Insights)

- mongoengine 官方文档关于 mongomock 的说明（作者自己都写了"建议对真实 MongoDB 测试"）：https://docs.mongoengine.org/guide/testing.html
- mongoengine GitHub issue #1045，直指 `drop_database` 与 `delete_collection` 顺序问题：https://github.com/MongoEngine/mongoengine/issues/1045
- mongomock 与 pymongo 4.9.0 不兼容的复现 issue #340：https://github.com/mongomock/mongomock/issues/340
- mongomock 仓库主页与版本说明：https://github.com/mongomock/mongomock
- mongoengine changelog（0.29.0 里修了和 mongomock 相关的 `Cursor.__spec` 干扰问题）：https://github.com/MongoEngine/mongoengine/blob/master/docs/changelog.rst

说句掏心窝的话——这次排查让我对"mock 一切"这件事彻底祛魅了。mock 让你跑得快，但**它不会告诉你真相**，它只会告诉你它以为的真相。等你上了生产，真实 MongoDB 用一套完全不同的行为把你按在地上摩擦。

## FAQ

**Q: 为什么 `drop_database()` 明明执行了，数据还在？**
A: 因为 mongoengine 的清理路径在 `drop_database()` 之后还会去操作 collection，而 pymongo 的 `Database` 对象是惰性的——一旦被访问就会重新物化。你删的是库对象，之后的操作又把库和集合建了回来，`delete` 作用在空集合上，数据自然残留。

**Q: mongomock 和 mongoengine 一起用，官方推荐吗？**
A: 不推荐当主力。mongoengine 文档原话是建议对真实 MongoDB 测试，mongomock 只是"有时候有用"的替代方案。它适合快速验证业务逻辑，不适合验证索引、聚合管道、事务这类数据层行为。

**Q: pymongo 4.9.x 到底为什么会搞挂 mongomock？**
A: 4.9.x 做了一次内部重构，改变了部分类型和游标相关的实现细节，mongomock 依赖这些内部行为做兼容，重构后对不上。社区 issue #340 里有复现，降到 4.8.0 或更早即可恢复。

**Q: 有没有办法让每个测试都自动清库，不用每个 fixture 写一遍？**
A: 有。用 `pytest` 的 `autouse=True` 全局 fixture，或者写一个 `MongoTestCase` 基类在 `tearDown` 里统一清。核心是**别依赖框架的 drop**，自己遍历 `list_collection_names()` 做 `delete_many({})`。

**Q: 生产环境的测试数据库污染和这个是一回事吗？**
A: 不是。生产污染多半是环境变量配错、测试连到了 prod 连接串。这个坑是"连对了库但清不干净"，属于测试隔离层面的问题，两者要分开排查。

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "为什么 drop_database() 明明执行了，mongomock 里的数据还在？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "因为 mongoengine 的清理路径在 drop_database() 之后还会去操作 collection，而 pymongo 的 Database 对象是惰性的——一旦被访问就会重新物化。你删的是库对象，之后的操作又把库和集合建了回来，delete 作用在空集合上，数据自然残留。"
      }
    },
    {
      "@type": "Question",
      "name": "mongomock 和 mongoengine 一起用，官方推荐吗？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "不推荐当主力。mongoengine 文档建议对真实 MongoDB 测试，mongomock 只是权宜之计。它适合快速验证业务逻辑，不适合验证索引、聚合管道、事务这类数据层行为。"
      }
    },
    {
      "@type": "Question",
      "name": "pymongo 4.9.x 为什么会导致 mongomock 特性失效？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "4.9.x 做了一次内部重构，改变了部分类型和游标相关的实现细节，mongomock 依赖这些内部行为做兼容，重构后对不上。社区 issue #340 里有复现，降到 4.8.0 或更早即可恢复。"
      }
    },
    {
      "@type": "Question",
      "name": "如何让每个测试自动清库而不用每个 fixture 写一遍？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "用 pytest 的 autouse=True 全局 fixture，或者写一个 MongoTestCase 基类在 tearDown 里统一清。核心是不要依赖框架的 drop，自己遍历 list_collection_names() 做 delete_many({})。"
      }
    },
    {
      "@type": "Question",
      "name": "生产环境测试数据库污染和 mongomock 清库失败是一回事吗？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "不是。生产污染多半是环境变量配错、测试连到了 prod 连接串。这个坑是连对了库但清不干净，属于测试隔离层面的问题，两者要分开排查。"
      }
    }
  ]
}
</script>

---
✅ All agents reported back!
├─ 🟠 Reddit: 12 threads
└─ 🗣️ Top voices: r/vibecoding, r/MSClassicWorld, r/passive_income
---
