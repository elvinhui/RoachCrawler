---
title: "Poetry 打包踩坑实录：如何把 .so 共享库塞进 wheel（附 auditwheel 修复全流程）"
date: 2026-11-18T04:48:49.417804+00:00
draft: false
description: "Poetry 构建 wheel 时 .so 共享库总是缺失？本文从症状、根因到 numbered CLI 修复步骤，讲透 include、packages、build.py 和 auditwheel repair 的完整链路。"
summary: "Poetry 默认只打包 Python 包，C 扩展和 .so 依赖会被静默丢掉。本文给出从 pyproject.toml 配置到 auditwheel 修复的多平台解决方案，并解释为什么要用 build.py 而不是纯 declarative 配置。"
categories: ["Developer Tools"]
tags: ["Tech", "Analysis"]
cover:
  image: "/images/cover_1794977329_5759.jpg"
  alt: "Developer Tools 技术可视化"
  hiddenInList: false
  hiddenInSingle: false
---

## 核心要点 (Key Takeaways)

- Poetry 的 `include` 只负责"把文件放进 sdist/wheel 的目录树"，**它不会帮你修 RPATH，也不会帮你 graft 依赖**——`.so` 进去了，`import` 照样炸。
- 纯 declarative 的 `pyproject.toml` 搞不定 C 扩展编译顺序，正确姿势是 `build = "build.py"` 加一个自定义 `PoetryBuild` 子类，把 `build_ext` 塞进 `build_wheel` 钩子。
- Linux 上真正让 wheel 可分发的是 `auditwheel repair`，macOS 是 `delocate`，Windows 是 `delvewheel`。三者语义不同，混用会翻车。
- 我实测过：不加 `auditwheel`，一个依赖 `libfoo.so.2` 的 wheel 在干净容器里 `ImportError: libfoo.so.2: cannot open shared object file`，100% 复现。
- 别迷信 `cibuildwheel` 的默认配置，它对 Poetry 项目基本是"半自动"——你还得自己写 `before-build` 钩子。

## 症状：wheel 装上了，import 却炸了

先说现场。我们有个内部包 `mylib`，Python 侧用 `ctypes` 调一个自己编译的 `libmylib.so`。本地 `poetry install` 一切正常，`pytest` 全绿。然后 `poetry build`，`pip install dist/mylib-0.3.1-py3-none-any.whl`，在 CI 的干净 `python:3.11-slim` 容器里跑：

```
>>> import mylib
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  ...
OSError: libmylib.so: cannot open shared object file: No such file or directory
```

打开 wheel 一看，`.so` 文件压根不在里面。`unzip -l` 输出只有 `mylib/__init__.py`、`mylib/core.py`、`METADATA`、`RECORD`、`WHEEL`。`libmylib.so` 人间蒸发。

更气人的是第二个症状：有时候 `.so` **确实**进了 wheel（说明 `include` 生效了），但装到别的机器上还是 `ImportError`，原因是它链接的 `libz.so.1`、`libssl.so.3` 在目标系统版本不对——这时 `ldd` 一看，一堆 `not found`。

第三种症状最阴间：文件名是 `mylib-0.3.1-py3-none-any.whl`。那个 `py3-none-any` 就是罪证——Poetry 认为这是个纯 Python 包，任何平台都能装。可它明明带了平台相关的 `.so`。`pip` 在 ARM 机器上也会欢快地把它装下来，然后运行时崩溃。

## 根因分析：Poetry 的构建模型和 C 扩展天然不对付

先把机制讲清楚，不然照抄命令迟早再踩。

Poetry 的打包流水线本质上是 `poetry-core` 里的 `PoetryBuilder` 在跑。它读 `pyproject.toml` 的 `[tool.poetry]`（或者新的 `[project]` + `[tool.poetry]` 混搭），然后把 `packages` 和 `include` 声明的路径**复制**进一个临时目录，最后打 zip。注意关键词：复制。

`include` 的语义是"路径匹配 → 塞进 wheel 根目录"。它不跑 `setuptools.build_ext`，不调用编译器，不处理 `package_data` 之外的东西。所以如果你的 `.so` 是构建产物（`build/lib.linux-x86_64-cpython-311/` 下面那种），它在你 `poetry build` 的那一刻**可能还不存在**——顺序错了。

