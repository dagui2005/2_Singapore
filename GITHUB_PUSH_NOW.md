# 推送清单（2026-09-12 上午)

> 本地仓库已 commit、SSH 端口 22 已通、SSH 密钥已认证到 dagui2005。
> 现在仅需在 GitHub 网页上点一下 「Create repository」。

---

## 🚀 一、浏览器先做（必须）

打开：https://github.com/new

| 字段 | 值 |
| --- | --- |
| Repository name | **`2_Singapore`** |
| Description | `Singapore LTA DataMall + MATSim 仿真 + 数据治理（源码 + 文档）` |
| Visibility | 公开 / 私有（你定） |
| Add README | **不勾选** |
| Add .gitignore | **不勾选** |
| Choose a license | **不勾选** |

点 **Create repository**。

如果已有同名的私有/公开仓库被清空状态 → 直接用 `Replace topic` 按钮。

---

## ⚡ 二、本机命令（一行复制粘贴）

打开 PowerShell（或命令提示符）：

```powershell
# 工作目录（macOS/Linux 改为 cd d:/Luan/2026-05/2_Singapore 改用 Linux 路径）
cd d:/Luan/2026-05/2_Singapore

# 查看 remote 配置
git remote -v
# 期望: origin git@github.com:dagui2005/2_Singapore.git

# 推送
git push -u origin master
```

预期输出（片段）：

```
Counting objects: 168, done.
Delta compression using up to 16 threads.
Compressing objects: 100% (160/160), done.
Writing objects: 100% (168/168), 5.32 MiB | 8.40 MiB/s, done.
Total 168 (delta 0), reused 0 (delta 0)
To github.com:dagui2005/2_Singapore.git
 * [new branch]      master -> master
Branch 'master' set up to track remote branch 'master' from 'origin'.
```

---

## ✅ 三、推送后验证

1. 打开 https://github.com/dagui2005/2_Singapore
2. 看见 165 文件列表 = 成功
3. 点击 README.md 应能渲染文档顶部
4. 检查首页"Code"→"About"侧栏 — Description 应已显示

---

## 🔁 四、推送异常排查

| 现象 | 排查 |
| --- | --- |
| `Repository not found` | 远端仓库还没创建 → 回第一步 |
| `Permission denied (publickey)` | `ssh-add ~/.ssh/id_ed25519` 或换 HTTPS+PAT |
| `Port 22 timeout` | 防火墙挡 SSH；改用 HTTPS+PAT |
| `refusing to merge unrelated histories` | 远端有内容；先 `git pull --rebase` 或让 GitHub 上是空仓库 |
| `Everything up-to-date` | 推送前请 `git log -1` 与 GitHub 上比对 SHA；可能仓库已存在 |
| 中文字符乱码 | 不会发生（commit message 已改纯英文） |

---

## 📦 五、推送完成后

1. 仓库元信息 → 在 https://github.com/dagui2005/2_Singapore/settings 编辑：
   - **Description**: `Singapore LTA DataMall + MATSim + data governance`
   - **Website**: （如果有项目站点 URL）
   - **Topics**: `singapore`, `matsim`, `lta-datamall`, `transport-simulation`, `gis`, `osm`

2. 启用 GitHub Pages（如有 mkdocs）→ https://github.com/dagui2005/2_Singapore/settings/pages

3. 配置 GitHub Actions 自动化 lint：
   ```yaml
   # .github/workflows/ci.yml（推送后可加）
   name: ci
   on: [push, pull_request]
   jobs:
     python:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: '3.12' }
         - run: pip install -r requirements.txt
         - run: python -m pytest scripts/tests/
   ```

---

## 📋 仓库快照（推送前）

| 项 | 值 |
| --- | --- |
| HEAD SHA | `a0e326f` |
| 文件数 | 165 |
| 体积 | ~12 MB |
| 仓库路径 | `d:/Luan/2026-05/2_Singapore/` |
| 本地分支 | `master` |
| remote | `origin = git@github.com:dagui2005/2_Singapore.git` |
| 含密钥？ | ❌ |
| 含 shp / tif | ❌ |
| 含 Singapore_OD 9 GB | ❌ |
| 含公共交通 csv | ✅（6 个） |
| 含 LTA 用户指南 PDF | ✅ |
| 含 docs/DATASETS.md | ✅（数据下载指南） |

---

**如果上面的 `git push` 也因网络问题失败（应用层阻塞 SSH）**，回退方案：
1. 切到手机热点 / 公司 VPN / 别的可连 GitHub 的网络
2. 在另一台机器上 clone 一个空仓库
3. 把 `d:/Luan/2026-05/2_Singapore/.git/objects/pack/` 复制过去再 `git push`
