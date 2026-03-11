# 腾讯会议来源接入手册

## 目标

把腾讯会议云录制分享页纳入原理治理系统，先建立稳定的“腾讯原生逐字稿优先”采集能力，再按需要补充浏览器态探测、导出媒体转写和未来的官方 API 接入。

## 基本原则

- 先把腾讯会议分享页当作材料入口，而不是默认要求导出文件。
- 腾讯会议产品层直接支持原生逐字稿/纪要；匿名分享页拿不到正文，不等于产品没有逐字稿。
- 必须明确区分三件事：
  - 页面能访问
  - 页面有录制元数据
  - 页面有可用逐字稿/纪要
- 不能因为“有云录制页”就直接认定“有逐字稿”。

## Phase 1：分享页直采

- 输入支持 `meeting.tencent.com/crm/*` 和 `meeting.tencent.com/cw/*`。
- 统一归一化到 `cw` 最终页。
- 先读 SSR 页面和内嵌 `serverData`，不要只依赖可见文本；腾讯会议常把会议码、会议 ID、时长、大小和封面放在转义 JSON 里。
- 标准产物：
  - `tencent-meeting-raw.json`
  - `tencent-meeting-normalized.json`
  - `tencent-meeting-assessment.md`
- 最小治理字段：
  - `source_platform = tencent_meeting`
  - `source_kind = tencent_meeting_share`
  - `source_id`
  - `title`
  - `record_created_at`
  - `meeting_code`
  - `meeting_id`
  - `recording_duration_ms`
  - `recording_size_bytes`
  - `transcript_status`
  - `native_transcript_capability`
  - `native_transcript_enabled`
  - `share_page_transcript_visible`
  - `transcript_access_path`
  - `capture_status`
  - `fallback_action`

## 状态解释

- `validation_status`
  - `validated`: 页面可访问，且至少拿到了可归档的录制元数据
  - `auth_required`: 页面需要更强登录态或权限
  - `not_found`: 分享页无效、过期或不可用
  - `empty_extraction`: 页面可访问，但没拿到足够结构化结果
- `capture_status`
  - `accessible`
  - `gated`
  - `expired`
  - `failed`
- `transcript_status`
  - `present`
  - `empty`
  - `unknown`
- `native_transcript_capability`
  - `supported`
  - `unsupported`
  - `unknown`
- `native_transcript_enabled`
  - `enabled`
  - `disabled`
  - `unknown`
- `share_page_transcript_visible`
  - `visible`
  - `hidden`
  - `gated`
  - `unknown`
- `transcript_access_path`
  - `share_page`
  - `login_probe`
  - `open_api`
  - `external_transcribe`
- `empty` 可以来自两类证据：
  - 页面明确显示“暂无文本内容”
  - 页面可访问且元数据可抽取，但 SSR 和内嵌数据都没有提供可用逐字稿文本

## Phase 2：补采分支

- 若 `capture_status = gated` 或 `share_page_transcript_visible = gated`：
  - 优先走更强登录态/权限态探测，确认是否有原生逐字稿可见。
- 若 `native_transcript_enabled = enabled` 且 `share_page_transcript_visible = hidden`：
  - 先走 `browser_probe`，不要立刻降到导出媒体。
- 若 `native_transcript_enabled = disabled` 且没有媒体直链：
  - 走 `export_media`，要求从腾讯会议导出 MP4 或音频。
  - 导出后用 `python3 scripts/yuanli_governance.py transcribe-tencent-meeting-file --source-id <source_id> --file /absolute/path/to/exported.mp4`
- 若已确认当前路径拿不到原生文本，但能拿到媒体直链：
  - 走 `external_transcribe`，把媒体交给独立转写链路。
  - 当前默认外部转写实现是 `Get笔记 transcribe-file`，会把 transcript TXT/JSON 和 note metadata 回写到该 source 的 artifact 目录。

## 准入规则

- `can_use_as_primary_material(record) = true`
  - 条件：`capture_status = accessible`
  - 且至少具备标题、创建时间、会议码、会议 ID 中的一项稳定元数据
- 只有 `transcript_status = present` 的记录，才能直接视为逐字稿材料。
- `transcript_status = empty | unknown` 的记录先按“素材记录”处理，不按“完整逐字稿”处理。
- 治理校验要分开看两层：
  - `source integrated`: 链接已登记并能在 canonical knowledge source 中找到
  - `sample verified`: 真实样本的产品能力、启用状态、分享页可见性都已被明确判定

## 未来扩展

- 如果后续拿到腾讯会议开放平台凭证，并且官方文档确认录制/纪要接口：
  - 在当前分享页探测器之外追加 API 通道
  - 不替换现有分享页入口
- 分享页入口始终保留，作为最轻量、最少授权的首层采集路径。
- `export_media -> external_transcribe` 继续保留，但只是最后兜底，不再作为默认主路径。