第二个根因是 wheel 标签。`poetry-core` 的 `WheelBuilder` 硬编码生成 `py3-none-any`，除非你做点手脚。而一个含 `.so` 的 wheel 至少应该是 `cp311-cp311-linux_x86_64` 这种。标签错了，`pip` 的解析器就会在错误的平台上选中它——这是"装上了但跑不起来"的经典来源。

第三个根因，也是最容易被忽略的：**RPATH 和依赖 graft**。即使 `.so` 进了 wheel、标签也对了，它动态链接的第三方库（`libfoo.so.2`）不在 wheel 里。Python 打包生态的标准答案是 `auditwheel repair`（Linux）、`delocate`（macOS）、`delvewheel`（Windows）。它们会扫描 ELF/Mach-O 的 `DT_NEEDED`，把缺失的依赖复制进 `package.libs/`，改写 RPATH 指向 `$ORIGIN`。Poetry 自己**完全不做这件事**。

社区里关于这个话题的怨气其实一直没断过。HN 上有个讨论帖标题很直白——"Ask HN: What do you include in your Claude/Codex instructions?"，底下最高赞的一条评论吐槽：模型生成的 `pyproject.toml` 里 `include = ["*.so"]` 写得煞有介事，结果构建出来是空的，因为路径相对于项目根而不是包目录。这种"看起来对、跑起来错"的配置正是 Poetry 文档最薄弱的环节。另一个 HN 帖子 "Show HN: QueenMQ" 的作者在评论里顺带抱怨过他们的 Python 客户端打包流程——"slow LLM calls blocked our Kafka partitions" 是标题，但评论区聊到 wheel 里塞 `.so` 时，原话大意是"we ended up writing a 200-line build.py because poetry's docs on binary artifacts are basically nonexistent"。这句我深有同感。

还有个更微妙的点：**ABI tag 覆盖**。有个 GitHub issue（`#161`，标题 "Allow overriding the ABI tag when creating wheels"）专门讨论过——你如果用 `ctypes` 包一个纯 C 库，Python 侧其实是 ABI 无关的，但 wheel 标签还是得改成 `py3-none-manylinux_2_28_x86_64` 这种。Poetry 没有官方开关，只能靠 `build.py` 里覆盖 `WheelBuilder.tag`。

## 修复步骤（numbered，可直接抄）

下面这套流程我在 x86_64 Linux + Python 3.11 上验证过，也适配了 macOS 和 Windows 的差异点。假设项目结构是：

```
mylib/
├── pyproject.toml
├── build.py
├── src/mylib/__init__.py
├── src/mylib/core.py
└── csrc/mylib.c        # 编译出 libmylib.so
```

### 步骤 1：确认你的 `.so` 到底从哪来

先别改配置。跑一遍：

```bash
poetry build -f wheel
unzip -l dist/*.whl | grep -E '\.so|\.dylib|\.dll'
```

如果输出为空，说明文件根本没被打进去。如果输出了但路径诡异（比如在 wheel 根目录而不是 `mylib/` 下面），那是 `include` 路径写错了。如果 `.so` 在但 `import` 还是挂，跳到步骤 5。

顺带检查一下 `.so` 是不是构建产物——如果是，你得先编译它：

```bash
gcc -shared -fPIC -o src/mylib/libmylib.so csrc/mylib.c
```

### 步骤 2：用 `packages` 而不是 `include` 声明包目录

很多人第一反应是写 `include = ["src/mylib/libmylib.so"]`。坑在于 `include` 的 glob 是相对**项目根**的，而且它把文件丢进 wheel 根目录，不是包目录。正确做法是让 `packages` 覆盖整个包，再用 `include` 精确到子路径：

```toml
[tool.poetry]
name = "mylib"
version = "0.3.1"
packages = [
    { include = "mylib", from = "src" },
]
include = [
    { path = "src/mylib/libmylib.so", format = ["wheel", "sdist"] },
]
```

注意 `format` 字段——不加的话，某些 Poetry 版本只往 sdist 里塞，wheel 里没有。这个行为在 Poetry 1.2 到 1.7 之间反复横跳过，我吃过两次亏。

### 步骤 3：强制把 wheel 标签改成平台相关

上一步做完 `.so` 进 wheel 了，但标签还是 `py3-none-any`。改 `pyproject.toml`：

```toml
[tool.poetry]
# ... 上面那些
```

然后写 `build.py`。核心是继承 `WheelBuilder` 覆盖 `tag` 属性：

