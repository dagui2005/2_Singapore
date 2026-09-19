# 把本地仓库 `2_Singapore` 推送到 GitHub

> 本地已 commit（`2ce6e65`），**SSH 端口 22 到 `ssh.github.com` 已通**，现有 SSH 密钥绑定到 `dagui2005` 账户。
> 只需要在 GitHub 网页上**点一下**「创建仓库」，然后回到本文件所在机器执行一段命令即可。

---

## 0. 现在该做什么（极简版）

1. **打开浏览器**：访问 https://github.com/new
2. **填写**：
   - Repository name: `2_Singapore`
   - Description: `Singapore LTA DataMall + MATSim 仿真 + 数据治理（源码 + 文档）`
   - 选择 **Public** 或 **Private**（你定）
   - **不要勾选** "Add a README file" / "Add .gitignore" / "Choose a license"
3. 点 **Create repository**
4. 在本机 PowerShell 中执行：

```powershell
git -C "d:/Luan/2026-05/2_Singapore" push -u origin master
```

5. 看见 `* [new branch] master -> master` 等输出就成功了 ✅

---

## 1. 仓库现状

| 项 | 值 |
| --- | --- |
| 本地分支 | `master`（单一 commit `2ce6e65`）|
| 远程 | `git@github.com:dagui2005/2_Singapore.git` |
| 文件数 | 165 |
| 体积 | 11.92 MB |
| 已包含 | `API_Key.txt`？❌、shapefile/GeoTIFF？❌、Singapore_OD 9 GB 数据？❌ |
| 已包含 | 全部 .py 代码 + 6 个公共交通 csv + LTA 用户指南 PDF + 5 个核心 .md 文档 + `docs/DATASETS.md` + 两个 .gitkeep 占位 |

## 2. 已配置的安全 `.gitignore`

- ✅ `API_Key.txt`、`*.key`、`*.secret`、`.env*` 全被忽略
- ✅ `*.shp/.dbf/.shx/.prj/.cpg/.sbn/.sbx/.lyr/.shp.xml`（shapefile 全家族）
- ✅ `*.tif/.tiff/.img/.ecw/.las/.laz`（GeoTIFF / 影像）
- ✅ `*.xlsx/.parquet/.png/.jpg/.docx`（含 GHS 2025 + 报告大图）
- ✅ `Singapore_OD_MATSim_FinalData/**`（9 GB 完整数据集）
- ✅ `Static_ 2026_03/OTHER/goverment_open/**`（670 MB 政府开放数据）
- ✅ `Dynamic_*/`（LTA DataMall 动态数据）
- ✅ `tools/jdk-*/tools/matsim-*.zip`（JDK/MATSim 安装包）
- ✅ `*.sr.lock.*`、`~$*`、`.~lock.*`（百度网盘锁、Office 锁）
- ✅ `.idea/.vscode/.venv/`（IDE + 虚拟环境）

**意外加入 `git ls-files` 的 .txt/.csv 会通过 commit history 留下痕迹，**但仓库体积已清干净。详见 [`PROJECT_LAYOUT.md`](PROJECT_LAYOUT.md)。

## 3. 上传与 remote 命令（完整版）

### 3.1 HTTPS + PAT 路径（不需要 SSH）

```powershell
# 1. 创建 PAT：https://github.com/settings/tokens/new
#    Scopes: 勾选 repo

# 2. 配 remote（HTTPS）
git -C "d:/Luan/2026-05/2_Singapore" remote add origin https://github.com/dagui2005/2_Singapore.git
# （已用 SSH，配过的话先移除）
git -C "d:/Luan/2026-05/2_Singapore" remote remove origin

# 3. push（按提示输入用户名 + PAT）
git -C "d:/Luan/2026-05/2_Singapore" push -u origin master
```

### 3.2 SSH 路径（已认证的 ed25519，默认推荐）

```powershell
git -C "d:/Luan/2026-05/2_Singapore" remote add origin git@github.com:dagui2005/2_Singapore.git
git -C "d:/Luan/2026-05/2_Singapore" push -u origin master
```

### 3.3 验证 SSH 凭据

```powershell
ssh -T -o ConnectTimeout=8 git@github.com
# 期望输出: "Hi dagui2005! You've successfully authenticated, but GitHub does not provide shell access."
```

## 4. push 后的维护

```powershell
# 之后修改 → commit → push
git -C "d:/Luan/2026-05/2_Singapore" add -A
git -C "d:/Luan/2026-05/2_Singapore" commit -m "docs: 更新某节"
git -C "d:/Luan/2026-05/2_Singapore" push

# 拉远端新变更
git -C "d:/Luan/2026-05/2_Singapore" pull --rebase
```

## 5. 后续可考虑

- [ ] `gh` CLI 安装：`winget install --id GitHub.CLI -e --source winget`（如果是 winget 可达网络）
- [ ] 在 GitHub 端开 **main 是 default**——push 时保持 `master` 或 `git branch -M main` 改名
- [ ] 设置 **GitHub Actions** 自动运行 `python scripts/matsim/network/reader.py --dry-run`
- [ ] 配置 **DVC** 管理 9 GB `Singapore_OD_MATSim_FinalData/` 远程数据
- [ ] 在 GitHub 上 fork/mirror OSM 子区域数据 [`osm-expand/`](osm-expand/)

## 6. 失败排查

| 现象 | 解决 |
| --- | --- |
| `Repository not found` | 远端仓库未创建，回到第 0 步 |
| `Permission denied (publickey)` | `ssh-add ~/.ssh/id_ed25519` 加载密钥；或用 HTTPS+PAT |
| `Could not resolve host github.com` | DNS 或网络问题；检查 `ipconfig /flushdns` |
| `Port 22 timeout` | 防火墙拦截 SSH；改用 HTTPS+PAT 走 443 |
| `Authentication failed` | PAT 没选 `repo` scope，或已过期 |

---

**关键事实**
- 本机 commit `2ce6e65`（2026-09-12）已包含 165 文件 / 11.92 MB / 无密钥
- SSH 端口 22 到 ssh.github.com 可达 ✅（2026-09-12 测试通过）
- `~/.ssh/id_ed25519` 注释：`dagui@UAV_Route`，归属 dagui2005
- dagui2005 当前公开仓库数：21 个（无 `2_Singapore`）
