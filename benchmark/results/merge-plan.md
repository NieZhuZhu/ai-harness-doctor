# 阶段 1 治疗合并计划骨架

## Inventory
| 文件 | 工具 | 字节 | 行数 |
|---|---|---:|---:|
| `.cursorrules` | Cursor | 1174 | 33 |
| `.github/copilot-instructions.md` | GitHub Copilot | 394 | 13 |
| `CLAUDE.md` | Claude Code | 1398 | 49 |

## Overlap clusters
- 无超过阈值的重叠。

## Conflict list
- **package_manager**
  - `pnpm`
    - .cursorrules:5 `Run lint with `pnpm lint`.`
  - `npm`
    - .github/copilot-instructions.md:6 `Run the unit tests with `npm run test:unit`.`
    - CLAUDE.md:21 `- Run `npm run build` before opening a pull request.`

## TODO decision checklist
- [ ] 确认迁移范围（全仓 / 子目录 / 指定文件）。
- [ ] 对每个冲突项记录人工裁决结论。
- [ ] 手工编写 root `AGENTS.md`，只纳入 agent 无法从代码/manifest 推断的信息。
- [ ] 运行 `canonicalize.py --write-stubs` 预览降级 diff。
- [ ] 运行 `canonicalize.py --validate` 复核。
