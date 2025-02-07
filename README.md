# QQ酒馆 - 角色扮演聊天插件 v0.1测试版

一个功能丰富的角色扮演聊天插件，支持多角色、记忆系统、世界设定等功能。完全兼容SillyTavern的角色卡和世界书格式。



## 功能特点

- 🎭 支持多角色切换和管理，兼容SillyTavern角色卡
- 💭 智能记忆系统，包含短期和长期记忆
- 📚 世界设定系统，支持常驻和关键词触发，兼容SillyTavern世界书
- 🎯 破甲模式，支持多种模板
- 👤 用户个人资料设置
- ⚙️ 灵活的正则处理系统

## 目录结构

```
QQSillyTavern/
├── config.yaml          # 主配置文件
├── regex_rules.yaml     # 正则规则文件
├── png/                 # 角色卡目录（与SillyTavern通用）
├── juese/               # 转换后角色卡目录（与SillyTavern通用）
│   ├── 角色1.yaml       # 角色配置文件
│   └── ...
└── shijieshu/          # 世界书目录（与SillyTavern通用）
    ├── 世界书1.json     # 世界书文件
    └── ...
```
## 使用前stars点个星星用的人少就不维护了
## 安装

1. 确保已安装并配置 [LangBot](https://github.com/RockChinQ/LangBot)
2. 使用管理员账号向机器人发送命令：
```
!plugin get https://github.com/sanxianxiaohuntun/QQSillyTavern
```

## 角色系统

### 1. 角色卡格式

角色卡完全兼容SillyTavern格式，可以直接使用SillyTavern的角色卡。将角色卡文件放在 `QQSillyTavern\png` 目录下。

支持的文件格式：
- YAML格式（推荐）：`角色名.yaml`
- JSON格式：`角色名.json`
- PNG格式：`角色名.png`

角色卡示例（YAML格式）：
```yaml
name: "余雪棠"
description: "一位年轻的女法师，擅长冰系魔法。"
personality: "温柔善良，但在战斗时会表现得非常果断。"
first_mes: "{{user}}，欢迎来到魔法学院。我是你的导师余雪棠。"
mes_example: |
  "今天的魔法课程是什么？"
  "让我们来练习一下冰系魔法吧。"
  "小心，这个魔法有点危险。"
scenario: "魔法学院的教学大厅"
system_prompt: |
  你扮演的是一位魔法学院的年轻女导师。
  - 擅长冰系魔法
  - 教学认真负责
  - 对学生温柔
  - 战斗时果断
```

### 2. 世界书系统

世界书完全兼容SillyTavern格式，将世界书文件放在 `QQSillyTavern\shijieshu` 目录下。

世界书示例：
```json
{
  "entries": [
    {
      "content": "魔法学院是一所培养魔法师的高等学府，有着悠久的历史。",
      "comment": "魔法学院设定",
      "constant": true,
      "enabled": true
    },
    {
      "content": "冰系魔法是最基础的元素魔法之一，入门容易但要精通非常困难。",
      "comment": "冰系魔法设定",
      "constant": false,
      "enabled": true,
      "key": ["冰系魔法", "冰魔法", "寒冰魔法"]
    }
  ]
}
```

世界书类型：
1. 常开条目（constant: true）
   - 始终生效的设定
   - 适合放置基础世界观、场景描述等
   - 例如：世界背景、基本规则等

2. 关键词条目（constant: false）
   - 需要触发词激活的设定
   - 在对话中提到关键词时生效
   - 适合放置具体物品、技能、事件的描述
   - 例如：特定魔法说明、道具效果等

### 3. 完整角色示例

以下是一个完整的角色设置示例：

1. 角色卡文件 `juese/余雪棠.yaml`：
```yaml
name: "余雪棠"
description: "魔法学院的年轻女导师，擅长冰系魔法。身材高挑，长发及腰，总是穿着整洁的导师长袍。"
personality: |
  - 温柔体贴，对学生极有耐心
  - 教学认真负责，要求严格
  - 战斗时性格会变得果断
  - 有些怕生，但熟悉后会变得活泼
first_mes: "啊，{{user}}同学，你来了。今天要学习什么魔法呢？"
mes_example: |
  "让我演示一下这个魔法的要领。"
  "记住，施法时要集中精神。"
  "做得很好！再试一次吧。"
scenario: "魔法学院的教学大厅，四周摆放着各种魔法道具。"
system_prompt: |
  你是魔法学院的导师余雪棠，扮演时请注意：
  1. 说话温柔，经常称赞学生
  2. 讲解魔法时会非常专业
  3. 遇到危险时会保护学生
  4. 不擅长应对突发社交情况
```

2. 对应的世界书 `shijieshu/魔法学院.json`：
```json
{
  "entries": [
    {
      "content": "魔法学院简介：\n- 位于永恒之森的中心\n- 有上千年历史\n- 分为初级、中级、高级三个部\n- 以培养全能魔法师为目标",
      "comment": "魔法学院基本设定",
      "constant": true,
      "enabled": true
    },
    {
      "content": "导师制度：\n- 每位学生都有专属导师\n- 导师负责学生的全面培养\n- 师生关系通常很亲密\n- 导师要对学生负责到毕业",
      "comment": "导师制度设定",
      "constant": true,
      "enabled": true
    },
    {
      "content": "冰系魔法特点：\n- 入门容易，精通难\n- 可以凝结冰晶\n- 能制造寒冷领域\n- 高阶可以冰封敌人",
      "comment": "冰系魔法设定",
      "constant": false,
      "enabled": true,
      "key": ["冰系魔法", "冰魔法", "寒冰魔法"]
    }
  ]
}
```

## 使用建议

### 1. 角色设计

1. 基础信息要完整
   - name：角色名称
   - description：外表和身份描述
   - personality：性格特点
   - first_mes：初次见面的话
   - scenario：场景描述

2. 丰富对话示例
   - mes_example 中提供多样的对话示例
   - 包含不同情况下的反应
   - 展现角色的性格特点

3. 系统提示要清晰
   - system_prompt 中说明扮演要点
   - 列出关键的行为准则
   - 指出需要注意的细节

### 2. 世界书编写

1. 分类管理
   - 按主题分文件
   - 相关内容放在同一文件中
   - 便于维护和更新

2. 条目设计
   - 常开条目：放置基础设定
   - 关键词条目：放置细节设定
   - 条目内容要简洁明了

3. 关键词设置
   - 设置多个同义词
   - 避免过于宽泛的词
   - 确保能准确触发

## 基础使用

### 1. 开始使用

1. 开启酒馆：
```
/开启酒馆
```

2. 设置个人资料：
```
/设定我的个人资料
```
按照提示依次设置：
- 称呼
- 性别
- 性格特点
- 补充信息（可选）

3. 选择角色：
```
/角色 列表
```
- 直接输入数字(1-100)选择当前页的角色
- 使用 `/角色 第N页` 切换页面

4. 开始对话：
```
/开始
```

### 2. 记忆系统命令

```
/记忆 历史 <数量>    - 设置保留对话轮数(1-100)
/记忆 清空历史       - 清空历史对话
/记忆 撤回          - 撤回最后一条消息
/记忆 重新生成       - 重新生成最后回复
/记忆 上限 <数量>    - 设置最大记忆数(1-1000)
/记忆 间隔 <数量>    - 设置总结间隔
/记忆 状态          - 查看当前记忆配置
/记忆 清空记忆       - 清空所有长期记忆
```

### 3. 世界书系统

```
/世界书 常开 [页码]              - 查看常开条目
/世界书 关键词调动 [页码]         - 查看关键词条目
/世界书 禁用 常开条目 <序号>      - 禁用指定常开条目
/世界书 禁用 关键词条目 <序号>    - 禁用指定关键词条目
/世界书 启用 常开条目 <序号>      - 启用指定常开条目
/世界书 启用 关键词条目 <序号>    - 启用指定关键词条目
```

### 4. 破甲模式

```
/破甲 开启           - 使用默认配置开启(gemini模板)
/破甲 开启 claude    - 使用Claude模板
/破甲 开启 deepseek  - 使用DeepSeek模板
/破甲 关闭           - 关闭破甲模式
/破甲 状态           - 查看当前配置
```

## 配置文件说明

### 1. 主配置文件 (config.yaml)

```yaml
system:
  debug: false  # 调试模式开关

memory:
  enabled: true           # 记忆系统开关
  short_term_limit: 20    # 短期记忆上限
  max_memory: 1000        # 最大记忆数量
  summary_batch_size: 10  # 记忆总结批次大小

world_book:
  enabled: true          # 世界书系统开关
  max_entries: 100       # 最大条目数
```

### 2. 正则规则文件 (regex_rules.yaml)

```yaml
enabled: true  # 正则处理系统开关
rules:
  - pattern: "\\[.*?\\]"      # 方括号内容
    replacement: ""           # 替换为空
  - pattern: "\\(.*?\\)"      # 圆括号内容
    replacement: ""           # 替换为空
  - pattern: "【.*?】"        # 中文方括号内容
    replacement: ""           # 替换为空
```

### 3. 角色配置文件 (juese/角色名.yaml)

```yaml
name: "角色名"
description: "角色描述"
personality: "性格特点"
first_mes: "初次见面的话"  # 支持使用 {{user}} 表示用户名
```

### 4. 世界书条目 (shijieshu/世界书名.json)

```json
{
  "entries": [
    {
      "content": "条目内容",
      "comment": "条目说明",
      "constant": true,     // true为常开条目，false为关键词条目
      "enabled": true,      // 是否启用
      "key": ["关键词1", "关键词2"]  // 关键词条目的触发词
    }
  ]
}
```

## 进阶功能

### 1. 状态系统

角色回复中可以包含状态信息，使用特定格式：<StatusBlock>包裹住然后用 “/状态” 命令查看状态栏
```
<StatusBlock></StatusBlock>
```