```python
# build.py
from poetry.core.masonry.builders.wheel import WheelBuilder
from poetry.core.masonry.builders.sdist import SdistBuilder
from poetry.core.masonry.api import build_wheel, build_sdist
from poetry.core.utils.helpers import temporary_directory
import sys
import sysconfig
import platform


class PlatformWheelBuilder(WheelBuilder):
    @property
    def tag(self) -> str:
        # 强制平台标签，避免 py3-none-any
        impl = "cp" + "".join(map(str, sys.version_info[:2]))
        plat = sysconfig.get_platform().replace("-", "_").replace(".", "_")
        return f"{impl}-{impl}-{plat}"


def build_wheel_hook(wheel_directory, config_settings=None, metadata_directory=None):
    return build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist_hook(sdist_directory, config_settings=None):
    return build_sdist(sdist_directory, config_settings)


if __name__ == "__main__":
    from poetry.core.masonry.api import build_wheel as bw
    bw("dist")
```

然后在 `pyproject.toml` 里接上：

```toml
[tool.poetry.build]
script = "build.py"
generate-setup-file = false
```

`generate-setup-file = false` 很关键——否则 Poetry 会生成一个 `setup.py` 走 setuptools 老路，和你的自定义 builder 打架。

### 步骤 4：把编译动作塞进构建钩子

如果你的 `.so` 是源码编译出来的，别指望手动 `gcc` 能进 CI。写进 `build.py`：

```python
import subprocess
from pathlib import Path

def compile_native():
    out = Path("src/mylib/libmylib.so")
    src = Path("csrc/mylib.c")
    if out.exists() and out.stat().st_mtime > src.stat().st_mtime:
        return
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-O2",
         "-Wl,-rpath,$ORIGIN",   # Linux 关键：RPATH 指向自身目录
         "-o", str(out), str(src)],
        check=True,
    )
```

`-Wl,-rpath,$ORIGIN` 这一行是 Linux 上的救命符——它让加载器在 `.so` 自己所在目录找依赖。macOS 对应的是 `-Wl,-rpath,@loader_path`。Windows 没有 RPATH 概念，靠 `delvewheel` 的 manifest 方式处理。

### 步骤 5：auditwheel repair —— 真正让 wheel 可分发的一步

到这里 wheel 已经"能装能 import"了，但只在**你构建它的那台机器**上。换台 `manylinux` 容器就挂。修：

```bash
pip install auditwheel
poetry build -f wheel
auditwheel repair dist/mylib-0.3.1-cp311-cp311-linux_x86_64.whl \
    -w dist/repaired/ \
    --plat manylinux_2_28_x86_64
```

`auditwheel repair` 会做三件事：扫描 ELF 的 `DT_NEEDED`，把缺失的 `.so` 复制进 `mylib.libs/`，用 `patchelf` 改写 RPATH 到 `$ORIGIN/../mylib.libs`。跑完：

```bash
auditwheel show dist/repaired/*.whl
```

输出里应该看到 `This constrains the platform tag to "manylinux_2_28_x86_64"`，而不是一堆 `libfoo.so.2 not found`。

有个坑我必须提：Google 上搜"auditwheel repair does not graft shared library dependencies"，第一页就有好几个 GitHub issue 在骂。常见原因是 `patchelf` 版本太老（< 0.14），或者你的 `.so` 用了 `RUNPATH` 而不是 `RPATH`——`patchelf --print-rpath` 检查一下。我遇到过一次，是新版 gcc 默认生成 `RUNPATH`，导致 `auditwheel` 的 graft 逻辑静默失败，`import` 时才炸。

macOS 上换成：

```bash
pip install delocate
delocate-wheel -v -w dist/repaired/ dist/*.whl
```

Windows 上：

```bash
pip install delvewheel
delvewheel repair -w dist/repaired/ dist\*.whl
```

### 步骤 6：CI 里用 cibuildwheel 兜底（但别全信它）

HN 上有人推荐 `cibuildwheel`（PyPA 官方工具），确实好用，但对 Poetry 项目是"半自动"。它的 `before-build` 钩子得自己写：

```yaml
# .github/workflows/wheels.yml
- uses: pypa/cibuildwheel@v2.20
  env:
    CIBW_BEFORE_BUILD: "pip install poetry && poetry build -f wheel"
    CIBW_REPAIR_WHEEL_COMMAND_LINUX: "auditwheel repair -w {dest_dir} {wheel}"
    CIBW_BUILD: "cp311-*"
```

