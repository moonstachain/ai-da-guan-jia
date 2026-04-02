# 飞书坐标系统完整映射

## 治理层（原力OS Base）

| 用途 | Base / Table ID | 备注 |
|------|----------------|------|
| live 运行态总控 | `PHp2wURl2i6SyBkDtmGcuaEenag / tblnRCmMS7QBMtHI` | ⚠️ 不是 tblkKkauA35yJOrH（旧表） |
| **战略任务追踪** | `PVDgbdWYFaDLBiss0hlcM5WRnQc / tblB9JQ4cROTBUnr` | 所有Task Spec闭环必须回写此表 |
| Skill 盘点表 | `PVDgbdWYFaDLBiss0hlcM5WRnQc / tbl7g2E33tHswDeE` | |
| 进化编年史 | `PVDgbdWYFaDLBiss0hlcM5WRnQc / tblpNcHFMZpsiu1P` | |
| 治理成熟度评估 | `PVDgbdWYFaDLBiss0hlcM5WRnQc / tblYnhPN5JyMNwrU` | |
| 治理 wiki 节点 | `Zge0wIkDDiGPsskJlLFcuT9Pnac` | |

## 投研层（康波 Base）

| 用途 | Table ID |
|------|----------|
| 康波 Base | `IqZhbMJJxaq8D4sHOvkciaWFnid` |
| 十五五 L0 | `tblwzxos2mtbBo4G` |
| 十五五 L5信号 | `tblGERh218ui9oyC` |
| 十五五 L5映射 | `tblhZGYE7WEAe2fc` |
| 十五五 L5矩阵 | `tbljcZoJhpBurxXL` |
| BW50事件 | `tbl5v57S6EUDFbNO` |
| BW50矩阵 | `tbl7xvp71C22Nwog` |
| L4命题 | `tblu9j7rpLFYCkto` |
| L4标的 | `tblypdAEzkxIyISM` |
| L4策略 | `tblUrtJLbF7aerLm` |
| L4量化 | `tblIwtSUXnsHWoGs` |

## 回旋镖局（战略客户 Base）

| 用途 | 值 |
|------|-----|
| Base app_token | `LDrsbKwysadY4UsHb44cZOwDn4O` |
| FEISHU_APP_ID | `cli_a92aeb1ceff9dcc7` |
| FEISHU_APP_SECRET | `HjjYSWf9CIlhjvE5iOWWtfwe8RGUgGJ8` |
| Wiki节点 | `W9ksww7QuiV969k8Hqtcro1Fn7c` |

### 回旋镖局 12张表

| 表名 | table_id | 数据量 |
|------|----------|--------|
| T01_月度经营数据 | `tbl4omKjGSEipVSw` | 32条 |
| T02_月度财务数据 | `tblTCk51kNvrFuzq` | 8条 |
| T03_客户分析 | `tblAPFrwA9WmC0ww` | 81条 |
| T04_品类分析 | `tbl00BgabIFxk0kA` | 292条 |
| T05_供应链效率 | `tblwGXJKriCHyiV8` | 20条 |
| T06_内容与IP | `tblEc0bPCRYhpiOU` | 41条 |
| T07_财务建模 | `tblKlMnCSO2sgUkH` | 6条 |
| T08_对标矩阵 | `tbluOHgssN7KHice` | 8条 |
| T09_进化追踪 | `tbluLWza2jHUo2qT` | 25条 |
| T10_估值测算 | `tblnB9jSLvtZLlgL` | 4条 |
| T11_月度经营快照 | `tblv9vGogcTZomsX` | |
| T12_元数据与配置 | `tblGtARQM1UNtbWV` | |

## 妙搭应用

| 应用 | ID |
|------|----|
| 康波智库 | `app_4jr14d6f1cczn` |
| 治理驾驶舱 | `app_4jr2unyrmpswy` |
| 商业模式创新智库 | `app_4jqv18nugm3sv` |
| 回旋镖局战略驾驶舱 | 待创建（代码已完成） |

## 飞书 API 注意事项

1. **文本字段**必须用 `type:1 bizType:Text`
2. **URL字段**写入时必须转成 `{link, text}` 对象格式
3. **capability JSON** 中注意字段类型映射
4. ⚠️ 不要把客户 Base（回旋镖局）和治理 Base 混淆
