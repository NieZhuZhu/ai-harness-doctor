# 阶段 0 体检报告

## 配置文件清单
| 文件 | 工具 | 字节 | 行数 | SHA256 |
|---|---:|---:|---:|---|
| `.cursorrules` | Cursor | 1174 | 33 | `fc6b219cb2dd` |
| `.github/copilot-instructions.md` | GitHub Copilot | 394 | 13 | `76f305651d0a` |
| `CLAUDE.md` | Claude Code | 1398 | 49 | `e95a8552f39b` |

## 体积告警
未发现体积告警。

## 重叠候选
未发现超过 30% 的重叠候选。

## 冲突候选
- **package_manager**
  - `pnpm`：.cursorrules:5 `Run lint with `pnpm lint`.`
  - `npm`：.github/copilot-instructions.md:6 `Run the unit tests with `npm run test:unit`.`; CLAUDE.md:21 `- Run `npm run build` before opening a pull request.`

## 嵌套 AGENTS.md
无。

> 停止条件：请确认迁移范围（全仓 / 子目录 / 指定文件）后再进入阶段 1 治疗。