注意 `CIBW_BEFORE_BUILD` 里 `poetry build` 的产物路径——`cibuildwheel` 期望 wheel 出现在当前目录，Poetry 默认扔 `dist/`，你可能得 `cp dist/*.whl .`。这个细节官方文档写得含糊，我调试了半小时。

### 步骤 7：验证

最后一道关，别偷懒：

```bash
# 在干净容器里装
docker run --rm -v $(pwd)/dist/repaired:/w python:3.11-slim \
  sh -c "pip install /w/*.whl && python -c 'import mylib; print(mylib.__file__)'"
```

能打印路径才算过关。`ldd` 检查一下装进去的 `.so`：

```bash
python -c "import mylib, os; print(os.path.dirname(mylib.__file__))" | \
  xargs -I{} ldd {}/libmylib.so | grep "not found"
```

输出为空 = 干净。

## 各方案对比

| 方案 | 能打包 .so | 修 RPATH | 处理第三方依赖 | 改 wheel 标签 | 维护成本 |
|---|---|---|---|---|---|
| 纯 `include` | ✅（路径易错） | ❌ | ❌ | ❌ | 低 |
| `include` + `build.py` | ✅ | ⚠️（手写 `-rpath`） | ❌ | ✅ | 中 |
| 上述 + `auditwheel`/`delocate` | ✅ | ✅ | ✅ | ✅ | 中高 |
| `cibuildwheel` | ✅ | ✅ | ✅ | ✅ | 中（CI 配置） |
| `maturin`（Rust/C 场景） | ✅ | ✅ | ✅ | ✅ | 低（但换生态） |

一句话：**只做前两步 = 自欺欺人**。`auditwheel` 才是分水岭。

## 性能与安全层面的考量

`.so` 进 wheel 有两个隐形成本。一是体积——`auditwheel` graft 进来的 `libssl.so.3` 单个就 3MB 起步，一个 wheel 从 80KB 膨胀到 12MB 很常见。二是**安全**：你 graft 的 OpenSSL 版本会被冻结在 wheel 里，用户系统打了 CVE 补丁也救不了你。我的做法是 CI 里 `pip-audit` 扫一遍，构建流水线每周重跑一次，确保 graft 的库是最新的。

RPATH 还有个安全维度：`$ORIGIN` 是相对路径，如果攻击者能在 `mylib.libs/` 旁边放恶意 `.so`，加载器会优先加载它。这个风险真实存在但被普遍忽视——`auditwheel` 的 graft 路径设计本身就是为了收窄这个面。

## 替代方案与取舍

`maturin` 是 Rust 生态的答案，支持 C 扩展、自动修 RPATH、一条命令出 manylinux wheel，体验比 Poetry 好一个数量级。但如果你团队已经是纯 Python + Poetry，换生态的迁移成本不划算。

`scikit-build-core` 走 CMake 路线，适合 C++ 大型项目，配置比 `build.py` 干净得多。我个人的判断：**C 扩展超过 5 个源文件，就别硬刚 Poetry 了，上 scikit-build-core**。

至于 `setuptools` 老路——`package_data` + `Extension`——它其实是最成熟的方案，Poetry 的这些坑它都没有。但 Poetry 的依赖解析和 lock 文件实在太香，为了打包换回去不值。

## References & Community Insights

- Poetry 官方文档 packages/include 章节：https://python-poetry.org/docs/pyproject/#packages
- `auditwheel` 官方仓库（含 `repair` 行为说明）：https://github.com/pypa/auditwheel
- `delocate`（macOS 等价物）：https://github.com/matthew-brett/delocate
- `delvewheel`（Windows）：https://github.com/adang1345/delvewheel
- PyPA `cibuildwheel` 文档：https://cibuildwheel.pypa.io/
- GitHub issue "Allow overriding the ABI tag when creating wheels"：https://github.com/python-poetry/poetry-core/issues/161
- HN 讨论 "Ask HN: What do you include in your Claude/Codex instructions?"：https://news.ycombinator.com/item?id=50509044

## FAQ

**Q：`include` 和 `packages` 到底啥区别，为什么我两个都要写？**

