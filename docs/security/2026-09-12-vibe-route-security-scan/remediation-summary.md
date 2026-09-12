# Vibe Route 安全扫描修复记录

## 扫描基线

- 扫描日期：2026-09-12
- 扫描 ID：`6243ba17-df1e-4094-a40b-51d1345b9799`
- 基线提交：`b53e45285cb9ecf82f10aef2ba824e24a86c8c1c`
- 扫描方式：仓库级静态安全扫描（Standard）
- 报告数量：13 条 finding，其中包含 2 组重复项；按 rule 去重后为 11 类问题
- 部署约束：继续同时兼容 HTTP 和 HTTPS，不强制 HTTPS

原始报告与机器可读产物位于本目录：

- [report.md](report.md)
- [findings.json](findings.json)
- [coverage.json](coverage.json)
- [scan-manifest.json](scan-manifest.json)
- [SARIF](exports/results.sarif)

> 报告针对修复前基线生成，因此其中 finding 的“open”状态表示扫描时状态，不表示当前工作区仍有相同问题。本文件记录后续修复与处置结果。

## 处置结果

| 扫描问题 | 当前处置 | 主要修复 |
| --- | --- | --- |
| Fixed JWT secret permits administrator token forgery | 按项目负责人要求保留 | 开发环境暂不修改固定 `SECRET_KEY`；正式环境必须通过环境变量覆盖并轮换密钥，禁止沿用仓库默认值。 |
| Public font endpoint permits arbitrary file read on Windows | 已修复 | 字体 ID 和文件名归一化，解析路径限制在管理员或用户字体根目录内；用户字体按用户隔离并使用 UUID 文件名。 |
| Public poster secret exposes arbitrary private tracks | 已修复 | 移除公开 `POSTER_SECRET` 流程；海报和仅地图页面改为登录所有者或有效分享令牌访问。 |
| Stored XSS in shared-track map tooltips | 已修复 | 对轨迹名、行政区、地点和道路字段统一 HTML 转义后再写入地图 tooltip/HTML API。 |
| Reflected XSS in live-recording placeholder response | 已修复 | 占位响应改为编码后的重定向，不再反射路径令牌到可执行 HTML。 |
| Interpolation APIs allow cross-user track reads and mutations | 已修复 | 插值查询、预览、创建、更新、删除均绑定当前用户的轨迹所有权。 |
| Overlay export exposes arbitrary users' track data | 已修复 | 导出前校验轨迹所有者，并限制模板必须为本人、公开或系统模板。 |
| Poster generation can render another user's track | 已修复 | 服务端海报生成校验轨迹所有者；分享场景只接受与轨迹匹配的有效分享令牌。 |
| Private overlay templates are exposed by direct routes | 已修复 | 详情、导出、预览和复制统一应用模板可见性策略。 |
| Unauthenticated log relay leaks live-recording tokens | 已修复 | 日志 POST/WebSocket 需要认证；实时连接改用 `bearer` 子协议传递令牌，并移除完整令牌日志。 |
| Generated export artifacts are publicly reachable | 已修复 | 移除 `/exports` 静态挂载；动画文件通过带任务所有权校验的下载接口返回。 |

## 额外加固

- KML 解析显式关闭实体解析、DTD 和网络访问，并限制文档树。
- ZIP/KMZ/RAR 导入增加条目数量和解压后大小预算。
- 邀请码消费改为原子条件更新，创建用户与消费邀请码尽量在同一事务内完成。
- 海报尺寸和地图缩放范围增加边界校验。
- 异步动画/覆盖层任务不再向前端返回原始异常文本。
- 管理端和其他 API 的 500 响应不再回显异常字符串。
- 保留 HTTP/HTTPS 双协议兼容，未新增 HTTPS 强制跳转。

## 验证记录

- `python -m compileall -q backend\app backend\tests`：通过。
- `(cd backend; ..\.venv\Scripts\python.exe -m pytest -q)`：120 passed，20 个既有 warning。
- `(cd frontend; npm run build)`：通过，仅有既有 chunk size warning。
- `git diff --check`：通过。
- 路由导入检查：字体路由存在，`/exports` 静态挂载不存在，动画下载路由存在。
- `vue-tsc --noEmit`：因当前 `vue-tsc` 与 Node 24 不兼容而无法运行；这是工具链限制，不是本次代码编译或构建失败。错误为 `Search string not found: "/supportedTSExtensions = .*(?=;)/"`。

## 后续事项

- 正式环境部署前必须更换 `SECRET_KEY`，并让旧密钥签发的令牌失效。
- 地图和地理编码服务商侧的来源、IP、配额与 scope 限制需在部署平台确认。
- 生产数据库上建议补充邀请码并发消费测试。
- 根据实际部署的 lxml/gpxpy 版本补充 XML 解析安全回归测试。
- 本目录中的扫描产物已检查，不包含部署密钥、数据库密码或本次扫描使用的登录凭据。