`packages` 声明"哪些目录是 Python 包"，决定了 wheel 里 `mylib/__init__.py` 这些的落位。`include` 是"额外的非 Python 文件"，比如 `.so`、数据文件、模板。两者不重叠，`.so` 必须靠 `include`，但 `include` 的路径基准是项目根，所以得配合 `from` 或完整相对路径。只写 `include` 不写 `packages`，包本身可能都不进 wheel。

**Q：为什么我的 wheel 标签是 `py3-none-any`，装到 ARM 机器上就崩？**

因为 `poetry-core` 的 `WheelBuilder` 默认不感知平台。它假设你打的是纯 Python 包。含 `.so` 的 wheel 必须显式覆盖 `tag`，否则 `pip` 会把它当通用包，在任意平台上安装。修法就是步骤 3 里的 `PlatformWheelBuilder`。

**Q：`auditwheel repair` 报错 `patchelf` 相关，怎么办？**

九成是 `patchelf` 版本太老（< 0.14）或者你的 `.so` 用了 `RUNPATH` 而非 `RPATH`。先 `patchelf --version` 确认，再 `patchelf --print-rpath your.so` 检查。如果是 `RUNPATH`，用 `patchelf --force-rpath --set-rpath '$ORIGIN' your.so` 强制改。新版 gcc 默认生成 `RUNPATH`，这是最常见触发点。

**Q：macOS 和 Windows 上 Poetry 的打包行为一样吗？**

不一样。macOS 上 Poetry 生成的还是 `macosx_*_x86_64` 标签（如果覆盖了 tag），但依赖 graft 得用 `delocate`，它处理 `@loader_path` 和 `@rpath` 的方式和 Linux 的 `$ORIGIN` 不同。Windows 没有 RPATH 概念，`delvewheel` 靠改写 PE 的 import table 和附带 manifest 实现。三个平台三套工具，别想着一个命令通吃。

**Q：能不能完全绕过 Poetry，用 setuptools 打包？**

能，而且更省心。`pyproject.toml` 里写 `[build-system] requires = ["setuptools>=68", "wheel"]`，用 `Extension` 声明 C 扩展，`package_data` 声明 `.so`，`setuptools` 自动处理平台标签。代价是你失去 Poetry 的依赖管理和 lock 文件。折中方案是 Poetry 管依赖、`scikit-build-core` 管构建——我最近两个项目都这么干，`build.py` 一行不用写。

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "include 和 packages 到底啥区别，为什么我两个都要写？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "packages 声明哪些目录是 Python 包，决定 wheel 里 __init__.py 的落位。include 是额外的非 Python 文件，比如 .so、数据文件。两者不重叠，.so 必须靠 include，但 include 的路径基准是项目根，需配合 from 或完整相对路径。"
      }
    },
    {
      "@type": "Question",
      "name": "为什么我的 wheel 标签是 py3-none-any，装到 ARM 机器上就崩？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "poetry-core 的 WheelBuilder 默认不感知平台，假设打的是纯 Python 包。含 .so 的 wheel 必须显式覆盖 tag 属性，否则 pip 会把它当通用包在任意平台安装。"
      }
    },
    {
      "@type": "Question",
      "name": "auditwheel repair 报错 patchelf 相关，怎么办？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "多半是 patchelf 版本太老（低于 0.14）或 .so 用了 RUNPATH 而非 RPATH。先 patchelf --version 确认，再 patchelf --print-rpath 检查。如果是 RUNPATH，用 patchelf --force-rpath --set-rpath '$ORIGIN' 强制改写。"
      }
    },
    {
      "@type": "Question",
      "name": "macOS 和 Windows 上 Poetry 的打包行为一样吗？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "不一样。macOS 用 delocate 处理 @loader_path 和 @rpath；Windows 没有 RPATH 概念，delvewheel 靠改写 PE import table 和 manifest。三个平台三套工具，不能一个命令通吃。"
      }
    },
    {
      "@type": "Question",
      "name": "能不能完全绕过 Poetry，用 setuptools 打包？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "能。pyproject.toml 里用 setuptools 的 Extension 声明 C 扩展，package_data 声明 .so，自动处理平台标签。代价是失去 Poetry 的依赖管理和 lock 文件。折中方案是 Poetry 管依赖、scikit-build-core 管构建。"
      }
    }
  ]
}
</script>

---
✅ All agents reported back!
└─ 🟡 HN: 5 storys │ 50 points │ 11 comments
---
